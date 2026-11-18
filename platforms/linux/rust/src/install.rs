//! Explicit first installation on an identified target. Never starts services
//! or changes networking. The initial bundle is trusted by the operator over
//! SSH; later releases need the separately provisioned public key.
use crate::args::{usage_error, Args};
use crate::error::{invalid, Error, Result};
use crate::json::{self, json, Value};
use crate::package::{self, BINARY, DEPLOY};
use crate::runner::run_with_timeout;
use crate::{fsutil, py, updates};
use std::fs;
use std::os::unix::fs::{DirBuilderExt, PermissionsExt};
use std::path::{Path, PathBuf};
use std::time::Duration;

/// End-entity certificate: the default OpenSSL `v3_ca` section would make a
/// self-signed certificate CA:TRUE, so trusting it in a
/// client would trust it as an authority for every site.
const CERTIFICATE_CONFIG: &str = "[req]\nprompt = no\ndistinguished_name = dn\nx509_extensions = ext\n\
[dn]\nCN = Phoenix Local Administration\n\
[ext]\nbasicConstraints = critical,CA:FALSE\nkeyUsage = critical,digitalSignature,keyEncipherment\n\
extendedKeyUsage = serverAuth\nsubjectAltName = IP:127.0.0.1,DNS:localhost\nsubjectKeyIdentifier = hash\n";

fn set_mode(path: &Path, mode: u32) -> Result<()> {
    Ok(fs::set_permissions(path, fs::Permissions::from_mode(mode))?)
}

fn mkdirs(path: &Path, mode: u32) -> Result<()> {
    fs::DirBuilder::new().recursive(true).mode(mode).create(path)?;
    Ok(())
}

fn present(path: &Path) -> bool {
    fs::symlink_metadata(path).is_ok()
}

/// Self-signed loopback certificate via the openssl CLI (RSA 2048, 365 days).
pub fn openssl_certificate(key: &Path, certificate: &Path) -> Result<()> {
    let config = key.with_file_name(format!(".openssl-req-{}.cnf", py::token_hex(4)));
    fsutil::write_private(&config, CERTIFICATE_CONFIG.as_bytes())?;
    let (key_text, certificate_text, config_text) = (key.to_string_lossy(), certificate.to_string_lossy(), config.to_string_lossy());
    let argv = [
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "365", "-config", &config_text, "-keyout", &key_text, "-out", &certificate_text,
    ];
    let result = run_with_timeout(&argv, None, Duration::from_secs(120));
    let _ = fs::remove_file(&config);
    match result {
        Ok(Some((0, _))) => Ok(()),
        _ => invalid("certificate_generation_failed"),
    }
}

fn read_model(root: &Path) -> Result<String> {
    let model = fs::read_to_string(root.join("proc/device-tree/model"))?;
    Ok(model.trim_matches(|c| c == '\0' || c == '\n').to_string())
}

/// Copy the release binary to `<bootstrap>/bin/phoenix` (0755): the updater
/// must keep working even if the active release is broken.
fn install_bootstrap(binary: &Path, bootstrap: &Path) -> Result<()> {
    mkdirs(&bootstrap.join("bin"), 0o755)?;
    set_mode(bootstrap, 0o755)?;
    set_mode(&bootstrap.join("bin"), 0o755)?;
    let destination = bootstrap.join(BINARY);
    fs::copy(binary, &destination)?;
    set_mode(&destination, 0o755)?;
    fs::File::open(&destination)?.sync_all()?;
    Ok(())
}

/// Copy a unit via a temporary file and rename (no half-written unit).
fn install_unit(source: &Path, destination: &Path) -> Result<()> {
    let temporary = destination.with_file_name(format!(".{}.new", destination.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default()));
    fs::copy(source, &temporary)?;
    set_mode(&temporary, 0o644)?;
    fs::rename(&temporary, destination)?;
    Ok(())
}

fn service_units() -> impl Iterator<Item = &'static str> {
    DEPLOY.into_iter().filter(|n| n.ends_with(".service"))
}

pub fn install(bundle: &Path, config: &Path, public_key: Option<&Path>, root: &Path) -> Result<()> {
    install_with(bundle, config, public_key, root, &openssl_certificate)
}

