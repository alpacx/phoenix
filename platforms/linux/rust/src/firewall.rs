//! Deterministic nftables compiler. No execution or global ruleset flush
//! (firewall.py). IPv4 only; owns the `inet phoenix` table on a dedicated
//! Phoenix target.
use crate::error::{invalid, Error, Result};
use crate::json::{field, object, Value};
use crate::policy::validate;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Mode {
    Blocked,
    Vpn,
    Direct,
}

impl Mode {
    pub fn as_str(&self) -> &'static str {
        match self {
            Mode::Blocked => "blocked",
            Mode::Vpn => "vpn",
            Mode::Direct => "direct",
        }
    }
}

/// Interface role assignment {ap, usb, uplink, vpn}.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Names {
    pub ap: String,
    pub usb: String,
    pub uplink: String,
    pub vpn: String,
}

impl Names {
    /// From target.json `interfaces`; each name validated with `interface`.
    pub fn from_json(interfaces: &Value) -> Result<Names> {
        let map = object(interfaces)?;
        Ok(Names {
            ap: interface_value(field(map, "ap")?)?,
            usb: interface_value(field(map, "usb")?)?,
            uplink: interface_value(field(map, "uplink")?)?,
            vpn: interface_value(field(map, "vpn")?)?,
        })
    }
    /// Role lookup: "ap" | "usb" | "uplink" | "vpn" (panics on other roles).
    pub fn get(&self, role: &str) -> &str {
        match role {
            "ap" => &self.ap,
            "usb" => &self.usb,
            "uplink" => &self.uplink,
            "vpn" => &self.vpn,
            _ => panic!("unknown interface role"),
        }
    }
    /// All four names differ.
    pub fn distinct(&self) -> bool {
        let all = [&self.ap, &self.usb, &self.uplink, &self.vpn];
        (0..4).all(|i| (i + 1..4).all(|j| all[i] != all[j]))
    }
}

/// `[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,14}`.
pub fn interface(value: &str) -> Result<String> {
    let bytes = value.as_bytes();
    let ok = !bytes.is_empty()
        && bytes.len() <= 15
        && (bytes[0].is_ascii_alphanumeric() || bytes[0] == b'_')
        && bytes[1..].iter().all(|b| b.is_ascii_alphanumeric() || matches!(b, b'_' | b'.' | b'-'));
    if ok {
        Ok(value.to_string())
    } else {
        invalid("invalid_interface")
    }
}

/// Same check for a JSON value (non-strings are invalid).
pub fn interface_value(value: &Value) -> Result<String> {
    match value {
        Value::String(s) => interface(s),
        _ => invalid("invalid_interface"),
    }
}

fn text<'a>(map: &'a crate::json::Map<String, Value>, key: &str) -> Result<&'a str> {
    field(map, key)?.as_str().ok_or_else(|| Error::Invalid("invalid_policy".into()))
}

fn number(map: &crate::json::Map<String, Value>, key: &str) -> Result<i64> {
    field(map, key)?.as_i64().ok_or_else(|| Error::Invalid("invalid_policy".into()))
}

fn flag(map: &crate::json::Map<String, Value>, key: &str) -> Result<bool> {
    field(map, key)?.as_bool().ok_or_else(|| Error::Invalid("invalid_policy".into()))
}

