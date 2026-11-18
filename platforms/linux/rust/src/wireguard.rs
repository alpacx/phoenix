//! Strict, script-free WireGuard profile parsing matching Phoenix IPv4
//! scope (wireguard.py).
use crate::error::{invalid, Error, Result};
use crate::ipv4;
use crate::py;
use base64::Engine;
use std::collections::HashMap;
use std::fmt;

/// Canonical base64 of exactly 32 bytes.
pub fn key(value: &str) -> Result<String> {
    let engine = base64::engine::general_purpose::STANDARD;
    match engine.decode(value) {
        Ok(raw) if raw.len() == 32 && engine.encode(&raw) == value => Ok(value.to_string()),
        _ => invalid("invalid_key"),
    }
}

fn number(value: &str, low: u64, high: u64) -> Result<u32> {
    if !py::is_digits(value) {
        return invalid("invalid_number");
    }
    match value.parse::<u64>() {
        Ok(n) if low <= n && n <= high => Ok(n as u32),
        _ => invalid("invalid_number"),
    }
}

#[derive(Clone, PartialEq, Eq)]
pub struct Profile {
    pub private_key: String,
    pub public_key: String,
    /// IPv4Interface text, e.g. "10.5.0.2/32".
    pub address: String,
    pub dns: String,
    /// "a.b.c.d:port".
    pub endpoint: String,
    pub mtu: u32,
    pub keepalive: u32,
    pub preshared_key: String,
}

impl fmt::Debug for Profile {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        // Private and preshared keys never appear in logs or panics.
        f.debug_struct("Profile")
            .field("public_key", &self.public_key)
            .field("address", &self.address)
            .field("dns", &self.dns)
            .field("endpoint", &self.endpoint)
            .field("mtu", &self.mtu)
            .field("keepalive", &self.keepalive)
            .finish_non_exhaustive()
    }
}

impl Profile {
    /// `wg setconf` text (never passed as argv).
    pub fn setconf(&self) -> String {
        let mut text = format!("[Interface]\nPrivateKey = {}\n[Peer]\nPublicKey = {}\n", self.private_key, self.public_key);
        if !self.preshared_key.is_empty() {
            text += &format!("PresharedKey = {}\n", self.preshared_key);
        }
        text + &format!("Endpoint = {}\nAllowedIPs = 0.0.0.0/0\nPersistentKeepalive = {}\n", self.endpoint, self.keepalive)
    }
}

fn missing() -> Error {
    Error::Invalid("missing_profile_fields".into())
}

pub fn parse(text: &str) -> Result<Profile> {
    if text.is_empty() || text.len() > 4096 || text.contains('\0') {
        return invalid("invalid_profile");
    }
    let allowed = |section: &str, name: &str| match section {
        "Interface" => ["PrivateKey", "Address", "DNS", "MTU"].contains(&name),
        "Peer" => ["PublicKey", "PresharedKey", "Endpoint", "AllowedIPs", "PersistentKeepalive"].contains(&name),
        _ => false,
    };
    let mut sections: HashMap<String, HashMap<String, String>> = HashMap::new();
    let mut current: Option<String> = None;
    for line in py::splitlines(text) {
        if line.len() > 255 {
            return invalid("line_too_long");
        }
        let line = py::strip(line.split('#').next().unwrap_or(""));
        if line.is_empty() {
            continue;
        }
        if line.starts_with('[') {
            let name = if line.len() >= 2 && line.ends_with(']') { &line[1..line.len() - 1] } else { "" };
            if !matches!(name, "Interface" | "Peer") || sections.contains_key(name) || (name == "Peer" && !sections.contains_key("Interface")) {
                return invalid("invalid_section");
            }
            sections.insert(name.to_string(), HashMap::new());
            current = Some(name.to_string());
        } else {
            let (Some(section), Some((name, value))) = (current.as_ref(), line.split_once('=')) else {
                return invalid("invalid_field");
            };
            let (name, value) = (py::strip(name), py::strip(value));
            let fields = sections.get_mut(section).expect("current section exists");
            if !allowed(section, name) || fields.contains_key(name) {
                return invalid("unknown_or_duplicate_field");
            }
            fields.insert(name.to_string(), value.to_string());
        }
    }
    let a = sections.get("Interface").ok_or_else(missing)?;
    let b = sections.get("Peer").ok_or_else(missing)?;
    let get = |m: &HashMap<String, String>, k: &str| m.get(k).cloned().ok_or_else(missing);
    let private = key(&get(a, "PrivateKey")?)?;
    let public = key(&get(b, "PublicKey")?)?;
    let address_text = get(a, "Address")?;
    if !address_text.contains('/') {
        return invalid("prefix_required");
    }
    let address = ipv4::interface(&address_text)?;
    if address.prefix == 0 {
        return invalid("invalid_prefix");
    }
    let dns = ipv4::address(&get(a, "DNS")?)?.to_string();
    let endpoint_text = get(b, "Endpoint")?;
    let parts: Vec<&str> = endpoint_text.split(':').collect();
    if parts.len() != 2 {
        return invalid("invalid_endpoint");
    }
    let endpoint = format!("{}:{}", ipv4::address(parts[0])?, number(parts[1], 1, 65535)?);
    if get(b, "AllowedIPs")? != "0.0.0.0/0" {
        return invalid("full_tunnel_required");
    }
    Ok(Profile {
        private_key: private,
        public_key: public,
        address: address.to_string(),
        dns,
        endpoint,
        mtu: number(a.get("MTU").map(String::as_str).unwrap_or("1380"), 1280, 1420)?,
        keepalive: number(b.get("PersistentKeepalive").map(String::as_str).unwrap_or("0"), 0, 65535)?,
        preshared_key: match b.get("PresharedKey") {
            Some(k) => key(k)?,
            None => String::new(),
        },
    })
}

