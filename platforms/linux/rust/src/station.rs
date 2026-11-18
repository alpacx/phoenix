//! Opt-in NetworkManager STA adapter (station.py). Secrets never appear in
//! command arguments; only the Phoenix-owned connection is replaced and
//! arbitrary active connections are not disconnected.
use crate::error::{invalid, Error, Result};
use crate::firewall::interface;
use crate::json::{self, Map, Value};
use crate::runner::SharedRunner;
use crate::vault::Vault;
use crate::{fsutil, ipv4, py};
use std::path::{Path, PathBuf};

pub fn validate(body: &Value) -> Result<()> {
    let Some(map) = body.as_object() else {
        return invalid("invalid_wifi_configuration");
    };
    let save_ok = map.get("save").map(Value::is_boolean).unwrap_or(true);
    if map.get("mode").and_then(Value::as_str) != Some("sta") || !save_ok {
        return invalid("invalid_wifi_configuration");
    }
    match map.get("ssid") {
        Some(Value::String(ssid)) if (1..=32).contains(&ssid.len()) && !ssid.chars().any(|c| (c as u32) < 32) => {}
        _ => return invalid("invalid_ssid"),
    }
    match map.get("password") {
        None => {}
        Some(Value::String(p)) if p.is_empty() || ((8..=63).contains(&py::len_chars(p)) && p.is_ascii() && !p.chars().any(|c| (c as u32) < 32)) => {}
        _ => return invalid("invalid_password"),
    }
    Ok(())
}

/// nmcli terse output with `--escape yes`: `\:` and `\\` escapes.
pub fn split_fields(line: &str) -> Result<Vec<String>> {
    let mut fields = Vec::new();
    let mut value = String::new();
    let mut escaped = false;
    for c in line.chars() {
        if escaped {
            value.push(c);
            escaped = false;
        } else if c == '\\' {
            escaped = true;
        } else if c == ':' {
            fields.push(std::mem::take(&mut value));
        } else {
            value.push(c);
        }
    }
    if escaped {
        return invalid("invalid_scan_line");
    }
    fields.push(value);
    Ok(fields)
}

/// RFC 4122 name-based UUID (SHA-1) in the URL namespace, as Python's uuid5.
pub fn uuid5_url(name: &str) -> String {
    const NAMESPACE_URL: [u8; 16] = [0x6b, 0xa7, 0xb8, 0x11, 0x9d, 0xad, 0x11, 0xd1, 0x80, 0xb4, 0x00, 0xc0, 0x4f, 0xd4, 0x30, 0xc8];
    let mut context = ring::digest::Context::new(&ring::digest::SHA1_FOR_LEGACY_USE_ONLY);
    context.update(&NAMESPACE_URL);
    context.update(name.as_bytes());
    let digest = context.finish();
    let mut bytes = [0u8; 16];
    bytes.copy_from_slice(&digest.as_ref()[..16]);
    bytes[6] = (bytes[6] & 0x0f) | 0x50;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    let hex = py::hex(&bytes);
    format!("{}-{}-{}-{}-{}", &hex[..8], &hex[8..12], &hex[12..16], &hex[16..20], &hex[20..])
}

pub struct Station {
    pub name: String,
    pub uuid: String,
    pub connection_name: String,
    /// Saved/last profile body (object), `{}` when none.
    pub current: Value,
    pub active: bool,
    directory: PathBuf,
    profile_directory: PathBuf,
    run: SharedRunner,
    vault: Vault,
}

fn network_error(code: &str) -> Error {
    Error::Network(code.to_string())
}

impl Station {
    pub fn new(name: &str, directory: &Path, runner: SharedRunner, profile_directory: Option<&Path>) -> Result<Station> {
        let name = interface(name)?;
        fsutil::ensure_dir(directory, 0o700, 0o077, "station_directory_not_private")?;
        let profile_directory = profile_directory.unwrap_or(directory).to_path_buf();
        fsutil::ensure_dir(&profile_directory, 0o700, 0o022, "unsafe_networkmanager_profile_directory")?;
        let vault = Vault::new(directory);
        let current = vault.load()?;
        Ok(Station {
            uuid: uuid5_url(&format!("phoenix://station/{name}")),
            connection_name: format!("phoenix-sta-{name}"),
            name,
            current,
            active: false,
            directory: directory.to_path_buf(),
            profile_directory,
            run: runner,
            vault,
        })
    }

    /// Python `bool(self.current)`.
    pub fn has_profile(&self) -> bool {
        crate::json::truthy(Some(&self.current))
    }

