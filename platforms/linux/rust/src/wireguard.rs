//! Script-free WireGuard profile parsing for Phoenix's IPv4 dataplane.
//!
//! Accepts ordinary wg / wg-quick client configurations: one [Interface] and
//! 1..=16 [Peer] sections, case-insensitive names, repeated or
//! comma-separated Address, DNS and AllowedIPs, hostname endpoints (resolved
//! later over the selected uplink, never by the system resolver). Peers with
//! identical IPv4 AllowedIPs form a failover group (one member in use at a
//! time); different groups are used together, like wg-quick. IPv6 parts and wg-quick options
//! (PostUp, Table, ...) are ignored and reported as notes: nothing in a
//! profile is ever executed. Profiles accepted by the original strict parser
//! (wireguard.py) parse to identical values and `setconf()` text.
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

/// Largest accepted profile. The HTTP API caps JSON bodies at 16 KiB, so an
/// 8 KiB profile still fits once JSON-escaped; real profiles are < 2 KiB.
pub const MAX_PROFILE: usize = 8192;
const MAX_LINE: usize = 2048;
const DEFAULT_DNS: &str = "1.1.1.1";
const MAX_DNS: usize = 3;
/// wg-quick options with no meaning for Phoenix: accepted, never applied.
const IGNORED_INTERFACE: [&str; 8] = ["listenport", "fwmark", "table", "saveconfig", "preup", "postup", "predown", "postdown"];

/// Non-secret remarks about how a profile is used (API `profile_notes`).
pub const NOTE_IGNORED_IPV6: &str = "ignored_ipv6";
pub const NOTE_IGNORED_HOOKS: &str = "ignored_hooks";
pub const NOTE_DNS_FALLBACK: &str = "dns_fallback";
pub const NOTE_DNS_SEARCH_IGNORED: &str = "dns_search_ignored";
pub const NOTE_DNS_TRUNCATED: &str = "dns_truncated";
pub const NOTE_SPLIT_ALLOWED_IPS: &str = "split_allowed_ips";
pub const NOTE_EXTRA_ADDRESSES: &str = "extra_addresses";
pub const NOTE_HOSTNAME_ENDPOINT: &str = "hostname_endpoint";
pub const NOTE_DNS_OUTSIDE_ALLOWED_IPS: &str = "dns_outside_allowed_ips";
pub const NOTE_MULTIPLE_PEERS: &str = "multiple_peers";
/// Most [Peer] sections in one profile.
pub const MAX_PEERS: usize = 16;

#[derive(Clone, PartialEq, Eq)]
pub struct Peer {
    pub public_key: String,
    pub preshared_key: String,
    /// "a.b.c.d:port", or "name:port" until `resolved()`.
    pub endpoint: String,
    /// Hostname of the endpoint as written in the profile ("" for IPv4).
    pub endpoint_name: String,
    /// Canonical IPv4 networks, file order.
    pub allowed_ips: Vec<String>,
    /// As written in the profile (0: absent or `off`); `wg` gets
    /// `effective_keepalive()`.
    pub keepalive: u32,
}

/// Keepalive given to `wg` for a peer whose profile has none (absent, 0 or
/// `off`). The supervisor judges each group by its latest handshake
/// (connected ≤ 180 s), and WireGuard only handshakes when it has something
/// to send: without a keepalive an idle gateway (no client traffic) never
/// handshakes with its Internet exit and is reconnected in a loop.
pub const DEFAULT_KEEPALIVE: u32 = 25;

/// Upper bound for a profile's keepalive. A rekey happens on the first packet
/// sent 120 s after the last handshake, so an idle peer's handshake ages up
/// to ceil(120 / K) * K seconds; K ≤ 60 keeps it under the 180 s limit.
pub const MAX_KEEPALIVE: u32 = 60;

impl fmt::Debug for Peer {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        // The preshared key never appears in logs or panics.
        f.debug_struct("Peer")
            .field("public_key", &self.public_key)
            .field("endpoint", &self.endpoint)
            .field("endpoint_name", &self.endpoint_name)
            .field("allowed_ips", &self.allowed_ips)
            .field("keepalive", &self.keepalive)
            .finish_non_exhaustive()
    }
}

impl Peer {
    /// One `[Peer]` block of `wg setconf` / `wg addconf` text (stdin only).
    pub fn block(&self) -> String {
        let mut text = format!("[Peer]\nPublicKey = {}\n", self.public_key);
        if !self.preshared_key.is_empty() {
            text += &format!("PresharedKey = {}\n", self.preshared_key);
        }
        text + &format!("Endpoint = {}\nAllowedIPs = {}\nPersistentKeepalive = {}\n", self.endpoint, self.allowed_ips.join(", "), self.effective_keepalive())
    }

    /// Keepalive applied in `wg`: DEFAULT_KEEPALIVE when the profile has none,
    /// otherwise its value capped at MAX_KEEPALIVE (see both).
    pub fn effective_keepalive(&self) -> u32 {
        match self.keepalive {
            0 => DEFAULT_KEEPALIVE,
            k => k.min(MAX_KEEPALIVE),
        }
    }

    /// Numeric endpoint address, None while a hostname is unresolved.
    pub fn endpoint_ip(&self) -> Option<std::net::Ipv4Addr> {
        let (host, _) = self.endpoint.rsplit_once(':')?;
        ipv4::address(host).ok()
    }

