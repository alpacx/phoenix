//! Signed application releases: monotonic sequence, atomic activation and
//! rollback (updates.py). Ed25519 via ring; no openssl CLI.
//! Does not update the kernel, bootloader, systemd units or the bootstrap.
use crate::args::{usage_error, Args};
use crate::error::{invalid, Error, Result};
use crate::httpc::{self, Target, Trust};
use crate::json::{self, json, Map, Value};
use crate::package;
use crate::runner::run_with_timeout;
use crate::vault::Vault;
use crate::{fsutil, py};
use base64::Engine;
use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::net::{Ipv4Addr, SocketAddrV4};
use std::os::fd::AsRawFd;
use std::os::unix::fs::{DirBuilderExt, MetadataExt, OpenOptionsExt};
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

pub const MAX_UPLOAD: usize = 20 * 1024 * 1024;
const KIND: &str = "phoenix-linux-application";
const FORMAT: i64 = 2;
const SPKI_PREFIX: [u8; 12] = [0x30, 0x2a, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x03, 0x21, 0x00];
const ENVELOPE: [&str; 3] = ["payload.zip", "release.json", "signature.bin"];

fn code(c: &str) -> impl Fn() -> Error + '_ {
    move || Error::Invalid(c.to_string())
}

/// Body of the first `-----BEGIN {label}-----` block.
pub fn pem_decode(text: &[u8], label: &str) -> Result<Vec<u8>> {
    let text = std::str::from_utf8(text).map_err(|_| Error::Invalid("invalid_pem".into()))?;
    let (begin, end) = (format!("-----BEGIN {label}-----"), format!("-----END {label}-----"));
    let start = text.find(&begin).ok_or_else(code("invalid_pem"))? + begin.len();
    let stop = start + text[start..].find(&end).ok_or_else(code("invalid_pem"))?;
    let body: String = text[start..stop].chars().filter(|c| !c.is_ascii_whitespace()).collect();
    base64::engine::general_purpose::STANDARD.decode(body).map_err(|_| Error::Invalid("invalid_pem".into()))
}

pub fn pem_encode(der: &[u8], label: &str) -> String {
    let body = base64::engine::general_purpose::STANDARD.encode(der);
    let lines: Vec<&str> = body.as_bytes().chunks(64).map(|c| std::str::from_utf8(c).unwrap_or("")).collect();
    format!("-----BEGIN {label}-----\n{}\n-----END {label}-----\n", lines.join("\n"))
}

/// Raw Ed25519 key from a PEM SubjectPublicKeyInfo (exactly 44 DER bytes).
pub fn public_key_from_pem(pem: &[u8]) -> Result<[u8; 32]> {
    let der = pem_decode(pem, "PUBLIC KEY").map_err(|_| Error::Invalid("ed25519_required".into()))?;
    if der.len() != 44 || der[..12] != SPKI_PREFIX {
        return invalid("ed25519_required");
    }
    let mut key = [0u8; 32];
    key.copy_from_slice(&der[12..]);
    Ok(key)
}

fn trusted_public_key(path: &Path) -> Result<[u8; 32]> {
    let meta = fs::symlink_metadata(path)?;
    if meta.file_type().is_symlink() || meta.uid() != fsutil::getuid() || meta.mode() & 0o022 != 0 {
        return invalid("untrusted_key_file_permissions");
    }
    public_key_from_pem(&fs::read(path)?)
}

fn version_ok(version: &str) -> bool {
    let bytes = version.as_bytes();
    !bytes.is_empty()
        && bytes.len() <= 64
        && bytes[0].is_ascii_alphanumeric()
        && bytes.iter().all(|b| b.is_ascii_alphanumeric() || matches!(b, b'.' | b'_' | b'-'))
}

fn sequence_ok(sequence: i64) -> bool {
    (1..(1i64 << 53)).contains(&sequence)
}

