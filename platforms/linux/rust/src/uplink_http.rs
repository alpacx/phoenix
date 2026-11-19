//! Bound HTTPS for provisioning: DNS and TLS use only the selected uplink
//! (uplink_http.py). DNS bootstrap uses authenticated DoH at a numeric
//! address, so it never consults the host resolver. No proxies, redirects,
//! alternate interfaces or TLS bypass.
use crate::error::{invalid, Result};
use crate::httpc::{self, Target, Trust};
use crate::ipv4;
use crate::json::{self, Value};
use std::net::{Ipv4Addr, SocketAddrV4};
use std::time::Duration;

const LIMIT: usize = 262144;
const TIMEOUT: Duration = Duration::from_secs(12);

/// Performs one bound HTTPS GET; injectable for tests.
pub type Fetch<'a> = &'a dyn Fn(&Target, &str, &[(&str, &str)]) -> Result<(u16, Vec<u8>)>;

fn read_json(fetch: Fetch, target: &Target, path: &str, headers: &[(&str, &str)]) -> Result<Value> {
    let (status, body) = fetch(target, path, headers)?;
    if status != 200 {
        return invalid("https_status_rejected");
    }
    if body.len() > LIMIT {
        return invalid("https_response_too_large");
    }
    json::parse(&body)
}

/// `headers` as (name, value). Returns the parsed JSON body (status 200 only).
pub fn get(path: &str, headers: &[(String, String)], device: &str, mark: u32) -> Result<Value> {
    get_with(path, headers, device, mark, &|target, path, headers| httpc::get(target, path, headers, &Trust::System, LIMIT))
}

pub fn get_with(path: &str, headers: &[(String, String)], device: &str, mark: u32, fetch: Fetch) -> Result<Value> {
    if !path.starts_with("/v1/") || path.chars().any(|c| (c as u32) < 32) {
        return invalid("invalid_api_path");
    }
    let address = resolve_with("api.nordvpn.com", device, mark, fetch)?;
    // TLS still authenticates api.nordvpn.com; a DNS result is not a trust anchor.
    let api = Target { host: "api.nordvpn.com", address: SocketAddrV4::new(address, 443), device: Some(device), mark, timeout: TIMEOUT };
    let headers: Vec<(&str, &str)> = headers.iter().map(|(n, v)| (n.as_str(), v.as_str())).collect();
    read_json(fetch, &api, path, &headers)
}

/// First A record of `name` via authenticated DoH at 1.1.1.1, bound to
/// `device` (and `mark`): never the host resolver or another interface.
/// Used for api.nordvpn.com and for WireGuard endpoint host names.
pub fn resolve(name: &str, device: &str, mark: u32) -> Result<Ipv4Addr> {
    resolve_with(name, device, mark, &|target, path, headers| httpc::get(target, path, headers, &Trust::System, LIMIT))
}