    /// Copy with the hostname endpoint replaced by its resolved address.
    pub fn resolved(&self, address: std::net::Ipv4Addr) -> Peer {
        let port = self.endpoint.rsplit_once(':').map(|(_, port)| port).unwrap_or("51820");
        Peer { endpoint: format!("{address}:{port}"), ..self.clone() }
    }

    /// Endpoint as written: "name:port" for host names, else "a.b.c.d:port".
    pub fn configured_endpoint(&self) -> String {
        match self.endpoint.rsplit_once(':') {
            Some((_, port)) if !self.endpoint_name.is_empty() => format!("{}:{port}", self.endpoint_name),
            _ => self.endpoint.clone(),
        }
    }

    /// Short public identifier for the panel (prefix of the public key).
    pub fn fingerprint(&self) -> String {
        self.public_key.chars().take(8).collect::<String>() + "…"
    }

    fn networks(&self) -> Vec<ipv4::Network> {
        self.allowed_ips.iter().filter_map(|n| ipv4::network(n).ok()).collect()
    }
}

#[derive(Clone, PartialEq, Eq)]
pub struct Profile {
    pub private_key: String,
    /// First IPv4 interface, e.g. "10.5.0.2/32".
    pub address: String,
    /// 1..=3 IPv4 resolvers handed to DHCP clients.
    pub dns: Vec<String>,
    pub mtu: u32,
    /// Every [Peer] in file order (at least one).
    pub peers: Vec<Peer>,
    /// Failover groups: indexes into `peers` with identical IPv4 AllowedIPs,
    /// in file order of their first member.
    pub groups: Vec<Vec<usize>>,
    /// Per group, the position in `groups[g]` of the member in use.
    pub active: Vec<usize>,
    /// DNS servers in `dns` that no AllowedIPs network covers.
    pub dns_outside: Vec<String>,
    pub notes: Vec<&'static str>,
}

impl fmt::Debug for Profile {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        // Private and preshared keys never appear in logs or panics.
        f.debug_struct("Profile")
            .field("address", &self.address)
            .field("dns", &self.dns)
            .field("mtu", &self.mtu)
            .field("peers", &self.peers)
            .field("groups", &self.groups)
            .field("active", &self.active)
            .field("notes", &self.notes)
            .finish_non_exhaustive()
    }
}

impl Profile {
    /// Index into `peers` of the member in use for `group`.
    pub fn active_index(&self, group: usize) -> usize {
        self.groups[group][self.active[group]]
    }

    pub fn active_peer(&self, group: usize) -> &Peer {
        &self.peers[self.active_index(group)]
    }

    /// The members in use, one per group, in group order.
    pub fn active_peers(&self) -> Vec<&Peer> {
        (0..self.groups.len()).map(|g| self.active_peer(g)).collect()
    }

    /// First group whose AllowedIPs cover every IPv4 address (the Internet exit).
    pub fn exit_group(&self) -> Option<usize> {
        (0..self.groups.len()).find(|&g| covers_everything(&self.active_peer(g).networks()))
    }

    /// Peer shown as "the" endpoint: active member of the exit group, else of
    /// the first group. The only peer of a single-peer profile.
    pub fn primary(&self) -> &Peer {
        self.active_peer(self.exit_group().unwrap_or(0))
    }

    /// True when at least one group has alternates.
    pub fn has_failover(&self) -> bool {
        self.groups.iter().any(|g| g.len() > 1)
    }

    /// Copy using `member` (position in `groups[group]`) for `group`.
    pub fn with_member(&self, group: usize, member: usize) -> Profile {
        let mut profile = self.clone();
        profile.active[group] = member % self.groups[group].len();
        profile
    }

    /// Copy with the peer at `index` replaced (e.g. its resolved endpoint).
    pub fn with_peer(&self, index: usize, peer: Peer) -> Profile {
        let mut profile = self.clone();
        profile.peers[index] = peer;
        profile
    }

    /// True when every member in use has a numeric endpoint.
    pub fn resolved(&self) -> bool {
        self.active_peers().iter().all(|p| p.endpoint_ip().is_some())
    }

    /// `wg setconf` text with the members in use (never passed as argv).
    /// Needs numeric endpoints.
    pub fn setconf(&self) -> String {
        let mut text = format!("[Interface]\nPrivateKey = {}\n", self.private_key);
        for peer in self.active_peers() {
            text += &peer.block();
        }
        text
    }

    /// DNS servers as dnsmasq/`Lan::set_dns` text: "a" or "a,b,c".
    pub fn dns_text(&self) -> String {
        self.dns.join(",")
    }
}

fn missing() -> Error {
    Error::Invalid("missing_profile_fields".into())
}

/// RFC 1123 host name (letters, digits, '-', dots), lowercase. Dotted
/// numbers are never host names: they must be valid IPv4 addresses.
pub fn hostname(text: &str) -> Result<String> {
    let name = text.strip_suffix('.').unwrap_or(text).to_ascii_lowercase();
    let labels: Vec<&str> = name.split('.').collect();
    let label_ok = |l: &&str| {
        (1..=63).contains(&l.len()) && l.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-') && !l.starts_with('-') && !l.ends_with('-')
    };
    let numeric_tld = labels.last().map(|l| l.bytes().all(|b| b.is_ascii_digit())).unwrap_or(true);
    if name.is_empty() || name.len() > 253 || !labels.iter().all(label_ok) || numeric_tld {
        return invalid("invalid_hostname");
    }
    Ok(name)
}

