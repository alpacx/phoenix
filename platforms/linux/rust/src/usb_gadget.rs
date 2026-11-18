//! Opt-in configfs USB Ethernet (usb_gadget.py). Never changes port role,
//! VBUS or foreign gadgets; binding the UDC is the last step.
use crate::args::{usage_error, Args};
use crate::error::{invalid, Error, Result};
use crate::firewall::interface_value;
use crate::json::{self, json, Map, Value};
use crate::{fsutil, py};
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

pub const PRODUCT: &str = "Phoenix USB Ethernet";
const CONFIGFS: &str = "/sys/kernel/config/usb_gadget";
const UDCS: &str = "/sys/class/udc";

/// Our gadget is bound and its single ncm/ecm function owns `name`.
pub fn owned_binding(name: &str) -> bool {
    owned_binding_at(name, Path::new(CONFIGFS))
}

fn read_strip(path: &Path) -> io::Result<String> {
    let data = fs::read(path)?;
    let text = String::from_utf8(data).map_err(|_| io::Error::from(io::ErrorKind::InvalidData))?;
    Ok(py::strip(&text).to_string())
}

pub fn owned_binding_at(name: &str, root: &Path) -> bool {
    let path = root.join("phoenix");
    let check = || -> io::Result<bool> {
        if read_strip(&path.join("strings/0x409/product"))? != PRODUCT || read_strip(&path.join("UDC"))?.is_empty() {
            return Ok(false);
        }
        let functions: Vec<fs::DirEntry> = fs::read_dir(path.join("functions"))?.collect::<io::Result<_>>()?;
        Ok(functions.len() == 1
            && matches!(functions[0].file_name().to_str(), Some("ncm.usb0" | "ecm.usb0"))
            && read_strip(&functions[0].path().join("ifname"))? == name)
    };
    check().unwrap_or(false)
}

fn matches_charset(value: &str, min: usize, max: usize, extra: &[u8]) -> bool {
    (min..=max).contains(&value.len()) && value.bytes().all(|b| b.is_ascii_alphanumeric() || extra.contains(&b))
}

/// Validated `usb_gadget` options plus the assigned `interface`.
pub fn settings(config: &Value) -> Result<Map<String, Value>> {
    let value = config.get("usb_gadget").cloned().unwrap_or_else(|| json!({}));
    let mut result = json::object(&value).map_err(|_| Error::Invalid("usb_not_enabled".into()))?.clone();
    if result.get("enabled") != Some(&Value::Bool(true)) {
        return invalid("usb_not_enabled");
    }
    if !matches!(result.get("function").and_then(Value::as_str), Some("ncm" | "ecm")) {
        return invalid("usb_function_must_be_ncm_or_ecm");
    }
    for key in ["vendor_id", "product_id"] {
        let ok = result.get(key).and_then(Value::as_str).and_then(|v| v.strip_prefix("0x")).map(|hex| {
            hex.len() == 4 && hex.bytes().all(|b| b.is_ascii_hexdigit()) && u16::from_str_radix(hex, 16).map(|n| n != 0).unwrap_or(false)
        });
        if ok != Some(true) {
            return invalid(&format!("invalid_usb_{key}"));
        }
    }
    for key in ["udc", "serial"] {
        if !result.get(key).and_then(Value::as_str).map(|v| matches_charset(v, 1, 64, b"_.:-")).unwrap_or(false) {
            return invalid(&format!("invalid_usb_{key}"));
        }
    }
    if matches!(result["udc"].as_str(), Some("." | "..")) {
        return invalid("invalid_usb_udc");
    }
    let interfaces = config.get("interfaces").ok_or_else(|| Error::Invalid("missing_field".into()))?;
    let name = interface_value(interfaces.get("usb").ok_or_else(|| Error::Invalid("missing_field".into()))?)?;
    let bytes = name.as_bytes();
    let pattern = bytes.len() >= 2
        && bytes[0].is_ascii_alphabetic()
        && bytes[bytes.len() - 1] == b'0'
        && bytes[1..bytes.len() - 1].iter().all(|b| b.is_ascii_alphabetic() || matches!(b, b'_' | b'.' | b'-'));
    if !pattern {
        return invalid("usb_interface_must_end_in_zero");
    }
    for role in ["uplink", "ap", "vpn"] {
        if interfaces.get(role).and_then(Value::as_str) == Some(name.as_str()) {
            return invalid("usb_interface_role_conflict");
        }
    }
    result.insert("interface".into(), Value::String(name));
    Ok(result)
}