/// Verify an uploaded release (release.json + payload.zip + signature.bin)
/// against the trusted public key file; returns (release metadata, payload).
pub fn verify(data: &[u8], public_key: &Path) -> Result<(Value, Vec<u8>)> {
    if data.len() > MAX_UPLOAD {
        return invalid("update_too_large");
    }
    let key = trusted_public_key(public_key)?;
    let entries = package::zip_read(data).map_err(|_| Error::Invalid("invalid_update_archive".into()))?;
    let mut names: Vec<&str> = entries.iter().map(|e| e.name.as_str()).collect();
    names.sort_unstable();
    let total: usize = entries.iter().map(|e| e.data.len()).sum();
    if names != ENVELOPE || total > MAX_UPLOAD || entries.iter().any(|e| e.is_symlink() || e.is_dir()) {
        return invalid("invalid_update_archive");
    }
    let member = |name: &str| entries.iter().find(|e| e.name == name).map(|e| e.data).unwrap_or_default();
    let (meta, payload, signature) = (member("release.json"), member("payload.zip"), member("signature.bin"));
    if meta.len() > 4096 || signature.len() != 64 {
        return invalid("invalid_signature");
    }
    ring::signature::UnparsedPublicKey::new(&ring::signature::ED25519, &key)
        .verify(meta, signature)
        .map_err(|_| Error::Invalid("signature_operation_failed".into()))?;
    // Bind the payload to the signed hash before parsing any of it.
    let release = json::loads(meta)?;
    let object = json::object(&release)?;
    if object.get("kind").and_then(Value::as_str) != Some(KIND) || object.get("format") != Some(&Value::from(FORMAT)) {
        return invalid("wrong_update_type");
    }
    match object.get("sequence") {
        Some(s) if json::is_int(s) && s.as_i64().map(sequence_ok).unwrap_or(false) => {}
        _ => return invalid("invalid_sequence"),
    }
    if !object.get("version").and_then(Value::as_str).map(version_ok).unwrap_or(false) {
        return invalid("invalid_version");
    }
    if object.get("sha256").and_then(Value::as_str) != Some(package::sha256_hex(payload).as_str()) {
        return invalid("payload_hash_mismatch");
    }
    package::verify_bytes(payload)?;
    Ok((release, payload.to_vec()))
}

/// Canonical metadata: sorted keys, no whitespace (Python separators=(',', ':')).
fn metadata(sequence: i64, version: &str, sha256: &str) -> String {
    let mut meta = Map::new();
    meta.insert("format".into(), Value::from(FORMAT));
    meta.insert("kind".into(), Value::from(KIND));
    meta.insert("sequence".into(), Value::from(sequence));
    meta.insert("sha256".into(), Value::from(sha256));
    meta.insert("version".into(), Value::from(version));
    json::dumps(&Value::Object(meta))
}

/// Create a signed release from a format-2 payload bundle (PKCS#8 PEM key).
pub fn sign(payload: &Path, output: &Path, key: &Path, sequence: i64, version: &str) -> Result<()> {
    if !sequence_ok(sequence) || !version_ok(version) {
        return invalid("invalid_release_metadata");
    }
    let data = fs::read(payload)?;
    package::verify_bytes(&data)?;
    let meta = metadata(sequence, version, &package::sha256_hex(&data));
    let der = pem_decode(&fs::read(key)?, "PRIVATE KEY").map_err(|_| Error::Invalid("ed25519_required".into()))?;
    let pair = ring::signature::Ed25519KeyPair::from_pkcs8_maybe_unchecked(&der).map_err(|_| Error::Invalid("ed25519_required".into()))?;
    let signature = pair.sign(meta.as_bytes());
    let archive = package::zip_write(&[("release.json", meta.as_bytes(), 0o644), ("payload.zip", &data, 0o644), ("signature.bin", signature.as_ref(), 0o644)])?;
    let mut file = OpenOptions::new().write(true).create_new(true).mode(0o644).open(output)?;
    file.write_all(&archive)?;
    file.sync_all()?;
    Ok(())
}