fn is_ipv6(text: &str) -> bool {
    let (address, prefix) = match text.split_once('/') {
        Some((a, p)) => (a, Some(p)),
        None => (text, None),
    };
    address.parse::<std::net::Ipv6Addr>().is_ok() && prefix.map(|p| py::is_digits(p) && p.parse::<u32>().map(|n| n <= 128).unwrap_or(false)).unwrap_or(true)
}

/// Comma lists over repeated lines, empty items dropped (wg-quick semantics).
fn items(values: &[String]) -> Vec<&str> {
    values.iter().flat_map(|v| v.split(',')).map(py::strip).filter(|v| !v.is_empty()).collect()
}

fn note(notes: &mut Vec<&'static str>, code: &'static str) {
    if !notes.contains(&code) {
        notes.push(code);
    }
}

/// True when the networks together cover every IPv4 address.
fn covers_everything(networks: &[ipv4::Network]) -> bool {
    let mut ranges: Vec<(u64, u64)> = networks.iter().map(|n| (n.address as u64, n.address as u64 + (1u64 << (32 - n.prefix as u32)))).collect();
    ranges.sort();
    let mut reached = 0u64;
    for (start, end) in ranges {
        if start > reached {
            return false;
        }
        reached = reached.max(end);
    }
    reached >= 1 << 32
}

fn endpoint(text: &str, notes: &mut Vec<&'static str>) -> Result<(String, String)> {
    if text.starts_with('[') || text.matches(':').count() > 1 {
        return invalid("ipv6_endpoint_unsupported");
    }
    let Some((host, port)) = text.rsplit_once(':') else {
        return invalid("invalid_endpoint");
    };
    let port = number(port, 1, 65535)?;
    if !host.is_empty() && host.bytes().all(|b| b.is_ascii_digit() || b == b'.') {
        return Ok((format!("{}:{port}", ipv4::address(host)?), String::new()));
    }
    let name = hostname(host).or_else(|_| invalid("invalid_endpoint"))?;
    note(notes, NOTE_HOSTNAME_ENDPOINT);
    Ok((format!("{name}:{port}"), name))
}

type Fields = HashMap<String, Vec<String>>;

fn sections(text: &str) -> Result<(Fields, Vec<Fields>)> {
    if text.is_empty() || text.len() > MAX_PROFILE || text.contains('\0') {
        return invalid("invalid_profile");
    }
    let text = text.strip_prefix('\u{feff}').unwrap_or(text);
    let repeatable = |section: &str, key: &str| matches!((section, key), ("interface", "address" | "dns") | ("peer", "allowedips"));
    let known = |section: &str, key: &str| match section {
        "interface" => ["privatekey", "address", "dns", "mtu"].contains(&key) || IGNORED_INTERFACE.contains(&key),
        _ => ["publickey", "presharedkey", "endpoint", "allowedips", "persistentkeepalive"].contains(&key),
    };
    let (mut interface, mut peers): (Option<Fields>, Vec<Fields>) = (None, Vec::new());
    let mut in_peer = None::<bool>;
    for line in py::splitlines(text) {
        if line.len() > MAX_LINE {
            return invalid("line_too_long");
        }
        let line = py::strip(line.split('#').next().unwrap_or(""));
        if line.is_empty() {
            continue;
        }
        if line.starts_with('[') {
            let name = if line.len() >= 2 && line.ends_with(']') { py::strip(&line[1..line.len() - 1]).to_ascii_lowercase() } else { String::new() };
            match name.as_str() {
                "interface" if interface.is_none() && peers.is_empty() => {
                    interface = Some(Fields::new());
                    in_peer = Some(false);
                }
                "peer" if interface.is_some() && peers.len() == MAX_PEERS => return invalid("too_many_peers"),
                "peer" if interface.is_some() => {
                    peers.push(Fields::new());
                    in_peer = Some(true);
                }
                _ => return invalid("invalid_section"),
            }
            continue;
        }
        let (Some(peer), Some((key, value))) = (in_peer, line.split_once('=')) else {
            return invalid("invalid_field");
        };
        let section = if peer { "peer" } else { "interface" };
        let (key, value) = (py::strip(key).to_ascii_lowercase(), py::strip(value).to_string());
        let fields = if peer { peers.last_mut() } else { interface.as_mut() }.expect("current section exists");
        if !known(section, &key) || (fields.contains_key(&key) && !repeatable(section, &key)) {
            return invalid("unknown_or_duplicate_field");
        }
        fields.entry(key).or_default().push(value);
    }
    if peers.is_empty() {
        return Err(missing());
    }
    Ok((interface.ok_or_else(missing)?, peers))
}

fn one(fields: &Fields, key: &str) -> Result<String> {
    fields.get(key).and_then(|v| v.first()).cloned().ok_or_else(missing)
}