/// Stable locally administered (dev, host) MACs derived from the serial.
pub fn macs(serial: &str) -> (String, String) {
    let digest = ring::digest::digest(&ring::digest::SHA256, serial.as_bytes());
    let format = |prefix: u8| {
        std::iter::once(prefix).chain(digest.as_ref()[..5].iter().copied()).map(|b| format!("{b:02x}")).collect::<Vec<_>>().join(":")
    };
    (format(2), format(6))
}

/// configfs operations on paths relative to the gadget directory; real
/// configfs creates/removes attribute groups itself, tests emulate that.
pub trait Configfs {
    fn mkdir(&mut self, gadget: &Path, relative: &str) -> io::Result<()>;
    fn write(&mut self, gadget: &Path, relative: &str, value: &str) -> io::Result<()>;
    fn rmdir(&mut self, gadget: &Path, relative: &str) -> io::Result<()>;
}

pub struct RealConfigfs;

fn join(gadget: &Path, relative: &str) -> PathBuf {
    if relative.is_empty() {
        gadget.to_path_buf()
    } else {
        gadget.join(relative)
    }
}

impl Configfs for RealConfigfs {
    fn mkdir(&mut self, gadget: &Path, relative: &str) -> io::Result<()> {
        fs::create_dir(join(gadget, relative))
    }
    fn write(&mut self, gadget: &Path, relative: &str, value: &str) -> io::Result<()> {
        fs::write(join(gadget, relative), format!("{value}\n"))
    }
    fn rmdir(&mut self, gadget: &Path, relative: &str) -> io::Result<()> {
        fs::remove_dir(join(gadget, relative))
    }
}

pub struct Gadget<F: Configfs = RealConfigfs> {
    pub options: Map<String, Value>,
    pub root: PathBuf,
    pub udcs: PathBuf,
    pub net: PathBuf,
    pub path: PathBuf,
    pub function: String,
    pub fs: F,
}

impl Gadget<RealConfigfs> {
    pub fn new(config: &Value) -> Result<Self> {
        Gadget::with(config, Path::new(CONFIGFS), Path::new(UDCS), Path::new("/sys/class/net"), RealConfigfs)
    }
}

impl<F: Configfs> Gadget<F> {
    pub fn with(config: &Value, root: &Path, udcs: &Path, net: &Path, fs: F) -> Result<Self> {
        let options = settings(config)?;
        let function = format!("{}.usb0", options["function"].as_str().unwrap_or_default());
        Ok(Gadget { options, root: root.into(), udcs: udcs.into(), net: net.into(), path: root.join("phoenix"), function, fs })
    }

    fn option(&self, key: &str) -> String {
        self.options.get(key).and_then(Value::as_str).unwrap_or_default().to_string()
    }

    fn mkdir(&mut self, relative: &str) -> Result<()> {
        Ok(self.fs.mkdir(&self.path, relative)?)
    }

    fn write(&mut self, relative: &str, value: &str) -> Result<()> {
        Ok(self.fs.write(&self.path, relative, value)?)
    }

    fn rmdir(&mut self, relative: &str) -> Result<()> {
        Ok(self.fs.rmdir(&self.path, relative)?)
    }

