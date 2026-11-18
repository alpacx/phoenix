//! Explicit, current-boot laboratory VBUS exception; never electrical
//! certification (usb_bench.py).
use crate::json::{self, json, Map, Value};
use std::os::unix::fs::MetadataExt;
use std::path::Path;

pub fn authorized(options: &Map<String, Value>) -> bool {
    authorized_at(options, Path::new("/"))
}

/// gpio-35 must be driven low by our "phoenix-usb-source-o(ff)" consumer:
/// `^\s*gpio-35\s+\([^\n]*\|phoenix-usb-source-o(?:ff)?\s*\)\s+out lo\s*$` (multiline).
fn source_off(gpio: &str) -> bool {
    let space = crate::py::is_space;
    gpio.split('\n').any(|line| {
        let Some(rest) = line.trim_start_matches(space).strip_prefix("gpio-35") else {
            return false;
        };
        let after = rest.trim_start_matches(space);
        if after.len() == rest.len() {
            return false;
        }
        let Some(inner) = after.strip_prefix('(') else {
            return false;
        };
        inner.match_indices('|').any(|(at, _)| {
            let Some(tail) = inner[at + 1..].strip_prefix("phoenix-usb-source-o") else {
                return false;
            };
            let tail = tail.strip_prefix("ff").unwrap_or(tail).trim_start_matches(space);
            let Some(tail) = tail.strip_prefix(')') else {
                return false;
            };
            let state = tail.trim_start_matches(space);
            state.len() != tail.len() && state.strip_prefix("out lo").map(|end| end.chars().all(space)).unwrap_or(false)
        })
    })
}

/// Same check with all paths under `root` (tests).
pub fn authorized_at(options: &Map<String, Value>, root: &Path) -> bool {
    if options.get("bench_unmeasured_vbus") != Some(&Value::Bool(true)) {
        return false;
    }
    let check = || -> Option<bool> {
        let permit_path = root.join("run/phoenix-usb-bench.json");
        let info = std::fs::symlink_metadata(&permit_path).ok()?;
        if !info.file_type().is_file() || info.uid() != 0 || info.mode() & 0o077 != 0 {
            return Some(false);
        }
        let read = |relative: &str| std::fs::read_to_string(root.join(relative)).ok();
        let permit = json::parse(read("run/phoenix-usb-bench.json")?.as_bytes()).ok()?;
        let model = read("proc/device-tree/model")?;
        let boot = read("proc/sys/kernel/random/boot_id")?;
        let status = read("proc/device-tree/vbus-typec/status")?;
        let gpio = read("sys/kernel/debug/gpio")?;
        let udc = options.get("udc")?;
        let nul_newline = |c: char| c == '\0' || c == '\n';
        Some(
            model.trim_matches(nul_newline) == "Radxa ROCK 4C+"
                && status.trim_matches(nul_newline) == "disabled"
                && permit == json!({"boot_id": crate::py::strip(&boot), "udc": udc, "acknowledge_unmeasured_vbus": true})
                && udc == "fe800000.usb"
                && source_off(&gpio),
        )
    };
    check().unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fsutil::testdir::TempDir;
    use std::os::unix::fs::PermissionsExt;

    fn check(gpio: &str, boot: &str, mode: u32, uid: u32, enabled: bool) -> bool {
        let dir = TempDir::new();
        let root = dir.path();
        let write = |relative: &str, text: &str| {
            let path = root.join(relative);
            std::fs::create_dir_all(path.parent().unwrap()).unwrap();
            std::fs::write(path, text).unwrap();
        };
        write("run/phoenix-usb-bench.json", r#"{"boot_id": "boot1", "udc": "fe800000.usb", "acknowledge_unmeasured_vbus": true}"#);
        write("proc/device-tree/model", "Radxa ROCK 4C+\0");
        write("proc/sys/kernel/random/boot_id", &format!("{boot}\n"));
        write("proc/device-tree/vbus-typec/status", "disabled\0");
        write("sys/kernel/debug/gpio", gpio);
        let permit = root.join("run/phoenix-usb-bench.json");
        std::fs::set_permissions(&permit, std::fs::Permissions::from_mode(mode)).unwrap();
        std::os::unix::fs::chown(&permit, Some(uid), None).unwrap();
        let options = json!({"bench_unmeasured_vbus": enabled, "udc": "fe800000.usb"});
        authorized_at(options.as_object().unwrap(), root)
    }

    const LOW: &str = "gpio-35 ( |phoenix-usb-source-o) out lo\n";

    #[test]
    fn explicit_current_boot_only() {
        assert!(check(LOW, "boot1", 0o600, 0, true));
        assert!(check(" gpio-35  (vbus|phoenix-usb-source-off ) out lo \n", "boot1", 0o600, 0, true));
        assert!(!check(LOW, "boot1", 0o600, 0, false));
        assert!(!check(LOW, "boot2", 0o600, 0, true));
    }

    #[test]
    fn high_missing_or_other_gpio_rejected() {
        for gpio in ["gpio-35 ( |phoenix-usb-source-o) out hi\n", "gpio-35 ( |vbus-typec) out lo\n", "", "gpio-351 ( |phoenix-usb-source-o) out lo\n", "gpio-35 ( |phoenix-usb-source-o) out lo x\n"] {
            assert!(!check(gpio, "boot1", 0o600, 0, true), "{gpio}");
        }
    }

    #[test]
    fn private_root_regular_file_required() {
        assert!(!check(LOW, "boot1", 0o600, 1000, true));
        assert!(!check(LOW, "boot1", 0o644, 0, true));
        let dir = TempDir::new();
        std::fs::create_dir_all(dir.path().join("run")).unwrap();
        std::os::unix::fs::symlink("/etc/hostname", dir.path().join("run/phoenix-usb-bench.json")).unwrap();
        let options = json!({"bench_unmeasured_vbus": true, "udc": "fe800000.usb"});
        assert!(!authorized_at(options.as_object().unwrap(), dir.path()));
        assert!(!authorized_at(options.as_object().unwrap(), &dir.path().join("missing")));
    }
}