fn peer(fields: &Fields, notes: &mut Vec<&'static str>) -> Result<(Peer, Vec<ipv4::Network>)> {
    let public = key(&one(fields, "publickey")?)?;
    let (endpoint, endpoint_name) = endpoint(&one(fields, "endpoint")?, notes)?;
    let mut networks = Vec::new();
    let mut allowed_ips: Vec<String> = Vec::new();
    for item in items(fields.get("allowedips").ok_or_else(missing)?) {
        if is_ipv6(item) {
            note(notes, NOTE_IGNORED_IPV6);
            continue;
        }
        let network = ipv4::network(item)?;
        if !allowed_ips.contains(&network.to_string()) {
            allowed_ips.push(network.to_string());
            networks.push(network);
        }
    }
    if networks.is_empty() {
        return invalid("ipv4_allowed_ips_required");
    }
    let keepalive = match fields.get("persistentkeepalive").and_then(|v| v.first()).map(String::as_str) {
        None => 0,
        Some(v) if v.eq_ignore_ascii_case("off") => 0,
        Some(v) => number(v, 0, 65535)?,
    };
    let preshared_key = match fields.get("presharedkey").and_then(|v| v.first()) {
        Some(k) => key(k)?,
        None => String::new(),
    };
    Ok((Peer { public_key: public, preshared_key, endpoint, endpoint_name, allowed_ips, keepalive }, networks))
}

/// Peers with identical IPv4 AllowedIPs sets are alternates (failover);
/// groups sharing only some identical prefix are refused, because WireGuard
/// would silently give that prefix to one peer.
fn group(networks: &[Vec<ipv4::Network>]) -> Result<Vec<Vec<usize>>> {
    let set = |n: &Vec<ipv4::Network>| {
        let mut keys: Vec<(u32, u8)> = n.iter().map(|n| (n.address, n.prefix)).collect();
        keys.sort_unstable();
        keys
    };
    let mut keys: Vec<Vec<(u32, u8)>> = Vec::new();
    let mut groups: Vec<Vec<usize>> = Vec::new();
    for (index, nets) in networks.iter().enumerate() {
        let k = set(nets);
        match keys.iter().position(|existing| *existing == k) {
            Some(g) => groups[g].push(index),
            None => {
                keys.push(k);
                groups.push(vec![index]);
            }
        }
    }
    for (i, a) in keys.iter().enumerate() {
        for b in &keys[i + 1..] {
            if a.iter().any(|prefix| b.contains(prefix)) {
                return invalid("allowed_ips_partial_overlap");
            }
        }
    }
    Ok(groups)
}

pub fn parse(text: &str) -> Result<Profile> {
    let (a, peer_fields) = sections(text)?;
    let mut notes = Vec::new();
    let private = key(&one(&a, "privatekey")?)?;
    // The single-peer parser checked the public key before the interface fields.
    key(&one(&peer_fields[0], "publickey")?)?;

    let mut addresses = Vec::new();
    for item in items(a.get("address").ok_or_else(missing)?) {
        if is_ipv6(item) {
            note(&mut notes, NOTE_IGNORED_IPV6);
            continue;
        }
        let text = if item.contains('/') { item.to_string() } else { format!("{item}/32") };
        let address = ipv4::interface(&text)?;
        if address.prefix == 0 {
            return invalid("invalid_prefix");
        }
        addresses.push(address.to_string());
    }
    let Some(address) = addresses.first().cloned() else {
        return invalid("ipv4_address_required");
    };
    if addresses.len() > 1 {
        note(&mut notes, NOTE_EXTRA_ADDRESSES);
    }

    let mut dns: Vec<String> = Vec::new();
    for item in items(a.get("dns").map(Vec::as_slice).unwrap_or(&[])) {
        if let Ok(server) = ipv4::address(item) {
            let server = server.to_string();
            if dns.contains(&server) {
                continue;
            }
            if dns.len() == MAX_DNS {
                note(&mut notes, NOTE_DNS_TRUNCATED);
                continue;
            }
            dns.push(server);
        } else if is_ipv6(item) {
            note(&mut notes, NOTE_IGNORED_IPV6);
        } else if hostname(item).is_ok() {
            note(&mut notes, NOTE_DNS_SEARCH_IGNORED);
        } else {
            return invalid("invalid_dns");
        }
    }
    if dns.is_empty() {
        dns.push(DEFAULT_DNS.to_string());
        note(&mut notes, NOTE_DNS_FALLBACK);
    }

    let mut peers: Vec<Peer> = Vec::new();
    let mut networks: Vec<Vec<ipv4::Network>> = Vec::new();
    for fields in &peer_fields {
        let (parsed, nets) = peer(fields, &mut notes)?;
        if peers.iter().any(|p| p.public_key == parsed.public_key) {
            return invalid("duplicate_peer");
        }
        peers.push(parsed);
        networks.push(nets);
    }
    let groups = group(&networks)?;
    let all: Vec<ipv4::Network> = networks.concat();
    if !covers_everything(&all) {
        note(&mut notes, NOTE_SPLIT_ALLOWED_IPS);
    }
    let dns_outside: Vec<String> = dns
        .iter()
        .filter(|server| {
            let address = u32::from(server.parse::<std::net::Ipv4Addr>().expect("validated IPv4"));
            !all.iter().any(|n| n.contains(address))
        })
        .cloned()
        .collect();
    if !dns_outside.is_empty() {
        note(&mut notes, NOTE_DNS_OUTSIDE_ALLOWED_IPS);
    }
    if IGNORED_INTERFACE.iter().any(|k| a.contains_key(*k)) {
        note(&mut notes, NOTE_IGNORED_HOOKS);
    }
    if peers.len() > 1 {
        note(&mut notes, NOTE_MULTIPLE_PEERS);
    }
    Ok(Profile {
        private_key: private,
        address,
        dns,
        mtu: number(a.get("mtu").and_then(|v| v.first()).map(String::as_str).unwrap_or("1380"), 1280, 1500)?,
        active: vec![0; groups.len()],
        peers,
        groups,
        dns_outside,
        notes,
    })
}