fn statvfs_free(path: &Path) -> Result<u64> {
    let c_path = std::ffi::CString::new(path.as_os_str().as_encoded_bytes()).map_err(|_| Error::Invalid("invalid_path".into()))?;
    let mut st: libc::statvfs = unsafe { std::mem::zeroed() };
    if unsafe { libc::statvfs(c_path.as_ptr(), &mut st) } != 0 {
        return Err(std::io::Error::last_os_error().into());
    }
    Ok(st.f_bavail as u64 * st.f_frsize as u64)
}

/// Exclusive flock held until drop.
struct Lock(#[allow(dead_code)] File);

pub struct Updates {
    pub releases: PathBuf,
    pub current: PathBuf,
    pub state_dir: PathBuf,
    pub public_key: PathBuf,
    vault: Vault,
    free_space: fn(&Path) -> Result<u64>,
}

impl Updates {
    pub fn new(releases: &Path, current: &Path, state: &Path, public_key: &Path) -> Result<Updates> {
        for directory in [releases, state] {
            fsutil::ensure_dir(directory, 0o700, 0o022, "update_directory_permissions")?;
        }
        Ok(Updates {
            releases: releases.to_path_buf(),
            current: current.to_path_buf(),
            state_dir: state.to_path_buf(),
            public_key: public_key.to_path_buf(),
            vault: Vault::named(state, "update-state.json"),
            free_space: statvfs_free,
        })
    }

    fn locked(&self) -> Result<Lock> {
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .mode(0o600)
            .custom_flags(libc::O_NOFOLLOW)
            .open(self.state_dir.join("update.lock"))?;
        if unsafe { libc::flock(file.as_raw_fd(), libc::LOCK_EX) } != 0 {
            return Err(std::io::Error::last_os_error().into());
        }
        Ok(Lock(file))
    }

    /// {phase, version, max_sequence, error}
    pub fn status(&self) -> Result<Value> {
        let state = self.vault.load_object()?;
        let mut out = Map::new();
        for key in ["phase", "version", "max_sequence", "error"] {
            out.insert(key.into(), state.get(key).cloned().unwrap_or(Value::Null));
        }
        Ok(Value::Object(out))
    }

    pub fn check_current(&self) -> Result<String> {
        if !fsutil::is_symlink(&self.current) {
            return invalid("current_must_be_managed_release_symlink");
        }
        let target = fs::canonicalize(&self.current)?;
        if target.parent() != Some(fs::canonicalize(&self.releases)?.as_path()) {
            return invalid("current_outside_release_directory");
        }
        Ok(target.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default())
    }

    pub fn switch(&self, name: &str) -> Result<()> {
        if name == "." || name == ".." || name.is_empty() || !name.bytes().all(|b| b.is_ascii_alphanumeric() || matches!(b, b'.' | b'_' | b'-')) {
            return invalid("invalid_release_name");
        }
        let target = self.releases.join(name);
        if fsutil::is_symlink(&target) || !target.is_dir() {
            return invalid("release_missing");
        }
        let mut temporary_name = self.current.file_name().ok_or_else(code("invalid_current_path"))?.to_os_string();
        temporary_name.push(".switch");
        let temporary = self.current.with_file_name(temporary_name);
        if fsutil::is_symlink(&temporary) {
            fs::remove_file(&temporary)?; // Interrupted atomic switch in this root-owned directory.
        } else if fs::symlink_metadata(&temporary).is_ok() {
            return invalid("switch_path_already_exists");
        }
        std::os::unix::fs::symlink(fs::canonicalize(&target)?, &temporary)?;
        fs::rename(&temporary, &self.current)?;
        fsutil::fsync_dir(self.current.parent().unwrap_or_else(|| Path::new("/")))
    }

    fn make_staging(&self) -> Result<PathBuf> {
        loop {
            let candidate = self.releases.join(format!(".stage-{}", py::token_hex(6)));
            match fs::DirBuilder::new().mode(0o700).create(&candidate) {
                Ok(()) => return Ok(candidate),
                Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(e) => return Err(e.into()),
            }
        }
    }

    pub fn stage(&self, data: &[u8]) -> Result<Value> {
        let (release, payload) = verify(data, &self.public_key)?;
        let _lock = self.locked()?;
        let needed: u64 = package::zip_read(&payload)?.iter().map(|e| e.data.len() as u64).sum::<u64>() + 64 * 1024 * 1024;
        if (self.free_space)(&self.releases)? < needed {
            return invalid("insufficient_update_space");
        }
        let previous = self.check_current()?;
        let state = self.vault.load_object()?;
        if matches!(state.get("phase").and_then(Value::as_str), Some("staged" | "activating")) {
            return invalid("update_in_progress");
        }
        let sequence = release["sequence"].as_i64().ok_or_else(code("invalid_sequence"))?;
        let max_sequence = match state.get("max_sequence") {
            None => 0,
            Some(value) => value.as_i64().filter(|_| json::is_int(value)).ok_or_else(code("invalid_update_state"))?,
        };
        if sequence <= max_sequence {
            return invalid("update_replay_or_downgrade");
        }
        let digest = release["sha256"].as_str().ok_or_else(code("payload_hash_mismatch"))?;
        let name = format!("{sequence}-{}", &digest[..16]);
        let destination = self.releases.join(&name);
        if fs::symlink_metadata(&destination).is_ok() {
            return invalid("release_already_exists");
        }
        let staging = self.make_staging()?;
        let result = (|| -> Result<()> {
            package::extract(&payload, &staging)?;
            fs::rename(&staging, &destination)?;
            fsutil::fsync_dir(&self.releases)?;
            self.vault.save(&json!({"phase": "staged", "max_sequence": sequence, "version": release["version"],
                                    "previous": previous, "next": name, "error": ""}))
        })();
        if fs::symlink_metadata(&staging).is_ok() {
            let _ = fs::remove_dir_all(&staging);
        }
        result?;
        self.status()
    }

    pub fn recover(&self) -> Result<bool> {
        let _lock = self.locked()?;
        let mut state = self.vault.load_object()?;
        if state.get("phase").and_then(Value::as_str) != Some("activating") {
            return Ok(false);
        }
        let previous = state.get("previous").and_then(Value::as_str).ok_or_else(code("invalid_update_state"))?.to_string();
        self.switch(&previous)?;
        state.insert("phase".into(), json!("rolled_back"));
        state.insert("error".into(), json!("interrupted_update"));
        self.vault.save(&Value::Object(state))?;
        Ok(true)
    }

    pub fn activate(&self, service: &dyn Fn(&str) -> Result<()>, healthy: &dyn Fn(&str) -> bool) -> Result<Value> {
        {
            let _lock = self.locked()?;
            let mut state = self.vault.load_object()?;
            if state.get("phase").and_then(Value::as_str) != Some("staged") {
                return invalid("no_staged_update");
            }
            let text = |key: &str| state.get(key).and_then(Value::as_str).map(str::to_owned).ok_or_else(code("invalid_update_state"));
            let (previous, next) = (text("previous")?, text("next")?);
            if self.check_current()? != previous {
                return invalid("current_release_changed");
            }
            state.insert("phase".into(), json!("activating"));
            self.vault.save(&Value::Object(state.clone()))?;
            let attempt = (|| -> Result<()> {
                service("stop")?;
                self.switch(&next)?;
                service("start")?;
                if healthy(&next) {
                    Ok(())
                } else {
                    invalid("updated_service_unhealthy")
                }
            })();
            if attempt.is_ok() {
                state.insert("phase".into(), json!("active"));
                state.insert("error".into(), json!(""));
                self.vault.save(&Value::Object(state))?;
            } else {
                let rollback = (|| -> Result<()> {
                    service("stop")?;
                    self.switch(&previous)?;
                    service("start")
                })();
                let (phase, error) = if rollback.is_ok() { ("rolled_back", "activation_failed") } else { ("rollback_failed", "manual_recovery_required") };
                state.insert("phase".into(), json!(phase));
                state.insert("error".into(), json!(error));
                self.vault.save(&Value::Object(state))?;
                return invalid(error);
            }
        }
        self.status()
    }
}

/// /etc/phoenix/updates.json -> Updates for /opt/phoenix(-releases), /var/lib/phoenix.
pub fn from_config(path: &Path) -> Result<Updates> {
    let meta = fs::symlink_metadata(path)?;
    if meta.file_type().is_symlink() || meta.uid() != fsutil::getuid() || meta.mode() & 0o022 != 0 {
        return invalid("untrusted_update_configuration");
    }
    let config = json::parse(&fs::read(path)?)?;
    let key = config.get("public_key").and_then(Value::as_str).ok_or_else(code("invalid_update_configuration"))?;
    Updates::new(Path::new("/opt/phoenix-releases"), Path::new("/opt/phoenix"), Path::new("/var/lib/phoenix"), Path::new(key))
}

fn service(action: &str) -> Result<()> {
    if action == "restart" {
        service("stop")?;
        return service("start");
    }
    let units = if action == "stop" { ["phoenix.service", "phoenix-control.service"] } else { ["phoenix-control.service", "phoenix.service"] };
    for unit in units {
        match run_with_timeout(&["systemctl", action, unit], None, Duration::from_secs(120)) {
            Ok(Some((0, _))) => {}
            _ => return Err(Error::Network("command_failed:systemctl".into())),
        }
    }
    Ok(())
}

/// The new frontend answers /healthz as ready from release `name` within 30 s.
fn healthy(name: &str) -> bool {
    let Some(certificate) = fs::read("/etc/phoenix/admin-cert.pem").ok().and_then(|pem| httpc::pem_certificate(&pem).ok()) else {
        return false;
    };
    let target = Target {
        host: "127.0.0.1",
        address: SocketAddrV4::new(Ipv4Addr::LOCALHOST, 8443),
        device: None,
        mark: 0,
        timeout: Duration::from_secs(2),
    };
    let trust = Trust::Pinned(certificate);
    let deadline = Instant::now() + Duration::from_secs(30);
    while Instant::now() < deadline {
        if let Ok((200, body)) = httpc::get(&target, "/healthz", &[], &trust, 4096) {
            if let Ok(status) = json::parse(&body) {
                if status.get("ready") == Some(&Value::Bool(true)) && status.get("release_id").and_then(Value::as_str) == Some(name) {
                    return true;
                }
            }
        }
        std::thread::sleep(Duration::from_secs(1));
    }
    false
}

fn fail(error: Error) -> i32 {
    eprintln!("phoenix: {error}");
    1
}

/// `phoenix update activate|recover [--restart] [--config F]`
/// `phoenix update sign --payload F --output F --key F --version V --sequence N`
pub fn main(args: &[String]) -> i32 {
    let Some((action, rest)) = args.split_first() else {
        return usage_error("usage: phoenix update activate|recover|sign [options]");
    };
    match action.as_str() {
        "sign" => {
            let parsed = match Args::parse(rest, &["payload", "output", "key", "version", "sequence"], &[]) {
                Ok(p) => p,
                Err(e) => return usage_error(&e),
            };
            let get = |n: &str| parsed.require(n).map(str::to_owned);
            let (payload, output, key, version, sequence) = match (get("payload"), get("output"), get("key"), get("version"), get("sequence")) {
                (Ok(a), Ok(b), Ok(c), Ok(d), Ok(e)) => (a, b, c, d, e),
                _ => return usage_error("--payload, --output, --key, --version and --sequence are required"),
            };
            let Ok(sequence) = sequence.parse::<i64>() else {
                return usage_error("--sequence must be an integer");
            };
            match sign(Path::new(&payload), Path::new(&output), Path::new(&key), sequence, &version) {
                Ok(()) => {
                    println!("Signed application release created");
                    0
                }
                Err(e) => fail(e),
            }
        }
        "activate" | "recover" => {
            let flags: &[&str] = if action == "recover" { &["restart"] } else { &[] };
            let parsed = match Args::parse(rest, &["config"], flags) {
                Ok(p) if p.positionals.is_empty() => p,
                Ok(_) => return usage_error("unexpected argument"),
                Err(e) => return usage_error(&e),
            };
            if fsutil::geteuid() != 0 || !Path::new("/proc/sys/kernel").exists() {
                eprintln!("Linux root required");
                return 1;
            }
            let updater = match from_config(Path::new(parsed.get("config").unwrap_or("/etc/phoenix/updates.json"))) {
                Ok(u) => u,
                Err(e) => return fail(e),
            };
            let result = if action == "recover" {
                updater.recover().and_then(|recovered| if recovered && parsed.flag("restart") { service("restart") } else { Ok(()) })
            } else {
                updater.activate(&service, &healthy).map(|_| ())
            };
            result.map(|()| 0).unwrap_or_else(fail)
        }
        _ => usage_error("usage: phoenix update activate|recover|sign [options]"),
    }
}

#[cfg(test)]
pub mod tests {
    use super::*;
    use crate::fsutil::testdir::TempDir;
    use std::cell::RefCell;
    use std::os::unix::fs::PermissionsExt;

    /// (private PEM, public PEM) written to dir/name.{key,pub}; public is 0644.
    pub fn keypair(dir: &Path, name: &str) -> (PathBuf, PathBuf) {
        let rng = ring::rand::SystemRandom::new();
        let pkcs8 = ring::signature::Ed25519KeyPair::generate_pkcs8(&rng).unwrap();
        let pair = ring::signature::Ed25519KeyPair::from_pkcs8(pkcs8.as_ref()).unwrap();
        use ring::signature::KeyPair;
        let mut spki = SPKI_PREFIX.to_vec();
        spki.extend_from_slice(pair.public_key().as_ref());
        let (key, public) = (dir.join(format!("{name}.key")), dir.join(format!("{name}.pub")));
        fs::write(&key, pem_encode(pkcs8.as_ref(), "PRIVATE KEY")).unwrap();
        fs::set_permissions(&key, fs::Permissions::from_mode(0o600)).unwrap();
        fs::write(&public, pem_encode(&spki, "PUBLIC KEY")).unwrap();
        fs::set_permissions(&public, fs::Permissions::from_mode(0o644)).unwrap();
        (key, public)
    }

    struct Fixture {
        dir: TempDir,
        public: PathBuf,
        key: PathBuf,
        data: Vec<u8>,
    }

    fn fixture() -> Fixture {
        let dir = TempDir::new();
        let (key, public) = keypair(dir.path(), "release");
        let payload = package::tests::bundle(dir.path(), "payload.zip");
        let envelope = dir.path().join("release.phx");
        sign(&payload, &envelope, &key, 2, "test-2").unwrap();
        let data = fs::read(envelope).unwrap();
        Fixture { dir, public, key, data }
    }

    fn updater(f: &Fixture) -> Updates {
        let root = f.dir.path().join(format!("u-{}", py::token_hex(4)));
        fs::create_dir_all(root.join("releases/factory")).unwrap();
        std::os::unix::fs::symlink(root.join("releases/factory"), root.join("current")).unwrap();
        Updates::new(&root.join("releases"), &root.join("current"), &root.join("state"), &f.public).unwrap()
    }

    fn resolved(update: &Updates) -> String {
        fs::canonicalize(&update.current).unwrap().file_name().unwrap().to_string_lossy().into_owned()
    }

    fn rebuild(data: &[u8], changed: &str) -> Vec<u8> {
        let entries = package::zip_read(data).unwrap();
        let owned: Vec<(String, Vec<u8>)> = entries
            .iter()
            .map(|e| {
                let mut content = e.data.to_vec();
                if e.name == changed {
                    content[0] ^= 1;
                }
                (e.name.clone(), content)
            })
            .collect();
        let all: Vec<(&str, &[u8], u32)> = owned.iter().map(|(n, d)| (n.as_str(), d.as_slice(), 0o644)).collect();
        package::zip_write(&all).unwrap()
    }

    #[test]
    fn real_signature_and_modified_members() {
        let f = fixture();
        let (meta, payload) = verify(&f.data, &f.public).unwrap();
        assert_eq!(meta["sequence"], 2);
        assert_eq!(meta["format"], 2);
        assert!(package::verify_bytes(&payload).is_ok());
        let entries = package::zip_read(&f.data).unwrap();
        let release = entries.iter().find(|e| e.name == "release.json").unwrap();
        assert!(std::str::from_utf8(release.data).unwrap().starts_with("{\"format\":2,\"kind\":\"phoenix-linux-application\",\"sequence\":2,\"sha256\":\""));
        for changed in ENVELOPE {
            assert!(verify(&rebuild(&f.data, changed), &f.public).is_err(), "{changed} tampering accepted");
        }
        let (_, other) = keypair(f.dir.path(), "other");
        assert!(verify(&f.data, &other).is_err());
        assert!(sign(&f.dir.path().join("payload.zip"), &f.dir.path().join("x.phx"), &f.key, 0, "v").is_err());
        assert!(sign(&f.dir.path().join("payload.zip"), &f.dir.path().join("x.phx"), &f.key, 3, "-bad").is_err());
    }

    #[test]
    fn key_file_must_be_trusted_and_ed25519() {
        let f = fixture();
        fs::set_permissions(&f.public, fs::Permissions::from_mode(0o664)).unwrap();
        assert_eq!(verify(&f.data, &f.public).unwrap_err().code(), "untrusted_key_file_permissions");
        fs::set_permissions(&f.public, fs::Permissions::from_mode(0o644)).unwrap();
        let link = f.dir.path().join("link.pub");
        std::os::unix::fs::symlink(&f.public, &link).unwrap();
        assert_eq!(verify(&f.data, &link).unwrap_err().code(), "untrusted_key_file_permissions");
        assert!(public_key_from_pem(pem_encode(&[0u8; 44], "PUBLIC KEY").as_bytes()).is_err());
        assert!(verify(&vec![0u8; MAX_UPLOAD + 1], &f.public).is_err());
    }

    #[test]
    fn pkcs8_v1_from_openssl_signs_rfc8032_vector() {
        // openssl genpkey -algorithm ed25519 emits PKCS#8 v1 (seed only).
        let seed = py::unhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60").unwrap();
        let mut der = py::unhex("302e020100300506032b657004220420").unwrap();
        der.extend_from_slice(&seed);
        let pem = pem_encode(&der, "PRIVATE KEY");
        let decoded = pem_decode(pem.as_bytes(), "PRIVATE KEY").unwrap();
        let pair = ring::signature::Ed25519KeyPair::from_pkcs8_maybe_unchecked(&decoded).unwrap();
        use ring::signature::KeyPair;
        assert_eq!(py::hex(pair.public_key().as_ref()), "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a");
        assert_eq!(
            py::hex(pair.sign(b"").as_ref()),
            "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
        );
    }

    #[test]
    fn activate_and_replay_rejected() {
        let f = fixture();
        let update = updater(&f);
        assert_eq!(update.stage(&f.data).unwrap()["phase"], "staged");
        let next = update.vault.load_object().unwrap()["next"].as_str().unwrap().to_string();
        assert!(next.starts_with("2-") && next.len() == 18);
        let release = update.releases.join(&next);
        assert_eq!(fs::metadata(release.join("bin/phoenix")).unwrap().mode() & 0o777, 0o755);
        assert_eq!(fs::metadata(release.join("deploy/phoenix.service")).unwrap().mode() & 0o777, 0o644);
        assert_eq!(fs::metadata(&release).unwrap().mode() & 0o777, 0o755);
        assert_eq!(update.stage(&f.data).unwrap_err().code(), "update_in_progress");
        let calls = RefCell::new(Vec::new());
        let result = update.activate(&|a| Ok(calls.borrow_mut().push(a.to_string())), &|name| resolved(&update) == name).unwrap();
        assert_eq!(result["phase"], "active");
        assert_eq!(*calls.borrow(), vec!["stop", "start"]);
        assert_eq!(update.stage(&f.data).unwrap_err().code(), "update_replay_or_downgrade");
        assert!(fs::read_dir(&update.releases).unwrap().all(|e| !e.unwrap().file_name().to_string_lossy().starts_with(".stage-")));
    }

    #[test]
    fn failed_health_rolls_back_and_keeps_sequence() {
        let f = fixture();
        let update = updater(&f);
        update.stage(&f.data).unwrap();
        assert_eq!(update.activate(&|_| Ok(()), &|_| false).unwrap_err().code(), "activation_failed");
        assert_eq!(resolved(&update), "factory");
        let status = update.status().unwrap();
        assert_eq!(status["phase"], "rolled_back");
        assert_eq!(status["max_sequence"], 2);
        assert!(update.stage(&f.data).is_err());
        assert_eq!(update.activate(&|_| Ok(()), &|_| true).unwrap_err().code(), "no_staged_update");
    }

    #[test]
    fn failing_rollback_requires_manual_recovery() {
        let f = fixture();
        let update = updater(&f);
        update.stage(&f.data).unwrap();
        let err = update.activate(&|a| if a == "start" { invalid("down") } else { Ok(()) }, &|_| true).unwrap_err();
        assert_eq!(err.code(), "manual_recovery_required");
        assert_eq!(update.status().unwrap()["phase"], "rollback_failed");
    }

    #[test]
    fn interrupted_activation_recovered() {
        let f = fixture();
        let update = updater(&f);
        update.stage(&f.data).unwrap();
        let mut state = update.vault.load_object().unwrap();
        state.insert("phase".into(), json!("activating"));
        update.vault.save(&Value::Object(state.clone())).unwrap();
        update.switch(state["next"].as_str().unwrap()).unwrap();
        assert_ne!(resolved(&update), "factory");
        assert!(update.recover().unwrap());
        assert_eq!(resolved(&update), "factory");
        assert_eq!(update.status().unwrap()["error"], "interrupted_update");
        assert!(!update.recover().unwrap());
        assert!(update.switch("..").is_err() && update.switch("missing").is_err());
    }

    #[test]
    fn low_disk_space_rejected_before_staging() {
        let f = fixture();
        let mut update = updater(&f);
        update.free_space = |_| Ok(1);
        assert_eq!(update.stage(&f.data).unwrap_err().code(), "insufficient_update_space");
        assert_eq!(resolved(&update), "factory");
        assert_eq!(update.status().unwrap()["phase"], Value::Null);
        assert_eq!(fs::read_dir(&update.releases).unwrap().count(), 1);
    }

    #[test]
    fn untrusted_directories_and_config_rejected() {
        let f = fixture();
        let dir = f.dir.path().join("open");
        fs::create_dir(&dir).unwrap();
        fs::set_permissions(&dir, fs::Permissions::from_mode(0o777)).unwrap();
        assert!(Updates::new(&dir, &f.dir.path().join("c"), &f.dir.path().join("s"), &f.public).is_err());
        let config = f.dir.path().join("updates.json");
        fs::write(&config, "{\"public_key\": \"/x\"}").unwrap();
        fs::set_permissions(&config, fs::Permissions::from_mode(0o666)).unwrap();
        assert_eq!(from_config(&config).err().unwrap().code(), "untrusted_update_configuration");
    }
}