    pub fn start(&mut self) -> Result<()> {
        if self.options.get("vbus_verified") != Some(&Value::Bool(true)) && !crate::usb_bench::authorized(&self.options) {
            return invalid("usb_vbus_not_verified");
        }
        let udc = self.option("udc");
        if !self.root.is_dir() || !self.udcs.join(&udc).is_dir() {
            return invalid("usb_configfs_or_udc_unavailable");
        }
        // Do not adopt Radxa's gadget (which may include ADB), or silently replace ours.
        if fs::symlink_metadata(&self.path).is_ok() {
            return invalid("usb_gadget_already_exists");
        }
        let interface = self.option("interface");
        let prefix = &interface[..interface.len() - 1];
        for entry in fs::read_dir(&self.net)? {
            let name = entry?.file_name();
            let name = name.to_string_lossy();
            if name.strip_prefix(prefix).map(py::is_digits).unwrap_or(false) {
                return invalid("usb_interface_already_exists");
            }
        }
        for other in fs::read_dir(&self.root)? {
            let binding = other?.path().join("UDC");
            if binding.exists() && read_strip(&binding)? == udc {
                return invalid("usb_udc_owned_by_another_gadget");
            }
        }
        let mut created: Vec<String> = Vec::new();
        let mut linked = false;
        self.mkdir("")?;
        let result = self.populate(&udc, &interface, prefix, &mut created, &mut linked);
        if result.is_err() {
            // Linux returns ENODEV when unbinding a gadget never bound.
            let binding = self.path.join("UDC");
            if binding.exists() && read_strip(&binding).map(|v| !v.is_empty()).unwrap_or(false) {
                let _ = self.write("UDC", "");
            }
            if linked {
                let _ = fs::remove_file(self.path.join("configs/c.1").join(&self.function));
            }
            for directory in created.iter().rev() {
                let _ = self.rmdir(directory);
            }
            let _ = self.rmdir("");
        }
        result
    }

    fn populate(&mut self, udc: &str, interface: &str, prefix: &str, created: &mut Vec<String>, linked: &mut bool) -> Result<()> {
        let (vendor, product) = (self.option("vendor_id"), self.option("product_id"));
        for (key, value) in [("idVendor", vendor.as_str()), ("idProduct", product.as_str()), ("bcdDevice", "0x0100"), ("bcdUSB", "0x0200")] {
            self.write(key, value)?;
        }
        let function_dir = format!("functions/{}", self.function);
        for directory in ["strings/0x409", "configs/c.1", "configs/c.1/strings/0x409", function_dir.as_str()] {
            self.mkdir(directory)?;
            created.push(directory.to_string());
        }
        let serial = self.option("serial");
        for (key, value) in [("manufacturer", "Phoenix"), ("product", PRODUCT), ("serialnumber", serial.as_str())] {
            self.write(&format!("strings/0x409/{key}"), value)?;
        }
        self.write("configs/c.1/strings/0x409/configuration", "USB Ethernet")?;
        // Separately powered target. These descriptors do NOT switch physical VBUS.
        self.write("configs/c.1/bmAttributes", "0xc0")?;
        self.write("configs/c.1/MaxPower", "0")?;
        let (dev, host) = macs(&serial);
        // gether_set_ifname requires one %d, not an already numbered name.
        let template = format!("{prefix}%d");
        for (key, value) in [("dev_addr", dev.as_str()), ("host_addr", host.as_str()), ("ifname", template.as_str())] {
            self.write(&format!("{function_dir}/{key}"), value)?;
        }
        std::os::unix::fs::symlink(self.path.join(&function_dir), self.path.join("configs/c.1").join(&self.function))?;
        *linked = true;
        // Binding is deliberately last; failures must not expose a partial gadget.
        self.write("UDC", udc)?;
        if read_strip(&self.path.join(&function_dir).join("ifname"))? != interface {
            return invalid("usb_allocated_interface_mismatch");
        }
        Ok(())
    }