#[cfg(test)]
pub mod tests {
    use super::*;

    pub const PRIVATE: &str = "yAnz5TF+lXXJte14tji3zlMNq+hd2rYUIgJBgB3fBmk=";
    pub const PUBLIC: &str = "xTIBA5rboUvnH4htodjb6e697QjLERt1NAB4mZqp8Dg=";
    pub const OTHER: &str = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=";

    /// Distinct, valid public keys for multi-peer tests.
    pub fn peer_key(n: u8) -> String {
        base64::engine::general_purpose::STANDARD.encode([n; 32])
    }

    pub fn profile_text() -> String {
        format!("[Interface]\nPrivateKey = {PRIVATE}\nAddress = 10.5.0.2/32\nDNS = 103.86.96.100\n# comment\n[Peer]\nPublicKey = {PUBLIC}\nEndpoint = 192.0.2.20:51820\nAllowedIPs = 0.0.0.0/0\nPersistentKeepalive = 25\n")
    }

    #[test]
    fn parses_and_renders() {
        let profile = parse(&profile_text()).unwrap();
        assert_eq!(profile.address, "10.5.0.2/32");
        assert_eq!(profile.primary().endpoint, "192.0.2.20:51820");
        assert_eq!((profile.groups.clone(), profile.active.clone()), (vec![vec![0]], vec![0]));
        assert_eq!(profile.mtu, 1380);
        assert_eq!(
            profile.setconf(),
            format!("[Interface]\nPrivateKey = {PRIVATE}\n[Peer]\nPublicKey = {PUBLIC}\nEndpoint = 192.0.2.20:51820\nAllowedIPs = 0.0.0.0/0\nPersistentKeepalive = 25\n")
        );
        assert!(!format!("{profile:?}").contains(PRIVATE));
    }

    #[test]
    fn rejects_unsafe_or_unsupported_profiles() {
        let base = profile_text();
        let cases = [
            (base.replace("10.5.0.2/32", "10.5.0.2/0"), "invalid_prefix"),
            (base.replace("[Peer]", "[Peer]\nPostUp = rm -rf /\n"), "unknown_or_duplicate_field"),
            (base.replace("[Interface]", "[Interface]\nPrivateKey = x"), "unknown_or_duplicate_field"),
            (base.replace("[Interface]", "[Interface]\nFoo = bar"), "unknown_or_duplicate_field"),
            (base.replace("192.0.2.20:51820", "192.0.2.20:0"), "invalid_number"),
            (base.replace("192.0.2.20:51820", "192.0.2.20"), "invalid_endpoint"),
            (base.replace("192.0.2.20:51820", "192.0.2:51820"), "invalid_ipv4_address"),
            (base.replace("192.0.2.20:51820", "[2001:db8::1]:51820"), "ipv6_endpoint_unsupported"),
            (base.replace("192.0.2.20:51820", "2001:db8::1:51820"), "ipv6_endpoint_unsupported"),
            (base.replace("192.0.2.20:51820", "bad_host!:51820"), "invalid_endpoint"),
            (base.replace(PUBLIC, "short"), "invalid_key"),
            (format!("{base}[Peer]\nPublicKey = {PUBLIC}\nEndpoint = 192.0.2.21:51820\nAllowedIPs = 0.0.0.0/0\n"), "duplicate_peer"),
            (format!("{base}[Peer]\nPublicKey = {OTHER}\nEndpoint = 192.0.2.21:51820\n"), "missing_profile_fields"),
            (format!("{base}[Peer]\n"), "missing_profile_fields"),
            (format!("{base}[Interface]\n"), "invalid_section"),
            (format!("[Peer]\n{base}"), "invalid_section"),
            (base.replace("Address = 10.5.0.2/32", "Address = fd00::2/128"), "ipv4_address_required"),
            (base.replace("AllowedIPs = 0.0.0.0/0", "AllowedIPs = ::/0"), "ipv4_allowed_ips_required"),
            (base.replace("DNS = 103.86.96.100", "DNS = 1.1.1"), "invalid_dns"),
            (base.replace("Address", "MTU = 1501\nAddress"), "invalid_number"),
            (base.replace("Address", "MTU = 1279\nAddress"), "invalid_number"),
            (base.replace("25", "x"), "invalid_number"),
            (format!("{base}\0"), "invalid_profile"),
            ("x".repeat(MAX_PROFILE + 1), "invalid_profile"),
            (String::new(), "invalid_profile"),
            (base.replace("# comment", &"#".repeat(MAX_LINE + 1)), "line_too_long"),
            (base.replace("PublicKey", "Public Key"), "unknown_or_duplicate_field"),
            ("# only a comment\n".to_string(), "missing_profile_fields"),
        ];
        for (i, (text, code)) in cases.iter().enumerate() {
            match parse(text) {
                Ok(p) => panic!("case {i} accepted: {p:?}"),
                Err(e) => assert_eq!(e.code(), *code, "case {i}"),
            }
        }
        assert!(key("yAnz5TF+lXXJte14tji3zlMNq+hd2rYUIgJBgB3fBmk").is_err());
    }

