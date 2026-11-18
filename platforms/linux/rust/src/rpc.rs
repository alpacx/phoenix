//! Small, allowlisted local control protocol; no shell/file/argv RPC methods
//! (rpc.py; the LocalAPI dispatch lives in local_api.rs).
//!
//! The HTTP process is unprivileged. The root worker checks the kernel peer
//! UID and validates requests again. Possession of the web UID authorizes
//! admin commands, not arbitrary execution. Payloads and error details are
//! never logged. Frame: 4-byte big-endian length + strict JSON.
use crate::error::{invalid, Error, Result};
use crate::json::{self, json, Map, Value};
use crate::signals;
use std::io::{self, ErrorKind, Read, Write};
use std::os::fd::AsRawFd;
use std::os::unix::fs::{FileTypeExt, PermissionsExt};
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

pub const LIMIT: usize = 28 * 1024 * 1024;
const READ_DEADLINE: Duration = Duration::from_secs(20);
const CLIENT_TIMEOUT: Duration = Duration::from_secs(25);
const BACKLOG: libc::c_int = 4;
const SERVER_TIMEOUT: Duration = Duration::from_secs(20);

/// Implemented by the in-process dispatcher and by the socket client.
pub trait Api: Send + Sync {
    fn call(&self, method: &str, args: Map<String, Value>) -> Result<Value>;
}

type SetTimeout<S> = fn(&mut S, Duration) -> io::Result<()>;

fn exact<S: Read>(stream: &mut S, size: usize, deadline: Instant, set_timeout: SetTimeout<S>) -> Result<Vec<u8>> {
    let mut out = Vec::with_capacity(size.min(65536));
    while out.len() < size {
        let remaining = deadline.saturating_duration_since(Instant::now());
        if remaining.is_zero() {
            return invalid("rpc_read_deadline");
        }
        set_timeout(stream, remaining)?;
        let start = out.len();
        out.resize(start + (size - start).min(65536), 0);
        match stream.read(&mut out[start..]) {
            Ok(0) => return invalid("truncated_rpc"),
            Ok(n) => out.truncate(start + n),
            Err(e) if e.kind() == ErrorKind::Interrupted => out.truncate(start),
            Err(e) => return Err(e.into()),
        }
    }
    Ok(out)
}

fn receive_until<S: Read>(stream: &mut S, deadline: Instant, set_timeout: SetTimeout<S>) -> Result<Value> {
    let header = exact(stream, 4, deadline, set_timeout)?;
    let size = u32::from_be_bytes([header[0], header[1], header[2], header[3]]) as usize;
    if size == 0 || size > LIMIT {
        return invalid("rpc_too_large");
    }
    json::loads(&exact(stream, size, deadline, set_timeout)?)
}

/// Read one frame; the whole read must finish within 20 s. For generic
/// streams the deadline is checked between reads; per-read timeouts are the
/// caller's (Unix sockets use [`receive_unix`], which shrinks them).
pub fn receive<S: Read>(stream: &mut S) -> Result<Value> {
    receive_until(stream, Instant::now() + READ_DEADLINE, |_, _| Ok(()))
}

/// [`receive`] with each socket read bounded by the remaining deadline.
pub fn receive_unix(stream: &mut UnixStream) -> Result<Value> {
    receive_until(stream, Instant::now() + READ_DEADLINE, |s, d| s.set_read_timeout(Some(d)))
}

pub fn send<S: Write>(stream: &mut S, value: &Value) -> Result<()> {
    let data = json::dumps(value);
    if data.len() > LIMIT {
        return invalid("rpc_too_large");
    }
    let mut frame = Vec::with_capacity(4 + data.len());
    frame.extend_from_slice(&(data.len() as u32).to_be_bytes());
    frame.extend_from_slice(data.as_bytes());
    stream.write_all(&frame)?;
    Ok(())
}

