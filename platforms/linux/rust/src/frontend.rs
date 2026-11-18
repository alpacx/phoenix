//! Unprivileged HTTPS frontend: loopback by default, explicit device-bound
//! socket opt-in (frontend.py). Talks to the root worker only through the
//! allowlisted RPC socket.
use crate::args::{usage_error, Args};
use crate::http::{self, Deadlined, Settings};
use crate::rpc::{Api, RemoteApi};
use crate::{fsutil, py, signals, usb_admin};
use rustls::pki_types::pem::PemObject;
use rustls::pki_types::{CertificateDer, PrivateKeyDer};
use rustls::{ServerConfig, ServerConnection, StreamOwned};
use std::io::Write;
use std::net::{Ipv4Addr, SocketAddrV4, TcpListener, TcpStream};
use std::os::fd::AsRawFd;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;

/// Concurrent connections; one slow client must not stall the panel, and
/// each extra connection costs only a small stack and TLS buffers.
const MAX_CONNECTIONS: usize = 8;
const THREAD_STACK: usize = 512 * 1024;

fn fail(message: &str) -> i32 {
    eprintln!("{message}");
    1
}

pub(crate) fn tls_config(cert: &Path, key: &Path) -> Result<Arc<ServerConfig>, String> {
    let certs = CertificateDer::pem_file_iter(cert)
        .and_then(|iter| iter.collect::<Result<Vec<_>, _>>())
        .map_err(|_| "Invalid TLS certificate".to_string())?;
    if certs.is_empty() {
        return Err("Invalid TLS certificate".into());
    }
    let key = PrivateKeyDer::from_pem_file(key).map_err(|_| "Invalid TLS key".to_string())?;
    let provider = Arc::new(rustls::crypto::ring::default_provider());
    let config = ServerConfig::builder_with_provider(provider)
        .with_protocol_versions(&[&rustls::version::TLS13, &rustls::version::TLS12])
        .map_err(|_| "TLS configuration failed".to_string())?
        .with_no_client_auth()
        .with_single_cert(certs, key)
        .map_err(|_| "TLS certificate and key do not match".to_string())?;
    Ok(Arc::new(config))
}

/// One TLS connection, one request. Failures only drop this connection.
pub(crate) fn serve_connection(tcp: TcpStream, config: &Arc<ServerConfig>, settings: &Settings, api: &dyn Api) {
    // One absolute deadline covers handshake, request and response: a peer
    // trickling bytes is cut off even though each single read succeeds.
    let Ok(connection) = ServerConnection::new(config.clone()) else {
        return;
    };
    let mut tls = StreamOwned::new(connection, Deadlined::new(tcp, http::CONNECTION_DEADLINE));
    while tls.conn.is_handshaking() {
        match tls.conn.complete_io(&mut tls.sock) {
            Ok((0, 0)) | Err(_) => return,
            Ok(_) => {}
        }
    }
    http::handle(&mut tls, settings, api);
    tls.conn.send_close_notify();
    let _ = tls.flush();
}

