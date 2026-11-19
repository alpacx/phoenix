//! Private hostapd/dnsmasq configuration rendering; never changes networking
//! itself (access_point.py).
use crate::error::{invalid, Result};
use crate::firewall::interface;
use crate::{ipv4, py};
use std::num::NonZeroU32;

/// Returns [("hostapd.conf", text), ("dnsmasq.conf", text)].
pub fn render(name: &str, ssid: &str, password: &str, country: &str, dns: &str) -> Result<Vec<(&'static str, String)>> {
    let name = interface(name)?;
    if !(1..=32).contains(&ssid.len()) {
        return invalid("invalid_ssid");
    }
    let length = py::len_chars(password);
    if !(8..=63).contains(&length) || !password.is_ascii() || password.chars().any(|c| (c as u32) < 32) {
        return invalid("invalid_wifi_password");
    }
    if country.len() != 2 || !country.bytes().all(|b| b.is_ascii_uppercase()) {
        return invalid("invalid_regulatory_country");
    }
    // One to three resolvers; a single one renders exactly as before.
    let dns = ipv4::dns_list(dns)?;
    let mut psk = [0u8; 32];
    ring::pbkdf2::derive(ring::pbkdf2::PBKDF2_HMAC_SHA1, NonZeroU32::new(4096).unwrap(), ssid.as_bytes(), password.as_bytes(), &mut psk);
    let hostapd = format!(
        "interface={name}\ndriver=nl80211\nssid2={}\ncountry_code={country}\nieee80211d=1\nhw_mode=g\nchannel=6\nwmm_enabled=1\nauth_algs=1\nwpa=2\nwpa_key_mgmt=WPA-PSK\nrsn_pairwise=CCMP\nwpa_psk={}\n",
        py::hex(ssid.as_bytes()),
        py::hex(&psk)
    );
    // DHCP only. Client DNS is routed through the same firewall/tunnel as other traffic.
    let dhcp = format!(
        "port=0\ninterface={name}\nbind-interfaces\ndhcp-range=192.168.9.20,192.168.9.200,255.255.255.0,1h\ndhcp-option=3,192.168.9.1\ndhcp-option=6,{dns}\ndhcp-authoritative\n"
    );
    Ok(vec![("hostapd.conf", hostapd), ("dnsmasq.conf", dhcp)])
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn renders_known_psk() {
        // IEEE 802.11i test vector: "password" / "IEEE".
        let configs = render("wlan0", "IEEE", "password", "IT", "103.86.96.100").unwrap();
        assert!(configs[0].1.contains("wpa_psk=f42c6fc52df0ebef9ebb4b90b38a5f902e83fe1b135a70e23aed762e9710a12e\n"));
        assert!(configs[0].1.contains("ssid2=49454545\n"));
        assert!(configs[1].1.contains("dhcp-option=6,103.86.96.100\n"));
        let configs = render("wlan0", "IEEE", "password", "IT", "10.64.0.1,9.9.9.9,1.1.1.1").unwrap();
        assert!(configs[1].1.contains("dhcp-option=6,10.64.0.1,9.9.9.9,1.1.1.1\n"));
        for (ssid, password, country, dns) in [
            ("", "password", "IT", "1.1.1.1"),
            (&"x".repeat(33)[..], "password", "IT", "1.1.1.1"),
            ("ok", "short", "IT", "1.1.1.1"),
            ("ok", "pässword", "IT", "1.1.1.1"),
            ("ok", "pass\nword", "IT", "1.1.1.1"),
            ("ok", "password", "it", "1.1.1.1"),
            ("ok", "password", "IT", "1.1.1"),
            ("ok", "password", "IT", "1.1.1.1, 9.9.9.9"),
            ("ok", "password", "IT", "1.1.1.1,2.2.2.2,3.3.3.3,4.4.4.4"),
        ] {
            assert!(render("wlan0", ssid, password, country, dns).is_err(), "{ssid} {password} {country} {dns}");
        }
    }

    /// The rendered DHCP configuration is accepted by the real dnsmasq
    /// (tools/rust-kernel-tests.sh). hostapd has no offline check: radio stays a
    /// hardware test.
    #[test]
    #[ignore = "needs the Docker test image (dnsmasq)"]
    fn kernel_dnsmasq_accepts_rendered_config() {
        use crate::fsutil::testdir::TempDir;
        use std::process::{Command, Stdio};
        assert!(std::path::Path::new("/.dockerenv").exists(), "never run on a host or target");
        let dir = TempDir::new();
        for dns in ["103.86.96.100", "10.64.0.1,9.9.9.9,1.1.1.1"] {
            let configs = render("wlan0", "Phoenix-Test", "test-only-passphrase", "IT", dns).unwrap();
            let path = dir.path().join("dnsmasq.conf");
            std::fs::write(&path, &configs[1].1).unwrap();
            let status = Command::new("dnsmasq")
                .arg("--test")
                .arg(format!("--conf-file={}", path.display()))
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status()
                .unwrap();
            assert!(status.success(), "dnsmasq rejected the rendered configuration ({dns})");
        }
    }
}