/// Connect with the timeouts set first (Python settimeout before connect):
/// SO_SNDTIMEO also bounds a connect that waits on a full backlog.
fn connect(path: &Path, timeout: Duration) -> Result<UnixStream> {
    use std::os::fd::FromRawFd;
    use std::os::unix::ffi::OsStrExt;
    let bytes = path.as_os_str().as_bytes();
    let mut address: libc::sockaddr_un = unsafe { std::mem::zeroed() };
    if bytes.is_empty() || bytes.len() >= address.sun_path.len() || bytes.contains(&0) {
        return Err(Error::Io("io_invalidinput".into()));
    }
    address.sun_family = libc::AF_UNIX as libc::sa_family_t;
    for (target, source) in address.sun_path.iter_mut().zip(bytes) {
        *target = *source as libc::c_char;
    }
    let fd = unsafe { libc::socket(libc::AF_UNIX, libc::SOCK_STREAM | libc::SOCK_CLOEXEC, 0) };
    if fd < 0 {
        return Err(io::Error::last_os_error().into());
    }
    // Owns the descriptor from here on, so every early return closes it.
    let stream = unsafe { UnixStream::from_raw_fd(fd) };
    stream.set_read_timeout(Some(timeout))?;
    stream.set_write_timeout(Some(timeout))?;
    let length = (std::mem::size_of::<libc::sa_family_t>() + bytes.len() + 1) as libc::socklen_t;
    if unsafe { libc::connect(fd, &address as *const libc::sockaddr_un as *const libc::sockaddr, length) } != 0 {
        return Err(io::Error::last_os_error().into());
    }
    Ok(stream)
}

/// Client used by the unprivileged frontend. Errors: Conflict for
/// "conflict", Unavailable for "unavailable", Invalid for any other error
/// reply, Io for socket failures.
pub struct RemoteApi {
    pub path: PathBuf,
}

impl Api for RemoteApi {
    fn call(&self, method: &str, args: Map<String, Value>) -> Result<Value> {
        let mut stream = connect(&self.path, CLIENT_TIMEOUT)?;
        send(&mut stream, &json!({"method": method, "args": Value::Object(args)}))?;
        let mut response = match receive_unix(&mut stream)? {
            Value::Object(map) => map,
            _ => return invalid("invalid_or_failed_operation"),
        };
        match response.get("error") {
            Some(Value::String(e)) if e == "conflict" => return Err(Error::Conflict("command_in_progress".into())),
            Some(Value::String(e)) if e == "unavailable" => return Err(Error::Unavailable("capability_unavailable".into())),
            Some(_) => return invalid("invalid_or_failed_operation"),
            None => {}
        }
        response.remove("result").ok_or_else(|| Error::Invalid("invalid_or_failed_operation".into()))
    }
}

fn peer_uid(stream: &UnixStream) -> Option<u32> {
    let mut credentials = libc::ucred { pid: 0, uid: 0, gid: 0 };
    let mut length = std::mem::size_of::<libc::ucred>() as libc::socklen_t;
    let status = unsafe {
        libc::getsockopt(stream.as_raw_fd(), libc::SOL_SOCKET, libc::SO_PEERCRED, &mut credentials as *mut _ as *mut libc::c_void, &mut length)
    };
    (status == 0 && length as usize == std::mem::size_of::<libc::ucred>()).then_some(credentials.uid)
}

fn dispatch(api: &dyn Api, request: Value) -> Result<Value> {
    let Value::Object(mut request) = request else {
        return invalid("invalid_rpc_request");
    };
    if request.len() != 2 {
        return invalid("invalid_rpc_request");
    }
    match (request.remove("method"), request.remove("args")) {
        (Some(Value::String(method)), Some(Value::Object(args))) => api.call(&method, args),
        _ => invalid("invalid_rpc_request"),
    }
}

fn error_reply(error: &Error) -> Value {
    let code = match error {
        Error::Conflict(_) => "conflict",
        Error::Unavailable(_) => "unavailable",
        _ => "invalid_or_failed_operation",
    };
    json!({ "error": code })
}

fn handle(mut stream: UnixStream, api: &dyn Api, allowed_uid: u32) {
    let _ = stream.set_read_timeout(Some(SERVER_TIMEOUT));
    let _ = stream.set_write_timeout(Some(SERVER_TIMEOUT));
    if peer_uid(&stream) != Some(allowed_uid) {
        return;
    }
    let reply = match receive_unix(&mut stream).and_then(|request| dispatch(api, request)) {
        Ok(result) => json!({ "result": result }),
        Err(error) => error_reply(&error),
    };
    if let Err(Error::Invalid(_)) = send(&mut stream, &reply) {
        // Result too large for a frame: report a failed operation instead.
        let _ = send(&mut stream, &json!({"error": "invalid_or_failed_operation"}));
    }
}