/// `certificate(key, cert)` creates the TLS key pair (injectable for tests).
pub fn install_with(bundle: &Path, config: &Path, public_key: Option<&Path>, root: &Path, certificate: &dyn Fn(&Path, &Path) -> Result<()>) -> Result<()> {
    let mut target = json::parse(&fs::read(config)?)?;
    let model = read_model(root)?;
    let expected = target.get("expected_model").and_then(Value::as_str).unwrap_or_default();
    if expected.is_empty() || expected != model {
        return invalid("target_model_mismatch");
    }
    let data = fs::read(bundle)?;
    package::verify_bytes(&data)?;
    let object = target.as_object_mut().ok_or_else(|| Error::Invalid("object_required".into()))?;
    if let Some(key) = public_key {
        updates::public_key_from_pem(&fs::read(key)?)?;
        object.insert("updates_config".into(), json!("/etc/phoenix/updates.json"));
    } else if json::truthy(object.get("updates_config")) {
        return invalid("trusted_key_required");
    }
    let mut destinations: Vec<PathBuf> = ["opt/phoenix", "opt/phoenix-releases", "opt/phoenix-bootstrap", "etc/phoenix"].iter().map(|p| root.join(p)).collect();
    destinations.extend(service_units().map(|n| root.join("etc/systemd/system").join(n)));
    if destinations.iter().any(|p| present(p)) {
        return invalid("existing_installation_not_overwritten");
    }
    let releases = root.join("opt/phoenix-releases");
    let release = releases.join("factory");
    mkdirs(&release, 0o755)?;
    package::extract(&data, &release)?;
    set_mode(&releases, 0o755)?;
    let config_dir = root.join("etc/phoenix");
    mkdirs(&config_dir, 0o700)?;
    set_mode(&config_dir, 0o700)?;
    let pretty = serde_json::to_string_pretty(&target).map_err(Error::from)? + "\n";
    fsutil::write_private(&config_dir.join("target.json"), pretty.as_bytes())?;
    install_bootstrap(&release.join(BINARY), &root.join("opt/phoenix-bootstrap"))?;
    if let Some(key) = public_key {
        let installed = config_dir.join("update-public.pem");
        fs::copy(key, &installed)?;
        set_mode(&installed, 0o644)?;
        let updates_json = json::dumps(&json!({"public_key": "/etc/phoenix/update-public.pem"})) + "\n";
        fsutil::write_private(&config_dir.join("updates.json"), updates_json.as_bytes())?;
    }
    let unit_dir = root.join("etc/systemd/system");
    fs::create_dir_all(&unit_dir)?;
    for name in service_units() {
        install_unit(&release.join("deploy").join(name), &unit_dir.join(name))?;
    }
    let state = root.join("var/lib/phoenix");
    mkdirs(&state, 0o700)?;
    let token = state.join("admin-token");
    if !present(&token) {
        fsutil::write_private(&token, py::token_hex(32).as_bytes())?;
    }
    let (key, cert) = (config_dir.join("admin-key.pem"), config_dir.join("admin-cert.pem"));
    certificate(&key, &cert)?;
    set_mode(&key, 0o600)?;
    set_mode(&cert, 0o644)?;
    std::os::unix::fs::symlink(fs::canonicalize(&release)?, root.join("opt/phoenix"))?;
    Ok(())
}

fn ensure_service_user() -> Result<()> {
    let name = std::ffi::CString::new("phoenix-web").expect("static name");
    if !unsafe { libc::getpwnam(name.as_ptr()) }.is_null() {
        return Ok(());
    }
    let argv = ["useradd", "--system", "--no-create-home", "--shell", "/usr/sbin/nologin", "phoenix-web"];
    match run_with_timeout(&argv, None, Duration::from_secs(60)) {
        Ok(Some((0, _))) => Ok(()),
        _ => Err(Error::Network("command_failed:useradd".into())),
    }
}