    /// Mullvad-style: IPv6 address, IPv6 AllowedIPs and DNS.
    #[test]
    fn mullvad_like_profile_uses_ipv4_parts() {
        let text = format!("[Interface]\n# Device: Quick Fox\nPrivateKey = {PRIVATE}\nAddress = 10.64.12.34/32,fc00:bbbb:bbbb:bb01::1:c21/128\nDNS = 10.64.0.1, 2001:db8::53\n\n[Peer]\nPublicKey = {PUBLIC}\nAllowedIPs = 0.0.0.0/0,::0/0\nEndpoint = 185.65.135.66:51820\n");
        let p = parse(&text).unwrap();
        assert_eq!((p.address.as_str(), p.dns_text().as_str(), p.primary().endpoint.as_str()), ("10.64.12.34/32", "10.64.0.1", "185.65.135.66:51820"));
        assert_eq!(p.primary().allowed_ips, vec!["0.0.0.0/0"]);
        assert_eq!(p.notes, vec![NOTE_IGNORED_IPV6]);
        assert_eq!(p.mtu, 1380);
        assert!(p.setconf().contains("AllowedIPs = 0.0.0.0/0\n"));
    }

    /// Proton-style export: BOM, CRLF, mixed-case keys, comments.
    #[test]
    fn proton_like_profile() {
        let text = format!("\u{feff}[Interface]\r\n# Key for phoenix\r\n# Bouncing = 3\r\nprivatekey = {PRIVATE}\r\nAddress = 10.2.0.2/32\r\nDNS = 10.2.0.1\r\n\r\n[peer]\r\n# CH#123\r\npublickey = {PUBLIC}\r\nAllowedIPs = 0.0.0.0/0\r\nEndpoint = 79.135.104.45:51820\r\n");
        let p = parse(&text).unwrap();
        assert_eq!((p.address.as_str(), p.dns_text().as_str(), p.primary().endpoint.as_str()), ("10.2.0.2/32", "10.2.0.1", "79.135.104.45:51820"));
        assert!(p.notes.is_empty(), "{:?}", p.notes);
    }

    /// wg-easy / self-hosted: PresharedKey, hostname endpoint, wg-quick hooks.
    #[test]
    fn wg_easy_like_profile_never_runs_hooks() {
        let psk = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=";
        let text = format!("[Interface]\nPrivateKey = {PRIVATE}\nAddress = 10.8.0.2/24\nDNS = 1.1.1.1, 9.9.9.9, 8.8.8.8, 8.8.4.4\nMTU = 1420\nListenPort = 51820\nTable = off\nPostUp = touch /tmp/pwned\nPostDown = rm -rf /\nSaveConfig = true\n\n[Peer]\nPublicKey = {PUBLIC}\nPresharedKey = {psk}\nAllowedIPs = 0.0.0.0/1, 128.0.0.0/1\nPersistentKeepalive = off\nEndpoint = VPN.Example.ORG.:51820\n");
        let p = parse(&text).unwrap();
        let peer = p.primary();
        assert_eq!(peer.endpoint, "vpn.example.org:51820");
        assert_eq!(peer.endpoint_name, "vpn.example.org");
        assert_eq!(peer.endpoint_ip(), None, "hostname must be resolved first");
        assert!(!p.resolved());
        assert_eq!(p.address, "10.8.0.2/24");
        assert_eq!(p.dns, vec!["1.1.1.1", "9.9.9.9", "8.8.8.8"]);
        assert_eq!((p.mtu, peer.keepalive), (1420, 0));
        assert_eq!(peer.allowed_ips, vec!["0.0.0.0/1", "128.0.0.0/1"]);
        assert_eq!(p.exit_group(), Some(0), "two /1 halves are an Internet exit");
        assert_eq!(p.notes, vec![NOTE_DNS_TRUNCATED, NOTE_HOSTNAME_ENDPOINT, NOTE_IGNORED_HOOKS], "two /1 halves are a full tunnel");
        let resolved = p.with_peer(0, peer.resolved("192.0.2.30".parse().unwrap()));
        assert_eq!(resolved.primary().endpoint, "192.0.2.30:51820");
        assert_eq!(resolved.primary().endpoint_name, "vpn.example.org");
        assert_eq!(resolved.primary().configured_endpoint(), "vpn.example.org:51820");
        assert!(resolved.resolved());
        let conf = resolved.setconf();
        assert!(conf.contains(&format!("PresharedKey = {psk}\nEndpoint = 192.0.2.30:51820\nAllowedIPs = 0.0.0.0/1, 128.0.0.0/1\n")), "{conf}");
        for forbidden in ["PostUp", "PostDown", "touch", "Table", "ListenPort", "SaveConfig"] {
            assert!(!conf.contains(forbidden), "{forbidden} leaked into setconf");
        }
        assert!(!format!("{p:?}").contains(psk) && !format!("{p:?}").contains(PRIVATE));
    }

