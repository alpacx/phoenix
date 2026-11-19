//! Linux-only network adapter: nftables, WireGuard kernel, policy routing
//! (runtime.py). Dedicated gateway, never the development host.
//!
//! All commands are argv lists; no wg-quick hooks, shell scripts or key
//! arguments. Owns only the phoenix nft table, phwg0, rule priorities
//! 17690-17711 and tables 17700/17710. Methods take &self; mutable state
//! lives in a short-lived mutex never held while a command runs, so status
//! reads never wait for long operations. The controller serializes mutations.
use crate::error::{invalid, Error, Result};
use crate::firewall::{compile_rules, interface, Mode, Names};
use crate::json::{self, json, Map, Value};
use crate::py::{self, Clock};
use crate::runner::SharedRunner;
use crate::wireguard::{Peer, Profile};
use crate::{ipv4, nord, speedcheck, uplink_http};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

#[derive(Debug, Clone)]
pub struct RuntimeState {
    pub names: Names,
    pub ethernet_name: String,
    /// "ethernet" | "wifi"
    pub uplink_kind: String,
    pub selected_route: bool,
    pub mode: Mode,
    pub profile: Option<Profile>,
    pub policy: Option<Value>,
    pub enforced: bool,
}

/// (path, headers, uplink device, fwmark) -> JSON; production uplink_http::get.
pub type NordTransport = Arc<dyn Fn(&str, &[(String, String)], &str, u32) -> Result<Value> + Send + Sync>;

/// (host name, uplink device, fwmark) -> IPv4; production uplink_http::resolve.
pub type EndpointResolver = Arc<dyn Fn(&str, &str, u32) -> Result<std::net::Ipv4Addr> + Send + Sync>;

pub struct Runtime {
    pub run: SharedRunner,
    clock: Clock,
    state: Mutex<RuntimeState>,
    root: PathBuf,
    transport: NordTransport,
    resolver: EndpointResolver,
}

const MARK: &str = "0x5048";

fn network_error(code: &str) -> Error {
    Error::Network(code.to_string())
}

fn is_inet(address: &Value) -> bool {
    address.get("family").and_then(Value::as_str) == Some("inet")
}

fn addr_info(item: Option<&Value>) -> &[Value] {
    item.and_then(|i| i.get("addr_info")).and_then(Value::as_array).map(Vec::as_slice).unwrap_or(&[])
}

impl Runtime {
    /// `interfaces` from target.json; names must be distinct and vpn == "phwg0".
    /// `clock` is wall time (handshake ages are epoch seconds).
    pub fn new(interfaces: &Value, runner: SharedRunner, clock: Clock) -> Result<Runtime> {
        let names = Names::from_json(interfaces)?;
        if !names.distinct() || names.vpn != "phwg0" {
            return invalid("invalid_interface_assignment");
        }
        let state = RuntimeState {
            ethernet_name: names.uplink.clone(),
            names,
            uplink_kind: "ethernet".into(),
            selected_route: false,
            mode: Mode::Blocked,
            profile: None,
            policy: None,
            enforced: false,
        };
        Ok(Runtime {
            run: runner,
            clock,
            state: Mutex::new(state),
            root: PathBuf::from("/"),
            transport: Arc::new(uplink_http::get),
            resolver: Arc::new(uplink_http::resolve),
        })
    }

    /// Test hook: read /proc and /sys/class/thermal below `root`.
    pub fn with_root(mut self, root: &Path) -> Self {
        self.root = root.to_path_buf();
        self
    }

    /// Test hook: replace the bound NordVPN HTTPS transport.
    pub fn with_nord_transport(mut self, transport: NordTransport) -> Self {
        self.transport = transport;
        self
    }

    /// Test hook: replace the bound DoH resolver for endpoint host names.
    pub fn with_resolver(mut self, resolver: EndpointResolver) -> Self {
        self.resolver = resolver;
        self
    }

    /// Profile whose members in use have numeric endpoints. Host names are
    /// resolved at every connect and member switch through DoH on the
    /// selected uplink (same path and mark as the NordVPN API), never the
    /// system resolver.
    pub fn resolve_endpoint(&self, profile: &Profile) -> Result<Profile> {
        let mut resolved = profile.clone();
        for group in 0..profile.groups.len() {
            resolved = self.resolve_member(&resolved, group)?;
        }
        Ok(resolved)
    }

    fn resolve_member(&self, profile: &Profile, group: usize) -> Result<Profile> {
        let index = profile.active_index(group);
        let peer = &profile.peers[index];
        if peer.endpoint_name.is_empty() {
            return Ok(profile.clone());
        }
        let (uplink, selected) = {
            let state = self.state.lock().unwrap();
            (state.names.uplink.clone(), state.selected_route)
        };
        let mark = if selected { 0x5048 } else { 0 };
        match (self.resolver)(&peer.endpoint_name, &uplink, mark) {
            Ok(address) => Ok(profile.with_peer(index, peer.resolved(address))),
            Err(_) => Err(network_error("endpoint_resolution_failed")),
        }
    }

    pub fn state(&self) -> RuntimeState {
        self.state.lock().unwrap().clone()
    }
    pub fn names(&self) -> Names {
        self.state.lock().unwrap().names.clone()
    }
    pub fn mode(&self) -> Mode {
        self.state.lock().unwrap().mode
    }
    pub fn enforced(&self) -> bool {
        self.state.lock().unwrap().enforced
    }
    pub fn set_enforced(&self, value: bool) {
        self.state.lock().unwrap().enforced = value;
    }
    pub fn selected_route(&self) -> bool {
        self.state.lock().unwrap().selected_route
    }
    pub fn profile(&self) -> Option<Profile> {
        self.state.lock().unwrap().profile.clone()
    }

    fn set_mode(&self, mode: Mode) {
        self.state.lock().unwrap().mode = mode;
    }

    fn set_profile(&self, profile: Option<Profile>) {
        self.state.lock().unwrap().profile = profile;
    }

    pub fn firewall(&self, policy: &Value, mode: Mode) -> Result<()> {
        let names = self.names();
        let exists = self.run.optional(&["nft", "list", "table", "inet", "phoenix"])?.code == 0;
        let text = compile_rules(policy, &names, mode, exists)?;
        self.run.input(&["nft", "--check", "-f", "-"], &text)?;
        self.run.input(&["nft", "-f", "-"], &text)?;
        let mut state = self.state.lock().unwrap();
        state.mode = mode;
        state.policy = Some(policy.clone());
        state.enforced = true;
        Ok(())
    }

    pub fn block(&self, policy: &Value) -> Result<()> {
        self.firewall(policy, Mode::Blocked)?;
        // Remove old NAT mappings in both directions after the drop barrier.
        for subnet in ["192.168.7.0/24", "192.168.9.0/24"] {
            for direction in ["-s", "-d"] {
                let result = self.run.optional(&["conntrack", "-D", "-f", "ipv4", direction, subnet])?;
                if result.code != 0 && result.code != 1 {
                    return Err(network_error("conntrack_cleanup_failed"));
                }
            }
        }
        Ok(())
    }