    /// Test/controller hook: replace the command runner.
    pub fn set_runner(&mut self, runner: SharedRunner) {
        self.run = runner;
    }

    pub fn vault(&self) -> &Vault {
        &self.vault
    }

    pub fn scan(&self) -> Result<Value> {
        let result = self.run.run(&["nmcli", "-t", "--escape", "yes", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list", "ifname", &self.name, "--rescan", "yes"])?;
        let mut networks = Vec::new();
        for line in py::splitlines(&result.stdout) {
            let fields = split_fields(line)?;
            if fields.len() != 3 || fields[0].is_empty() || !py::is_digits(&fields[1]) {
                continue;
            }
            let Ok(signal) = fields[1].parse::<i64>() else {
                continue;
            };
            networks.push(json::json!({"ssid": fields[0], "signal_percent": signal, "rssi": null, "security": fields[2]}));
        }
        networks.truncate(16);
        Ok(json::json!({"networks": networks}))
    }

    fn device_uuid(&self) -> Result<String> {
        Ok(py::strip(&self.run.run(&["nmcli", "-g", "GENERAL.CON-UUID", "device", "show", &self.name])?.stdout).to_string())
    }

    pub fn check_ownership(&self) -> Result<()> {
        let current = self.device_uuid()?;
        if !(current.is_empty() || current == "--" || current == self.uuid) {
            return Err(network_error("wifi_interface_has_foreign_connection"));
        }
        let existing = self.run.optional(&["nmcli", "-g", "connection.id", "connection", "show", "uuid", &self.uuid])?;
        if existing.code == 0 && py::strip(&existing.stdout) != self.connection_name {
            return Err(network_error("wifi_profile_collision"));
        }
        Ok(())
    }

    /// Recover only our connection after a prior process crash; never another profile.
    pub fn prepare_startup(&mut self, restore_ap: bool) -> Result<()> {
        self.check_ownership()?;
        if self.device_uuid()? == self.uuid {
            self.run.run(&["nmcli", "connection", "down", "uuid", &self.uuid])?;
        }
        self.active = false;
        if restore_ap {
            self.run.run(&["nmcli", "device", "set", &self.name, "autoconnect", "no"])?;
            self.run.run(&["nmcli", "device", "set", &self.name, "managed", "no"])?;
        }
        Ok(())
    }

    /// Returns the IPv4 gateway.
    pub fn connect(&mut self, body: &Value) -> Result<String> {
        validate(body)?;
        self.check_ownership()?;
        let map: &Map<String, Value> = body.as_object().expect("validated object");
        let ssid_text = map.get("ssid").and_then(Value::as_str).unwrap_or("");
        let password = map.get("password").and_then(Value::as_str).unwrap_or("");
        // Decimal SSID bytes are a supported keyfile representation: no keyfile
        // injection, loss of leading spaces, or dependency on nmcli --offline.
        let ssid: String = ssid_text.bytes().map(|b| format!("{b};")).collect();
        let mut profile = format!(
            "[connection]\nid={}\nuuid={}\ntype=wifi\ninterface-name={}\nautoconnect=false\n[wifi]\nmode=infrastructure\nssid={ssid}\n[ipv4]\nmethod=auto\nnever-default=true\nignore-auto-dns=true\n[ipv6]\nmethod=disabled\n",
            self.connection_name, self.uuid, self.name
        );
        if !password.is_empty() {
            profile += "[wifi-security]\nkey-mgmt=wpa-psk\npsk-flags=2\n";
        }
        let config = self.profile_directory.join(format!("{}.nmconnection", self.connection_name));
        let secret = self.directory.join("password");
        fsutil::write_private(&config, profile.as_bytes())?;
        let written = fsutil::write_private(&secret, format!("802-11-wireless-security.psk:{password}\n").as_bytes());
        let result = written.and_then(|_| self.bring_up(&config, &secret, body));
        let _ = std::fs::remove_file(&secret);
        result
    }

    fn bring_up(&mut self, config: &Path, secret: &Path, body: &Value) -> Result<String> {
        self.active = false;
        let attempt = (|| -> Result<String> {
            let run = &self.run;
            run.run(&["nmcli", "device", "set", &self.name, "autoconnect", "no"])?;
            run.run(&["nmcli", "device", "set", &self.name, "managed", "yes"])?;
            run.run(&["nmcli", "connection", "load", &config.to_string_lossy()])?;
            run.run(&["nmcli", "--wait", "10", "connection", "up", "uuid", &self.uuid, "ifname", &self.name, "passwd-file", &secret.to_string_lossy()])?;
            let output = run.run(&["nmcli", "-g", "IP4.GATEWAY", "device", "show", &self.name])?.stdout;
            let lines = py::splitlines(py::strip(&output));
            let first = lines.first().ok_or_else(|| network_error("wifi_gateway_not_assigned"))?;
            Ok(ipv4::address(first)?.to_string())
        })();
        let saved = attempt.and_then(|gateway| {
            // As in Python, the profile is remembered even if persisting it fails.
            self.current = body.clone();
            let save = body.get("save").and_then(Value::as_bool).unwrap_or(false);
            let empty = Value::Object(Map::new());
            self.vault.save(if save { body } else { &empty })?;
            Ok(gateway)
        });
        match saved {
            Ok(gateway) => {
                self.active = true;
                Ok(gateway)
            }
            Err(error) => {
                let _ = self.run.optional(&["nmcli", "connection", "down", "uuid", &self.uuid]);
                Err(error)
            }
        }
    }

    pub fn reconnect(&mut self) -> Result<String> {
        if !self.has_profile() {
            return invalid("wifi_profile_required");
        }
        let current = self.current.clone();
        self.connect(&current)
    }

    pub fn disconnect(&mut self) {
        if self.active {
            let _ = self.run.optional(&["nmcli", "connection", "down", "uuid", &self.uuid]);
            self.active = false;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fsutil::testdir::TempDir;
    use crate::json::json;
    use crate::runner::{exit, ok, FakeRunner, Output};
    use std::sync::Arc;

    fn body() -> Value {
        json!({"mode": "sta", "ssid": "Test:SSID", "password": "example-only-secret", "save": true})
    }

    fn adapter(dir: &Path, foreign: bool, fail: bool) -> (Station, Arc<FakeRunner>) {
        let runner = Arc::new(FakeRunner::with(move |argv, _| {
            if argv.iter().any(|a| a == "GENERAL.CON-UUID") {
                return ok(if foreign { "foreign-uuid" } else { "--" });
            }
            if argv.iter().any(|a| a == "connection.id") {
                return exit(10);
            }
            if argv.iter().any(|a| a == "passwd-file") {
                let text = std::fs::read_to_string(argv.last().unwrap()).unwrap();
                assert!(text.contains("example-only-secret"));
                if fail {
                    return exit(1);
                }
            }
            if argv.iter().any(|a| a == "IP4.GATEWAY") {
                return ok("192.0.2.1\n");
            }
            Some(Output::default())
        }));
        (Station::new("wlan0", dir, runner.clone(), None).unwrap(), runner)
    }

    #[test]
    fn uuid_matches_python() {
        // python3 -c "import uuid;print(uuid.uuid5(uuid.NAMESPACE_URL,'phoenix://station/wlan0'))"
        assert_eq!(uuid5_url("phoenix://station/wlan0"), "0dc048cc-cd66-5bfb-bf2e-730fc5e9f4ba");
    }

    #[test]
    fn secret_lifetime_persistence_and_no_argv_secret() {
        let tmp = TempDir::new();
        let (mut station, runner) = adapter(tmp.path(), false, false);
        assert_eq!(station.connect(&body()).unwrap(), "192.0.2.1");
        assert!(!tmp.path().join("password").exists());
        assert!(!format!("{:?}", runner.argvs()).contains("example-only-secret"));
        assert_eq!(station.vault().load().unwrap()["ssid"], "Test:SSID");
        assert!(station.active && station.has_profile());
        let keyfile = std::fs::read_to_string(tmp.path().join("phoenix-sta-wlan0.nmconnection")).unwrap();
        assert_eq!(
            keyfile,
            format!("[connection]\nid=phoenix-sta-wlan0\nuuid={}\ntype=wifi\ninterface-name=wlan0\nautoconnect=false\n[wifi]\nmode=infrastructure\nssid=84;101;115;116;58;83;83;73;68;\n[ipv4]\nmethod=auto\nnever-default=true\nignore-auto-dns=true\n[ipv6]\nmethod=disabled\n[wifi-security]\nkey-mgmt=wpa-psk\npsk-flags=2\n", station.uuid)
        );
        let expected: Vec<Vec<String>> = [
            vec!["nmcli", "device", "set", "wlan0", "autoconnect", "no"],
            vec!["nmcli", "device", "set", "wlan0", "managed", "yes"],
        ]
        .iter()
        .map(|v| v.iter().map(|s| s.to_string()).collect())
        .collect();
        assert_eq!(runner.argvs()[2..4], expected);
        station.disconnect();
        assert!(!station.active);
        assert!(runner.argvs().last().unwrap().contains(&"down".to_string()));
        let mut unsaved = body();
        unsaved["save"] = json!(false);
        station.connect(&unsaved).unwrap();
        assert_eq!(station.vault().load().unwrap(), json!({}));
        assert_eq!(station.current["save"], false);
    }

    #[test]
    fn failure_removes_password_and_deactivates_owned_profile() {
        let tmp = TempDir::new();
        let (mut station, runner) = adapter(tmp.path(), false, true);
        assert!(matches!(station.connect(&body()), Err(Error::Network(_))));
        assert!(!tmp.path().join("password").exists());
        assert!(!station.active);
        assert!(runner.argvs().iter().any(|c| c.contains(&"down".to_string())));
    }

    #[test]
    fn foreign_connection_not_touched() {
        let tmp = TempDir::new();
        let (mut station, runner) = adapter(tmp.path(), true, false);
        assert!(matches!(station.connect(&body()), Err(Error::Network(_))));
        assert_eq!(runner.argvs().len(), 1);
    }

    #[test]
    fn validation_and_scan_escaping() {
        assert_eq!(split_fields(r"Name\:with\\slash:70:WPA2").unwrap(), vec!["Name:with\\slash", "70", "WPA2"]);
        assert!(split_fields("bad\\").is_err());
        for (key, value) in [("ssid", json!("bad\nname")), ("password", json!("short")), ("save", json!(1)), ("mode", json!("ap")), ("ssid", json!("x".repeat(33))), ("password", json!("pässwordlong"))] {
            let mut b = body();
            b[key] = value;
            assert!(validate(&b).is_err(), "{key}");
        }
        let mut open = body();
        open.as_object_mut().unwrap().remove("password");
        open.as_object_mut().unwrap().remove("save");
        validate(&open).unwrap();
        let tmp = TempDir::new();
        let runner = Arc::new(FakeRunner::with(|_, _| ok("Home\\:Net:70:WPA2\n:40:WPA2\nOther:x:WPA\nCafe:55:\n")));
        let station = Station::new("wlan0", tmp.path(), runner.clone(), None).unwrap();
        assert_eq!(station.scan().unwrap(), json!({"networks": [
            {"ssid": "Home:Net", "signal_percent": 70, "rssi": null, "security": "WPA2"},
            {"ssid": "Cafe", "signal_percent": 55, "rssi": null, "security": ""},
        ]}));
        assert_eq!(runner.argvs()[0].join(" "), "nmcli -t --escape yes -f SSID,SIGNAL,SECURITY device wifi list ifname wlan0 --rescan yes");
    }

    #[test]
    fn startup_recovers_only_owned_station() {
        let tmp = TempDir::new();
        let mut station = Station::new("wlan0", tmp.path(), Arc::new(FakeRunner::new()), None).unwrap();
        let (uuid, name) = (station.uuid.clone(), station.connection_name.clone());
        let runner = Arc::new(FakeRunner::with(move |argv, _| ok(if argv.iter().any(|a| a == "GENERAL.CON-UUID") { &uuid } else { &name })));
        station.set_runner(runner.clone());
        station.prepare_startup(true).unwrap();
        let calls = runner.argvs();
        assert!(calls.contains(&["nmcli", "connection", "down", "uuid", &station.uuid].iter().map(|s| s.to_string()).collect()));
        assert_eq!(calls.last().unwrap().join(" "), "nmcli device set wlan0 managed no");
        station.set_runner(Arc::new(FakeRunner::with(|_, _| ok("foreign"))));
        assert!(matches!(station.prepare_startup(true), Err(Error::Network(_))));
    }

    #[test]
    fn reconnect_and_private_directories() {
        let tmp = TempDir::new();
        let (mut station, _) = adapter(tmp.path(), false, false);
        assert_eq!(station.reconnect().unwrap_err().code(), "wifi_profile_required");
        station.connect(&body()).unwrap();
        let (mut again, _) = adapter(tmp.path(), false, false);
        assert!(again.has_profile(), "saved profile restored from the vault");
        assert_eq!(again.reconnect().unwrap(), "192.0.2.1");
        use std::os::unix::fs::PermissionsExt;
        let shared = tmp.path().join("nm");
        std::fs::create_dir(&shared).unwrap();
        std::fs::set_permissions(&shared, std::fs::Permissions::from_mode(0o755)).unwrap();
        Station::new("wlan0", &tmp.path().join("state"), Arc::new(FakeRunner::new()), Some(&shared)).unwrap();
        std::fs::set_permissions(&shared, std::fs::Permissions::from_mode(0o775)).unwrap();
        assert_eq!(Station::new("wlan0", &tmp.path().join("state"), Arc::new(FakeRunner::new()), Some(&shared)).err().unwrap().code(), "unsafe_networkmanager_profile_directory");
        assert!(Station::new("bad name", tmp.path(), Arc::new(FakeRunner::new()), None).is_err());
    }

    /// A real NetworkManager daemon loads the generated keyfile from its
    /// runtime directory (tools/rust-kernel-tests.sh). Device commands are faked and the
    /// activation is refused: no Wi-Fi device, no radio.
    #[test]
    #[ignore = "needs the Docker test image (dbus, NetworkManager)"]
    fn kernel_networkmanager_loads_station_profile() {
        use crate::runner::{Runner, SystemRunner};
        use std::process::{Command, Stdio};
        use std::sync::atomic::{AtomicBool, Ordering};
        use std::time::{Duration, Instant};
        assert!(Path::new("/.dockerenv").exists(), "never run on a host or target");
        std::fs::create_dir_all("/run/dbus").unwrap();
        // Ignore failure: the bus may already run from an earlier test.
        let _ = Command::new("dbus-daemon").arg("--system").stdout(Stdio::null()).stderr(Stdio::null()).status();
        let mut manager = Command::new("NetworkManager").arg("--no-daemon").stdout(Stdio::null()).stderr(Stdio::null()).spawn().unwrap();
        let real = Arc::new(SystemRunner::new().unwrap());
        let deadline = Instant::now() + Duration::from_secs(30);
        while real.optional(&["nmcli", "-t", "general", "status"]).map(|o| o.code).unwrap_or(1) != 0 {
            assert!(Instant::now() < deadline, "NetworkManager did not start");
            std::thread::sleep(Duration::from_millis(200));
        }
        let profiles = Path::new("/run/NetworkManager/system-connections");
        std::fs::create_dir_all(profiles).unwrap();
        let tmp = TempDir::new();
        let checked = Arc::new(AtomicBool::new(false));
        let (seen, nm) = (checked.clone(), real.clone());
        let runner = Arc::new(FakeRunner::with(move |argv, _| {
            let args: Vec<&str> = argv.iter().map(String::as_str).collect();
            let real_daemon = args.windows(2).any(|w| w == ["connection", "show"] || w == ["connection", "load"]);
            match () {
                // Real daemon: ownership checks and keyfile loading.
                _ if real_daemon => Some(nm.optional(&args).unwrap()),
                _ if args.contains(&"up") => {
                    let uuid = args[args.iter().position(|a| *a == "uuid").unwrap() + 1];
                    let loaded = nm.run(&["nmcli", "-g", "connection.uuid,ipv4.never-default,802-11-wireless-security.psk-flags", "connection", "show", "uuid", uuid]).unwrap().stdout;
                    let lines: Vec<&str> = loaded.lines().collect();
                    assert_eq!(lines.first(), Some(&uuid), "{loaded}");
                    assert_eq!(lines.get(1), Some(&"yes"), "{loaded}");
                    assert!(lines.get(2).is_some_and(|f| f.starts_with('2')), "{loaded}");
                    seen.store(true, Ordering::SeqCst);
                    exit(1)
                }
                _ => None,
            }
        }));
        let mut station = Station::new("wlan0", &tmp.path().join("state"), runner, Some(profiles)).unwrap();
        let body = json!({"mode": "sta", "ssid": "Phoenix Test", "password": "test-only-passphrase", "save": false});
        let result = station.connect(&body);
        let keyfile = std::fs::read_to_string(profiles.join(format!("{}.nmconnection", station.connection_name))).unwrap();
        let _ = real.optional(&["nmcli", "connection", "delete", "uuid", &station.uuid]);
        let _ = manager.kill();
        let _ = manager.wait();
        assert!(result.is_err(), "activation must be refused without a radio");
        assert!(checked.load(Ordering::SeqCst), "profile was not loaded by NetworkManager");
        assert!(keyfile.contains("never-default=true") && keyfile.contains("psk-flags=2"), "{keyfile}");
        assert!(!keyfile.contains("test-only-passphrase"));
        assert!(!tmp.path().join("state/password").exists(), "secret file removed");
    }
}