    /// Phoenix supervises by handshake age, so every peer handed to `wg`
    /// keeps handshaking while idle: missing/0/off → 25 s, above 60 s → 60 s,
    /// explicit values up to 60 s unchanged. The parsed value stays as written.
    #[test]
    fn keepalive_always_applied_for_supervision() {
        let profile = |keepalive: &str| {
            parse(&format!("[Interface]\nPrivateKey = {PRIVATE}\nAddress = 10.14.0.2/16\n[Peer]\nPublicKey = {PUBLIC}\nEndpoint = 192.0.2.20:51820\nAllowedIPs = 0.0.0.0/0\n{keepalive}")).unwrap()
        };
        for (line, parsed, applied) in [
            ("", 0, 25),
            ("PersistentKeepalive = 0\n", 0, 25),
            ("PersistentKeepalive = off\n", 0, 25),
            ("PersistentKeepalive = 1\n", 1, 1),
            ("PersistentKeepalive = 10\n", 10, 10),
            ("PersistentKeepalive = 60\n", 60, 60),
            ("PersistentKeepalive = 61\n", 61, 60),
            ("PersistentKeepalive = 65535\n", 65535, 60),
        ] {
            let p = profile(line);
            assert_eq!((p.primary().keepalive, p.primary().effective_keepalive()), (parsed, applied), "{line:?}");
            assert!(p.setconf().ends_with(&format!("PersistentKeepalive = {applied}\n")), "{line:?}: {}", p.setconf());
        }
    }

    /// The reported case: exit peer without keepalive next to a split-route
    /// peer with one. Both members in use must keep handshaking.
    #[test]
    fn every_active_peer_gets_a_keepalive() {
        let text = format!(
            "[Interface]\nPrivateKey = {PRIVATE}\nAddress = 10.14.0.2/16\n\
             [Peer]\nPublicKey = {PUBLIC}\nEndpoint = 192.0.2.20:51820\nAllowedIPs = 0.0.0.0/0\n\
             [Peer]\nPublicKey = {}\nEndpoint = 192.0.2.21:51820\nAllowedIPs = 192.168.1.79/32, 91.108.4.0/22\nPersistentKeepalive = 25\n",
            peer_key(9)
        );
        let p = parse(&text).unwrap();
        assert_eq!(p.exit_group(), Some(0));
        assert_eq!(p.setconf().matches("PersistentKeepalive = 25\n").count(), 2, "{}", p.setconf());
        assert!(p.peers[0].block().contains("PersistentKeepalive = 25\n"), "wg addconf on failover too");
    }

    /// Surfshark-style: hostname endpoint, two DNS lines, no prefix.
    #[test]
    fn surfshark_like_profile() {
        let text = format!("[Interface]\nAddress = 10.14.0.2\nPrivateKey = {PRIVATE}\nDNS = 162.252.172.57\nDNS = 149.154.159.92, search.example\n[Peer]\nPublicKey = {PUBLIC}\nAllowedIPs = 0.0.0.0/0\nEndpoint = it-mil.prod.surfshark.com:51820\n");
        let p = parse(&text).unwrap();
        assert_eq!(p.address, "10.14.0.2/32");
        assert_eq!(p.dns_text(), "162.252.172.57,149.154.159.92");
        assert_eq!(p.primary().endpoint_name, "it-mil.prod.surfshark.com");
        assert_eq!(p.notes, vec![NOTE_DNS_SEARCH_IGNORED, NOTE_HOSTNAME_ENDPOINT]);
    }

    #[test]
    fn split_tunnel_extra_addresses_and_dns_fallback() {
        let text = format!("[Interface]\nPrivateKey = {PRIVATE}\nAddress = 10.0.0.2/32\nAddress = 10.0.0.3/32\n[Peer]\nPublicKey = {PUBLIC}\nEndpoint = 192.0.2.20:51820\nAllowedIPs = 10.0.0.9/24, 192.168.50.0/24, 10.0.0.0/24\n");
        let p = parse(&text).unwrap();
        assert_eq!(p.address, "10.0.0.2/32");
        assert_eq!(p.primary().allowed_ips, vec!["10.0.0.0/24", "192.168.50.0/24"]);
        assert_eq!(p.dns, vec!["1.1.1.1"]);
        assert_eq!(p.notes, vec![NOTE_EXTRA_ADDRESSES, NOTE_DNS_FALLBACK, NOTE_SPLIT_ALLOWED_IPS, NOTE_DNS_OUTSIDE_ALLOWED_IPS]);
        assert_eq!(p.dns_outside, vec!["1.1.1.1"], "the fallback resolver is outside the split tunnel");
        assert_eq!(p.exit_group(), None);
        assert!(p.setconf().contains("AllowedIPs = 10.0.0.0/24, 192.168.50.0/24\n"));
    }

    #[test]
    fn hostnames() {
        for good in ["vpn.example.com", "A-B.example", "localhost", "xn--d1acufc.xn--p1ai", "host."] {
            assert!(hostname(good).is_ok(), "{good}");
        }
        for bad in ["", "-a.example", "a-.example", "a..b", "1.2.3", "a.123", "a_b.example", "a b", &"a".repeat(64), &format!("{}.com", "a.".repeat(126))] {
            assert!(hostname(bad).is_err(), "{bad}");
        }
    }