    pub fn connect(&self, policy: &Value, profile: &Profile) -> Result<()> {
        // Install drop before touching routes or the old tunnel; no direct fallback.
        self.block(policy)?;
        self.set_profile(None);
        match self.connect_steps(policy, profile) {
            Ok(()) => Ok(()),
            Err(error) => {
                self.set_mode(Mode::Blocked);
                let blocked = self.block(policy);
                let _ = self.run.optional(&["ip", "link", "delete", "phwg0"]);
                self.set_profile(None);
                blocked?;
                Err(error)
            }
        }
    }

    /// Endpoint packets originate locally and must keep using the uplink route.
    fn check_endpoint_route(&self, peer: &Peer, names: &Names, selected: bool) -> Result<()> {
        let endpoint = peer.endpoint_ip().ok_or_else(|| network_error("endpoint_not_resolved"))?.to_string();
        let mut command = vec!["ip", "-j", "route", "get", endpoint.as_str()];
        if selected {
            command.extend(["mark", MARK]);
        }
        let routes = json::parse(self.run.run(&command)?.stdout.as_bytes())?;
        let dev = routes.as_array().and_then(|r| r.first()).and_then(|r| r.get("dev")).and_then(Value::as_str);
        if dev != Some(names.uplink.as_str()) {
            return Err(network_error("endpoint_route_not_selected_uplink"));
        }
        Ok(())
    }

    fn connect_steps(&self, policy: &Value, profile: &Profile) -> Result<()> {
        if !profile.resolved() {
            // wg would otherwise resolve the name with the system resolver.
            return Err(network_error("endpoint_not_resolved"));
        }
        let (names, selected) = {
            let state = self.state.lock().unwrap();
            (state.names.clone(), state.selected_route)
        };
        let run = &self.run;
        run.optional(&["ip", "link", "delete", "phwg0"])?;
        run.run(&["ip", "link", "add", "phwg0", "type", "wireguard"])?;
        run.input(&["wg", "setconf", "phwg0", "/dev/stdin"], &profile.setconf())?;
        if selected {
            run.run(&["wg", "set", "phwg0", "fwmark", MARK])?;
        }
        run.run(&["ip", "address", "add", &profile.address, "dev", "phwg0"])?;
        run.run(&["ip", "link", "set", "dev", "phwg0", "mtu", &profile.mtu.to_string(), "up"])?;
        run.run(&["ip", "route", "replace", "table", "17700", "default", "dev", "phwg0"])?;
        for (offset, role) in ["ap", "usb"].iter().enumerate() {
            let priority = (17700 + offset).to_string();
            run.optional(&["ip", "rule", "del", "priority", &priority])?;
            run.run(&["ip", "rule", "add", "priority", &priority, "iif", names.get(role), "lookup", "17700"])?;
        }
        run.optional(&["ip", "rule", "del", "priority", "17702"])?;
        run.run(&["ip", "rule", "add", "priority", "17702", "oif", "phwg0", "lookup", "17700"])?;
        for peer in profile.active_peers() {
            self.check_endpoint_route(peer, &names, selected)?;
        }
        self.set_profile(Some(profile.clone()));
        // WG mode sends clients only to phwg0, never plaintext to the uplink.
        self.firewall(policy, Mode::Vpn)
    }

    /// Failover: replace the member in use for `group` with the next
    /// alternate (round robin), leaving the other groups' peers untouched.
    /// The old peer is removed first; keys travel only on stdin. When the
    /// next member's host name does not resolve, the group stays without a
    /// peer (its traffic is dropped) and the error is returned; the next
    /// switch moves on from it.
    pub fn switch_member(&self, group: usize) -> Result<()> {
        let (mode, profile, names, selected) = {
            let state = self.state.lock().unwrap();
            (state.mode, state.profile.clone(), state.names.clone(), state.selected_route)
        };
        let Some(profile) = profile.filter(|p| mode == Mode::Vpn && group < p.groups.len()) else {
            return Err(network_error("vpn_not_connected"));
        };
        let old = profile.active_peer(group).public_key.clone();
        let next = profile.with_member(group, profile.active[group] + 1);
        self.run.optional(&["wg", "set", "phwg0", "peer", &old, "remove"])?;
        let resolved = match self.resolve_member(&next, group) {
            Ok(resolved) => resolved,
            Err(error) => {
                self.set_profile(Some(next));
                return Err(error);
            }
        };
        let peer = resolved.active_peer(group).clone();
        self.set_profile(Some(resolved));
        self.check_endpoint_route(&peer, &names, selected)?;
        self.run.input(&["wg", "addconf", "phwg0", "/dev/stdin"], &peer.block())?;
        Ok(())
    }

    pub fn disconnect(&self, policy: &Value) -> Result<()> {
        self.block(policy)?;
        self.run.optional(&["ip", "link", "delete", "phwg0"])?;
        for priority in ["17700", "17701", "17702"] {
            self.run.optional(&["ip", "rule", "del", "priority", priority])?;
        }
        self.set_profile(None);
        Ok(())
    }

    pub fn direct(&self, policy: &Value) -> Result<()> {
        self.disconnect(policy)?;
        self.firewall(policy, Mode::Direct)
    }

    /// The tunnel profile in use and, per group, the age in seconds of its
    /// active member's latest handshake (None: never, or unreadable). None
    /// outside VPN mode or when `wg` fails.
    pub fn group_handshakes(&self) -> Option<(Profile, Vec<Option<f64>>)> {
        let (mode, profile) = {
            let state = self.state.lock().unwrap();
            (state.mode, state.profile.clone())
        };
        let profile = profile.filter(|_| mode == Mode::Vpn)?;
        let result = self.run.optional(&["wg", "show", "phwg0", "latest-handshakes"]).ok()?;
        if result.code != 0 {
            return None;
        }
        let now = (self.clock)();
        let mut latest = std::collections::HashMap::new();
        for row in py::splitlines(&result.stdout) {
            let fields = py::split_ws(row);
            if fields.len() == 2 {
                if let Ok(at) = fields[1].parse::<i64>() {
                    latest.insert(fields[0].to_string(), at);
                }
            }
        }
        let ages = profile
            .active_peers()
            .iter()
            .map(|peer| latest.get(&peer.public_key).filter(|at| **at > 0).map(|at| now - *at as f64))
            .collect();
        Some((profile, ages))
    }

    /// A handshake at most 180 s old.
    pub fn recent(age: Option<f64>) -> bool {
        age.map(|a| (0.0..=180.0).contains(&a)).unwrap_or(false)
    }

