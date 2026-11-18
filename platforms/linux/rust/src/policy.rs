//! API-compatible IPv4 policy validation; no shell interpolation (policy.py).
use crate::error::{invalid, Error, Result};
use crate::ipv4;
use crate::json::{field, Map, Value};
pub use crate::json::{boolean, integer};

/// 1..=32 UTF-8 bytes, no control characters below 0x20.
pub fn label(value: &Value) -> Result<()> {
    match value {
        Value::String(s) if (1..=32).contains(&s.len()) && !s.chars().any(|c| (c as u32) < 32) => Ok(()),
        _ => invalid("invalid_label"),
    }
}

/// `str(IPv4Network(value, strict=False))`.
pub fn network(value: &Value) -> Result<String> {
    match value {
        Value::String(s) => ipv4::network_text(s).map_err(|_| Error::Invalid("invalid_cidr".into())),
        _ => invalid("invalid_cidr"),
    }
}

fn object_mut(value: &mut Value) -> Result<&mut Map<String, Value>> {
    value.as_object_mut().ok_or_else(|| Error::Invalid("invalid_policy".into()))
}

fn validate_rule(rule: &mut Value) -> Result<()> {
    let r = object_mut(rule)?;
    label(field(r, "name")?)?;
    boolean(field(r, "enabled")?)?;
    boolean(field(r, "allow")?)?;
    if !matches!(field(r, "ingress")?.as_str(), Some("ap" | "usb")) {
        return invalid("invalid_ingress");
    }
    let protocol = integer(field(r, "protocol")?, 0, 255)?;
    if ![0, 1, 6, 17].contains(&protocol) {
        return invalid("invalid_protocol");
    }
    for key in ["source", "destination"] {
        let normalized = network(field(r, key)?)?;
        r.insert(key.to_string(), Value::String(normalized));
    }
    let first = integer(field(r, "port_first")?, 0, 65535)?;
    let last = integer(field(r, "port_last")?, first, 65535)?;
    if (first == 0 && last != 0) || (last != 0 && protocol != 6 && protocol != 17) {
        return invalid("invalid_port_range");
    }
    Ok(())
}

struct Seen {
    enabled: bool,
    vpn: bool,
    protocol: i64,
    external: i64,
    target: String,
    internal: i64,
}

fn validate_forward(forward: &mut Value, seen: &mut Vec<Seen>) -> Result<()> {
    let f = object_mut(forward)?;
    label(field(f, "name")?)?;
    let enabled = boolean(field(f, "enabled")?)?;
    let vpn = boolean(field(f, "vpn")?)?;
    let protocol = integer(field(f, "protocol")?, 0, 255)?;
    if protocol != 6 && protocol != 17 {
        return invalid("invalid_protocol");
    }
    let external = integer(field(f, "external_port")?, 1, 65535)?;
    let internal = integer(field(f, "internal_port")?, 1, 65535)?;
    if external == 80 || external == 51820 || (49152..=61439).contains(&external) {
        return invalid("reserved_port");
    }
    let target = ipv4::network(&network(field(f, "target")?)?)?;
    let lans = [ipv4::network("192.168.7.0/24")?, ipv4::network("192.168.9.0/24")?];
    let host = target.address & 255;
    if target.prefix != 32 || !lans.iter().any(|lan| target.subnet_of(lan)) || !(2..255).contains(&host) {
        return invalid("invalid_target");
    }
    let target = target.to_string();
    f.insert("target".into(), Value::String(target.clone()));
    let source = network(field(f, "source")?)?;
    f.insert("source".into(), Value::String(source));
    f.shift_remove("active"); // Runtime-only field echoed by current UI.
    for other in seen.iter() {
        if enabled && other.enabled && vpn == other.vpn && protocol == other.protocol && (external == other.external || (target == other.target && internal == other.internal)) {
            return invalid("duplicate_forward");
        }
    }
    seen.push(Seen { enabled, vpn, protocol, external, target, internal });
    Ok(())
}