    pub fn stop(&mut self) -> Result<()> {
        if !self.path.exists() {
            return Ok(());
        }
        if fsutil::is_symlink(&self.path) || read_strip(&self.path.join("strings/0x409/product"))? != PRODUCT {
            return invalid("usb_gadget_not_owned");
        }
        if read_strip(&self.path.join("strings/0x409/serialnumber"))? != self.option("serial") {
            return invalid("usb_gadget_identity_mismatch");
        }
        let names = |relative: &str| -> Result<Vec<String>> {
            let mut out: Vec<String> = fs::read_dir(self.path.join(relative))?.map(|e| e.map(|e| e.file_name().to_string_lossy().into_owned())).collect::<io::Result<_>>()?;
            out.sort();
            Ok(out)
        };
        if names("functions")? != [self.function.clone()] {
            return invalid("usb_gadget_functions_changed");
        }
        if names("configs")? != ["c.1"] {
            return invalid("usb_gadget_configurations_changed");
        }
        let udc = self.option("udc");
        let bound = read_strip(&self.path.join("UDC"))?;
        if !bound.is_empty() && bound != udc {
            return invalid("usb_gadget_binding_changed");
        }
        let link = self.path.join("configs/c.1").join(&self.function);
        let function_dir = format!("functions/{}", self.function);
        if !fsutil::is_symlink(&link) || fs::canonicalize(&link)? != fs::canonicalize(self.path.join(&function_dir))? {
            return invalid("usb_gadget_link_changed");
        }
        if !bound.is_empty() {
            self.write("UDC", "")?;
        }
        fs::remove_file(&link)?;
        for directory in ["configs/c.1/strings/0x409", "configs/c.1", function_dir.as_str(), "strings/0x409", ""] {
            self.rmdir(directory)?;
        }
        Ok(())
    }
}

fn read_model() -> Option<String> {
    fs::read_to_string("/proc/device-tree/model").ok().map(|m| m.trim_matches(|c| c == '\0' || c == '\n').to_string())
}

fn inspect() -> Value {
    let mut controllers: Vec<PathBuf> = fs::read_dir(UDCS).map(|d| d.filter_map(|e| e.ok()).map(|e| e.path()).collect()).unwrap_or_default();
    controllers.sort();
    let udcs: Vec<Value> = controllers
        .iter()
        .map(|path| {
            let mut item = Map::new();
            item.insert("name".into(), json!(path.file_name().map(|n| n.to_string_lossy().into_owned())));
            for key in ["state", "current_speed", "maximum_speed", "function"] {
                item.insert(key.into(), read_strip(&path.join(key)).map(Value::String).unwrap_or(Value::Null));
            }
            Value::Object(item)
        })
        .collect();
    let mut gadgets: Vec<String> = fs::read_dir(CONFIGFS).map(|d| d.filter_map(|e| e.ok()).map(|e| e.file_name().to_string_lossy().into_owned()).collect()).unwrap_or_default();
    gadgets.sort();
    json!({"udcs": udcs, "configfs_available": Path::new(CONFIGFS).is_dir(), "gadgets": gadgets, "electrical_safety_verified": false})
}

fn act(action: &str, config_path: &Path) -> std::result::Result<(), String> {
    if fsutil::geteuid() != 0 {
        return Err("Root on the identified target required".into());
    }
    let config = fs::read(config_path).map_err(|e| e.to_string()).and_then(|d| json::loads(&d).map_err(|e| e.to_string()))?;
    let expected = config.get("expected_model").and_then(Value::as_str).unwrap_or_default();
    if expected.is_empty() || Some(expected.to_string()) != read_model() {
        return Err("Target model mismatch".into());
    }
    let mountinfo = fs::read_to_string("/proc/self/mountinfo").unwrap_or_default();
    if !mountinfo.lines().any(|l| l.contains(" /sys/kernel/config ") && l.contains(" - configfs ")) {
        return Err("configfs must already be mounted at /sys/kernel/config".into());
    }
    let mut gadget = Gadget::new(&config).map_err(|e| e.to_string())?;
    if action == "start" { gadget.start() } else { gadget.stop() }.map_err(|e| e.to_string())
}

