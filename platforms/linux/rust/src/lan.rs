//! Optional AP (hostapd + dnsmasq) and USB LAN (dnsmasq) lifecycles
//! (lan.py + usb_lan.py). Owns only the explicitly assigned interface and
//! the daemons it started; NetworkManager ownership is relinquished outside.
//! Also hosts the small child-process abstraction shared with speedcheck.
use crate::error::{Error, Result};
use crate::firewall::interface;
use crate::json::Value;
use crate::runner::SharedRunner;
use crate::{access_point, fsutil, ipv4, json, py};
use std::io::Read;
use std::os::unix::process::ExitStatusExt;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Arc;
use std::time::{Duration, Instant};

/// A child process as the Python code used `subprocess.Popen`.
pub trait Proc: Send {
    /// Exit code once finished (negative signal number when killed, like
    /// Python's returncode); None while running.
    fn poll(&mut self) -> Option<i32>;
    /// SIGTERM if still running.
    fn terminate(&mut self);
    /// SIGKILL if still running.
    fn kill(&mut self);
    /// Wait up to `seconds`; the exit code, or None on timeout.
    fn wait_timeout(&mut self, seconds: f64) -> Option<i32> {
        let deadline = Instant::now() + Duration::from_secs_f64(seconds.max(0.0));
        loop {
            if let Some(code) = self.poll() {
                return Some(code);
            }
            if Instant::now() >= deadline {
                return None;
            }
            std::thread::sleep(Duration::from_millis(10));
        }
    }
    /// Captured stdout of a finished process (spawned with capture), at most `limit` bytes.
    fn stdout(&mut self, limit: usize) -> Vec<u8> {
        let _ = limit;
        Vec::new()
    }
}

/// `(argv, capture_stdout)` -> process. stdin/stderr are always /dev/null.
pub type Spawn = Arc<dyn Fn(&[String], bool) -> std::io::Result<Box<dyn Proc>> + Send + Sync>;
pub type Which = Arc<dyn Fn(&str) -> bool + Send + Sync>;
pub type Wait = Arc<dyn Fn(f64) + Send + Sync>;
pub type Binding = Arc<dyn Fn(&str) -> bool + Send + Sync>;

struct OsProc {
    child: Child,
    code: Option<i32>,
}

impl Proc for OsProc {
    fn poll(&mut self) -> Option<i32> {
        if self.code.is_none() {
            if let Ok(Some(status)) = self.child.try_wait() {
                self.code = Some(status.code().unwrap_or_else(|| -status.signal().unwrap_or(0)));
            }
        }
        self.code
    }
    fn terminate(&mut self) {
        // Never signal a reaped PID: it may already belong to another process.
        if self.poll().is_none() {
            unsafe {
                libc::kill(self.child.id() as libc::pid_t, libc::SIGTERM);
            }
        }
    }
    fn kill(&mut self) {
        if self.poll().is_none() {
            let _ = self.child.kill();
        }
    }
    fn stdout(&mut self, limit: usize) -> Vec<u8> {
        let mut out = Vec::new();
        if let Some(stdout) = self.child.stdout.as_mut() {
            let _ = stdout.take(limit as u64).read_to_end(&mut out);
        }
        out
    }
}

/// Production spawner: PATH lookup like Popen, no inherited descriptors
/// (Rust sets CLOEXEC), stderr discarded.
pub fn os_spawn(argv: &[String], capture: bool) -> std::io::Result<Box<dyn Proc>> {
    let child = Command::new(&argv[0])
        .args(&argv[1..])
        .stdin(Stdio::null())
        .stdout(if capture { Stdio::piped() } else { Stdio::null() })
        .stderr(Stdio::null())
        .spawn()?;
    Ok(Box::new(OsProc { child, code: None }))
}

/// `shutil.which`: first executable regular file named `command` on PATH.
pub fn which(command: &str) -> Option<String> {
    use std::os::unix::fs::PermissionsExt;
    if command.contains('/') {
        return None;
    }
    let path = std::env::var("PATH").unwrap_or_else(|_| "/usr/local/bin:/usr/bin:/bin".into());
    path.split(':').filter(|d| !d.is_empty()).map(|d| Path::new(d).join(command)).find_map(|candidate| {
        let meta = std::fs::metadata(&candidate).ok()?;
        (meta.is_file() && meta.permissions().mode() & 0o111 != 0).then(|| candidate.to_string_lossy().into_owned())
    })
}

