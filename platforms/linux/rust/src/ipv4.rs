//! IPv4 parsing with the same acceptance rules as Python's `ipaddress`
//! (strict dotted decimal, no leading zeros, prefix or dotted mask forms).
use crate::error::{invalid, Result};
use std::fmt;
use std::net::Ipv4Addr;

fn octets(text: &str) -> Option<u32> {
    let parts: Vec<&str> = text.split('.').collect();
    if parts.len() != 4 {
        return None;
    }
    let mut value = 0u32;
    for part in parts {
        if part.is_empty() || part.len() > 3 || !part.bytes().all(|b| b.is_ascii_digit()) {
            return None;
        }
        if part != "0" && part.starts_with('0') {
            return None;
        }
        let octet: u32 = part.parse().ok()?;
        if octet > 255 {
            return None;
        }
        value = (value << 8) | octet;
    }
    Some(value)
}

/// Python `IPv4Address(text)`.
pub fn address(text: &str) -> Result<Ipv4Addr> {
    match octets(text) {
        Some(value) => Ok(Ipv4Addr::from(value)),
        None => invalid("invalid_ipv4_address"),
    }
}

fn mask(prefix: u8) -> u32 {
    if prefix == 0 {
        0
    } else {
        u32::MAX << (32 - prefix as u32)
    }
}

fn prefix_from_int(value: u32) -> Option<u8> {
    let zeros = if value == 0 { 32 } else { value.trailing_zeros() };
    let prefix = 32 - zeros;
    let ones = if zeros == 32 { 0 } else { value >> zeros };
    let all = if prefix == 0 { 0 } else { u32::MAX >> (32 - prefix) };
    (ones == all).then_some(prefix as u8)
}

fn prefix(text: &str) -> Option<u8> {
    if !text.is_empty() && text.bytes().all(|b| b.is_ascii_digit()) {
        let value: u64 = text.parse().ok()?;
        return (value <= 32).then_some(value as u8);
    }
    let value = octets(text)?;
    prefix_from_int(value).or_else(|| prefix_from_int(value ^ u32::MAX))
}

fn split(text: &str) -> Result<(u32, u8)> {
    let parts: Vec<&str> = text.split('/').collect();
    let address = match octets(parts[0]) {
        Some(value) if parts.len() <= 2 => value,
        _ => return invalid("invalid_ipv4_network"),
    };
    let prefix = match parts.get(1) {
        None => 32,
        Some(p) => match prefix(p) {
            Some(value) => value,
            None => return invalid("invalid_ipv4_network"),
        },
    };
    Ok((address, prefix))
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Network {
    pub address: u32,
    pub prefix: u8,
}

impl Network {
    pub fn new(address: u32, prefix: u8) -> Self {
        Network { address: address & mask(prefix), prefix }
    }
    pub fn mask(&self) -> u32 {
        mask(self.prefix)
    }
    pub fn contains(&self, address: u32) -> bool {
        address & self.mask() == self.address
    }
    pub fn subnet_of(&self, other: &Network) -> bool {
        self.prefix >= other.prefix && other.contains(self.address)
    }
    pub fn overlaps(&self, other: &Network) -> bool {
        self.contains(other.address) || other.contains(self.address)
    }
    pub fn network_address(&self) -> Ipv4Addr {
        Ipv4Addr::from(self.address)
    }
}

impl fmt::Display for Network {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}/{}", Ipv4Addr::from(self.address), self.prefix)
    }
}

/// Python `IPv4Network(text, strict=False)`.
pub fn network(text: &str) -> Result<Network> {
    let (address, prefix) = split(text)?;
    Ok(Network::new(address, prefix))
}

/// Python `str(IPv4Network(text, strict=False))`.
pub fn network_text(text: &str) -> Result<String> {
    Ok(network(text)?.to_string())
}

/// DHCP resolver list "a" or "a,b,c" (1..=3 distinct IPv4 addresses, no
/// spaces), returned canonical. A single address renders exactly as before.
pub fn dns_list(text: &str) -> Result<String> {
    let mut servers: Vec<String> = Vec::new();
    for item in text.split(',') {
        let server = address(item)?.to_string();
        if servers.contains(&server) {
            return invalid("invalid_dns");
        }
        servers.push(server);
    }
    if servers.len() > 3 {
        return invalid("invalid_dns");
    }
    Ok(servers.join(","))
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Interface {
    pub ip: Ipv4Addr,
    pub prefix: u8,
}

impl Interface {
    pub fn network(&self) -> Network {
        Network::new(u32::from(self.ip), self.prefix)
    }
}

impl fmt::Display for Interface {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}/{}", self.ip, self.prefix)
    }
}

/// Python `IPv4Interface(text)`.
pub fn interface(text: &str) -> Result<Interface> {
    let (address, prefix) = split(text)?;
    Ok(Interface { ip: Ipv4Addr::from(address), prefix })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matches_python_ipaddress() {
        assert_eq!(address("1.2.3.4").unwrap().to_string(), "1.2.3.4");
        for bad in ["01.2.3.4", "1.2.3", "1.2.3.256", " 1.2.3.4", "1.2.3.4 ", "", "1..3.4", "+1.2.3.4"] {
            assert!(address(bad).is_err(), "{bad}");
        }
        assert_eq!(dns_list("103.86.96.100").unwrap(), "103.86.96.100");
        assert_eq!(dns_list("1.1.1.1,9.9.9.9,8.8.8.8").unwrap(), "1.1.1.1,9.9.9.9,8.8.8.8");
        for bad in ["", "1.1.1.1,", "1.1.1.1, 9.9.9.9", "1.1.1.1,1.1.1.1", "1.1.1.1,2.2.2.2,3.3.3.3,4.4.4.4", "1.1.1"] {
            assert!(dns_list(bad).is_err(), "{bad}");
        }
        assert_eq!(network_text("10.1.2.3/24").unwrap(), "10.1.2.0/24");
        assert_eq!(network_text("10.1.2.3").unwrap(), "10.1.2.3/32");
        assert_eq!(network_text("10.1.2.3/024").unwrap(), "10.1.2.0/24");
        assert_eq!(network_text("10.1.2.3/255.255.0.0").unwrap(), "10.1.0.0/16");
        assert_eq!(network_text("10.1.2.3/0.0.0.255").unwrap(), "10.1.2.0/24");
        assert_eq!(network_text("10.1.2.3/0.0.0.0").unwrap(), "0.0.0.0/0");
        assert_eq!(network_text("0.0.0.0/0").unwrap(), "0.0.0.0/0");
        for bad in ["10.0.0.0/33", "10.0.0.0/", "10.0.0.0/8/8", "10.0.0.0/255.0.255.0", "10.0.0.0/-1"] {
            assert!(network(bad).is_err(), "{bad}");
        }
        let lan = network("192.168.7.0/24").unwrap();
        assert!(network("192.168.7.5/32").unwrap().subnet_of(&lan));
        assert!(!network("192.168.0.0/16").unwrap().subnet_of(&lan));
        assert!(network("192.168.0.0/16").unwrap().overlaps(&lan));
        assert_eq!(interface("10.5.0.2/32").unwrap().to_string(), "10.5.0.2/32");
        assert_eq!(interface("10.5.0.2/24").unwrap().network().to_string(), "10.5.0.0/24");
    }
}