/// `phoenix usb-gadget inspect|start|stop [--target-config F]`
pub fn main(args: &[String]) -> i32 {
    let parsed = match Args::parse(args, &["target-config"], &[]) {
        Ok(p) => p,
        Err(e) => return usage_error(&e),
    };
    let action = match parsed.positionals.as_slice() {
        [a] if matches!(a.as_str(), "inspect" | "start" | "stop") => a.clone(),
        _ => return usage_error("usage: phoenix usb-gadget inspect|start|stop [--target-config F]"),
    };
    if !cfg!(target_os = "linux") {
        eprintln!("Linux target required; no host networking changed");
        return 1;
    }
    if action == "inspect" {
        println!("{}", json::dumps(&inspect()));
        return 0;
    }
    match act(&action, Path::new(parsed.get("target-config").unwrap_or("/etc/phoenix/target.json"))) {
        Ok(()) => 0,
        Err(message) => {
            eprintln!("phoenix: {message}");
            1
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fsutil::testdir::TempDir;

    fn config() -> Value {
        json!({"interfaces": {"usb": "phusb0", "ap": "wlan0", "uplink": "eth0", "vpn": "phwg0"},
               "usb_gadget": {"enabled": true, "function": "ncm", "udc": "udc0", "serial": "test-device",
                              "vendor_id": "0x1234", "product_id": "0x5678", "vbus_verified": true}})
    }

    /// Models auto-created configfs groups/attributes, not a real controller.
    #[derive(Default)]
    struct Fake {
        writes: Vec<(String, String)>,
        fail_binding: bool,
        fail_function_mkdir: bool,
        fail_ifname: bool,
    }

    impl Configfs for Fake {
        fn mkdir(&mut self, gadget: &Path, relative: &str) -> io::Result<()> {
            if self.fail_function_mkdir && relative.starts_with("functions/") {
                return Err(io::Error::other("function unavailable"));
            }
            RealConfigfs.mkdir(gadget, relative)?;
            let groups: &[&str] = match relative {
                "" => &["strings", "configs", "functions"],
                "configs/c.1" => &["strings"],
                _ => &[],
            };
            for group in groups {
                fs::create_dir(join(gadget, relative).join(group))?;
            }
            Ok(())
        }
        fn write(&mut self, gadget: &Path, relative: &str, value: &str) -> io::Result<()> {
            self.writes.push((relative.into(), value.into()));
            if (self.fail_binding && relative == "UDC" && !value.is_empty()) || (self.fail_ifname && relative.ends_with("/ifname")) {
                return Err(io::Error::other("simulated failure"));
            }
            RealConfigfs.write(gadget, relative, value)?;
            if relative == "UDC" && !value.is_empty() {
                let functions = gadget.join("functions");
                for function in fs::read_dir(functions)? {
                    let name = function?.path().join("ifname");
                    let text = fs::read_to_string(&name)?;
                    fs::write(&name, text.replace("%d", "0"))?;
                }
            }
            Ok(())
        }
        fn rmdir(&mut self, gadget: &Path, relative: &str) -> io::Result<()> {
            let directory = join(gadget, relative);
            for entry in fs::read_dir(&directory)? {
                let entry = entry?;
                let kind = fs::symlink_metadata(entry.path())?.file_type();
                if kind.is_dir() {
                    let name = entry.file_name();
                    assert!(matches!(name.to_str(), Some("strings" | "configs" | "functions")), "cleanup order violated");
                    assert_eq!(fs::read_dir(entry.path())?.count(), 0, "cleanup order violated");
                    fs::remove_dir(entry.path())?;
                } else {
                    assert!(!kind.is_symlink(), "function link not removed first");
                    fs::remove_file(entry.path())?; // attributes vanish with their group
                }
            }
            fs::remove_dir(directory)
        }
    }

    fn make(dir: &Path, config: Value) -> Gadget<Fake> {
        for name in ["gadgets", "udcs/udc0", "net"] {
            fs::create_dir_all(dir.join(name)).unwrap();
        }
        Gadget::with(&config, &dir.join("gadgets"), &dir.join("udcs"), &dir.join("net"), Fake::default()).unwrap()
    }

    #[test]
    fn ncm_and_ecm_bind_last_and_stop_owned_only() {
        for function in ["ncm", "ecm"] {
            let dir = TempDir::new();
            let mut c = config();
            c["usb_gadget"]["function"] = json!(function);
            let mut g = make(dir.path(), c);
            g.start().unwrap();
            assert_eq!(g.fs.writes.last().unwrap(), &("UDC".to_string(), "udc0".to_string()));
            assert!(owned_binding_at("phusb0", &g.root));
            assert!(!owned_binding_at("eth0", &g.root));
            g.stop().unwrap();
            assert!(!g.path.exists());
            g.stop().unwrap();
        }
    }

    #[test]
    fn vbus_gate_and_foreign_udc_never_mutate() {
        let dir = TempDir::new();
        let mut c = config();
        c["usb_gadget"]["vbus_verified"] = json!(false);
        let mut g = make(dir.path(), c);
        assert_eq!(g.start().unwrap_err().code(), "usb_vbus_not_verified");
        assert!(g.fs.writes.is_empty());
        g.options.insert("vbus_verified".into(), json!(true));
        let other = g.root.join("radxa");
        fs::create_dir(&other).unwrap();
        fs::write(other.join("UDC"), "udc0\n").unwrap();
        assert_eq!(g.start().unwrap_err().code(), "usb_udc_owned_by_another_gadget");
        assert_eq!(fs::read_to_string(other.join("UDC")).unwrap(), "udc0\n");
        assert!(!g.path.exists());
    }

    #[test]
    fn failed_bind_rolls_back_and_can_retry() {
        let dir = TempDir::new();
        let mut g = make(dir.path(), config());
        g.fs.fail_binding = true;
        assert!(g.start().is_err());
        assert!(!g.path.exists());
        g.fs.fail_binding = false;
        g.start().unwrap();
        g.stop().unwrap();
    }

    #[test]
    fn unsupported_function_rolls_back_before_binding() {
        let dir = TempDir::new();
        let mut g = make(dir.path(), config());
        g.fs.fail_function_mkdir = true;
        assert!(g.start().is_err());
        assert!(!g.path.exists());
        assert!(!g.fs.writes.contains(&("UDC".into(), "udc0".into())));
    }

    #[test]
    fn existing_or_modified_gadget_not_adopted() {
        let dir = TempDir::new();
        let mut g = make(dir.path(), config());
        g.start().unwrap();
        assert_eq!(g.start().unwrap_err().code(), "usb_gadget_already_exists");
        fs::create_dir(g.path.join("functions/ffs.adb")).unwrap();
        assert_eq!(g.stop().unwrap_err().code(), "usb_gadget_functions_changed");
        assert_eq!(read_strip(&g.path.join("UDC")).unwrap(), "udc0");
    }

    #[test]
    fn input_validation_and_stable_local_macs() {
        for (key, value) in [("udc", "../udc0"), ("serial", "bad\nserial"), ("vendor_id", "0x0000"), ("function", "rndis"), ("udc", ".."), ("product_id", "0x12345")] {
            let mut c = config();
            c["usb_gadget"][key] = json!(value);
            assert!(settings(&c).is_err(), "{key}={value}");
        }
        let mut c = config();
        c["interfaces"]["usb"] = json!("phusb1");
        assert!(settings(&c).is_err());
        c["interfaces"]["usb"] = json!("eth0");
        assert!(settings(&c).is_err());
        let (dev, host) = macs("test-device");
        assert_ne!(dev, host);
        assert_eq!(macs("test-device"), (dev.clone(), host.clone()));
        for value in [dev, host] {
            assert_eq!(u8::from_str_radix(&value[..2], 16).unwrap() & 3, 2);
            assert_eq!(value.len(), 17);
        }
    }

    #[test]
    fn kernel_name_template_and_prefix_collision() {
        let dir = TempDir::new();
        let mut g = make(dir.path(), config());
        fs::create_dir(g.net.join("phusb1")).unwrap();
        assert_eq!(g.start().unwrap_err().code(), "usb_interface_already_exists");
        assert!(!g.path.exists());
        fs::remove_dir(g.net.join("phusb1")).unwrap();
        g.start().unwrap();
        assert!(g.fs.writes.contains(&("functions/ncm.usb0/ifname".into(), "phusb%d".into())));
        g.stop().unwrap();
    }

    #[test]
    fn failure_before_binding_does_not_unbind() {
        let dir = TempDir::new();
        let mut g = make(dir.path(), config());
        g.fs.fail_ifname = true;
        assert!(g.start().is_err());
        assert!(!g.path.exists());
        assert!(!g.fs.writes.contains(&("UDC".into(), String::new())));
    }
}