/// `phoenix install --bundle B --target-config F [--public-key F]`
pub fn main(args: &[String]) -> i32 {
    let parsed = match Args::parse(args, &["bundle", "target-config", "public-key"], &[]) {
        Ok(p) if p.positionals.is_empty() => p,
        Ok(_) => return usage_error("unexpected argument"),
        Err(e) => return usage_error(&e),
    };
    let Some(bundle) = parsed.get("bundle") else {
        return usage_error("--bundle is required");
    };
    if fsutil::geteuid() != 0 || !Path::new("/proc/sys/kernel").exists() {
        eprintln!("Run only as root on the identified Linux target");
        return 1;
    }
    let Some(config) = parsed.get("target-config") else {
        return usage_error("--target-config is required");
    };
    let result = ensure_service_user()
        .and_then(|()| install(Path::new(bundle), Path::new(config), parsed.get("public-key").map(Path::new), Path::new("/")))
        .map(|()| println!("Installed; no service started and no network changed. Review target configuration before starting."));
    match result {
        Ok(()) => 0,
        Err(e) => {
            eprintln!("phoenix: {e}");
            1
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fsutil::testdir::TempDir;
    use std::os::unix::fs::MetadataExt;

    fn fake_certificate(key: &Path, cert: &Path) -> Result<()> {
        fs::write(key, "key")?;
        fs::write(cert, "cert")?;
        Ok(())
    }

    fn target_root(base: &Path) -> PathBuf {
        let root = base.join("target");
        fs::create_dir_all(root.join("proc/device-tree")).unwrap();
        fs::write(root.join("proc/device-tree/model"), "Test target\0").unwrap();
        root
    }

    fn mode(path: &Path) -> u32 {
        fs::metadata(path).unwrap().mode() & 0o777
    }

    #[test]
    fn target_guard_and_first_install() {
        let dir = TempDir::new();
        let root = target_root(dir.path());
        let bundle = package::tests::bundle(dir.path(), "bundle.zip");
        let config = dir.path().join("target.json");
        fs::write(&config, r#"{"expected_model": "Wrong"}"#).unwrap();
        assert_eq!(install_with(&bundle, &config, None, &root, &fake_certificate).unwrap_err().code(), "target_model_mismatch");
        assert!(!root.join("opt").exists());
        fs::write(&config, r#"{"expected_model": "Test target", "updates_config": "/etc/phoenix/updates.json"}"#).unwrap();
        assert_eq!(install_with(&bundle, &config, None, &root, &fake_certificate).unwrap_err().code(), "trusted_key_required");
        let (_, public) = updates::tests::keypair(dir.path(), "release");
        install_with(&bundle, &config, Some(&public), &root, &fake_certificate).unwrap();
        assert_eq!(fs::canonicalize(root.join("opt/phoenix")).unwrap().file_name().unwrap(), "factory");
        for unit in service_units() {
            assert_eq!(mode(&root.join("etc/systemd/system").join(unit)), 0o644, "{unit}");
        }
        let bootstrap = root.join("opt/phoenix-bootstrap/bin/phoenix");
        assert_eq!(fs::read(&bootstrap).unwrap(), fs::read(root.join("opt/phoenix/bin/phoenix")).unwrap());
        assert_eq!(mode(&bootstrap), 0o755);
        assert_eq!(mode(&root.join("opt/phoenix/bin/phoenix")), 0o755);
        assert_eq!(mode(&root.join("etc/phoenix")), 0o700);
        assert_eq!(mode(&root.join("etc/phoenix/target.json")), 0o600);
        assert_eq!(mode(&root.join("etc/phoenix/updates.json")), 0o600);
        assert_eq!(mode(&root.join("etc/phoenix/update-public.pem")), 0o644);
        assert_eq!(mode(&root.join("etc/phoenix/admin-key.pem")), 0o600);
        let target: Value = json::parse(&fs::read(root.join("etc/phoenix/target.json")).unwrap()).unwrap();
        assert_eq!(target["updates_config"], "/etc/phoenix/updates.json");
        let token = fs::read_to_string(root.join("var/lib/phoenix/admin-token")).unwrap();
        assert!(token.len() == 64 && token.bytes().all(|b| b.is_ascii_hexdigit()));
        assert_eq!(mode(&root.join("var/lib/phoenix/admin-token")), 0o600);
        assert_eq!(install_with(&bundle, &config, Some(&public), &root, &fake_certificate).unwrap_err().code(), "existing_installation_not_overwritten");
    }

    #[test]
    fn certificate_config_is_end_entity() {
        assert!(CERTIFICATE_CONFIG.contains("basicConstraints = critical,CA:FALSE"));
        assert!(CERTIFICATE_CONFIG.contains("subjectAltName = IP:127.0.0.1,DNS:localhost"));
    }
}