fn valid_token(token: &str) -> bool {
    token.len() == 64 && token.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

/// `phoenix frontend [--usb-socket] --token-file F --tls-cert F --tls-key F [--socket P] [--port N]`
pub fn main(args: &[String]) -> i32 {
    let args = match Args::parse(args, &["socket", "port", "token-file", "tls-cert", "tls-key"], &["usb-socket"]) {
        Ok(args) if args.positionals.is_empty() => args,
        Ok(_) => return usage_error("unexpected argument"),
        Err(message) => return usage_error(&message),
    };
    let (token_file, cert, key) = match (args.require("token-file"), args.require("tls-cert"), args.require("tls-key")) {
        (Ok(t), Ok(c), Ok(k)) => (t, c, k),
        (Err(m), _, _) | (_, Err(m), _) | (_, _, Err(m)) => return usage_error(&m),
    };
    let port: u16 = match args.get("port").unwrap_or("8443").parse() {
        Ok(port) => port,
        Err(_) => return usage_error("--port: invalid int value"),
    };
    if fsutil::geteuid() == 0 {
        return fail("Frontend must run without root privileges");
    }
    let token = match std::fs::read_to_string(token_file) {
        Ok(text) if valid_token(py::strip(&text)) => py::strip(&text).to_string(),
        _ => return fail("Invalid admin token"),
    };
    let config = match tls_config(Path::new(cert), Path::new(key)) {
        Ok(config) => config,
        Err(message) => return fail(&message),
    };
    let usb = args.flag("usb-socket");
    let (listener, authority) = if usb {
        match usb_admin::activated_listener(443) {
            Ok(listener) => (listener, "192.168.7.1".to_string()),
            Err(error) => return fail(&format!("USB administration socket rejected: {error}")),
        }
    } else {
        match TcpListener::bind(SocketAddrV4::new(Ipv4Addr::LOCALHOST, port)) {
            Ok(listener) => {
                let bound = listener.local_addr().map(|a| a.port()).unwrap_or(port);
                (listener, format!("127.0.0.1:{bound}"))
            }
            Err(_) => return fail("Cannot bind the administration port"),
        }
    };
    let settings = Settings { authority, tls: true, password_auth: true, allow_bearer: !usb, token, release_id: http::release_id() };
    let api = RemoteApi { path: PathBuf::from(args.get("socket").unwrap_or("/run/phoenix-control/control.sock")) };
    let shared = Arc::new((config, settings, api));
    let active = Arc::new(AtomicUsize::new(0));
    signals::install();
    while !signals::stopping() {
        if !signals::wait_readable(listener.as_raw_fd(), 500) {
            continue;
        }
        let Ok((tcp, _)) = listener.accept() else {
            continue;
        };
        if active.load(Ordering::SeqCst) >= MAX_CONNECTIONS {
            continue; // Dropped: the client retries; every slot frees within the deadline.
        }
        active.fetch_add(1, Ordering::SeqCst);
        let (shared, slot) = (Arc::clone(&shared), Arc::clone(&active));
        let spawned = std::thread::Builder::new().stack_size(THREAD_STACK).spawn(move || {
            serve_connection(tcp, &shared.0, &shared.1, &shared.2);
            slot.fetch_sub(1, Ordering::SeqCst);
        });
        if spawned.is_err() {
            active.fetch_sub(1, Ordering::SeqCst);
        }
    }
    0
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::error::Result;
    use crate::fsutil::testdir::TempDir;
    use crate::json::{json, Map, Value};
    use rustls::pki_types::ServerName;
    use rustls::{ClientConfig, ClientConnection, RootCertStore};
    use std::io::Read;

    // Self-signed P-256 certificate for 127.0.0.1 (CA:FALSE), generated for tests only.
    const CERT: &str = "-----BEGIN CERTIFICATE-----\nMIIBmDCCAT+gAwIBAgIUFbrasVrnv164HQF+bWBhP+AxyzcwCgYIKoZIzj0EAwIw\nFDESMBAGA1UEAwwJbG9jYWxob3N0MCAXDTI2MTExODE0MTQxOFoYDzIxMjYxMDI1\nMTQxNDE4WjAUMRIwEAYDVQQDDAlsb2NhbGhvc3QwWTATBgcqhkjOPQIBBggqhkjO\nPQMBBwNCAAT3Wm7y4H9bGy2RJkFeSZ58dWl1lbwFWQkEAVpVf2UZjvlc6AeKWkBm\n6uCW2egTiFUR8D3qMcyNyVSG754PJTeLo20wazAdBgNVHQ4EFgQUGufbqnvh8yM2\ns40r7fzYKwXBVg0wGgYDVR0RBBMwEYcEfwAAAYIJbG9jYWxob3N0MAwGA1UdEwEB\n/wQCMAAwCwYDVR0PBAQDAgeAMBMGA1UdJQQMMAoGCCsGAQUFBwMBMAoGCCqGSM49\nBAMCA0cAMEQCIEVERiRguSHlbByLbyBYzosVeGo0/FM62xxZVGf78RmpAiBe8gdw\nKG9fpsiI2OihlIbujUAFP1G6vO/NEE5WqnFLhw==\n-----END CERTIFICATE-----\n";
    const KEY: &str = "-----BEGIN PRIVATE KEY-----\nMIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgF9aX4ndXIjKnWWs1\n55o4GN58Q85RTSKybyN7XXqsRiChRANCAAT3Wm7y4H9bGy2RJkFeSZ58dWl1lbwF\nWQkEAVpVf2UZjvlc6AeKWkBm6uCW2egTiFUR8D3qMcyNyVSG754PJTeL\n-----END PRIVATE KEY-----\n";

    struct Fake;

    impl Api for Fake {
        fn call(&self, method: &str, _: Map<String, Value>) -> Result<Value> {
            match method {
                "health" => Ok(json!({"ready": true, "release_id": "r1"})),
                _ => Ok(json!({})),
            }
        }
    }

    #[test]
    fn tls_round_trip_and_bad_client() {
        let dir = TempDir::new();
        let (cert, key) = (dir.path().join("cert.pem"), dir.path().join("key.pem"));
        std::fs::write(&cert, CERT).unwrap();
        std::fs::write(&key, KEY).unwrap();
        let config = tls_config(&cert, &key).unwrap();
        assert!(tls_config(&key, &key).is_err());
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let settings = Settings { authority: format!("127.0.0.1:{port}"), tls: true, password_auth: true, allow_bearer: true, token: "a".repeat(64), release_id: "r1".into() };
        let server = std::thread::spawn(move || {
            for _ in 0..2 {
                let (tcp, _) = listener.accept().unwrap();
                serve_connection(tcp, &config, &settings, &Fake);
            }
        });
        // A plaintext client must not break the server.
        let mut plain = TcpStream::connect(("127.0.0.1", port)).unwrap();
        plain.write_all(b"GET /healthz HTTP/1.0\r\n\r\n").unwrap();
        let mut sink = Vec::new();
        let _ = plain.read_to_end(&mut sink);
        let mut roots = RootCertStore::empty();
        roots.add(CertificateDer::from_pem_slice(CERT.as_bytes()).unwrap()).unwrap();
        let client_config = ClientConfig::builder_with_provider(Arc::new(rustls::crypto::ring::default_provider()))
            .with_safe_default_protocol_versions()
            .unwrap()
            .with_root_certificates(roots)
            .with_no_client_auth();
        let connection = ClientConnection::new(Arc::new(client_config), ServerName::try_from("127.0.0.1").unwrap()).unwrap();
        let mut tls = StreamOwned::new(connection, TcpStream::connect(("127.0.0.1", port)).unwrap());
        tls.write_all(b"GET /healthz HTTP/1.0\r\n\r\n").unwrap();
        let mut response = Vec::new();
        let _ = tls.read_to_end(&mut response);
        server.join().unwrap();
        let text = String::from_utf8_lossy(&response);
        assert!(text.starts_with("HTTP/1.0 200 OK\r\n"), "{text}");
        assert!(text.ends_with(r#"{"ready":true,"release_id":"r1"}"#), "{text}");
    }

    #[test]
    fn token_format() {
        assert!(valid_token(&"0f".repeat(32)));
        assert!(!valid_token(&"A".repeat(64)));
        assert!(!valid_token(&"a".repeat(63)));
    }
}