fn bind(path: &Path) -> Result<UnixListener> {
    // systemd owns the private directory. Refuse replacing non-socket files.
    match std::fs::symlink_metadata(path) {
        Ok(meta) => {
            if meta.file_type().is_symlink() || !meta.file_type().is_socket() {
                return invalid("unsafe_control_socket");
            }
            std::fs::remove_file(path)?;
        }
        Err(e) if e.kind() == ErrorKind::NotFound => {}
        Err(e) => return Err(e.into()),
    }
    let listener = UnixListener::bind(path)?;
    // Small backlog: requests queued behind a stalled worker are few, so few
    // commands can run after their client already reported a timeout.
    if unsafe { libc::listen(listener.as_raw_fd(), BACKLOG) } != 0 {
        return Err(io::Error::last_os_error().into());
    }
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o660))?;
    Ok(listener)
}

fn serve_until(listener: &UnixListener, api: &dyn Api, allowed_uid: u32, stop: &dyn Fn() -> bool) {
    while !stop() {
        if !signals::wait_readable(listener.as_raw_fd(), 500) {
            continue;
        }
        if let Ok((stream, _)) = listener.accept() {
            handle(stream, api, allowed_uid);
        }
    }
}

/// Bind `path` (refusing to replace a non-socket), chmod 0660 and serve
/// requests one at a time until `signals::stopping()`. Only peers whose
/// SO_PEERCRED uid equals `allowed_uid` get an answer.
pub fn serve(path: &Path, api: &dyn Api, allowed_uid: u32) -> Result<()> {
    let listener = bind(path)?;
    serve_until(&listener, api, allowed_uid, &signals::stopping);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fsutil::testdir::TempDir;
    use std::os::unix::fs::MetadataExt;
    use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
    use std::sync::Arc;

    struct Fake;

    impl Api for Fake {
        fn call(&self, method: &str, args: Map<String, Value>) -> Result<Value> {
            match method {
                "policy" => Ok(json!({"revision": 0, "args": args})),
                "busy" => Err(Error::Conflict("command_in_progress".into())),
                "missing" => Err(Error::Unavailable("target_network_not_initialized".into())),
                "broken" => Err(Error::Network("command_failed:nft".into())),
                _ => invalid("unknown_rpc_method"),
            }
        }
    }

    struct Server {
        _dir: TempDir,
        path: PathBuf,
        stop: Arc<AtomicBool>,
        uid: Arc<AtomicU32>,
        thread: Option<std::thread::JoinHandle<()>>,
    }

    impl Server {
        fn start() -> Server {
            let dir = TempDir::new();
            let path = dir.path().join("control.sock");
            let listener = bind(&path).unwrap();
            let stop = Arc::new(AtomicBool::new(false));
            let uid = Arc::new(AtomicU32::new(crate::fsutil::getuid()));
            let (s, u) = (stop.clone(), uid.clone());
            let thread = std::thread::spawn(move || {
                // The allowed UID is read per connection so the test can change it.
                while !s.load(Ordering::SeqCst) {
                    if !signals::wait_readable(listener.as_raw_fd(), 50) {
                        continue;
                    }
                    if let Ok((stream, _)) = listener.accept() {
                        handle(stream, &Fake, u.load(Ordering::SeqCst));
                    }
                }
            });
            Server { _dir: dir, path, stop, uid, thread: Some(thread) }
        }
    }

    impl Drop for Server {
        fn drop(&mut self) {
            self.stop.store(true, Ordering::SeqCst);
            if let Some(thread) = self.thread.take() {
                let _ = thread.join();
            }
        }
    }

    #[test]
    fn allowlist_errors_and_peer_uid() {
        let server = Server::start();
        assert_eq!(std::fs::metadata(&server.path).unwrap().mode() & 0o777, 0o660);
        let remote = RemoteApi { path: server.path.clone() };
        let mut args = Map::new();
        args.insert("x".into(), json!(1));
        assert_eq!(remote.call("policy", args).unwrap(), json!({"revision": 0, "args": {"x": 1}}));
        assert_eq!(remote.call("busy", Map::new()).unwrap_err(), Error::Conflict("command_in_progress".into()));
        assert_eq!(remote.call("missing", Map::new()).unwrap_err(), Error::Unavailable("capability_unavailable".into()));
        assert_eq!(remote.call("broken", Map::new()).unwrap_err(), Error::Invalid("invalid_or_failed_operation".into()));
        assert_eq!(remote.call("execute", Map::new()).unwrap_err(), Error::Invalid("invalid_or_failed_operation".into()));
        server.uid.store(crate::fsutil::getuid() + 1, Ordering::SeqCst);
        assert!(remote.call("policy", Map::new()).is_err());
    }

    #[test]
    fn malformed_requests_get_generic_error() {
        let server = Server::start();
        for request in [json!([1]), json!({"method": "policy"}), json!({"method": 1, "args": {}}), json!({"method": "policy", "args": [], "x": 1}), json!({"method": "policy", "args": []})] {
            let mut stream = UnixStream::connect(&server.path).unwrap();
            send(&mut stream, &request).unwrap();
            assert_eq!(receive_unix(&mut stream).unwrap(), json!({"error": "invalid_or_failed_operation"}));
        }
        let mut stream = UnixStream::connect(&server.path).unwrap();
        stream.write_all(&[0, 0, 0, 0]).unwrap();
        assert_eq!(receive_unix(&mut stream).unwrap(), json!({"error": "invalid_or_failed_operation"}));
    }

    #[test]
    fn refuses_to_replace_regular_file_or_symlink() {
        let dir = TempDir::new();
        let file = dir.path().join("control.sock");
        std::fs::write(&file, b"x").unwrap();
        assert_eq!(serve(&file, &Fake, 0).unwrap_err().code(), "unsafe_control_socket");
        let link = dir.path().join("link.sock");
        std::os::unix::fs::symlink(&file, &link).unwrap();
        assert_eq!(serve(&link, &Fake, 0).unwrap_err().code(), "unsafe_control_socket");
    }

    #[test]
    fn strict_json_at_protocol_boundary() {
        for value in [&br#"{"a":1,"a":2}"#[..], br#"{"a":NaN}"#, br#"{"a":Infinity}"#] {
            let (mut left, mut right) = UnixStream::pair().unwrap();
            left.write_all(&(value.len() as u32).to_be_bytes()).unwrap();
            left.write_all(value).unwrap();
            assert!(receive_unix(&mut right).is_err());
        }
        let (mut left, mut right) = UnixStream::pair().unwrap();
        left.write_all(&((LIMIT + 1) as u32).to_be_bytes()).unwrap();
        assert_eq!(receive_unix(&mut right).unwrap_err().code(), "rpc_too_large");
        let (mut left, mut right) = UnixStream::pair().unwrap();
        left.write_all(&[0, 0, 0, 5, b'{']).unwrap();
        drop(left);
        assert_eq!(receive_unix(&mut right).unwrap_err().code(), "truncated_rpc");
    }

    /// Delivers one byte per read after a delay: partial reads must not reset the deadline.
    struct Slow(Vec<u8>, usize);

    impl Read for Slow {
        fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
            std::thread::sleep(Duration::from_millis(30));
            if self.1 >= self.0.len() || buf.is_empty() {
                return Ok(0);
            }
            buf[0] = self.0[self.1];
            self.1 += 1;
            Ok(1)
        }
    }

    #[test]
    fn total_deadline_not_reset_by_partial_reads() {
        let mut frame = 2u32.to_be_bytes().to_vec();
        frame.extend_from_slice(b"{}");
        let mut slow = Slow(frame.clone(), 0);
        let error = receive_until(&mut slow, Instant::now() + Duration::from_millis(100), |_, _| Ok(())).unwrap_err();
        assert_eq!(error.code(), "rpc_read_deadline");
        let mut slow = Slow(frame, 0);
        assert_eq!(receive_until(&mut slow, Instant::now() + Duration::from_secs(5), |_, _| Ok(())).unwrap(), json!({}));
    }
}