/// Stop with SIGTERM, then SIGKILL after 3 s (lan.py stop()).
pub fn stop_process(process: &mut dyn Proc) {
    if process.poll().is_none() {
        process.terminate();
        if process.wait_timeout(3.0).is_none() {
            process.kill();
            process.wait_timeout(3.0);
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    AccessPoint,
    Usb,
}

pub struct Lan {
    pub kind: Kind,
    pub name: String,
    pub ssid: String,
    pub password: String,
    pub country: String,
    pub dns: String,
    pub default_dns: String,
    pub active: bool,
    directory: PathBuf,
    run: SharedRunner,
    processes: Vec<Box<dyn Proc>>,
    added_address: bool,
    spawn: Spawn,
    which: Which,
    wait: Wait,
    binding: Binding,
}

fn network_error(code: &str) -> Error {
    Error::Network(code.to_string())
}

impl Lan {
    fn base(kind: Kind, name: String, directory: &Path, runner: SharedRunner) -> Lan {
        Lan {
            kind,
            name,
            ssid: String::new(),
            password: String::new(),
            country: String::new(),
            dns: String::new(),
            default_dns: String::new(),
            active: false,
            directory: directory.to_path_buf(),
            run: runner,
            processes: Vec::new(),
            added_address: false,
            spawn: Arc::new(os_spawn),
            which: Arc::new(|c| which(c).is_some()),
            wait: Arc::new(|s| std::thread::sleep(Duration::from_secs_f64(s))),
            binding: Arc::new(crate::usb_gadget::owned_binding),
        }
    }

    pub fn access_point(name: &str, ssid: &str, password: &str, country: &str, dns: &str, directory: &Path, runner: SharedRunner) -> Result<Lan> {
        let name = interface(name)?;
        access_point::render(&name, ssid, password, country, dns)?;
        let mut lan = Lan::base(Kind::AccessPoint, name, directory, runner);
        lan.ssid = ssid.to_string();
        lan.password = password.to_string();
        lan.country = country.to_string();
        lan.dns = dns.to_string();
        lan.default_dns = dns.to_string();
        Ok(lan)
    }

    pub fn usb(name: &str, dns: &str, directory: &Path, runner: SharedRunner) -> Result<Lan> {
        let name = interface(name)?;
        let dns = ipv4::address(dns)?.to_string();
        let mut lan = Lan::base(Kind::Usb, name, directory, runner);
        lan.dns = dns.clone();
        lan.default_dns = dns;
        Ok(lan)
    }

    /// Test hook: process spawner, tool lookup and the post-spawn delay.
    pub fn with_hooks(mut self, spawn: Spawn, which: Which, wait: Wait) -> Self {
        self.spawn = spawn;
        self.which = which;
        self.wait = wait;
        self
    }

    /// Test hook: USB gadget binding check (default usb_gadget::owned_binding).
    pub fn with_binding(mut self, binding: Binding) -> Self {
        self.binding = binding;
        self
    }

    pub fn set_binding(&mut self, binding: Binding) {
        self.binding = binding;
    }

    pub fn directory(&self) -> &Path {
        &self.directory
    }

    pub fn process_count(&self) -> usize {
        self.processes.len()
    }

    fn address(&self) -> &'static str {
        match self.kind {
            Kind::AccessPoint => "192.168.9.1/24",
            Kind::Usb => "192.168.7.1/24",
        }
    }

    fn owned_by_networkmanager(&self, code: &str) -> Result<()> {
        if (self.which)("nmcli") {
            let result = self.run.run(&["nmcli", "-g", "GENERAL.NM-MANAGED", "device", "show", &self.name])?;
            if py::strip(&result.stdout).to_lowercase() != "no" {
                return Err(network_error(code));
            }
        }
        Ok(())
    }

    /// IPv4 addresses on the interface; any other than ours is a conflict.
    fn ipv4_addresses(&self, local: &str, code: &str) -> Result<bool> {
        let addresses = json::parse(self.run.run(&["ip", "-j", "address", "show", "dev", &self.name])?.stdout.as_bytes())?;
        let mut found = false;
        for entry in addresses.as_array().map(Vec::as_slice).unwrap_or(&[]) {
            for a in entry.get("addr_info").and_then(Value::as_array).map(Vec::as_slice).unwrap_or(&[]) {
                if a.get("family").and_then(Value::as_str) != Some("inet") {
                    continue;
                }
                found = true;
                if a.get("local").and_then(Value::as_str) != Some(local) || a.get("prefixlen").and_then(Value::as_i64) != Some(24) {
                    return Err(network_error(code));
                }
            }
        }
        Ok(found)
    }

    fn check(&self) -> Result<bool> {
        match self.kind {
            Kind::AccessPoint => {
                for command in ["ip", "iw", "hostapd", "dnsmasq"] {
                    if !(self.which)(command) {
                        return Err(network_error(&format!("ap_missing_tool:{command}")));
                    }
                }
                self.owned_by_networkmanager("ap_interface_owned_by_networkmanager")?;
                let info = self.run.run(&["iw", "dev", &self.name, "info"])?.stdout;
                let phy = py::splitlines(&info)
                    .into_iter()
                    .find_map(|line| {
                        let rest = py::strip(line).strip_prefix("wiphy ")?;
                        py::is_digits(rest).then(|| rest.to_string())
                    })
                    .ok_or_else(|| network_error("ap_wiphy_not_found"))?;
                let phy_info = self.run.run(&["iw", "phy", &format!("phy{phy}"), "info"])?.stdout;
                if !py::splitlines(&phy_info).into_iter().any(|line| py::strip(line) == "* AP") {
                    return Err(network_error("ap_mode_not_supported"));
                }
                self.ipv4_addresses("192.168.9.1", "ap_interface_has_existing_address")
            }
            Kind::Usb => {
                if !(self.binding)(&self.name) {
                    return Err(network_error("usb_phoenix_gadget_not_bound"));
                }
                for command in ["ip", "dnsmasq"] {
                    if !(self.which)(command) {
                        return Err(network_error(&format!("usb_missing_tool:{command}")));
                    }
                }
                self.owned_by_networkmanager("usb_interface_owned_by_networkmanager")?;
                let existing = self.ipv4_addresses("192.168.7.1", "usb_interface_has_existing_address")?;
                let routes = json::parse(self.run.run(&["ip", "-j", "-4", "route", "show", "table", "all"])?.stdout.as_bytes())?;
                let usb = ipv4::network("192.168.7.0/24")?;
                for route in routes.as_array().map(Vec::as_slice).unwrap_or(&[]) {
                    let destination = match route.get("dst") {
                        None => "default",
                        Some(Value::String(s)) => s.as_str(),
                        Some(_) => return Err(Error::Invalid("invalid_route".into())),
                    };
                    if destination == "default" || destination == "0.0.0.0/0" || route.get("dev").and_then(Value::as_str) == Some(self.name.as_str()) {
                        continue;
                    }
                    if ipv4::network(destination)?.overlaps(&usb) {
                        return Err(network_error("usb_subnet_conflicts_with_route"));
                    }
                }
                Ok(existing)
            }
        }
    }

    fn render_configs(&self, dns: &str) -> Result<Vec<(&'static str, String)>> {
        match self.kind {
            Kind::AccessPoint => {
                let mut configs = access_point::render(&self.name, &self.ssid, &self.password, &self.country, dns)?;
                configs[0].1 += &format!("ignore_broadcast_ssid=0\nctrl_interface={}\n", self.directory.join("control").display());
                Ok(configs)
            }
            Kind::Usb => {
                let dns = ipv4::address(dns)?;
                Ok(vec![(
                    "dnsmasq.conf",
                    format!(
                        "port=0\ninterface={}\nbind-interfaces\ndhcp-range=192.168.7.20,192.168.7.200,255.255.255.0,1h\ndhcp-option=3,192.168.7.1\ndhcp-option=6,{dns}\ndhcp-authoritative\n",
                        self.name
                    ),
                )])
            }
        }
    }

    fn dnsmasq_command(&self) -> Vec<String> {
        vec!["dnsmasq".into(), "--no-daemon".into(), format!("--conf-file={}", self.directory.join("dnsmasq.conf").display())]
    }

    fn daemon_commands(&self) -> Vec<Vec<String>> {
        match self.kind {
            Kind::AccessPoint => vec![vec!["hostapd".into(), self.directory.join("hostapd.conf").display().to_string()], self.dnsmasq_command()],
            Kind::Usb => vec![self.dnsmasq_command()],
        }
    }

    fn write_configs(&self, dns: &str) -> Result<()> {
        fsutil::ensure_dir(&self.directory, 0o700, 0o077, "ap_state_directory_not_private")?;
        let mut configs = self.render_configs(dns)?;
        for (name, data) in configs.iter_mut() {
            if *name == "dnsmasq.conf" {
                *data += &format!("dhcp-leasefile={}\n", self.directory.join("leases").display());
            }
        }
        for (name, data) in &configs {
            fsutil::write_private(&self.directory.join(name), data.as_bytes())?;
        }
        let test = format!("--conf-file={}", self.directory.join("dnsmasq.conf").display());
        self.run.run(&["dnsmasq", "--test", &test])?;
        Ok(())
    }

    fn spawn_daemon(&mut self, argv: &[String]) -> Result<()> {
        let process = (self.spawn)(argv, false)?;
        self.processes.push(process);
        (self.wait)(0.25);
        if self.processes.last_mut().map(|p| p.poll().is_some()).unwrap_or(true) {
            return Err(network_error("ap_daemon_start_failed"));
        }
        Ok(())
    }

    pub fn start(&mut self) -> Result<()> {
        if self.active {
            return Err(network_error("ap_already_active"));
        }
        let existing = self.check()?;
        self.write_configs(&self.dns.clone())?;
        let result = (|| -> Result<()> {
            if !existing {
                self.run.run(&["ip", "address", "add", self.address(), "dev", &self.name])?;
                self.added_address = true;
            }
            self.run.run(&["ip", "link", "set", "dev", &self.name, "up"])?;
            for command in self.daemon_commands() {
                self.spawn_daemon(&command)?;
            }
            Ok(())
        })();
        match result {
            Ok(()) => {
                self.active = true;
                Ok(())
            }
            Err(error) => {
                self.stop();
                Err(error)
            }
        }
    }

    /// Never fails: terminates daemons, removes the address it added.
    pub fn stop(&mut self) {
        for process in self.processes.iter_mut().rev() {
            stop_process(process.as_mut());
        }
        self.processes.clear();
        if self.added_address {
            let _ = self.run.optional(&["ip", "address", "del", self.address(), "dev", &self.name]);
            self.added_address = false;
        }
        self.active = false;
    }

    pub fn set_dns(&mut self, dns: &str) -> Result<()> {
        if dns == self.dns {
            return Ok(());
        }
        self.write_configs(dns)?;
        if self.active {
            if let Some(mut process) = self.processes.pop() {
                stop_process(process.as_mut());
            }
            let command = self.dnsmasq_command();
            self.spawn_daemon(&command)?;
        }
        self.dns = dns.to_string();
        Ok(())
    }

    /// (state, clients) from hostapd_cli; ("DISABLED", Some(0)) when inactive.
    pub fn radio_status(&self) -> (String, Option<i64>) {
        if !self.active {
            return ("DISABLED".into(), Some(0));
        }
        let unknown = ("UNKNOWN".to_string(), None);
        if !(self.which)("hostapd_cli") {
            return unknown;
        }
        let control = self.directory.join("control").display().to_string();
        let Ok(output) = self.run.run(&["hostapd_cli", "-p", &control, "-i", &self.name, "status"]) else {
            return unknown;
        };
        let mut state = None;
        let mut clients = None;
        for line in py::splitlines(&output.stdout) {
            if let Some((key, value)) = line.split_once('=') {
                match key {
                    "state" => state = Some(value.to_string()),
                    "num_sta[0]" => clients = Some(value.to_string()),
                    _ => {}
                }
            }
        }
        let clients = match clients {
            None => None,
            Some(text) => match py::strip(&text).parse::<i64>() {
                Ok(n) => Some(n),
                Err(_) => return unknown,
            },
        };
        (state.unwrap_or_else(|| "UNKNOWN".into()), clients)
    }

    pub fn healthy(&mut self) -> bool {
        if self.kind == Kind::Usb && !(self.binding)(&self.name) {
            return false;
        }
        let expected = self.daemon_commands().len();
        self.active && self.processes.len() == expected && self.processes.iter_mut().all(|p| p.poll().is_none())
    }
}

#[cfg(test)]
pub mod tests {
    use super::*;
    use crate::fsutil::testdir::TempDir;
    use crate::runner::{ok, FakeRunner, Output};
    use std::os::unix::fs::MetadataExt;
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::Mutex;

    /// Fake daemon: running until terminated.
    pub struct FakeProc {
        pub stopped: Arc<AtomicBool>,
    }

    impl Proc for FakeProc {
        fn poll(&mut self) -> Option<i32> {
            self.stopped.load(Ordering::SeqCst).then_some(0)
        }
        fn terminate(&mut self) {
            self.stopped.store(true, Ordering::SeqCst);
        }
        fn kill(&mut self) {
            self.stopped.store(true, Ordering::SeqCst);
        }
    }

    pub struct Fixture {
        pub runner: Arc<FakeRunner>,
        pub spawned: Arc<Mutex<Vec<(Vec<String>, Arc<AtomicBool>)>>>,
    }

    impl Fixture {
        pub fn commands(&self) -> Vec<Vec<String>> {
            self.runner.argvs()
        }
        pub fn all_stopped(&self) -> bool {
            self.spawned.lock().unwrap().iter().all(|(_, s)| s.load(Ordering::SeqCst))
        }
    }

    fn hooks(fail_dnsmasq: bool, spawned: Arc<Mutex<Vec<(Vec<String>, Arc<AtomicBool>)>>>) -> (Spawn, Which, Wait) {
        let spawn: Spawn = Arc::new(move |argv: &[String], _| {
            if fail_dnsmasq && argv[0] == "dnsmasq" {
                return Err(std::io::Error::other("startup_failed"));
            }
            let stopped = Arc::new(AtomicBool::new(false));
            spawned.lock().unwrap().push((argv.to_vec(), stopped.clone()));
            Ok(Box::new(FakeProc { stopped }) as Box<dyn Proc>)
        });
        (spawn, Arc::new(|_| true), Arc::new(|_| {}))
    }

    /// test_lan.LanTests.manager equivalent.
    pub fn manager(directory: &Path, managed: &'static str, addresses: &'static str, fail_dns: bool) -> (Lan, Fixture) {
        let runner = Arc::new(FakeRunner::with(move |argv, _| {
            let mut out = if argv[0] == "nmcli" { managed } else { "" };
            if argv[..3] == ["iw", "dev", "wlan0"] {
                out = "Interface wlan0\n wiphy 0\n";
            }
            if argv[..3] == ["iw", "phy", "phy0"] {
                out = "Supported interface modes:\n * managed\n * AP\n";
            }
            if argv.len() >= 3 && argv[..3] == ["ip", "-j", "address"] {
                out = addresses;
            }
            ok(out)
        }));
        let spawned = Arc::new(Mutex::new(Vec::new()));
        let (spawn, which, wait) = hooks(fail_dns, spawned.clone());
        let lan = Lan::access_point("wlan0", "Phoenix-Test", "test-password-only", "IT", "1.1.1.1", directory, runner.clone())
            .unwrap()
            .with_hooks(spawn, which, wait);
        (lan, Fixture { runner, spawned })
    }

    #[test]
    fn ownership_conflict_has_no_mutations() {
        let tmp = TempDir::new();
        let (mut ap, fx) = manager(tmp.path(), "yes", "[]", false);
        assert!(matches!(ap.start(), Err(Error::Network(_))));
        assert_eq!(fx.commands().len(), 1);
        assert_eq!(std::fs::read_dir(tmp.path()).unwrap().count(), 0);
    }

    #[test]
    fn existing_address_not_overwritten() {
        let tmp = TempDir::new();
        let (mut ap, fx) = manager(tmp.path(), "no", r#"[{"addr_info":[{"family":"inet","local":"10.0.0.2","prefixlen":24}]}]"#, false);
        assert!(matches!(ap.start(), Err(Error::Network(_))));
        assert!(!fx.commands().iter().any(|c| c.iter().any(|a| a == "add")));
    }

    #[test]
    fn owned_processes_stop_and_secrets_not_in_argv() {
        let tmp = TempDir::new();
        let (mut ap, fx) = manager(tmp.path(), "no", "[]", false);
        ap.start().unwrap();
        assert!(ap.healthy());
        assert_eq!(std::fs::metadata(tmp.path().join("hostapd.conf")).unwrap().mode() & 0o777, 0o600);
        let hostapd = std::fs::read_to_string(tmp.path().join("hostapd.conf")).unwrap();
        assert!(hostapd.ends_with(&format!("ignore_broadcast_ssid=0\nctrl_interface={}/control\n", tmp.path().display())));
        let dnsmasq = std::fs::read_to_string(tmp.path().join("dnsmasq.conf")).unwrap();
        assert!(dnsmasq.ends_with(&format!("dhcp-authoritative\ndhcp-leasefile={}/leases\n", tmp.path().display())));
        assert!(!format!("{:?}", fx.commands()).contains("test-password-only"));
        let spawned: Vec<Vec<String>> = fx.spawned.lock().unwrap().iter().map(|(a, _)| a.clone()).collect();
        assert_eq!(spawned[0], vec!["hostapd".to_string(), format!("{}/hostapd.conf", tmp.path().display())]);
        assert_eq!(spawned[1][..2], ["dnsmasq", "--no-daemon"]);
        ap.stop();
        assert!(fx.all_stopped());
        assert!(fx.commands().iter().any(|c| c[..3] == ["ip", "address", "del"]));
        assert!(!ap.healthy());
    }

    #[test]
    fn partial_start_rolls_back() {
        let tmp = TempDir::new();
        let (mut ap, fx) = manager(tmp.path(), "no", "[]", true);
        assert!(matches!(ap.start(), Err(Error::Io(_))));
        assert!(!ap.active);
        assert!(fx.all_stopped());
        assert_eq!(ap.process_count(), 0);
    }

    #[test]
    fn dns_change_keeps_ap_and_restarts_only_dhcp() {
        let tmp = TempDir::new();
        let (mut ap, fx) = manager(tmp.path(), "no", "[]", false);
        ap.start().unwrap();
        ap.set_dns("9.9.9.9").unwrap();
        {
            let spawned = fx.spawned.lock().unwrap();
            assert!(!spawned[0].1.load(Ordering::SeqCst), "hostapd kept");
            assert!(spawned[1].1.load(Ordering::SeqCst), "old dnsmasq stopped");
            assert_eq!(spawned.len(), 3);
        }
        assert!(ap.healthy());
        assert!(std::fs::read_to_string(tmp.path().join("dnsmasq.conf")).unwrap().contains("dhcp-option=6,9.9.9.9"));
        assert_eq!(ap.dns, "9.9.9.9");
        assert_eq!(ap.default_dns, "1.1.1.1");
        ap.stop();
    }

    #[test]
    fn radio_status_parses_hostapd_cli() {
        let tmp = TempDir::new();
        let runner = Arc::new(FakeRunner::with(|argv, _| match argv[0].as_str() {
            "hostapd_cli" => ok("state=ENABLED\nnum_sta[0]=2\n"),
            "iw" if argv[1] == "dev" => ok("wiphy 3"),
            "iw" => ok("* AP"),
            "ip" if argv[1] == "-j" => ok("[]"),
            "nmcli" => ok("no"),
            _ => Some(Output::default()),
        }));
        let spawned = Arc::new(Mutex::new(Vec::new()));
        let (spawn, which, wait) = hooks(false, spawned);
        let mut ap = Lan::access_point("wlan0", "x", "password", "IT", "1.1.1.1", tmp.path(), runner).unwrap().with_hooks(spawn, which, wait);
        assert_eq!(ap.radio_status(), ("DISABLED".to_string(), Some(0)));
        ap.start().unwrap();
        assert_eq!(ap.radio_status(), ("ENABLED".to_string(), Some(2)));
        ap.stop();
    }

    #[test]
    fn rejects_invalid_configuration_and_unprivate_directory() {
        let tmp = TempDir::new();
        let runner: SharedRunner = Arc::new(FakeRunner::new());
        assert!(Lan::access_point("wlan0", "x", "short", "IT", "1.1.1.1", tmp.path(), runner.clone()).is_err());
        assert!(Lan::access_point("bad name", "x", "password", "IT", "1.1.1.1", tmp.path(), runner.clone()).is_err());
        assert!(Lan::usb("phusb0", "1.1.1", tmp.path(), runner).is_err());
        use std::os::unix::fs::PermissionsExt;
        let open = tmp.path().join("open");
        std::fs::create_dir(&open).unwrap();
        std::fs::set_permissions(&open, std::fs::Permissions::from_mode(0o755)).unwrap();
        let (mut ap, _fx) = manager(&open, "no", "[]", false);
        assert_eq!(ap.start().unwrap_err().code(), "ap_state_directory_not_private");
    }

    // usb_lan tests (test_usb_lan.py).
    fn usb(directory: &Path, bound: bool, managed: &'static str, addresses: String, routes: String, fail: bool) -> (Lan, Fixture) {
        let runner = Arc::new(FakeRunner::with(move |argv, _| {
            let mut out = if argv[0] == "nmcli" { managed.to_string() } else { String::new() };
            if argv.len() >= 3 && argv[..3] == ["ip", "-j", "address"] {
                out = addresses.clone();
            }
            if argv.len() >= 4 && argv[..4] == ["ip", "-j", "-4", "route"] {
                out = routes.clone();
            }
            ok(&out)
        }));
        let spawned = Arc::new(Mutex::new(Vec::new()));
        let (spawn, which, wait) = hooks(fail, spawned.clone());
        let lan = Lan::usb("phusb0", "1.1.1.1", directory, runner.clone()).unwrap().with_hooks(spawn, which, wait).with_binding(Arc::new(move |_| bound));
        (lan, Fixture { runner, spawned })
    }

    #[test]
    fn usb_dhcp_subnet_dns_update_and_stop() {
        let tmp = TempDir::new();
        let (mut lan, fx) = usb(tmp.path(), true, "no", "[]".into(), "[]".into(), false);
        lan.start().unwrap();
        assert!(lan.healthy());
        let text = std::fs::read_to_string(tmp.path().join("dnsmasq.conf")).unwrap();
        assert!(text.contains("dhcp-option=3,192.168.7.1") && text.contains("port=0"));
        assert!(!tmp.path().join("hostapd.conf").exists());
        assert_eq!(fx.spawned.lock().unwrap()[0].0[0], "dnsmasq");
        lan.set_dns("9.9.9.9").unwrap();
        assert!(fx.spawned.lock().unwrap()[0].1.load(Ordering::SeqCst));
        assert!(std::fs::read_to_string(tmp.path().join("dnsmasq.conf")).unwrap().contains("dhcp-option=6,9.9.9.9"));
        lan.stop();
        assert!(!lan.healthy());
        assert!(fx.commands().contains(&["ip", "address", "del", "192.168.7.1/24", "dev", "phusb0"].iter().map(|s| s.to_string()).collect()));
    }

    #[test]
    fn usb_conflicts_block_before_address_changes() {
        let cases: Vec<(bool, &'static str, String, String)> = vec![
            (false, "no", "[]".into(), "[]".into()),
            (true, "yes", "[]".into(), "[]".into()),
            (true, "no", "[]".into(), r#"[{"dst":"192.168.7.0/24","dev":"eth0"}]"#.into()),
            (true, "no", "[]".into(), r#"[{"dst":"192.168.0.0/16","dev":"eth0"}]"#.into()),
            (true, "no", r#"[{"addr_info":[{"family":"inet","local":"10.0.0.1","prefixlen":24}]}]"#.into(), "[]".into()),
        ];
        for (bound, managed, addresses, routes) in cases {
            let tmp = TempDir::new();
            let (mut lan, fx) = usb(tmp.path(), bound, managed, addresses, routes, false);
            assert!(matches!(lan.start(), Err(Error::Network(_))));
            assert!(!fx.commands().iter().any(|c| c.len() >= 3 && c[..3] == ["ip", "address", "add"]));
        }
        let tmp = TempDir::new();
        let routes = r#"[{"dst":"default","dev":"eth0"},{"dst":"192.168.7.0/24","dev":"phusb0"},{"dst":"10.0.0.0/8","dev":"eth0"}]"#;
        let (mut lan, _fx) = usb(tmp.path(), true, "no", "[]".into(), routes.into(), false);
        lan.start().unwrap();
        lan.stop();
    }

    #[test]
    fn usb_partial_start_removes_only_added_address() {
        let tmp = TempDir::new();
        let (mut lan, fx) = usb(tmp.path(), true, "no", "[]".into(), "[]".into(), true);
        assert!(lan.start().is_err());
        assert!(!lan.active);
        assert!(fx.commands().contains(&["ip", "address", "del", "192.168.7.1/24", "dev", "phusb0"].iter().map(|s| s.to_string()).collect()));
        let tmp = TempDir::new();
        let existing = r#"[{"addr_info":[{"family":"inet","local":"192.168.7.1","prefixlen":24}]}]"#;
        let (mut lan, fx) = usb(tmp.path(), true, "no", existing.into(), "[]".into(), true);
        assert!(lan.start().is_err());
        assert!(!fx.commands().iter().any(|c| c.len() >= 3 && c[..3] == ["ip", "address", "del"]));
    }

    #[test]
    fn usb_unbinding_is_unhealthy() {
        let tmp = TempDir::new();
        let (mut lan, _fx) = usb(tmp.path(), true, "no", "[]".into(), "[]".into(), false);
        lan.start().unwrap();
        assert!(lan.healthy());
        lan.set_binding(Arc::new(|_| false));
        assert!(!lan.healthy());
        lan.stop();
    }

    /// One busybox udhcpc exchange on `interface`: (address, router, dns).
    fn udhcpc_lease(directory: &Path, interface: &str) -> (String, String, String) {
        use std::os::unix::fs::PermissionsExt;
        let lease = directory.join("lease");
        let _ = std::fs::remove_file(&lease);
        let script = directory.join("udhcpc.sh");
        std::fs::write(&script, format!("#!/bin/sh\n[ \"$1\" = bound ] && echo \"$ip $router $dns\" > {}\nexit 0\n", lease.display())).unwrap();
        std::fs::set_permissions(&script, std::fs::Permissions::from_mode(0o755)).unwrap();
        // -B: broadcast replies (no address configured on the client side yet).
        let status = Command::new("busybox")
            .args(["udhcpc", "-B", "-n", "-q", "-f", "-t", "5", "-T", "2", "-i", interface, "-s"])
            .arg(&script)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .unwrap();
        assert!(status.success(), "no DHCP lease on {interface}");
        let text = std::fs::read_to_string(&lease).unwrap();
        let fields: Vec<String> = text.split_whitespace().map(str::to_string).collect();
        assert_eq!(fields.len(), 3, "{text}");
        (fields[0].clone(), fields[1].clone(), fields[2].clone())
    }

    /// Real ip + dnsmasq on a veth pair, with a real DHCP client on the peer
    /// (tools/rust-kernel-tests.sh). USB enumeration/configfs is NOT exercised.
    #[test]
    #[ignore = "needs an isolated Docker container with NET_ADMIN"]
    fn kernel_usb_dhcp_in_isolated_container() {
        use crate::runner::SystemRunner;
        assert!(Path::new("/.dockerenv").exists(), "never run on a host or target");
        let system: SharedRunner = Arc::new(SystemRunner::new().unwrap());
        system.optional(&["ip", "link", "del", "phusbk0"]).unwrap();
        system.run(&["ip", "link", "add", "phusbk0", "type", "veth", "peer", "name", "phclientk0"]).unwrap();
        system.run(&["ip", "link", "set", "phclientk0", "address", "02:50:48:00:00:02"]).unwrap();
        system.run(&["ip", "link", "set", "phclientk0", "up"]).unwrap();
        let tmp = TempDir::new();
        // NetworkManager is installed in the image but not running: skip its check.
        let no_nmcli: Which = Arc::new(|c| c != "nmcli" && which(c).is_some());
        let mut lan = Lan::usb("phusbk0", "1.1.1.1", &tmp.path().join("usb"), system.clone())
            .unwrap()
            .with_hooks(Arc::new(os_spawn), no_nmcli, Arc::new(|s| std::thread::sleep(Duration::from_secs_f64(s))))
            .with_binding(Arc::new(|_| true));
        lan.start().unwrap();
        assert!(lan.healthy());
        let addresses = system.run(&["ip", "-4", "address", "show", "dev", "phusbk0"]).unwrap().stdout;
        assert!(addresses.contains("192.168.7.1/24"), "{addresses}");
        let (address, router, dns) = udhcpc_lease(tmp.path(), "phclientk0");
        let leased = ipv4::address(&address).unwrap();
        assert!(ipv4::network("192.168.7.0/24").unwrap().contains(u32::from(leased)), "{address}");
        assert_eq!((router.as_str(), dns.as_str()), ("192.168.7.1", "1.1.1.1"));
        lan.set_dns("9.9.9.9").unwrap();
        assert!(lan.healthy());
        let (renewed, router, dns) = udhcpc_lease(tmp.path(), "phclientk0");
        assert_eq!((renewed.as_str(), router.as_str(), dns.as_str()), (address.as_str(), "192.168.7.1", "9.9.9.9"));
        lan.stop();
        assert!(!lan.healthy());
        let addresses = system.run(&["ip", "-4", "address", "show", "dev", "phusbk0"]).unwrap().stdout;
        assert!(!addresses.contains("192.168.7.1"), "{addresses}");
        system.run(&["ip", "link", "del", "phusbk0"]).unwrap();
    }

    #[test]
    fn os_processes_terminate() {
        assert!(which("sh").is_some());
        assert!(which("definitely-not-a-tool").is_none());
        let mut process = os_spawn(&["sleep".into(), "30".into()], false).unwrap();
        assert!(process.poll().is_none());
        stop_process(process.as_mut());
        assert_eq!(process.poll(), Some(-15));
        let mut echo = os_spawn(&["sh".into(), "-c".into(), "echo 12 200".into()], true).unwrap();
        assert_eq!(echo.wait_timeout(5.0), Some(0));
        assert_eq!(echo.stdout(1024), b"12 200\n");
    }
}