pub fn resolve_with(name: &str, device: &str, mark: u32, fetch: Fetch) -> Result<Ipv4Addr> {
    crate::firewall::interface(device)?;
    // Validated RFC 1123 name: safe to place in the query string as is.
    let name = crate::wireguard::hostname(name)?;
    let doh = Target { host: "1.1.1.1", address: SocketAddrV4::new(Ipv4Addr::new(1, 1, 1, 1), 443), device: Some(device), mark, timeout: TIMEOUT };
    let dns = read_json(fetch, &doh, &format!("/dns-query?name={name}&type=A"), &[("Accept", "application/dns-json")])?;
    if dns.get("Status").and_then(Value::as_i64) != Some(0) || !json::is_int(&dns["Status"]) {
        return invalid("uplink_dns_failed");
    }
    let mut address = None;
    for answer in dns.get("Answer").and_then(Value::as_array).map(Vec::as_slice).unwrap_or(&[]) {
        if answer.get("type").and_then(Value::as_i64) == Some(1) {
            let data = answer.get("data").and_then(Value::as_str).unwrap_or("");
            let parsed = ipv4::address(data)?;
            address.get_or_insert(parsed);
        }
    }
    address.ok_or_else(|| crate::error::Error::Invalid("uplink_dns_failed".into()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    type Seen = Mutex<Vec<(String, String, Option<String>, u32, String)>>;

    fn fake<'a>(seen: &'a Seen, replies: &'a Mutex<Vec<(u16, &'static str)>>) -> impl Fn(&Target, &str, &[(&str, &str)]) -> Result<(u16, Vec<u8>)> + 'a {
        move |target, path, _| {
            seen.lock().unwrap().push((target.host.into(), target.address.to_string(), target.device.map(str::to_string), target.mark, path.into()));
            let (status, body) = replies.lock().unwrap().remove(0);
            Ok((status, body.as_bytes().to_vec()))
        }
    }

    #[test]
    fn dns_and_api_bound_to_same_uplink() {
        let seen = Seen::default();
        let replies = Mutex::new(vec![(200, r#"{"Status":0,"Answer":[{"type":5,"data":"x"},{"type":1,"data":"192.0.2.20"},{"type":1,"data":"192.0.2.21"}]}"#), (200, r#"{"ok":true}"#)]);
        let headers = vec![("Accept".to_string(), "application/json".to_string())];
        let value = get_with("/v1/test", &headers, "wlan1", 0x5048, &fake(&seen, &replies)).unwrap();
        assert_eq!(value, crate::json::json!({"ok": true}));
        let seen = seen.into_inner().unwrap();
        assert_eq!(seen[0], ("1.1.1.1".into(), "1.1.1.1:443".into(), Some("wlan1".into()), 0x5048, "/dns-query?name=api.nordvpn.com&type=A".into()));
        assert_eq!(seen[1], ("api.nordvpn.com".into(), "192.0.2.20:443".into(), Some("wlan1".into()), 0x5048, "/v1/test".into()));
    }

    #[test]
    fn dns_failure_does_not_request_api() {
        for reply in [r#"{"Status":2}"#, r#"{"Status":0,"Answer":[]}"#, r#"{"Status":0,"Answer":[{"type":1,"data":"bad"}]}"#, "[]"] {
            let seen = Seen::default();
            let replies = Mutex::new(vec![(200, reply), (200, "{}")]);
            assert!(get_with("/v1/test", &[], "wlan1", 0, &fake(&seen, &replies)).is_err(), "{reply}");
            assert_eq!(seen.lock().unwrap().len(), 1);
        }
        let seen = Seen::default();
        let replies = Mutex::new(vec![(200, r#"{"Status":0,"Answer":[{"type":1,"data":"192.0.2.20"}]}"#), (302, "{}")]);
        assert_eq!(get_with("/v1/test", &[], "wlan1", 0, &fake(&seen, &replies)).unwrap_err().code(), "https_status_rejected");
    }

    #[test]
    fn resolves_endpoint_names_on_the_uplink() {
        let seen = Seen::default();
        let replies = Mutex::new(vec![(200, r#"{"Status":0,"Answer":[{"type":5,"data":"edge.example."},{"type":1,"data":"198.51.100.7"}]}"#)]);
        assert_eq!(resolve_with("VPN.Example.org", "end0", 0, &fake(&seen, &replies)).unwrap(), Ipv4Addr::new(198, 51, 100, 7));
        assert_eq!(seen.lock().unwrap()[0], ("1.1.1.1".into(), "1.1.1.1:443".into(), Some("end0".into()), 0, "/dns-query?name=vpn.example.org&type=A".into()));
        let seen = Seen::default();
        let replies = Mutex::new(vec![]);
        for name in ["a b", "x&type=AAAA", "1.2.3", ""] {
            assert!(resolve_with(name, "end0", 0, &fake(&seen, &replies)).is_err(), "{name}");
        }
        assert!(seen.lock().unwrap().is_empty(), "invalid names never reach DoH");
    }

    #[test]
    fn rejects_paths_and_devices() {
        let seen = Seen::default();
        let replies = Mutex::new(vec![]);
        for (path, device) in [("/v2/x", "wlan1"), ("/v1/x\n", "wlan1"), ("/v1/x", "bad dev")] {
            assert!(get_with(path, &[], device, 0, &fake(&seen, &replies)).is_err());
        }
        assert!(seen.lock().unwrap().is_empty());
    }

    /// Real TLS + DoH only through the selected uplink (tools/rust-kernel-tests.sh):
    /// a peer network namespace answers on 1.1.1.1 and api.nordvpn.com behind
    /// the uplink gateway while the main table blackholes 1.1.1.1. A WireGuard
    /// endpoint host name is resolved over the same path. The roots
    /// are a throwaway CA given to httpc in this test; production trust
    /// (system roots) is unchanged.
    #[test]
    #[ignore = "needs an isolated Docker container with NET_ADMIN and SYS_ADMIN"]
    fn kernel_selected_uplink_https_in_isolated_container() {
        use crate::fsutil::testdir::TempDir;
        use crate::json::json;
        use crate::runner::{Runner, SystemRunner};
        use crate::runtime::Runtime;
        use rustls::{ServerConfig, ServerConnection, StreamOwned};
        use rustls_pki_types::pem::PemObject;
        use rustls_pki_types::{CertificateDer, PrivateKeyDer};
        use std::io::{Read, Write};
        use std::net::{SocketAddr, TcpListener, TcpStream};
        use std::os::fd::AsRawFd;
        use std::sync::atomic::{AtomicBool, Ordering};
        use std::sync::Arc;

        assert!(std::path::Path::new("/.dockerenv").exists(), "never run on a host or target");
        let system = Arc::new(SystemRunner::new().unwrap());
        let sh = |script: &str| {
            system.run(&["sh", "-ec", script]).unwrap_or_else(|e| panic!("{script}: {e}"));
        };
        sh("ip netns del phpeerk 2>/dev/null || true
ip link del phupk0 2>/dev/null || true
ip netns add phpeerk
ip link add phupk0 type veth peer name phpeerk0
ip link set phpeerk0 netns phpeerk
ip address add 192.0.2.10/24 dev phupk0
ip link set phupk0 up
ip -n phpeerk address add 192.0.2.20/24 dev phpeerk0
ip -n phpeerk link set phpeerk0 up
ip -n phpeerk link set lo up
ip -n phpeerk address add 1.1.1.1/32 dev lo
ip route replace blackhole 1.1.1.1/32");
        let dir = TempDir::new();
        sh(&format!("cd {}
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -days 1 -subj /CN=Phoenix-test-CA -keyout ca.key -out ca.pem 2>/dev/null
openssl req -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -subj /CN=api.nordvpn.com -keyout leaf.key -out leaf.csr 2>/dev/null
printf 'subjectAltName=IP:1.1.1.1,DNS:api.nordvpn.com\\nbasicConstraints=critical,CA:FALSE\\nextendedKeyUsage=serverAuth\\nkeyUsage=critical,digitalSignature\\n' > leaf.ext
openssl x509 -req -in leaf.csr -CA ca.pem -CAkey ca.key -CAcreateserial -days 1 -extfile leaf.ext -out leaf.pem 2>/dev/null", dir.path().display()));
        let certs = vec![CertificateDer::from_pem_file(dir.path().join("leaf.pem")).unwrap()];
        let key = PrivateKeyDer::from_pem_file(dir.path().join("leaf.key")).unwrap();
        let config = Arc::new(
            ServerConfig::builder_with_provider(Arc::new(rustls::crypto::ring::default_provider()))
                .with_safe_default_protocol_versions()
                .unwrap()
                .with_no_client_auth()
                .with_single_cert(certs, key)
                .unwrap(),
        );

        // The server thread alone enters the peer namespace (setns is per thread).
        let stop = Arc::new(AtomicBool::new(false));
        let (ready_tx, ready_rx) = std::sync::mpsc::channel();
        let server = {
            let stop = stop.clone();
            std::thread::spawn(move || {
                let netns = std::fs::File::open("/run/netns/phpeerk").unwrap();
                assert_eq!(unsafe { libc::setns(netns.as_raw_fd(), libc::CLONE_NEWNET) }, 0);
                let listener = TcpListener::bind("0.0.0.0:443").unwrap();
                listener.set_nonblocking(true).unwrap();
                ready_tx.send(()).unwrap();
                let mut served = Vec::new();
                while !stop.load(Ordering::SeqCst) {
                    let socket = match listener.accept() {
                        Ok((socket, _)) => socket,
                        Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                            std::thread::sleep(std::time::Duration::from_millis(20));
                            continue;
                        }
                        Err(e) => panic!("{e}"),
                    };
                    socket.set_nonblocking(false).unwrap();
                    socket.set_read_timeout(Some(std::time::Duration::from_secs(5))).unwrap();
                    let mut tls = StreamOwned::new(ServerConnection::new(config.clone()).unwrap(), socket);
                    let mut request = Vec::new();
                    let mut byte = [0u8; 1];
                    while !request.ends_with(b"\r\n\r\n") && matches!(tls.read(&mut byte), Ok(1)) {
                        request.push(byte[0]);
                    }
                    let text = String::from_utf8_lossy(&request).into_owned();
                    let path = text.split(' ').nth(1).unwrap_or("").to_string();
                    let body = if path.starts_with("/dns-query?") {
                        r#"{"Status":0,"Answer":[{"type":1,"data":"192.0.2.20"}]}"#
                    } else if path == "/v1/fixture" {
                        r#"{"local_fixture":true}"#
                    } else {
                        "{}"
                    };
                    let sni = tls.conn.server_name().unwrap_or("").to_string();
                    let _ = write!(tls, "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}", body.len());
                    tls.conn.send_close_notify();
                    let _ = tls.flush();
                    served.push((sni, path));
                }
                served
            })
        };
        ready_rx.recv().unwrap();

        // Without the selected-uplink route, 1.1.1.1 is unreachable.
        assert!(TcpStream::connect_timeout(&SocketAddr::from(([1, 1, 1, 1], 443)), std::time::Duration::from_secs(2)).is_err());
        let roots = dir.path().join("ca.pem");
        let endpoint_roots = roots.clone();
        let names = json!({"ap": "apk0", "usb": "usbk0", "uplink": "eth0", "vpn": "phwg0"});
        let policy = json!({"revision": 0, "default_allow": true, "rules": [], "forwards": []});
        let rt = Runtime::new(&names, system.clone(), crate::py::wall_clock()).unwrap().with_nord_transport(Arc::new(move |path, headers, device, mark| {
            get_with(path, headers, device, mark, &|target, path, headers| httpc::get_with_roots(target, path, headers, &Trust::System, LIMIT, &roots))
        }))
        .with_resolver(Arc::new(move |name, device, mark| {
            resolve_with(name, device, mark, &|target, path, headers| httpc::get_with_roots(target, path, headers, &Trust::System, LIMIT, &endpoint_roots))
        }));
        let key = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=";
        let profile = crate::wireguard::parse(&format!(
            "[Interface]\nPrivateKey={key}\nAddress=10.5.0.2/32\n[Peer]\nPublicKey={key}\nEndpoint=VPN.Phoenix.test:51820\nAllowedIPs=0.0.0.0/0\n"
        ))
        .unwrap();
        rt.select_uplink(&policy, "phupk0", "ethernet", Some("192.0.2.20"), None).unwrap();
        let result = rt.nord_request("/v1/fixture", None);
        let resolved = rt.resolve_endpoint(&profile);
        system.run(&["ip", "link", "set", "phupk0", "down"]).unwrap();
        let after_loss = rt.nord_request("/v1/fixture", None);
        let resolved_after_loss = rt.resolve_endpoint(&profile);
        stop.store(true, Ordering::SeqCst);
        let served = server.join().unwrap();
        sh("ip netns del phpeerk
ip route del blackhole 1.1.1.1/32
for p in 17690 17691 17710 17711; do ip rule del priority $p 2>/dev/null || true; done
ip route flush table 17710 2>/dev/null || true
nft delete table inet phoenix 2>/dev/null || true");
        assert_eq!(result.unwrap(), json!({"local_fixture": true}));
        assert_eq!(after_loss.unwrap_err().code(), "nord_api_failed", "no alternate interface after link loss");
        assert_eq!(resolved.unwrap().primary().endpoint, "192.0.2.20:51820");
        assert_eq!(resolved_after_loss.unwrap_err().code(), "endpoint_resolution_failed", "no host resolver fallback");
        // No SNI for the IP literal (RFC 6066); its certificate is still verified by IP SAN.
        assert_eq!(
            served,
            vec![
                (String::new(), "/dns-query?name=api.nordvpn.com&type=A".to_string()),
                ("api.nordvpn.com".to_string(), "/v1/fixture".to_string()),
                (String::new(), "/dns-query?name=vpn.phoenix.test&type=A".to_string()),
            ]
        );
    }
}
