//! Read-only inventory (preflight.py). Tool presence is never a claim of
//! working networking.
use crate::json::{self, json, Map, Value};
use crate::runner::run_with_timeout;
use std::ffi::CStr;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::time::Duration;

const TOOLS: [&str; 11] = ["ip", "nft", "wg", "iw", "hostapd", "dnsmasq", "systemctl", "curl", "conntrack", "nmcli", "openssl"];

/// shutil.which: first executable regular file named `name` on PATH.
pub fn which(name: &str) -> Option<PathBuf> {
    let path = std::env::var_os("PATH").unwrap_or_else(|| ":/bin:/usr/bin".into());
    std::env::split_paths(&path)
        .map(|dir| dir.join(name))
        .find(|candidate| std::fs::metadata(candidate).map(|m| m.is_file() && m.permissions().mode() & 0o111 != 0).unwrap_or(false))
}

fn read_text(path: &Path) -> Value {
    match std::fs::read(path).ok().and_then(|data| String::from_utf8(data).ok()) {
        Some(text) => Value::String(crate::py::strip(&text).replace('\0', "")),
        None => Value::Null,
    }
}

fn uname() -> (String, String, String) {
    let mut name: libc::utsname = unsafe { std::mem::zeroed() };
    if unsafe { libc::uname(&mut name) } != 0 {
        return (String::new(), String::new(), String::new());
    }
    let field = |raw: &[libc::c_char]| unsafe { CStr::from_ptr(raw.as_ptr()) }.to_string_lossy().into_owned();
    (field(&name.sysname), field(&name.release), field(&name.machine))
}

/// `run` returns stdout of a successful command, or None on any failure.
pub fn inspect_with(system: &str, root: &Path, which: &dyn Fn(&str) -> bool, run: &dyn Fn(&[&str]) -> Option<String>) -> Value {
    let (_, kernel, architecture) = uname();
    let mut report = Map::new();
    for (key, value) in [
        ("system", json!(system)),
        ("kernel", json!(kernel)),
        ("architecture", json!(architecture)),
        ("read_only", json!(true)),
        ("gateway_verified", json!(false)),
        ("wireguard_verified", json!(false)),
        ("usb_network_verified", json!(false)),
    ] {
        report.insert(key.into(), value);
    }
    if system != "Linux" {
        report.insert("supported_host".into(), json!(false));
        report.insert("blockers".into(), json!(["linux_required"]));
        return Value::Object(report);
    }
    report.insert("supported_host".into(), json!(true));
    report.insert("board_model".into(), read_text(&root.join("proc/device-tree/model")));
    report.insert("os_release".into(), read_text(&root.join("etc/os-release")));
    let tools: Map<String, Value> = TOOLS.iter().map(|t| (t.to_string(), Value::Bool(which(t)))).collect();
    let mut interfaces = Vec::new();
    let mut inventory_failed = false;
    if tools["ip"] == Value::Bool(true) {
        let parsed = run(&["ip", "-j", "link", "show"]).and_then(|out| json::parse(out.as_bytes()).ok());
        match parsed.as_ref().and_then(Value::as_array) {
            Some(links) => {
                for link in links {
                    match link.get("ifname") {
                        Some(name) => interfaces.push(json!({
                            "name": name, "state": link.get("operstate").cloned().unwrap_or(Value::Null),
                            "mtu": link.get("mtu").cloned().unwrap_or(Value::Null),
                            "kind": link.get("linkinfo").and_then(|l| l.get("info_kind")).cloned().unwrap_or(Value::Null)})),
                        None => {
                            inventory_failed = true;
                            break;
                        }
                    }
                }
            }
            None => inventory_failed = true,
        }
    }
    let mut blockers: Vec<Value> = tools.iter().filter(|(_, found)| **found == Value::Bool(false)).map(|(name, _)| json!(format!("missing_tool:{name}"))).collect();
    report.insert("tools".into(), Value::Object(tools));
    report.insert("interfaces".into(), Value::Array(interfaces));
    if inventory_failed {
        report.insert("interface_inventory_error".into(), json!(true));
        blockers.push(json!("interface_inventory_failed"));
    }
    let mut controllers: Vec<String> = std::fs::read_dir(root.join("sys/class/udc"))
        .map(|entries| entries.filter_map(|e| e.ok()).map(|e| e.file_name().to_string_lossy().into_owned()).collect())
        .unwrap_or_default();
    controllers.sort();
    report.insert("usb_device_controllers".into(), json!(controllers));
    report.insert("ipv4_forwarding".into(), read_text(&root.join("proc/sys/net/ipv4/ip_forward")));
    report.insert("blockers".into(), Value::Array(blockers));
    Value::Object(report)
}

pub fn inspect() -> Value {
    let system = uname().0;
    let run = |argv: &[&str]| match run_with_timeout(argv, None, Duration::from_secs(5)) {
        Ok(Some((0, out))) => String::from_utf8(out).ok(),
        _ => None,
    };
    inspect_with(&system, Path::new("/"), &|name| which(name).is_some(), &run)
}

/// `phoenix preflight`: prints JSON, exit 2 when blockers exist.
pub fn main(args: &[String]) -> i32 {
    if !args.is_empty() {
        return crate::args::usage_error("usage: phoenix preflight");
    }
    let report = inspect();
    println!("{}", serde_json::to_string_pretty(&report).unwrap_or_default());
    if report["blockers"].as_array().map(|b| b.is_empty()).unwrap_or(false) {
        0
    } else {
        2
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fsutil::testdir::TempDir;

    #[test]
    fn non_linux_never_runs_commands() {
        let report = inspect_with("Darwin", Path::new("/"), &|_| panic!("which on host"), &|_| panic!("Linux command attempted on host"));
        assert_eq!(report["blockers"], json!(["linux_required"]));
        assert_eq!(report["supported_host"], false);
    }

    #[test]
    fn inventory_does_not_claim_function_or_leak_addresses() {
        let dir = TempDir::new();
        std::fs::create_dir_all(dir.path().join("sys/class/udc/controller")).unwrap();
        std::fs::create_dir_all(dir.path().join("proc/device-tree")).unwrap();
        std::fs::write(dir.path().join("proc/device-tree/model"), "Radxa ROCK 4C+\0").unwrap();
        let run = |argv: &[&str]| {
            assert_eq!(argv, ["ip", "-j", "link", "show"]);
            Some(r#"[{"ifname":"end0","operstate":"UP","mtu":1500,"address":"private"}]"#.to_string())
        };
        let report = inspect_with("Linux", dir.path(), &|_| true, &run);
        assert_eq!(report["blockers"], json!([]));
        assert_eq!(report["wireguard_verified"], false);
        assert_eq!(report["usb_network_verified"], false);
        assert_eq!(report["interfaces"], json!([{"name": "end0", "state": "UP", "mtu": 1500, "kind": null}]));
        assert_eq!(report["usb_device_controllers"], json!(["controller"]));
        assert_eq!(report["board_model"], "Radxa ROCK 4C+");
        assert_eq!(report["os_release"], Value::Null);
    }

    #[test]
    fn ip_failure_and_missing_tools_are_blockers() {
        let dir = TempDir::new();
        let report = inspect_with("Linux", dir.path(), &|name| name != "wg", &|_| None);
        let blockers = report["blockers"].as_array().unwrap();
        assert!(blockers.contains(&json!("interface_inventory_failed")));
        assert!(blockers.contains(&json!("missing_tool:wg")));
        assert_eq!(report["interface_inventory_error"], true);
        assert!(which("sh").is_some());
    }
}