    /// Connected: some member in use has a recent handshake and, when a
    /// group is the Internet exit (AllowedIPs cover everything), that
    /// group's member has one.
    pub fn connected(profile: &Profile, ages: &[Option<f64>]) -> bool {
        let any = ages.iter().any(|a| Runtime::recent(*a));
        match profile.exit_group() {
            Some(group) => any && Runtime::recent(ages[group]),
            None => any,
        }
    }

    /// See `connected`. A failing `wg` reads as "not connected" (Python let
    /// runner exceptions escape here).
    pub fn handshake(&self) -> bool {
        self.group_handshakes().map(|(profile, ages)| Runtime::connected(&profile, &ages)).unwrap_or(false)
    }

    fn read(&self, relative: &str) -> Result<String> {
        Ok(std::fs::read_to_string(self.root.join(relative))?)
    }

    pub fn status(&self) -> Result<Value> {
        let thermal = speedcheck::temperatures_at(&self.root.join("sys/class/thermal"));
        let state = self.state();
        let links = json::parse(self.run.run(&["ip", "-j", "address", "show"])?.stdout.as_bytes())?;
        let mut by_name: Map<String, Value> = Map::new();
        for item in links.as_array().map(Vec::as_slice).unwrap_or(&[]) {
            if let Some(name) = item.get("ifname").and_then(Value::as_str) {
                by_name.insert(name.to_string(), item.clone());
            }
        }
        let link = |name: &str| {
            let item = by_name.get(name);
            let up = item.and_then(|i| i.get("operstate")).and_then(Value::as_str) == Some("UP");
            (up, addr_info(item).iter().any(is_inet))
        };
        let (eth_link, eth_ip) = link(&state.names.uplink);
        let (ap_link, ap_ip) = link(&state.names.ap);
        let (usb_link, usb_ip) = link(&state.names.usb);
        let (ethernet_link, ethernet_ip) = link(&state.ethernet_name);
        let mut available = 0i64;
        for line in py::splitlines(&self.read("proc/meminfo")?) {
            let fields = py::split_ws(line);
            if fields.len() >= 2 && fields[0].trim_end_matches(':') == "MemAvailable" {
                available = fields[1].parse::<i64>().map_err(|_| Error::Invalid("invalid_meminfo".into()))? * 1024;
            }
        }
        let uptime: f64 = py::split_ws(&self.read("proc/uptime")?).first().and_then(|s| s.parse().ok()).ok_or_else(|| Error::Invalid("invalid_uptime".into()))?;
        let ruleset = json::parse(self.run.run(&["nft", "-j", "list", "table", "inet", "phoenix"])?.stdout.as_bytes())?;
        let (mut accepted, mut dropped) = (0i64, 0i64);
        for item in ruleset.get("nftables").and_then(Value::as_array).map(Vec::as_slice).unwrap_or(&[]) {
            let Some(rule) = item.get("rule") else {
                continue;
            };
            if rule.get("chain").and_then(Value::as_str) != Some("forward") {
                continue;
            }
            let expr = rule.get("expr").and_then(Value::as_array).map(Vec::as_slice).unwrap_or(&[]);
            let packets: i64 = expr.iter().filter_map(|e| e.get("counter")).filter(|c| c.is_object()).map(|c| c.get("packets").and_then(Value::as_i64).unwrap_or(0)).sum();
            if expr.iter().any(|e| e.get("accept").is_some()) {
                accepted += packets;
            }
            if expr.iter().any(|e| e.get("drop").is_some()) {
                dropped += packets;
            }
        }
        let wifi = state.uplink_kind == "wifi";
        let temperature = thermal.iter().copied().fold(None, |acc: Option<f64>, t| Some(acc.map_or(t, |a| a.max(t))));
        Ok(json!({
            "uplink": state.uplink_kind, "uplink_ready": eth_link && eth_ip,
            "ethernet_link": ethernet_link, "ethernet_ip": ethernet_ip,
            "wifi_link": wifi && eth_link, "wifi_ip": wifi && eth_ip, "ap_active": ap_link && ap_ip,
            "usb_configured": usb_ip, "usb_mounted": usb_link, "usb_suspended": false,
            "vpn_up": self.handshake(), "direct": state.mode == Mode::Direct,
            "allowed": accepted, "blocked": dropped, "malformed": 0,
            "heap_free": available,
            "temperature_c": temperature.map(|t| py::round(t, 1)),
            "uptime_ms": (uptime * 1000.0) as i64,
            "firewall_enforced": state.enforced, "counter_scope": "current_nft_ruleset",
            "malformed_counter_available": false,
        }))
    }

    /// (exit IPv4, two-letter country) via curl on phwg0.
    pub fn verify_exit(&self) -> Result<(String, String)> {
        if !self.handshake() {
            return Err(network_error("vpn_required_for_exit_check"));
        }
        let result = self.run.run(&[
            "curl", "--interface", "phwg0", "--noproxy", "*", "--connect-timeout", "5", "--max-time", "12",
            "--silent", "--show-error", "--fail", "https://1.1.1.1/cdn-cgi/trace",
        ])?;
        let mut fields: Map<String, Value> = Map::new();
        for line in py::splitlines(&result.stdout) {
            if let Some((key, value)) = line.split_once('=') {
                fields.insert(key.to_string(), json!(value));
            }
        }
        let address = ipv4::address(fields.get("ip").and_then(Value::as_str).unwrap_or(""))?.to_string();
        let country = fields.get("loc").and_then(Value::as_str).unwrap_or("");
        if country.len() != 2 || !country.bytes().all(|b| b.is_ascii_uppercase()) {
            return Err(network_error("exit_check_failed"));
        }
        Ok((address, country.to_string()))
    }

    pub fn nord_request(&self, path: &str, token: Option<&str>) -> Result<Value> {
        let (uplink, selected) = {
            let state = self.state.lock().unwrap();
            (state.names.uplink.clone(), state.selected_route)
        };
        let mark = if selected { 0x5048 } else { 0 };
        let transport = self.transport.clone();
        nord::get(path, token, &move |path, headers| transport(path, headers, &uplink, mark))
    }

