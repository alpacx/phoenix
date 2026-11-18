//! Minimal HTTPS/1.1 GET client over rustls (used by uplink_http and the
//! updater health check). No proxies, no redirects, no system resolver:
//! callers pass the numeric address to connect to.
use crate::error::{invalid, Error, Result};
use crate::firewall::interface;
use rustls::client::danger::{HandshakeSignatureValid, ServerCertVerified, ServerCertVerifier};
use rustls::crypto::{verify_tls12_signature, verify_tls13_signature, CryptoProvider, WebPkiSupportedAlgorithms};
use rustls::{ClientConfig, ClientConnection, DigitallySignedStruct, RootCertStore, SignatureScheme, StreamOwned};
use rustls_pki_types::pem::PemObject;
use rustls_pki_types::{CertificateDer, ServerName, UnixTime};
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{SocketAddr, SocketAddrV4, TcpStream};
use std::os::fd::{AsRawFd, FromRawFd, OwnedFd};
use std::path::Path;
use std::sync::Arc;
use std::time::Duration;

pub const SYSTEM_ROOTS: &str = "/etc/ssl/certs/ca-certificates.crt";
const MAX_LINE: usize = 65536;
const MAX_HEADERS: usize = 100;

pub enum Trust {
    /// System roots from /etc/ssl/certs/ca-certificates.crt.
    System,
    /// Accept only this exact end-entity certificate (DER), any CA flags.
    Pinned(Vec<u8>),
}

pub struct Target<'a> {
    /// TLS server name and Host header (DNS name or IP literal).
    pub host: &'a str,
    pub address: SocketAddrV4,
    /// SO_BINDTODEVICE interface, if any.
    pub device: Option<&'a str>,
    /// SO_MARK (0 = unset).
    pub mark: u32,
    pub timeout: Duration,
}

fn failed() -> Error {
    Error::Network("https_failed".into())
}

fn provider() -> Arc<CryptoProvider> {
    Arc::new(rustls::crypto::ring::default_provider())
}

/// Pins the admin certificate: byte equality replaces chain building, so
/// a self-signed CA:TRUE leaf (as on existing installs) is still accepted.
#[derive(Debug)]
struct PinnedVerifier {
    der: Vec<u8>,
    algorithms: WebPkiSupportedAlgorithms,
}

impl ServerCertVerifier for PinnedVerifier {
    fn verify_server_cert(&self, end_entity: &CertificateDer<'_>, _: &[CertificateDer<'_>], _: &ServerName<'_>, _: &[u8], _: UnixTime) -> std::result::Result<ServerCertVerified, rustls::Error> {
        if end_entity.as_ref() == self.der.as_slice() {
            Ok(ServerCertVerified::assertion())
        } else {
            Err(rustls::Error::InvalidCertificate(rustls::CertificateError::UnknownIssuer))
        }
    }
    fn verify_tls12_signature(&self, message: &[u8], cert: &CertificateDer<'_>, dss: &DigitallySignedStruct) -> std::result::Result<HandshakeSignatureValid, rustls::Error> {
        verify_tls12_signature(message, cert, dss, &self.algorithms)
    }
    fn verify_tls13_signature(&self, message: &[u8], cert: &CertificateDer<'_>, dss: &DigitallySignedStruct) -> std::result::Result<HandshakeSignatureValid, rustls::Error> {
        verify_tls13_signature(message, cert, dss, &self.algorithms)
    }
    fn supported_verify_schemes(&self) -> Vec<SignatureScheme> {
        self.algorithms.supported_schemes()
    }
}

fn load_roots(path: &Path) -> Result<RootCertStore> {
    let mut roots = RootCertStore::empty();
    let certificates = CertificateDer::pem_file_iter(path).map_err(|_| Error::Network("trust_store_unavailable".into()))?;
    let (added, _) = roots.add_parsable_certificates(certificates.flatten());
    if added == 0 {
        return Err(Error::Network("trust_store_unavailable".into()));
    }
    Ok(roots)
}

fn config(trust: &Trust, roots_path: &Path) -> Result<ClientConfig> {
    let provider = provider();
    let builder = ClientConfig::builder_with_provider(provider.clone()).with_safe_default_protocol_versions().map_err(|_| failed())?;
    let config = match trust {
        Trust::System => builder.with_root_certificates(load_roots(roots_path)?).with_no_client_auth(),
        Trust::Pinned(der) => builder
            .dangerous()
            .with_custom_certificate_verifier(Arc::new(PinnedVerifier { der: der.clone(), algorithms: provider.signature_verification_algorithms }))
            .with_no_client_auth(),
    };
    Ok(config)
}