#[cfg(test)]
pub mod tests {
    use super::*;

    pub const PRIVATE: &str = "yAnz5TF+lXXJte14tji3zlMNq+hd2rYUIgJBgB3fBmk=";
    pub const PUBLIC: &str = "xTIBA5rboUvnH4htodjb6e697QjLERt1NAB4mZqp8Dg=";

    pub fn profile_text() -> String {
        format!("[Interface]\nPrivateKey = {PRIVATE}\nAddress = 10.5.0.2/32\nDNS = 103.86.96.100\n# comment\n[Peer]\nPublicKey = {PUBLIC}\nEndpoint = 192.0.2.20:51820\nAllowedIPs = 0.0.0.0/0\nPersistentKeepalive = 25\n")
    }

    #[test]
    fn parses_and_renders() {
        let profile = parse(&profile_text()).unwrap();
        assert_eq!(profile.address, "10.5.0.2/32");
        assert_eq!(profile.endpoint, "192.0.2.20:51820");
        assert_eq!(profile.mtu, 1380);
        assert_eq!(
            profile.setconf(),
            format!("[Interface]\nPrivateKey = {PRIVATE}\n[Peer]\nPublicKey = {PUBLIC}\nEndpoint = 192.0.2.20:51820\nAllowedIPs = 0.0.0.0/0\nPersistentKeepalive = 25\n")
        );
        assert!(!format!("{profile:?}").contains(PRIVATE));
    }

    #[test]
    fn rejects_unsafe_profiles() {
        let base = profile_text();
        let cases = [
            base.replace("0.0.0.0/0", "10.0.0.0/8"),
            base.replace("10.5.0.2/32", "10.5.0.2"),
            base.replace("10.5.0.2/32", "10.5.0.2/0"),
            base.replace("[Interface]", "[Interface]\nPostUp = rm -rf /"),
            base.replace("DNS = 103.86.96.100", "DNS = 103.86.96.100\nDNS = 1.1.1.1"),
            base.replace("192.0.2.20:51820", "example.com:51820"),
            base.replace("192.0.2.20:51820", "192.0.2.20:0"),
            base.replace(PUBLIC, "short"),
            base.replace("[Peer]", "[Peer]\n[Peer]"),
            format!("[Peer]\n{base}"),
            base.replace("Address", "MTU = 9000\nAddress"),
            base.replace("25", "x"),
            format!("{base}\0"),
            "x".repeat(4097),
            String::new(),
            base.replace("# comment", &"#".repeat(256)),
        ];
        for (i, text) in cases.iter().enumerate() {
            assert!(parse(text).is_err(), "case {i} accepted");
        }
        assert!(key("yAnz5TF+lXXJte14tji3zlMNq+hd2rYUIgJBgB3fBmk").is_err());
    }
}