    #[test]
    fn dns_coverage_warns_without_rejecting() {
        let base = profile_text().replace("AllowedIPs = 0.0.0.0/0", "AllowedIPs = 10.88.0.0/24");
        let p = parse(&base).unwrap();
        assert_eq!(p.dns_outside, vec!["103.86.96.100"]);
        assert!(p.notes.contains(&NOTE_DNS_OUTSIDE_ALLOWED_IPS));
        let inside = parse(&base.replace("DNS = 103.86.96.100", "DNS = 10.88.0.1, 9.9.9.9")).unwrap();
        assert_eq!(inside.dns_outside, vec!["9.9.9.9"], "each uncovered server is named");
        let covered = parse(&base.replace("DNS = 103.86.96.100", "DNS = 10.88.0.53")).unwrap();
        assert!(covered.dns_outside.is_empty() && !covered.notes.contains(&NOTE_DNS_OUTSIDE_ALLOWED_IPS));
        // A second group can cover the resolver.
        let two = format!("{base}[Peer]\nPublicKey = {OTHER}\nEndpoint = 192.0.2.21:51820\nAllowedIPs = 103.86.96.0/24\n");
        assert!(parse(&two).unwrap().dns_outside.is_empty());
        assert!(parse(&profile_text()).unwrap().dns_outside.is_empty(), "full tunnel covers every resolver");
    }

    fn peer_block(n: u8, endpoint: &str, allowed: &str) -> String {
        format!("[Peer]\nPublicKey = {}\nEndpoint = {endpoint}\nAllowedIPs = {allowed}\nPersistentKeepalive = 25\n", peer_key(n))
    }

    #[test]
    fn peers_with_identical_allowed_ips_are_failover_alternates() {
        let interface = format!("[Interface]\nPrivateKey = {PRIVATE}\nAddress = 10.5.0.2/32\nDNS = 10.88.0.1\n");
        let text = format!(
            "{interface}{}{}{}{}",
            peer_block(1, "192.0.2.20:51820", "0.0.0.0/0, ::/0"),
            peer_block(2, "192.0.2.22:51820", "10.0.0.0/8"),
            peer_block(3, "backup.example.net:51820", "0.0.0.0/0"),
            peer_block(4, "192.0.2.23:51820", "10.88.0.0/24"),
        );
        let p = parse(&text).unwrap();
        assert_eq!(p.groups, vec![vec![0, 2], vec![1], vec![3]]);
        assert_eq!(p.active, vec![0, 0, 0]);
        assert_eq!(p.exit_group(), Some(0));
        assert_eq!(p.primary().public_key, peer_key(1));
        assert!(p.has_failover());
        assert_eq!(p.notes, vec![NOTE_IGNORED_IPV6, NOTE_HOSTNAME_ENDPOINT, NOTE_MULTIPLE_PEERS]);
        // setconf holds one member per group, never two alternates.
        let conf = p.setconf();
        assert_eq!(conf.matches("[Peer]").count(), 3);
        assert!(conf.contains(&peer_key(1)) && !conf.contains(&peer_key(3)) && conf.contains(&peer_key(2)) && conf.contains(&peer_key(4)));
        let switched = p.with_member(0, 1);
        assert_eq!(switched.primary().public_key, peer_key(3));
        assert!(!switched.resolved(), "the alternate has a host name");
        assert!(!switched.setconf().contains(&peer_key(1)));
        assert_eq!(switched.with_member(0, 2).active, vec![0, 0, 0], "round robin");
    }

    #[test]
    fn multi_peer_rejections() {
        let interface = format!("[Interface]\nPrivateKey = {PRIVATE}\nAddress = 10.5.0.2/32\n");
        let cases = [
            (format!("{interface}{}{}", peer_block(1, "192.0.2.20:51820", "10.0.0.0/24, 10.1.0.0/24"), peer_block(2, "192.0.2.21:51820", "10.1.0.0/24")), "allowed_ips_partial_overlap"),
            (format!("{interface}{}{}", peer_block(1, "192.0.2.20:51820", "0.0.0.0/0"), peer_block(1, "192.0.2.21:51820", "10.1.0.0/24")), "duplicate_peer"),
            (format!("{interface}{}{}", peer_block(1, "192.0.2.20:51820", "0.0.0.0/0"), peer_block(2, "[2001:db8::1]:51820", "10.1.0.0/24")), "ipv6_endpoint_unsupported"),
            (format!("{interface}{}{}", peer_block(1, "192.0.2.20:51820", "0.0.0.0/0"), peer_block(2, "192.0.2.21:51820", "::/0")), "ipv4_allowed_ips_required"),
            (format!("{interface}{}[Interface]\n", peer_block(1, "192.0.2.20:51820", "0.0.0.0/0")), "invalid_section"),
            (format!("{interface}{}", (1..=17).map(|n| peer_block(n, "192.0.2.20:51820", &format!("10.{n}.0.0/16"))).collect::<String>()), "too_many_peers"),
        ];
        for (i, (text, code)) in cases.iter().enumerate() {
            match parse(text) {
                Ok(p) => panic!("case {i} accepted: {p:?}"),
                Err(e) => assert_eq!(e.code(), *code, "case {i}"),
            }
        }
        // Containment is longest-prefix routing, not a conflict; 16 peers fit.
        let nested = format!("{interface}{}{}", peer_block(1, "192.0.2.20:51820", "0.0.0.0/0"), peer_block(2, "192.0.2.21:51820", "10.0.0.0/8"));
        assert_eq!(parse(&nested).unwrap().groups, vec![vec![0], vec![1]]);
        let sixteen = format!("{interface}{}", (1..=16).map(|n| peer_block(n, "192.0.2.20:51820", &format!("10.{n}.0.0/16"))).collect::<String>());
        assert_eq!(parse(&sixteen).unwrap().groups.len(), 16);
        assert!(sixteen.len() < MAX_PROFILE);
    }
}