    pub fn select_uplink(&self, policy: &Value, name: &str, kind: &str, gateway: Option<&str>, ap_name: Option<&str>) -> Result<()> {
        let name = interface(name)?;
        if kind != "ethernet" && kind != "wifi" {
            return invalid("invalid_uplink");
        }
        let mut candidate = self.names();
        candidate.uplink = name.clone();
        if let Some(ap) = ap_name {
            candidate.ap = interface(ap)?;
        }
        if !candidate.distinct() {
            return invalid("conflicting_interface_roles");
        }
        self.block(policy)?;
        let run = &self.run;
        let addresses = json::parse(run.run(&["ip", "-j", "address", "show", "dev", &name])?.stdout.as_bytes())?;
        let first = addresses
            .as_array()
            .map(Vec::as_slice)
            .unwrap_or(&[])
            .iter()
            .flat_map(|entry| addr_info(Some(entry)).iter())
            .find(|a| is_inet(a))
            .cloned()
            .ok_or_else(|| network_error("uplink_has_no_address"))?;
        let part = |key: &str| match first.get(key) {
            Some(Value::String(s)) => Ok(s.clone()),
            Some(Value::Number(n)) => Ok(n.to_string()),
            _ => invalid("invalid_address"),
        };
        let address = ipv4::interface(&format!("{}/{}", part("local")?, part("prefixlen")?))?;
        let gateway = match gateway {
            Some(g) => g.to_string(),
            None => {
                let defaults = json::parse(run.run(&["ip", "-j", "route", "show", "default", "dev", &name])?.stdout.as_bytes())?;
                defaults
                    .as_array()
                    .map(Vec::as_slice)
                    .unwrap_or(&[])
                    .iter()
                    .find_map(|r| r.get("gateway").and_then(Value::as_str).filter(|g| !g.is_empty()).map(str::to_string))
                    .ok_or_else(|| network_error("uplink_has_no_gateway"))?
            }
        };
        let gateway = ipv4::address(&gateway)?.to_string();
        run.optional(&["ip", "route", "flush", "table", "17710"])?;
        let ip = address.ip.to_string();
        run.run(&["ip", "route", "add", "table", "17710", &address.network().to_string(), "dev", &name, "src", &ip])?;
        run.run(&["ip", "route", "add", "table", "17710", "default", "via", &gateway, "dev", &name])?;
        for priority in ["17690", "17691", "17710", "17711"] {
            run.optional(&["ip", "rule", "del", "priority", priority])?;
        }
        run.run(&["ip", "rule", "add", "priority", "17690", "fwmark", MARK, "lookup", "17710"])?;
        // Native clients bound to the selected uplink need its routing table too.
        run.run(&["ip", "rule", "add", "priority", "17691", "oif", &name, "lookup", "17710"])?;
        for (offset, role) in ["ap", "usb"].iter().enumerate() {
            run.run(&["ip", "rule", "add", "priority", &(17710 + offset).to_string(), "iif", candidate.get(role), "lookup", "17710"])?;
        }
        {
            let mut state = self.state.lock().unwrap();
            state.names = candidate;
            state.uplink_kind = kind.to_string();
            state.selected_route = true;
        }
        self.block(policy)
    }
}

#[cfg(test)]
pub mod tests {
    use super::*;
    use crate::fsutil::testdir::TempDir;
    use crate::runner::{exit, ok, FakeRunner, Output, Runner};
    use crate::wireguard::parse;
    use base64::Engine;

    pub fn key() -> String {
        base64::engine::general_purpose::STANDARD.encode((0u8..32).collect::<Vec<u8>>())
    }

    pub fn profile_text() -> String {
        let key = key();
        format!("[Interface]\nPrivateKey={key}\nAddress=10.5.0.2/32\nDNS=103.86.96.100\n[Peer]\nPublicKey={key}\nEndpoint=192.0.2.1:51820\nAllowedIPs=0.0.0.0/0\n")
    }

    pub fn names() -> Value {
        json!({"ap": "wlan0", "usb": "usb0", "uplink": "end0", "vpn": "phwg0"})
    }

    pub fn base() -> Value {
        json!({"revision": 0, "default_allow": true, "rules": [], "forwards": []})
    }

    pub fn clock(now: f64) -> Clock {
        Arc::new(move || now)
    }