fn setsockopt(fd: i32, option: i32, value: &[u8]) -> std::io::Result<()> {
    let rc = unsafe { libc::setsockopt(fd, libc::SOL_SOCKET, option, value.as_ptr().cast(), value.len() as libc::socklen_t) };
    if rc == 0 {
        Ok(())
    } else {
        Err(std::io::Error::last_os_error())
    }
}

/// TCP connect, optionally bound to a device and marked, with a timeout.
pub fn connect(target: &Target) -> Result<TcpStream> {
    let stream = if target.device.is_none() && target.mark == 0 {
        TcpStream::connect_timeout(&SocketAddr::V4(target.address), target.timeout).map_err(|_| failed())?
    } else {
        bound_connect(target).map_err(|_| failed())?
    };
    stream.set_read_timeout(Some(target.timeout)).map_err(|_| failed())?;
    stream.set_write_timeout(Some(target.timeout)).map_err(|_| failed())?;
    Ok(stream)
}

fn bound_connect(target: &Target) -> std::io::Result<TcpStream> {
    let raw = unsafe { libc::socket(libc::AF_INET, libc::SOCK_STREAM | libc::SOCK_CLOEXEC, 0) };
    if raw < 0 {
        return Err(std::io::Error::last_os_error());
    }
    let fd = unsafe { OwnedFd::from_raw_fd(raw) };
    if let Some(device) = target.device {
        let mut name = device.as_bytes().to_vec();
        name.push(0);
        setsockopt(raw, libc::SO_BINDTODEVICE, &name)?;
    }
    if target.mark != 0 {
        setsockopt(raw, libc::SO_MARK, &(target.mark as libc::c_int).to_ne_bytes())?;
    }
    let flags = unsafe { libc::fcntl(raw, libc::F_GETFL) };
    unsafe { libc::fcntl(raw, libc::F_SETFL, flags | libc::O_NONBLOCK) };
    let address = libc::sockaddr_in {
        sin_family: libc::AF_INET as libc::sa_family_t,
        sin_port: target.address.port().to_be(),
        sin_addr: libc::in_addr { s_addr: u32::from(*target.address.ip()).to_be() },
        sin_zero: [0; 8],
    };
    let rc = unsafe { libc::connect(raw, (&address as *const libc::sockaddr_in).cast(), std::mem::size_of::<libc::sockaddr_in>() as libc::socklen_t) };
    if rc != 0 {
        let error = std::io::Error::last_os_error();
        if error.raw_os_error() != Some(libc::EINPROGRESS) {
            return Err(error);
        }
        let mut pfd = libc::pollfd { fd: raw, events: libc::POLLOUT, revents: 0 };
        let millis = target.timeout.as_millis().min(i32::MAX as u128) as i32;
        if unsafe { libc::poll(&mut pfd, 1, millis) } <= 0 {
            return Err(std::io::Error::from(std::io::ErrorKind::TimedOut));
        }
        let mut status: libc::c_int = 0;
        let mut length = std::mem::size_of::<libc::c_int>() as libc::socklen_t;
        unsafe { libc::getsockopt(raw, libc::SOL_SOCKET, libc::SO_ERROR, (&mut status as *mut libc::c_int).cast(), &mut length) };
        if status != 0 {
            return Err(std::io::Error::from_raw_os_error(status));
        }
    }
    unsafe { libc::fcntl(raw, libc::F_SETFL, flags & !libc::O_NONBLOCK) };
    let stream = TcpStream::from(fd);
    debug_assert!(stream.as_raw_fd() == raw);
    Ok(stream)
}

fn read_line<R: BufRead>(reader: &mut R) -> Result<String> {
    let mut line = Vec::new();
    reader.by_ref().take(MAX_LINE as u64 + 1).read_until(b'\n', &mut line).map_err(|_| failed())?;
    if line.len() > MAX_LINE || !line.ends_with(b"\n") {
        return invalid("invalid_http_response");
    }
    while matches!(line.last(), Some(b'\n' | b'\r')) {
        line.pop();
    }
    String::from_utf8(line).or_else(|_| invalid("invalid_http_response"))
}

/// Read until EOF; TLS peers closing without close_notify count as EOF
/// (Python's ssl suppress_ragged_eofs default).
fn read_to_end_limited<R: Read>(reader: &mut R, limit: usize, out: &mut Vec<u8>) -> Result<()> {
    let mut buffer = [0u8; 8192];
    loop {
        match reader.read(&mut buffer) {
            Ok(0) => return Ok(()),
            Ok(n) => {
                out.extend_from_slice(&buffer[..n]);
                if out.len() > limit {
                    return invalid("https_response_too_large");
                }
            }
            Err(e) if e.kind() == std::io::ErrorKind::UnexpectedEof => return Ok(()),
            Err(e) if e.kind() == std::io::ErrorKind::Interrupted => continue,
            Err(_) => return Err(failed()),
        }
    }
}

