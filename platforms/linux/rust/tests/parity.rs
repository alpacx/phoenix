//! Parity with the original Python service: tests/parity/fixtures.json holds
//! its outputs on a deterministic corpus, frozen on 2026-11-18 when that code
//! was removed (generator in git history). Every accepted input must produce
//! byte-identical output; every rejected input must be rejected, except the
//! documented WireGuard import relaxations (see `wireguard_relaxation`).
use phoenix_linux::firewall::{compile_rules, Mode, Names};
use phoenix_linux::json::Value;
use phoenix_linux::{access_point, ipv4, policy, wireguard};

fn fixtures() -> Value {
    serde_json::from_str(include_str!("parity/fixtures.json")).expect("valid fixtures")
}

fn check<T: std::fmt::Debug>(kind: &str, case: &Value, actual: Result<T, phoenix_linux::error::Error>, expected: impl Fn(&T) -> Value) {
    match (case.get("ok"), &actual) {
        (Some(ok), Ok(value)) => assert_eq!(&expected(value), ok, "{kind} output differs for {}", case["input"]),
        (None, Err(_)) => {}
        (Some(_), Err(error)) => panic!("{kind}: Rust rejected ({error}) what Python accepted: {}", case["input"]),
        (None, Ok(value)) => panic!("{kind}: Rust accepted what Python rejected: {} -> {value:?}", case["input"]),
    }
}

#[test]
fn policy_validation_matches_python() {
    let cases = fixtures();
    let cases = cases["policy"].as_array().unwrap();
    assert!(cases.len() > 200);
    for case in cases {
        check("policy", case, policy::validate(&case["input"]), Value::clone);
    }
}

#[test]
fn nftables_text_matches_python() {
    let names = Names { ap: "wlan0".into(), usb: "usb0".into(), uplink: "end0".into(), vpn: "phwg0".into() };
    let all = fixtures();
    let policies = all["policy"].as_array().unwrap();
    let cases = all["compile"].as_array().unwrap();
    assert!(cases.len() >= 120);
    for case in cases {
        let input = &policies[case["policy"].as_u64().unwrap() as usize]["input"];
        let mode = match case["mode"].as_str().unwrap() {
            "blocked" => Mode::Blocked,
            "vpn" => Mode::Vpn,
            _ => Mode::Direct,
        };
        let existing = case["existing"].as_bool().unwrap();
        check("compile", case, compile_rules(input, &names, mode, existing), |text| Value::String(text.clone()));
    }
}

/// Why the extended importer may accept a profile the Python parser
/// rejected (platforms/linux/API_STATUS.md). None: it must still be rejected.
fn wireguard_relaxation(input: &str) -> Option<&'static str> {
    let mut section = String::new();
    for line in input.lines() {
        let line = line.split('#').next().unwrap_or("").trim();
        if line.starts_with('[') {
            if line != "[Interface]" && line != "[Peer]" {
                return Some("case-insensitive section names");
            }
            section = line.to_string();
            continue;
        }
        let Some((key, value)) = line.split_once('=') else { continue };
        let (key, value) = (key.trim(), value.trim());
        let canonical = ["PrivateKey", "Address", "DNS", "MTU", "PublicKey", "PresharedKey", "Endpoint", "AllowedIPs", "PersistentKeepalive"];
        if !canonical.contains(&key) && canonical.iter().any(|c| c.eq_ignore_ascii_case(key)) {
            return Some("case-insensitive key names");
        }
        match key {
            "MTU" if value.parse::<u32>().map(|m| (1421..=1500).contains(&m)).unwrap_or(false) => return Some("MTU up to 1500"),
            "Address" if !value.contains('/') || value.contains(',') => return Some("address without prefix or list"),
            "DNS" if value.contains(',') => return Some("DNS list"),
            "AllowedIPs" if value != "0.0.0.0/0" => return Some("AllowedIPs list, IPv6 ignored, split tunnel"),
            "Endpoint" if value.rsplit_once(':').map(|(h, _)| !h.bytes().all(|b| b.is_ascii_digit() || b == b'.')).unwrap_or(false) && !value.starts_with('[') => {
                return Some("host name endpoint")
            }
            "PersistentKeepalive" if value.eq_ignore_ascii_case("off") => return Some("keepalive off"),
            "ListenPort" | "FwMark" | "Table" | "SaveConfig" | "PreUp" | "PostUp" | "PreDown" | "PostDown" if section == "[Interface]" => {
                return Some("wg-quick options ignored")
            }
            _ => {}
        }
    }
    let count = |k: &str| input.lines().filter(|l| l.trim_start().starts_with(k)).count();
    if count("DNS") == 0 {
        return Some("DNS optional (fallback)");
    }
    if count("DNS") > 1 || count("Address") > 1 || count("AllowedIPs") > 1 {
        return Some("repeated Address/DNS/AllowedIPs lines");
    }
    None
}

#[test]
fn wireguard_profiles_match_python() {
    let mut relaxed = 0;
    for case in fixtures()["wireguard"].as_array().unwrap() {
        let input = case["input"].as_str().unwrap();
        let parsed = wireguard::parse(input);
        if case.get("ok").is_none() {
            if let Ok(profile) = &parsed {
                let reason = wireguard_relaxation(input).unwrap_or_else(|| panic!("accepted outside documented relaxations: {input:?} -> {profile:?}"));
                assert!(!profile.address.is_empty() && !profile.primary().allowed_ips.is_empty(), "{reason}");
                relaxed += 1;
            }
            continue;
        }
        let without_notes = parsed.as_ref().map(|p| p.notes.is_empty()).unwrap_or(false);
        // Documented divergence (API_STATUS.md, 2026-11-25): a peer without
        // keepalive gets wireguard::DEFAULT_KEEPALIVE in `wg`, so the
        // supervisor sees handshakes on an idle gateway. Python wrote 0.
        let mut case = case.clone();
        if let Some(setconf) = case.get_mut("ok").and_then(|ok| ok.get_mut("setconf")) {
            let applied = format!("PersistentKeepalive = {}\n", wireguard::DEFAULT_KEEPALIVE);
            *setconf = Value::String(setconf.as_str().unwrap().replace("PersistentKeepalive = 0\n", &applied));
        }
        let case = &case;
        check("wireguard", case, parsed, |p| {
            let peer = p.primary();
            serde_json::json!({"private_key": p.private_key, "public_key": peer.public_key, "address": p.address,
                               "dns": p.dns_text(), "endpoint": peer.endpoint, "mtu": p.mtu, "keepalive": peer.keepalive,
                               "preshared_key": peer.preshared_key, "setconf": p.setconf()})
        });
        // Profiles the strict parser accepted carry no import notes.
        assert!(without_notes, "{input:?}");
    }
    assert!(relaxed >= 5, "fixtures exercise the relaxations ({relaxed})");
}

#[test]
fn access_point_configs_match_python() {
    for case in fixtures()["render"].as_array().unwrap() {
        let a: Vec<&str> = case["input"].as_array().unwrap().iter().map(|v| v.as_str().unwrap()).collect();
        let rendered = access_point::render(a[0], a[1], a[2], a[3], a[4]);
        check("render", case, rendered, |files| {
            Value::Object(files.iter().map(|(name, text)| (name.to_string(), Value::String(text.clone()))).collect())
        });
    }
}

#[test]
fn ipv4_networks_match_python() {
    for case in fixtures()["network"].as_array().unwrap() {
        let input = case["input"].as_str().unwrap();
        check("network", case, ipv4::network_text(input), |text| Value::String(text.clone()));
    }
}