pub fn compile_rules(policy: &Value, names: &Names, mode: Mode, existing: bool) -> Result<String> {
    let p = validate(policy)?;
    for role in ["ap", "usb", "uplink", "vpn"] {
        interface(names.get(role))?;
    }
    if !names.distinct() {
        return invalid("interfaces_must_be_distinct");
    }
    let p = object(&p)?;
    let rules = field(p, "rules")?.as_array().expect("validated");
    let forwards = field(p, "forwards")?.as_array().expect("validated");
    let mut lines: Vec<String> = Vec::new();
    if existing {
        lines.push("delete table inet phoenix".into());
    }
    for line in ["table inet phoenix {", " chain forward {", "  type filter hook forward priority -10; policy drop;", "  meta nfproto ipv6 counter drop", "  ct state invalid counter drop"] {
        lines.push(line.into());
    }
    let vpn_mode = mode == Mode::Vpn;
    let exit_if = names.get(if vpn_mode { "vpn" } else { "uplink" });
    if mode != Mode::Blocked {
        for (role, cidr) in [("ap", "192.168.9.0/24"), ("usb", "192.168.7.0/24")] {
            let src = names.get(role);
            lines.push(format!("  iifname \"{src}\" ip saddr != {cidr} counter drop"));
            lines.push(format!("  iifname \"{exit_if}\" oifname \"{src}\" ip daddr {cidr} ct state established,related counter accept"));
            // Evaluate ordered rules for EVERY outgoing packet, including existing flows.
            for rule in rules {
                let rule = object(rule)?;
                if !flag(rule, "enabled")? || text(rule, "ingress")? != role {
                    continue;
                }
                let protocol = number(rule, "protocol")?;
                let mut parts = vec![
                    format!("  iifname \"{src}\" oifname \"{exit_if}\""),
                    format!("ip saddr {} ip daddr {}", text(rule, "source")?, text(rule, "destination")?),
                ];
                if protocol != 0 {
                    parts.push(format!("ip protocol {protocol}"));
                }
                let first = number(rule, "port_first")?;
                if first != 0 {
                    let proto = if protocol == 6 { "tcp" } else { "udp" };
                    parts.push(format!("{proto} dport {first}-{}", number(rule, "port_last")?));
                }
                parts.push(format!("counter {}", if flag(rule, "allow")? { "accept" } else { "drop" }));
                lines.push(parts.join(" "));
            }
            if flag(p, "default_allow")? {
                lines.push(format!("  iifname \"{src}\" oifname \"{exit_if}\" ip saddr {cidr} ip protocol {{ tcp, udp, icmp }} counter accept"));
            }
        }
        for f in forwards {
            let f = object(f)?;
            if !flag(f, "enabled")? || flag(f, "vpn")? != vpn_mode {
                continue;
            }
            let target = text(f, "target")?.split('/').next().unwrap_or("");
            let lan = names.get(if target.starts_with("192.168.9.") { "ap" } else { "usb" });
            let proto = if number(f, "protocol")? == 6 { "tcp" } else { "udp" };
            let source = text(f, "source")?;
            let internal = number(f, "internal_port")?;
            lines.push(format!("  iifname \"{exit_if}\" oifname \"{lan}\" ip saddr {source} ip daddr {target} {proto} dport {internal} ct status dnat counter accept"));
            lines.push(format!("  iifname \"{lan}\" oifname \"{exit_if}\" ip saddr {target} {proto} sport {internal} ct status dnat ct state established counter accept"));
        }
    }
    lines.push("  counter drop".into());
    for line in [" }", " chain prerouting {", "  type nat hook prerouting priority dstnat; policy accept;"] {
        lines.push(line.into());
    }
    if mode != Mode::Blocked {
        for f in forwards {
            let f = object(f)?;
            if flag(f, "enabled")? && flag(f, "vpn")? == vpn_mode {
                let proto = if number(f, "protocol")? == 6 { "tcp" } else { "udp" };
                let target = text(f, "target")?.split('/').next().unwrap_or("");
                lines.push(format!(
                    "  iifname \"{exit_if}\" ip saddr {} {proto} dport {} dnat ip to {target}:{}",
                    text(f, "source")?,
                    number(f, "external_port")?,
                    number(f, "internal_port")?
                ));
            }
        }
    }
    for line in [" }", " chain postrouting {", "  type nat hook postrouting priority srcnat; policy accept;"] {
        lines.push(line.into());
    }
    if mode != Mode::Blocked {
        lines.push(format!("  oifname \"{exit_if}\" ip saddr {{ 192.168.7.0/24, 192.168.9.0/24 }} masquerade"));
    }
    lines.push(" }".into());
    lines.push("}".into());
    Ok(lines.join("\n") + "\n")
}

#[cfg(test)]
pub mod tests {
    use super::*;
    use crate::json::json;

    pub fn names() -> Names {
        Names { ap: "phap0".into(), usb: "phusb0".into(), uplink: "eth0".into(), vpn: "phwg0".into() }
    }

    #[test]
    fn interface_names() {
        for good in ["eth0", "_x", "a.b-c_d", "abcdefghijklmno"] {
            assert!(interface(good).is_ok(), "{good}");
        }
        for bad in ["", "-eth", ".eth", "abcdefghijklmnop", "eth 0", "eth\"0", "éth0"] {
            assert!(interface(bad).is_err(), "{bad}");
        }
        assert!(Names::from_json(&json!({"ap": "a", "usb": "b", "uplink": "c"})).is_err());
    }

    #[test]
    fn blocked_has_no_forwarding() {
        let policy = crate::policy::tests::policy();
        let text = compile_rules(&policy, &names(), Mode::Blocked, true).unwrap();
        assert!(text.starts_with("delete table inet phoenix\ntable inet phoenix {\n"));
        assert!(!text.contains("accept\n  counter drop") && !text.contains("masquerade"));
        assert!(text.ends_with(" chain postrouting {\n  type nat hook postrouting priority srcnat; policy accept;\n }\n}\n"));
    }

    #[test]
    fn vpn_rules_and_forwards() {
        let policy = crate::policy::tests::policy();
        let text = compile_rules(&policy, &names(), Mode::Vpn, false).unwrap();
        assert!(text.contains("  iifname \"phap0\" oifname \"phwg0\" ip saddr 192.168.9.0/24 ip daddr 1.2.3.4/32 ip protocol 6 tcp dport 80-443 counter drop\n"));
        assert!(text.contains("  iifname \"phwg0\" ip saddr 0.0.0.0/0 tcp dport 2222 dnat ip to 192.168.9.10:22\n"));
        assert!(text.contains("  oifname \"phwg0\" ip saddr { 192.168.7.0/24, 192.168.9.0/24 } masquerade\n"));
        let direct = compile_rules(&policy, &names(), Mode::Direct, false).unwrap();
        assert!(!direct.contains("dnat ip to"), "VPN-only forward must not apply in direct mode");
        let mut same = names();
        same.usb = "phap0".into();
        assert!(compile_rules(&policy, &same, Mode::Vpn, false).is_err());
    }
}