/// Parse a response from `reader`: (status, body).
pub fn read_response<R: BufRead>(reader: &mut R, limit: usize) -> Result<(u16, Vec<u8>)> {
    loop {
        let status_line = read_line(reader)?;
        let mut parts = status_line.splitn(3, ' ');
        let version = parts.next().unwrap_or("");
        let status: u16 = match parts.next().map(str::parse) {
            Some(Ok(code)) if version.starts_with("HTTP/1.") && (100..=999).contains(&code) => code,
            _ => return invalid("invalid_http_response"),
        };
        let mut length: Option<usize> = None;
        let mut chunked = false;
        let mut count = 0;
        loop {
            let line = read_line(reader)?;
            if line.is_empty() {
                break;
            }
            count += 1;
            if count > MAX_HEADERS {
                return invalid("invalid_http_response");
            }
            let Some((name, value)) = line.split_once(':') else {
                return invalid("invalid_http_response");
            };
            let value = value.trim();
            if name.eq_ignore_ascii_case("content-length") {
                let parsed: usize = value.parse().or_else(|_| invalid("invalid_http_response"))?;
                if length.is_some_and(|l| l != parsed) {
                    return invalid("invalid_http_response");
                }
                length = Some(parsed);
            } else if name.eq_ignore_ascii_case("transfer-encoding") {
                chunked = value.eq_ignore_ascii_case("chunked");
            }
        }
        if (100..200).contains(&status) {
            continue; // Interim response; the final one follows.
        }
        let mut body = Vec::new();
        if status == 204 || status == 304 {
            return Ok((status, body));
        }
        if chunked {
            loop {
                let line = read_line(reader)?;
                let size_text = line.split(';').next().unwrap_or("").trim();
                let size = usize::from_str_radix(size_text, 16).or_else(|_| invalid("invalid_http_response"))?;
                if size == 0 {
                    while !read_line(reader)?.is_empty() {}
                    break;
                }
                if body.len() + size > limit {
                    return invalid("https_response_too_large");
                }
                let start = body.len();
                body.resize(start + size, 0);
                reader.read_exact(&mut body[start..]).map_err(|_| failed())?;
                if !read_line(reader)?.is_empty() {
                    return invalid("invalid_http_response");
                }
            }
        } else if let Some(length) = length {
            if length > limit {
                return invalid("https_response_too_large");
            }
            body.resize(length, 0);
            reader.read_exact(&mut body).map_err(|_| failed())?;
        } else {
            read_to_end_limited(reader, limit, &mut body)?;
        }
        return Ok((status, body));
    }
}

/// GET `path`; returns (status, body). Body larger than `limit` is an error.
/// Handles Content-Length, chunked and close-delimited bodies.
pub fn get(target: &Target, path: &str, headers: &[(&str, &str)], trust: &Trust, limit: usize) -> Result<(u16, Vec<u8>)> {
    get_with_roots(target, path, headers, trust, limit, Path::new(SYSTEM_ROOTS))
}

pub fn get_with_roots(target: &Target, path: &str, headers: &[(&str, &str)], trust: &Trust, limit: usize, roots: &Path) -> Result<(u16, Vec<u8>)> {
    if let Some(device) = target.device {
        interface(device)?;
    }
    let unsafe_text = |s: &str| s.chars().any(|c| c.is_control());
    if !path.starts_with('/') || unsafe_text(path) || path.contains(' ') || unsafe_text(target.host) || headers.iter().any(|(n, v)| unsafe_text(n) || unsafe_text(v) || n.contains(':')) {
        return invalid("invalid_http_request");
    }
    let config = config(trust, roots)?;
    let name = ServerName::try_from(target.host.to_string()).or_else(|_| invalid("invalid_server_name"))?;
    let connection = ClientConnection::new(Arc::new(config), name).map_err(|_| failed())?;
    let stream = connect(target)?;
    let mut tls = StreamOwned::new(connection, stream);
    let host = if target.address.port() == 443 { target.host.to_string() } else { format!("{}:{}", target.host, target.address.port()) };
    let mut request = format!("GET {path} HTTP/1.1\r\nHost: {host}\r\nAccept-Encoding: identity\r\n");
    for (name, value) in headers {
        request += &format!("{name}: {value}\r\n");
    }
    request += "Connection: close\r\n\r\n";
    tls.write_all(request.as_bytes()).map_err(|_| failed())?;
    tls.flush().map_err(|_| failed())?;
    let mut reader = BufReader::new(tls);
    read_response(&mut reader, limit)
}