/// Returns the normalized deep copy; unknown keys are kept as in Python.
pub fn validate(policy: &Value) -> Result<Value> {
    let mut p = policy.clone();
    let obj = object_mut(&mut p)?;
    integer(field(obj, "revision")?, 0, (1i64 << 32) - 1)?;
    boolean(field(obj, "default_allow")?)?;
    for (key, limit) in [("rules", 20), ("forwards", 8)] {
        match field(obj, key)? {
            Value::Array(items) if items.len() <= limit => {}
            _ => return invalid("too_many_rules"),
        }
    }
    for rule in obj.get_mut("rules").and_then(Value::as_array_mut).expect("checked array") {
        validate_rule(rule)?;
    }
    let mut seen = Vec::new();
    for forward in obj.get_mut("forwards").and_then(Value::as_array_mut).expect("checked array") {
        validate_forward(forward, &mut seen)?;
    }
    Ok(p)
}

#[cfg(test)]
pub mod tests {
    use super::*;
    use crate::json::json;

    pub fn rule() -> Value {
        json!({"name": "web", "enabled": true, "allow": false, "ingress": "ap", "protocol": 6,
               "source": "192.168.9.0/24", "destination": "1.2.3.4", "port_first": 80, "port_last": 443})
    }

    pub fn forward() -> Value {
        json!({"name": "ssh", "enabled": true, "vpn": true, "protocol": 6, "external_port": 2222,
               "internal_port": 22, "target": "192.168.9.10", "source": "0.0.0.0/0", "active": true})
    }

    pub fn policy() -> Value {
        json!({"revision": 0, "default_allow": true, "rules": [rule()], "forwards": [forward()]})
    }

    #[test]
    fn normalizes_and_keeps_unknown_keys() {
        let mut p = policy();
        p["rules"][0]["note"] = json!("kept");
        let v = validate(&p).unwrap();
        assert_eq!(v["rules"][0]["destination"], "1.2.3.4/32");
        assert_eq!(v["rules"][0]["note"], "kept");
        assert_eq!(v["forwards"][0]["target"], "192.168.9.10/32");
        assert!(v["forwards"][0].get("active").is_none());
    }

    #[test]
    fn rejects_invalid() {
        let cases: Vec<Box<dyn Fn(&mut Value)>> = vec![
            Box::new(|p| p["revision"] = json!(-1)),
            Box::new(|p| p["revision"] = json!(true)),
            Box::new(|p| p["default_allow"] = json!(1)),
            Box::new(|p| p["rules"] = json!(vec![rule(); 21])),
            Box::new(|p| p["rules"][0]["name"] = json!("")),
            Box::new(|p| p["rules"][0]["name"] = json!("a\nb")),
            Box::new(|p| p["rules"][0]["ingress"] = json!("wan")),
            Box::new(|p| p["rules"][0]["protocol"] = json!(2)),
            Box::new(|p| p["rules"][0]["port_last"] = json!(79)),
            Box::new(|p| {
                p["rules"][0]["protocol"] = json!(1);
            }),
            Box::new(|p| {
                p["rules"][0]["port_first"] = json!(0);
            }),
            Box::new(|p| p["rules"][0]["source"] = json!("10.0.0.0/33")),
            Box::new(|p| p["forwards"][0]["external_port"] = json!(80)),
            Box::new(|p| p["forwards"][0]["external_port"] = json!(50000)),
            Box::new(|p| p["forwards"][0]["target"] = json!("192.168.9.1")),
            Box::new(|p| p["forwards"][0]["target"] = json!("192.168.9.255")),
            Box::new(|p| p["forwards"][0]["target"] = json!("192.168.9.0/30")),
            Box::new(|p| p["forwards"][0]["target"] = json!("10.0.0.5")),
            Box::new(|p| p["forwards"][0]["protocol"] = json!(1)),
            Box::new(|p| {
                let mut other = forward();
                other["internal_port"] = json!(23);
                p["forwards"].as_array_mut().unwrap().push(other);
            }),
            Box::new(|p| {
                p.as_object_mut().unwrap().remove("forwards");
            }),
        ];
        for (i, change) in cases.iter().enumerate() {
            let mut p = policy();
            change(&mut p);
            assert!(validate(&p).is_err(), "case {i} accepted");
        }
        let mut disabled = policy();
        let mut other = forward();
        other["enabled"] = json!(false);
        disabled["forwards"].as_array_mut().unwrap().push(other);
        assert!(validate(&disabled).is_ok());
    }
}