    /// test_runtime.FakeRunner equivalent; `fail` argv returns exit 1.
    pub fn fake(fail: Option<Vec<&'static str>>) -> Arc<FakeRunner> {
        let key = key();
        Arc::new(FakeRunner::with(move |argv, _| {
            if let Some(fail) = &fail {
                if argv.iter().map(String::as_str).eq(fail.iter().copied()) {
                    return exit(1);
                }
            }
            if argv.len() >= 4 && argv[..4] == ["ip", "-j", "route", "get"] {
                return ok(r#"[{"dev":"end0"}]"#);
            }
            if argv.len() >= 3 && argv[..3] == ["wg", "show", "phwg0"] {
                return ok(&format!("{key}\t1000\n"));
            }
            ok("")
        }))
    }

    fn runtime(runner: Arc<FakeRunner>, now: f64) -> Runtime {
        Runtime::new(&names(), runner, clock(now)).unwrap()
    }

    #[test]
    fn rejects_bad_assignments() {
        let runner: SharedRunner = Arc::new(FakeRunner::new());
        assert!(Runtime::new(&json!({"ap": "a", "usb": "a", "uplink": "c", "vpn": "phwg0"}), runner.clone(), clock(0.0)).is_err());
        assert!(Runtime::new(&json!({"ap": "a", "usb": "b", "uplink": "c", "vpn": "wg0"}), runner.clone(), clock(0.0)).is_err());
        assert!(Runtime::new(&json!({"ap": "a", "usb": "b", "uplink": "c\"", "vpn": "phwg0"}), runner, clock(0.0)).is_err());
    }

    #[test]
    fn connect_blocks_first_and_keeps_keys_out_of_argv() {
        let runner = fake(None);
        let rt = runtime(runner.clone(), 1010.0);
        rt.connect(&base(), &parse(&profile_text()).unwrap()).unwrap();
        let calls = runner.calls.lock().unwrap().clone();
        assert_eq!(calls[0].argv, ["nft", "list", "table", "inet", "phoenix"]);
        assert_eq!(calls[2].argv, ["nft", "-f", "-"]);
        assert!(!calls[2].input.as_ref().unwrap().contains("counter accept"));
        assert!(rt.handshake());
        assert_eq!(rt.mode(), Mode::Vpn);
        assert!(rt.enforced());
        assert!(calls.iter().all(|c| !c.argv.join(" ").contains(&key())));
        let setconf = calls.iter().find(|c| c.argv[0] == "wg").unwrap();
        assert_eq!(setconf.argv, ["wg", "setconf", "phwg0", "/dev/stdin"]);
        assert!(setconf.input.as_ref().unwrap().contains("PrivateKey"));
        let argvs: Vec<String> = calls.iter().map(|c| c.argv.join(" ")).collect();
        let expected = [
            "ip link delete phwg0",
            "ip link add phwg0 type wireguard",
            "wg setconf phwg0 /dev/stdin",
            "ip address add 10.5.0.2/32 dev phwg0",
            "ip link set dev phwg0 mtu 1380 up",
            "ip route replace table 17700 default dev phwg0",
            "ip rule del priority 17700",
            "ip rule add priority 17700 iif wlan0 lookup 17700",
            "ip rule del priority 17701",
            "ip rule add priority 17701 iif usb0 lookup 17700",
            "ip rule del priority 17702",
            "ip rule add priority 17702 oif phwg0 lookup 17700",
            "ip -j route get 192.0.2.1",
            "nft list table inet phoenix",
        ];
        let start = argvs.iter().position(|a| a == "ip link delete phwg0").unwrap();
        assert_eq!(argvs[start..start + expected.len()], expected);
        assert_eq!(argvs[3..7], ["conntrack -D -f ipv4 -s 192.168.7.0/24", "conntrack -D -f ipv4 -d 192.168.7.0/24", "conntrack -D -f ipv4 -s 192.168.9.0/24", "conntrack -D -f ipv4 -d 192.168.9.0/24"]);
        let last = calls.last().unwrap();
        assert!(last.input.as_ref().unwrap().contains("masquerade"));
    }

    /// Host-name endpoints: resolved by the injected DoH resolver on the
    /// uplink (mark only with a selected route), never handed to wg.
    #[test]
    fn hostname_endpoint_is_resolved_on_the_uplink() {
        let key = key();
        let text = format!("[Interface]\nPrivateKey={key}\nAddress=10.5.0.2/32\n[Peer]\nPublicKey={key}\nEndpoint=vpn.example.org:51821\nAllowedIPs=0.0.0.0/0\n");
        let profile = parse(&text).unwrap();
        let seen = Arc::new(Mutex::new(Vec::new()));
        let s = seen.clone();
        let runner = fake(None);
        let rt = runtime(runner.clone(), 1010.0).with_resolver(Arc::new(move |name, device, mark| {
            s.lock().unwrap().push((name.to_string(), device.to_string(), mark));
            Ok(std::net::Ipv4Addr::new(192, 0, 2, 1))
        }));
        // Never connects with the name: wg would use the system resolver.
        assert_eq!(rt.connect(&base(), &profile).unwrap_err().code(), "endpoint_not_resolved");
        assert!(runner.calls.lock().unwrap().iter().all(|c| c.argv[0] != "wg"));
        assert_eq!(rt.mode(), Mode::Blocked);
        let resolved = rt.resolve_endpoint(&profile).unwrap();
        assert_eq!((resolved.primary().endpoint.as_str(), resolved.primary().endpoint_name.as_str()), ("192.0.2.1:51821", "vpn.example.org"));
        rt.connect(&base(), &resolved).unwrap();
        let calls = runner.calls.lock().unwrap().clone();
        let setconf = calls.iter().find(|c| c.argv[0] == "wg").unwrap().input.clone().unwrap();
        assert!(setconf.contains("Endpoint = 192.0.2.1:51821\n") && !setconf.contains("example"), "{setconf}");
        assert!(calls.iter().any(|c| c.argv.join(" ") == "ip -j route get 192.0.2.1"));
        rt.state.lock().unwrap().selected_route = true;
        rt.resolve_endpoint(&profile).unwrap();
        assert_eq!(seen.lock().unwrap().clone(), vec![("vpn.example.org".to_string(), "end0".to_string(), 0), ("vpn.example.org".to_string(), "end0".to_string(), 0x5048)]);
        let numeric = parse(&profile_text()).unwrap();
        assert_eq!(rt.resolve_endpoint(&numeric).unwrap(), numeric, "numeric endpoints need no lookup");
        assert_eq!(seen.lock().unwrap().len(), 2);
        let failing = runtime(fake(None), 0.0).with_resolver(Arc::new(|_, _, _| Err(Error::Network("boom".into()))));
        assert_eq!(failing.resolve_endpoint(&profile).unwrap_err().code(), "endpoint_resolution_failed");
    }

    /// Split AllowedIPs reach wg verbatim; Phoenix still sends every client
    /// packet into phwg0 (kill switch), so the rest is dropped, not leaked.
    #[test]
    fn split_allowed_ips_keep_the_kill_switch() {
        let key = key();
        let text = format!("[Interface]\nPrivateKey={key}\nAddress=10.5.0.2/32,fd00::2/128\nDNS=10.0.0.1,9.9.9.9\nPostUp=touch /tmp/never\n[Peer]\nPublicKey={key}\nEndpoint=192.0.2.1:51820\nAllowedIPs=10.0.0.0/24, 192.168.50.0/24, ::/0\n");
        let runner = fake(None);
        let rt = runtime(runner.clone(), 1010.0);
        rt.connect(&base(), &parse(&text).unwrap()).unwrap();
        let calls = runner.calls.lock().unwrap().clone();
        let setconf = calls.iter().find(|c| c.argv[0] == "wg").unwrap().input.clone().unwrap();
        assert!(setconf.contains("AllowedIPs = 10.0.0.0/24, 192.168.50.0/24\n"), "{setconf}");
        let argvs: Vec<String> = calls.iter().map(|c| c.argv.join(" ")).collect();
        assert!(argvs.contains(&"ip route replace table 17700 default dev phwg0".to_string()));
        assert!(argvs.contains(&"ip address add 10.5.0.2/32 dev phwg0".to_string()));
        assert!(argvs.iter().all(|a| !a.contains("touch") && !a.contains("fd00")), "{argvs:?}");
        assert_eq!(rt.mode(), Mode::Vpn);
    }

    /// Multi-peer profile: exit failover group (two 0.0.0.0/0 alternates, the
    /// second with a host name and a preshared key) plus a site group.
    pub fn multi_peer_text() -> String {
        let key = key();
        let peer = |n: u8| base64::engine::general_purpose::STANDARD.encode([n; 32]);
        let psk = base64::engine::general_purpose::STANDARD.encode([9u8; 32]);
        format!(
            "[Interface]\nPrivateKey={key}\nAddress=10.5.0.2/32\nDNS=10.88.0.1\n\
             [Peer]\nPublicKey={}\nEndpoint=192.0.2.1:51820\nAllowedIPs=0.0.0.0/0\nPersistentKeepalive=25\n\
             [Peer]\nPublicKey={}\nEndpoint=site.example.org:51822\nAllowedIPs=10.88.0.0/24\n\
             [Peer]\nPublicKey={}\nPresharedKey={psk}\nEndpoint=backup.example.org:51821\nAllowedIPs=0.0.0.0/0\nPersistentKeepalive=25\n",
            peer(1),
            peer(2),
            peer(3)
        )
    }

    /// Handshakes per public key (epoch seconds; 0 = never).
    fn multi_fake(handshakes: Arc<Mutex<Vec<(String, i64)>>>) -> Arc<FakeRunner> {
        Arc::new(FakeRunner::with(move |argv, _| {
            if argv.len() >= 4 && argv[..4] == ["ip", "-j", "route", "get"] {
                return ok(r#"[{"dev":"end0"}]"#);
            }
            if argv.len() >= 3 && argv[..3] == ["wg", "show", "phwg0"] {
                return ok(&handshakes.lock().unwrap().iter().map(|(k, at)| format!("{k}\t{at}\n")).collect::<String>());
            }
            ok("")
        }))
    }

    #[test]
    fn multi_peer_connect_switch_and_handshakes() {
        let peer = |n: u8| base64::engine::general_purpose::STANDARD.encode([n; 32]);
        let psk = base64::engine::general_purpose::STANDARD.encode([9u8; 32]);
        let handshakes = Arc::new(Mutex::new(vec![(peer(1), 0), (peer(2), 1000)]));
        let runner = multi_fake(handshakes.clone());
        let lookups = Arc::new(Mutex::new(Vec::new()));
        let l = lookups.clone();
        let rt = runtime(runner.clone(), 1010.0).with_resolver(Arc::new(move |name, _, _| {
            l.lock().unwrap().push(name.to_string());
            Ok(if name == "site.example.org" { std::net::Ipv4Addr::new(192, 0, 2, 22) } else { std::net::Ipv4Addr::new(192, 0, 2, 21) })
        }));
        let profile = rt.resolve_endpoint(&parse(&multi_peer_text()).unwrap()).unwrap();
        assert_eq!(lookups.lock().unwrap().clone(), vec!["site.example.org"], "only members in use are resolved");
        rt.connect(&base(), &profile).unwrap();
        let calls = runner.calls.lock().unwrap().clone();
        let setconf = calls.iter().find(|c| c.argv[..2] == ["wg", "setconf"]).unwrap().input.clone().unwrap();
        assert_eq!(setconf.matches("[Peer]").count(), 2, "one member per group: {setconf}");
        assert!(setconf.contains(&peer(1)) && setconf.contains(&peer(2)) && !setconf.contains(&peer(3)));
        let routes: Vec<String> = calls.iter().map(|c| c.argv.join(" ")).filter(|a| a.starts_with("ip -j route get")).collect();
        assert_eq!(routes, ["ip -j route get 192.0.2.1", "ip -j route get 192.0.2.22"], "every endpoint in use stays on the uplink");

        // Site group up, exit member without handshake: not connected.
        let (_, ages) = rt.group_handshakes().unwrap();
        assert_eq!(ages, vec![None, Some(10.0)]);
        assert!(!rt.handshake());

        runner.calls.lock().unwrap().clear();
        rt.switch_member(0).unwrap();
        let calls = runner.calls.lock().unwrap().clone();
        let argvs: Vec<String> = calls.iter().map(|c| c.argv.join(" ")).collect();
        assert_eq!(argvs, [format!("wg set phwg0 peer {} remove", peer(1)), "ip -j route get 192.0.2.21".to_string(), "wg addconf phwg0 /dev/stdin".to_string()]);
        let added = calls[2].input.clone().unwrap();
        assert!(added.contains(&peer(3)) && added.contains(&format!("PresharedKey = {psk}")) && added.contains("Endpoint = 192.0.2.21:51821"), "{added}");
        assert!(argvs.iter().all(|a| !a.contains(&psk) && !a.contains(&key())), "no secrets in argv");
        assert!(argvs.iter().all(|a| !a.contains(&peer(2))), "the site group is untouched");
        assert_eq!(lookups.lock().unwrap().last().unwrap(), "backup.example.org", "resolved again at the switch");
        let current = rt.profile().unwrap();
        assert_eq!(current.primary().public_key, peer(3));

        handshakes.lock().unwrap().push((peer(3), 1005));
        assert!(rt.handshake(), "exit alternate and site both up");
        handshakes.lock().unwrap()[1].1 = 0;
        assert!(rt.handshake(), "a failing site group does not disconnect the exit");

        // Round robin back to the first member.
        rt.switch_member(0).unwrap();
        assert_eq!(rt.profile().unwrap().primary().public_key, peer(1));

        // Unresolvable alternate: group left without a peer, next switch moves on.
        let failing = runtime(multi_fake(handshakes.clone()), 1010.0).with_resolver(Arc::new(|name, _, _| {
            if name == "backup.example.org" { Err(Error::Network("down".into())) } else { Ok(std::net::Ipv4Addr::new(192, 0, 2, 22)) }
        }));
        let profile = failing.resolve_endpoint(&parse(&multi_peer_text()).unwrap()).unwrap();
        failing.connect(&base(), &profile).unwrap();
        assert_eq!(failing.switch_member(0).unwrap_err().code(), "endpoint_resolution_failed");
        assert_eq!(failing.profile().unwrap().active, vec![1, 0]);
        failing.switch_member(0).unwrap();
        assert_eq!(failing.profile().unwrap().active, vec![0, 0]);
        failing.disconnect(&base()).unwrap();
        assert_eq!(failing.switch_member(0).unwrap_err().code(), "vpn_not_connected");
    }

    #[test]
    fn failure_does_not_enable_direct() {
        let runner = fake(Some(vec!["ip", "link", "add", "phwg0", "type", "wireguard"]));
        let rt = runtime(runner.clone(), 1010.0);
        assert!(matches!(rt.connect(&base(), &parse(&profile_text()).unwrap()), Err(Error::Network(_))));
        assert_eq!(rt.mode(), Mode::Blocked);
        assert!(rt.profile().is_none());
        let calls = runner.calls.lock().unwrap();
        assert!(calls.iter().filter(|c| c.argv[0] == "nft").all(|c| !c.input.as_deref().unwrap_or("").contains("masquerade")));
        assert_eq!(calls.last().unwrap().argv, ["ip", "link", "delete", "phwg0"]);
    }

    #[test]
    fn endpoint_route_must_use_uplink() {
        let runner = Arc::new(FakeRunner::with(|argv, _| if argv.len() >= 4 && argv[..4] == ["ip", "-j", "route", "get"] { ok(r#"[{"dev":"wlan9"}]"#) } else { ok("") }));
        let rt = runtime(runner, 1010.0);
        assert_eq!(rt.connect(&base(), &parse(&profile_text()).unwrap()).unwrap_err().code(), "endpoint_route_not_selected_uplink");
        assert_eq!(rt.mode(), Mode::Blocked);
    }

    #[test]
    fn stale_handshake_not_connected() {
        let rt = runtime(fake(None), 1500.0);
        rt.connect(&base(), &parse(&profile_text()).unwrap()).unwrap();
        assert!(!rt.handshake());
        let rt = runtime(fake(None), 999.0);
        rt.connect(&base(), &parse(&profile_text()).unwrap()).unwrap();
        assert!(!rt.handshake(), "handshake in the future");
        let rt = runtime(fake(None), 1010.0);
        assert!(!rt.handshake(), "no profile");
    }

    #[test]
    fn exit_check_is_bound_and_has_no_fallback() {
        let inner = fake(None);
        let runner = Arc::new(FakeRunner::with(move |argv, input| {
            if argv[0] == "curl" {
                return ok("fl=1\nip=203.0.113.9\nloc=IT\n");
            }
            let refs: Vec<&str> = argv.iter().map(String::as_str).collect();
            Some(inner.exec(&refs, input, true).unwrap_or(Output::default()))
        }));
        let rt = runtime(runner.clone(), 1010.0);
        assert!(rt.verify_exit().is_err(), "VPN required");
        rt.connect(&base(), &parse(&profile_text()).unwrap()).unwrap();
        assert_eq!(rt.verify_exit().unwrap(), ("203.0.113.9".to_string(), "IT".to_string()));
        let command = runner.argvs().last().unwrap().clone();
        assert_eq!(command[command.iter().position(|a| a == "--interface").unwrap() + 1], "phwg0");
        assert!(command.contains(&"--noproxy".to_string()));
    }

    #[test]
    fn disconnect_and_direct() {
        let runner = fake(None);
        let rt = runtime(runner.clone(), 1010.0);
        rt.connect(&base(), &parse(&profile_text()).unwrap()).unwrap();
        runner.clear();
        rt.direct(&base()).unwrap();
        assert_eq!(rt.mode(), Mode::Direct);
        assert!(rt.profile().is_none());
        let argvs: Vec<String> = runner.argvs().iter().map(|a| a.join(" ")).collect();
        assert!(argvs.contains(&"ip link delete phwg0".to_string()));
        assert!(argvs.contains(&"ip rule del priority 17702".to_string()));
        let last = runner.calls.lock().unwrap().last().unwrap().clone();
        assert!(last.input.unwrap().contains("oifname \"end0\" ip saddr { 192.168.7.0/24, 192.168.9.0/24 } masquerade"));
    }

    #[test]
    fn conntrack_errors_are_fatal() {
        let runner = Arc::new(FakeRunner::with(|argv, _| if argv[0] == "conntrack" { exit(2) } else { ok("") }));
        assert_eq!(runtime(runner, 0.0).block(&base()).unwrap_err().code(), "conntrack_cleanup_failed");
        let runner = Arc::new(FakeRunner::with(|argv, _| if argv[0] == "conntrack" { exit(1) } else { ok("") }));
        runtime(runner, 0.0).block(&base()).unwrap();
    }

    #[test]
    fn existing_table_is_replaced() {
        let runner = Arc::new(FakeRunner::with(|argv, _| if argv[..2] == ["nft", "list"] { exit(1) } else { ok("") }));
        let rt = runtime(runner.clone(), 0.0);
        rt.block(&base()).unwrap();
        assert!(!runner.calls.lock().unwrap()[1].input.as_ref().unwrap().starts_with("delete table"));
        let runner = fake(None);
        runtime(runner.clone(), 0.0).block(&base()).unwrap();
        assert!(runner.calls.lock().unwrap()[1].input.as_ref().unwrap().starts_with("delete table inet phoenix\n"));
    }

    #[test]
    fn status_fields_match_ui_contract() {
        let tmp = TempDir::new();
        std::fs::create_dir_all(tmp.path().join("proc")).unwrap();
        std::fs::create_dir_all(tmp.path().join("sys/class/thermal/thermal_zone0")).unwrap();
        std::fs::write(tmp.path().join("proc/meminfo"), "MemTotal: 2000 kB\nMemAvailable: 1000 kB\nHugePages_Total:       0\n").unwrap();
        std::fs::write(tmp.path().join("proc/uptime"), "100.25 0.00\n").unwrap();
        std::fs::write(tmp.path().join("sys/class/thermal/thermal_zone0/temp"), "47250\n").unwrap();
        let links = r#"[{"ifname":"end0","operstate":"UP","addr_info":[{"family":"inet","local":"192.0.2.10"}]},{"ifname":"wlan0","operstate":"UP","addr_info":[{"family":"inet6"}]},{"ifname":"usb0","operstate":"DOWN","addr_info":[{"family":"inet"}]}]"#;
        let ruleset = r#"{"nftables":[{"metainfo":{}},{"rule":{"chain":"forward","expr":[{"counter":{"packets":5,"bytes":1}},{"accept":null}]}},{"rule":{"chain":"forward","expr":[{"counter":{"packets":3}},{"drop":null}]}},{"rule":{"chain":"prerouting","expr":[{"counter":{"packets":9}},{"accept":null}]}}]}"#;
        let runner = Arc::new(FakeRunner::with(move |argv, _| match argv[..2].join(" ").as_str() {
            "ip -j" => ok(links),
            "nft -j" => ok(ruleset),
            _ => ok(""),
        }));
        let rt = runtime(runner, 0.0).with_root(tmp.path());
        let status = rt.status().unwrap();
        let expected = json!({
            "uplink": "ethernet", "uplink_ready": true, "ethernet_link": true, "ethernet_ip": true,
            "wifi_link": false, "wifi_ip": false, "ap_active": false,
            "usb_configured": true, "usb_mounted": false, "usb_suspended": false,
            "vpn_up": false, "direct": false, "allowed": 5, "blocked": 3, "malformed": 0,
            "heap_free": 1024000, "temperature_c": 47.3, "uptime_ms": 100250,
            "firewall_enforced": false, "counter_scope": "current_nft_ruleset", "malformed_counter_available": false,
        });
        assert_eq!(status, expected);
        let keys: Vec<&String> = status.as_object().unwrap().keys().collect();
        assert_eq!(keys, expected.as_object().unwrap().keys().collect::<Vec<_>>());
        std::fs::remove_file(tmp.path().join("sys/class/thermal/thermal_zone0/temp")).unwrap();
        assert!(rt.status().unwrap()["temperature_c"].is_null());
    }

    #[test]
    fn selected_uplink_uses_separate_route_table() {
        let runner = Arc::new(FakeRunner::with(|argv, _| {
            if argv.len() >= 3 && argv[..3] == ["ip", "-j", "address"] {
                ok(r#"[{"addr_info":[{"family":"inet6"},{"family":"inet","local":"192.0.2.10","prefixlen":24}]}]"#)
            } else if argv.len() >= 4 && argv[..4] == ["ip", "-j", "route", "show"] {
                ok(r#"[{"dst":"default","gateway":"192.0.2.254"}]"#)
            } else {
                ok("")
            }
        }));
        let rt = runtime(runner.clone(), 0.0);
        rt.select_uplink(&base(), "wlan1", "wifi", Some("192.0.2.1"), None).unwrap();
        assert_eq!(rt.mode(), Mode::Blocked);
        assert_eq!(rt.names().uplink, "wlan1");
        assert_eq!(rt.state().uplink_kind, "wifi");
        assert_eq!(rt.state().ethernet_name, "end0");
        assert!(rt.selected_route());
        let calls: Vec<String> = runner.argvs().iter().map(|a| a.join(" ")).collect();
        for expected in [
            "ip route add table 17710 192.0.2.0/24 dev wlan1 src 192.0.2.10",
            "ip route add table 17710 default via 192.0.2.1 dev wlan1",
            "ip rule add priority 17690 fwmark 0x5048 lookup 17710",
            "ip rule add priority 17691 oif wlan1 lookup 17710",
            "ip rule add priority 17710 iif wlan0 lookup 17710",
            "ip rule add priority 17711 iif usb0 lookup 17710",
        ] {
            assert!(calls.contains(&expected.to_string()), "{expected}");
        }
        assert!(!calls.iter().any(|c| c.contains("main")));
        runner.clear();
        rt.select_uplink(&base(), "end0", "ethernet", None, Some("phapoff")).unwrap();
        assert!(runner.argvs().iter().any(|a| a.join(" ") == "ip route add table 17710 default via 192.0.2.254 dev end0"));
        assert_eq!(rt.names().ap, "phapoff");
        assert!(rt.select_uplink(&base(), "usb0", "ethernet", None, None).is_err(), "role conflict");
        assert!(rt.select_uplink(&base(), "x", "cellular", None, None).is_err());
        // Selected route marks the tunnel and the endpoint lookup.
        let runner = fake(None);
        let rt = runtime(runner.clone(), 1010.0);
        rt.state.lock().unwrap().selected_route = true;
        rt.connect(&base(), &parse(&profile_text()).unwrap()).unwrap();
        let calls: Vec<String> = runner.argvs().iter().map(|a| a.join(" ")).collect();
        assert!(calls.contains(&"wg set phwg0 fwmark 0x5048".to_string()));
        assert!(calls.contains(&"ip -j route get 192.0.2.1 mark 0x5048".to_string()));
    }

    #[test]
    fn select_uplink_requires_address_and_gateway() {
        let runner = Arc::new(FakeRunner::with(|_, _| ok("[]")));
        assert_eq!(runtime(runner, 0.0).select_uplink(&base(), "wlan1", "wifi", None, None).unwrap_err().code(), "uplink_has_no_address");
        let runner = Arc::new(FakeRunner::with(|argv, _| {
            if argv.len() >= 3 && argv[..3] == ["ip", "-j", "address"] {
                ok(r#"[{"addr_info":[{"family":"inet","local":"192.0.2.10","prefixlen":24}]}]"#)
            } else {
                ok("[]")
            }
        }));
        assert_eq!(runtime(runner, 0.0).select_uplink(&base(), "wlan1", "wifi", None, None).unwrap_err().code(), "uplink_has_no_gateway");
    }

    /// Real nft/ip/wg/conntrack in an isolated container: tools/rust-kernel-tests.sh.
    #[test]
    #[ignore = "needs an isolated Docker container with NET_ADMIN"]
    fn kernel_transitions_in_isolated_container() {
        use crate::runner::SystemRunner;
        assert!(Path::new("/.dockerenv").exists(), "never run on a host or target");
        let system = SystemRunner::new().unwrap();
        for name in ["aptest", "usbtest"] {
            system.optional(&["ip", "link", "add", name, "type", "dummy"]).unwrap();
            system.run(&["ip", "link", "set", name, "up"]).unwrap();
        }
        let policy = json!({"revision": 0, "default_allow": true,
            "rules": [{"name": "Deny HTTPS", "enabled": true, "allow": false, "ingress": "ap", "protocol": 6,
                       "source": "192.168.9.0/24", "destination": "0.0.0.0/0", "port_first": 443, "port_last": 443}],
            "forwards": [{"name": "Test", "enabled": true, "vpn": false, "protocol": 6, "external_port": 8080,
                          "internal_port": 80, "target": "192.168.9.2/32", "source": "0.0.0.0/0"}]});
        let names = json!({"ap": "aptest", "usb": "usbtest", "uplink": "eth0", "vpn": "phwg0"});
        let rt = Runtime::new(&names, Arc::new(system), crate::py::wall_clock()).unwrap();
        rt.block(&policy).unwrap();
        rt.direct(&policy).unwrap();
        let ruleset = rt.run.run(&["nft", "list", "table", "inet", "phoenix"]).unwrap().stdout;
        assert!(ruleset.contains("masquerade") && ruleset.contains("dnat ip to 192.168.9.2:80"), "{ruleset}");
        let private = rt.run.run(&["wg", "genkey"]).unwrap().stdout.trim().to_string();
        let public = rt.run.input(&["wg", "pubkey"], &private).unwrap().stdout.trim().to_string();
        let profile = parse(&format!("[Interface]\nPrivateKey={private}\nAddress=10.77.0.2/32\nDNS=1.1.1.1\n[Peer]\nPublicKey={public}\nEndpoint=192.0.2.1:51820\nAllowedIPs=0.0.0.0/0\n")).unwrap();
        rt.connect(&policy, &profile).unwrap();
        assert_eq!(rt.mode(), Mode::Vpn);
        assert!(!rt.handshake(), "no real peer exists in this test");
        let status = rt.status().unwrap();
        assert_eq!(status["firewall_enforced"], true);
        assert_eq!(status["uplink_ready"], true, "{status}");
        assert!(status["heap_free"].as_i64().unwrap() > 0);
        let rules = rt.run.run(&["ip", "rule", "show"]).unwrap().stdout;
        assert!(rules.contains("17700") && rules.contains("17702"), "{rules}");
        rt.direct(&policy).unwrap();
        assert_eq!(rt.mode(), Mode::Direct);
        assert!(rt.run.optional(&["ip", "link", "show", "phwg0"]).unwrap().code != 0, "tunnel removed");
        rt.select_uplink(&policy, "eth0", "ethernet", None, None).unwrap();
        assert!(rt.selected_route());
        let table = rt.run.run(&["ip", "route", "show", "table", "17710"]).unwrap().stdout;
        assert!(table.contains("default via"), "{table}");
        rt.connect(&policy, &profile).unwrap();
        let mark = rt.run.run(&["wg", "show", "phwg0", "fwmark"]).unwrap().stdout;
        assert_eq!(mark.trim(), "0x5048");
        rt.disconnect(&policy).unwrap();
        assert_eq!(rt.mode(), Mode::Blocked);
        let blocked = rt.run.run(&["nft", "list", "table", "inet", "phoenix"]).unwrap().stdout;
        assert!(!blocked.contains("masquerade") && !blocked.contains(" accept\n"), "{blocked}");
    }

    #[test]
    fn nord_request_uses_selected_uplink_and_mark() {
        let seen = Arc::new(Mutex::new(Vec::new()));
        let s = seen.clone();
        let rt = runtime(fake(None), 0.0).with_nord_transport(Arc::new(move |path, headers, device, mark| {
            s.lock().unwrap().push((path.to_string(), headers.len(), device.to_string(), mark));
            Ok(json!([1]))
        }));
        assert_eq!(rt.nord_request("/v1/servers/countries", None).unwrap(), json!([1]));
        rt.state.lock().unwrap().selected_route = true;
        rt.nord_request("/v1/users/services/credentials", Some("tok")).unwrap();
        assert_eq!(seen.lock().unwrap().clone(), vec![("/v1/servers/countries".to_string(), 1, "end0".to_string(), 0), ("/v1/users/services/credentials".to_string(), 2, "end0".to_string(), 0x5048)]);
        let failing = runtime(fake(None), 0.0).with_nord_transport(Arc::new(|_, _, _, _| Err(Error::Network("boom".into()))));
        assert_eq!(failing.nord_request("/v1/x", None).unwrap_err().code(), "nord_api_failed");
    }
}
