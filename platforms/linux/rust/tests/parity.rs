//! Parity with the original Python service: tests/parity/fixtures.json holds
//! its outputs on a deterministic corpus, frozen on 2026-11-18 when that code
//! was removed (generator in git history). Every accepted input must produce
//! byte-identical output; every rejected input must be rejected.
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

#[test]
fn wireguard_profiles_match_python() {
    for case in fixtures()["wireguard"].as_array().unwrap() {
        let parsed = wireguard::parse(case["input"].as_str().unwrap());
        check("wireguard", case, parsed, |p| {
            serde_json::json!({"private_key": p.private_key, "public_key": p.public_key, "address": p.address,
                               "dns": p.dns, "endpoint": p.endpoint, "mtu": p.mtu, "keepalive": p.keepalive,
                               "preshared_key": p.preshared_key, "setconf": p.setconf()})
        });
    }
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