/// First certificate of a PEM file as DER (for Trust::Pinned).
pub fn pem_certificate(pem: &[u8]) -> Result<Vec<u8>> {
    match CertificateDer::pem_slice_iter(pem).next() {
        Some(Ok(certificate)) => Ok(certificate.as_ref().to_vec()),
        _ => invalid("invalid_certificate"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rustls::{ServerConfig, ServerConnection};
    use rustls_pki_types::PrivateKeyDer;
    use std::net::{Ipv4Addr, TcpListener};

    // Throwaway self-signed P-256 test certificates (CA:TRUE, SAN 127.0.0.1).
    const CERT_A: &str = "-----BEGIN CERTIFICATE-----
MIIBdjCCARugAwIBAgIUXPQvDdv+8No23lugjUC6VX2h860wCgYIKoZIzj0EAwIw
FzEVMBMGA1UEAwwMcGhvZW5peC10ZXN0MCAXDTI2MTExODE0MDUzMVoYDzIxMjYx
MDI1MTQwNTMxWjAXMRUwEwYDVQQDDAxwaG9lbml4LXRlc3QwWTATBgcqhkjOPQIB
BggqhkjOPQMBBwNCAARucclqQvIvAzfA/ix5G+Z0nG9w3cY9Qbwuhy4V+pwxe3fn
UW2SNFpuGkjFJfYjkcktpDkKc/emeVBmHGWIbJUso0MwQTAdBgNVHQ4EFgQUmw7K
vPvDoZ6ezYO72fx4HQh7+yIwDwYDVR0TAQH/BAUwAwEB/zAPBgNVHREECDAGhwR/
AAABMAoGCCqGSM49BAMCA0kAMEYCIQDUcM5uKyjPFaeS9iioScdz5pMhuUy/3YON
2MBaDCYJUwIhAILKCpcG4UUqk+tMh192n7vofKwWKRHv5S8VdDZDwk3B
-----END CERTIFICATE-----
";
    const KEY_A: &str = "-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgYPvvrl6FJWtdjqm9
b8oknYcaJrgzEqFgZeqqeeBPHhuhRANCAARucclqQvIvAzfA/ix5G+Z0nG9w3cY9
Qbwuhy4V+pwxe3fnUW2SNFpuGkjFJfYjkcktpDkKc/emeVBmHGWIbJUs
-----END PRIVATE KEY-----
";
    const CERT_B: &str = "-----BEGIN CERTIFICATE-----
MIIBdjCCARugAwIBAgIUJ2hgzjUkjJoui4mluN0C8Bzq/agwCgYIKoZIzj0EAwIw
FzEVMBMGA1UEAwwMcGhvZW5peC10ZXN0MCAXDTI2MTExODE0MDUzMVoYDzIxMjYx
MDI1MTQwNTMxWjAXMRUwEwYDVQQDDAxwaG9lbml4LXRlc3QwWTATBgcqhkjOPQIB
BggqhkjOPQMBBwNCAATYabPcSbuHj2WV7IZoMF++j+x0eOnT39bXIqxTRYukWHFL
17Fnh4xULOXSzWkjiNgBQsiJQY1k1XxkEBmuyNMOo0MwQTAdBgNVHQ4EFgQUuBA0
qB/7LP0AfVb493XnyA1FIS0wDwYDVR0TAQH/BAUwAwEB/zAPBgNVHREECDAGhwR/
AAABMAoGCCqGSM49BAMCA0kAMEYCIQD+UKsmO8t+GDk8CkGm85JfrziodSq2mG8E
F+aokvgsuwIhALj5t3UDlllCCO5lSTVYw0RpiBpqm7XZ1KoS4eJ1kGHF
-----END CERTIFICATE-----
";

    /// One-shot TLS server answering `response` to the first request.
    fn serve(response: &'static [u8]) -> (u16, std::thread::JoinHandle<String>) {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let handle = std::thread::spawn(move || {
            let certs = vec![CertificateDer::from_pem_slice(CERT_A.as_bytes()).unwrap()];
            let key = PrivateKeyDer::from_pem_slice(KEY_A.as_bytes()).unwrap();
            let config = ServerConfig::builder_with_provider(provider()).with_safe_default_protocol_versions().unwrap().with_no_client_auth().with_single_cert(certs, key).unwrap();
            let (socket, _) = listener.accept().unwrap();
            let mut tls = StreamOwned::new(ServerConnection::new(Arc::new(config)).unwrap(), socket);
            let mut request = Vec::new();
            let mut byte = [0u8; 1];
            while !request.ends_with(b"\r\n\r\n") {
                if tls.read(&mut byte).unwrap_or(0) == 0 {
                    return String::from_utf8_lossy(&request).into_owned();
                }
                request.push(byte[0]);
            }
            let _ = tls.write_all(response);
            let _ = tls.flush();
            tls.conn.send_close_notify();
            let _ = tls.flush();
            String::from_utf8_lossy(&request).into_owned()
        });
        (port, handle)
    }

    fn target(port: u16) -> Target<'static> {
        Target { host: "127.0.0.1", address: SocketAddrV4::new(Ipv4Addr::LOCALHOST, port), device: None, mark: 0, timeout: Duration::from_secs(5) }
    }

    fn pin(pem: &str) -> Trust {
        Trust::Pinned(pem_certificate(pem.as_bytes()).unwrap())
    }

    #[test]
    fn pinned_certificate_and_bodies() {
        let (port, server) = serve(b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\n{\"ok\":true}");
        let (status, body) = get(&target(port), "/healthz", &[("Accept", "application/json")], &pin(CERT_A), 4096).unwrap();
        assert_eq!((status, body.as_slice()), (200, &b"{\"ok\":true}"[..]));
        let request = server.join().unwrap();
        assert!(request.starts_with(&format!("GET /healthz HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAccept-Encoding: identity\r\nAccept: application/json\r\nConnection: close\r\n\r\n")), "{request}");

        let (port, server) = serve(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n4;x=y\r\nabcd\r\n2\r\nef\r\n0\r\n\r\n");
        assert_eq!(get(&target(port), "/", &[], &pin(CERT_A), 4096).unwrap().1, b"abcdef");
        server.join().unwrap();

        let (port, server) = serve(b"HTTP/1.1 100 Continue\r\n\r\nHTTP/1.0 302 Found\r\nLocation: https://elsewhere/\r\n\r\nmoved");
        assert_eq!(get(&target(port), "/", &[], &pin(CERT_A), 4096).unwrap(), (302, b"moved".to_vec()));
        server.join().unwrap();

        let (port, server) = serve(b"HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\n");
        assert_eq!(get(&target(port), "/", &[], &pin(CERT_A), 10).unwrap_err().code(), "https_response_too_large");
        server.join().unwrap();
    }

    #[test]
    fn wrong_pin_and_untrusted_system_roots_fail_closed() {
        let (port, server) = serve(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n");
        assert!(get(&target(port), "/", &[], &pin(CERT_B), 4096).is_err());
        let _ = server.join();
        let tmp = crate::fsutil::testdir::TempDir::new();
        let roots = tmp.path().join("roots.pem");
        std::fs::write(&roots, CERT_A).unwrap();
        let (port, server) = serve(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n");
        // A CA:TRUE certificate is never accepted as a web PKI leaf.
        assert!(get_with_roots(&target(port), "/", &[], &Trust::System, 4096, &roots).is_err());
        let _ = server.join();
        assert_eq!(get_with_roots(&target(port), "/", &[], &Trust::System, 4096, &tmp.path().join("missing")).unwrap_err().code(), "trust_store_unavailable");
    }

    #[test]
    fn rejects_unsafe_requests_and_responses() {
        let t = target(1);
        assert!(get(&t, "/a\r\nX: y", &[], &pin(CERT_A), 10).is_err());
        assert!(get(&t, "/", &[("X", "a\nb")], &pin(CERT_A), 10).is_err());
        let bad = Target { device: Some("bad name"), ..target(1) };
        assert_eq!(get(&bad, "/", &[], &pin(CERT_A), 10).unwrap_err().code(), "invalid_interface");
        for response in [&b"garbage\r\n\r\n"[..], b"HTTP/1.1 200 OK\r\nbroken\r\n\r\n", b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\nzz\r\n"] {
            assert!(read_response(&mut &response[..], 100).is_err());
        }
        assert_eq!(read_response(&mut &b"HTTP/1.1 200 OK\r\n\r\nuntil-close"[..], 100).unwrap().1, b"until-close");
        assert!(read_response(&mut &b"HTTP/1.1 200 OK\r\n\r\nuntil-close"[..], 5).is_err());
        assert!(pem_certificate(b"nothing").is_err());
        assert!(connect(&Target { timeout: Duration::from_millis(200), ..target(9) }).is_err());
    }
}
