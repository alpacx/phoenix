//! USB-only socket activation and HTTP-to-HTTPS redirect; no wildcard
//! binding (usb_admin.py). systemd binds 192.168.7.1 on phusb0 only; this
//! process verifies that before serving anything.
use crate::args::usage_error;
use crate::error::{invalid, Result};
use crate::http::{self, Conn, ParseError};
use crate::signals;
use std::io::{Read, Write};
use std::net::{Ipv4Addr, SocketAddrV4, TcpListener};
use std::os::fd::{AsRawFd, FromRawFd, RawFd};

const LISTEN_FD: RawFd = 3;
const USB_ADDRESS: Ipv4Addr = Ipv4Addr::new(192, 168, 7, 1);
const USB_DEVICE: &str = "phusb0";

fn int_option(fd: RawFd, name: libc::c_int) -> Option<libc::c_int> {
    let mut value: libc::c_int = 0;
    let mut length = std::mem::size_of::<libc::c_int>() as libc::socklen_t;
    let status = unsafe { libc::getsockopt(fd, libc::SOL_SOCKET, name, &mut value as *mut _ as *mut libc::c_void, &mut length) };
    (status == 0).then_some(value)
}

fn bound_device(fd: RawFd) -> Option<Vec<u8>> {
    let mut buffer = [0u8; 64];
    let mut length = buffer.len() as libc::socklen_t;
    let status = unsafe { libc::getsockopt(fd, libc::SOL_SOCKET, libc::SO_BINDTODEVICE, buffer.as_mut_ptr() as *mut libc::c_void, &mut length) };
    if status != 0 {
        return None;
    }
    let mut name = buffer[..(length as usize).min(buffer.len())].to_vec();
    while name.last() == Some(&0) {
        name.pop();
    }
    Some(name)
}

fn local_address(fd: RawFd) -> Option<SocketAddrV4> {
    let mut storage: libc::sockaddr_storage = unsafe { std::mem::zeroed() };
    let mut length = std::mem::size_of::<libc::sockaddr_storage>() as libc::socklen_t;
    let status = unsafe { libc::getsockname(fd, &mut storage as *mut _ as *mut libc::sockaddr, &mut length) };
    if status != 0 || storage.ss_family as libc::c_int != libc::AF_INET {
        return None;
    }
    let address = unsafe { *(&storage as *const _ as *const libc::sockaddr_in) };
    Some(SocketAddrV4::new(Ipv4Addr::from(u32::from_be(address.sin_addr.s_addr)), u16::from_be(address.sin_port)))
}

/// AF_INET stream socket bound to `expected` on `device`, already listening.
fn check_listener(fd: RawFd, expected: SocketAddrV4, device: &str) -> Result<()> {
    let isolated = local_address(fd) == Some(expected)
        && int_option(fd, libc::SO_TYPE) == Some(libc::SOCK_STREAM)
        && bound_device(fd).as_deref() == Some(device.as_bytes())
        && int_option(fd, libc::SO_ACCEPTCONN).map(|v| v != 0).unwrap_or(false);
    if isolated {
        Ok(())
    } else {
        invalid("usb_admin_socket_not_isolated")
    }
}

fn activation_env(pid: Option<&str>, fds: Option<&str>) -> Result<()> {
    if pid != Some(std::process::id().to_string().as_str()) || fds != Some("1") {
        return invalid("one_systemd_socket_required");
    }
    Ok(())
}

/// The single systemd-activated listener (fd 3), checked to be bound to
/// 192.168.7.1:`port` on device phusb0 and listening.
pub fn activated_listener(port: u16) -> Result<TcpListener> {
    let pid = std::env::var("LISTEN_PID").ok();
    let fds = std::env::var("LISTEN_FDS").ok();
    activation_env(pid.as_deref(), fds.as_deref())?;
    match check_listener(LISTEN_FD, SocketAddrV4::new(USB_ADDRESS, port), USB_DEVICE) {
        Ok(()) => Ok(unsafe { TcpListener::from_raw_fd(LISTEN_FD) }),
        Err(error) => {
            unsafe { libc::close(LISTEN_FD) };
            Err(error)
        }
    }
}

/// Never reflect Host, path or query; do not handle credentials over HTTP.
fn redirect_one<S: Read + Write>(stream: &mut S) {
    let mut conn = Conn::new(stream);
    match http::read_request(&mut conn) {
        Ok(request) => match request.method.as_str() {
            "GET" | "HEAD" => http::write_response(&mut conn, 308, &[("Location", "https://192.168.7.1/"), ("Content-Length", "0"), ("Cache-Control", "no-store")], b""),
            "POST" => http::write_response(&mut conn, 405, &[("Allow", "GET, HEAD"), ("Content-Length", "0")], b""),
            _ => http::send_error(&mut conn, 501, "Unsupported method"),
        },
        Err(ParseError::Closed) => {}
        Err(ParseError::Status(code, message)) => http::send_error(&mut conn, code, message),
    }
}

/// `phoenix usb-redirect`: socket-activated port 80 redirect server.
pub fn main(args: &[String]) -> i32 {
    if !args.is_empty() {
        return usage_error("usb-redirect takes no arguments");
    }
    let listener = match activated_listener(80) {
        Ok(listener) => listener,
        Err(error) => {
            eprintln!("USB redirect socket rejected: {error}");
            return 1;
        }
    };
    signals::install();
    while !signals::stopping() {
        if !signals::wait_readable(listener.as_raw_fd(), 500) {
            continue;
        }
        if let Ok((stream, _)) = listener.accept() {
            // Absolute deadline: a trickling peer cannot hold the redirect loop.
            redirect_one(&mut crate::http::Deadlined::new(stream, crate::http::CONNECTION_DEADLINE));
        }
    }
    0
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::http::tests::{Mock, Response};

    fn redirect(raw: &str) -> Response {
        let mut mock = Mock::new(raw.as_bytes());
        redirect_one(&mut mock);
        Response::parse(&mock.output)
    }

    #[test]
    fn redirect_fixed_destination_and_no_http_api() {
        let response = redirect("GET //evil.test/?token=secret HTTP/1.1\r\nHost: evil.test\r\n\r\n");
        assert_eq!(response.status, 308);
        assert_eq!(response.header("Location"), Some("https://192.168.7.1/"));
        assert_eq!(response.header("Cache-Control"), Some("no-store"));
        assert!(response.body.is_empty());
        assert_eq!(redirect("HEAD / HTTP/1.0\r\n\r\n").status, 308);
        let post = redirect("POST /api/v1/vpn HTTP/1.1\r\nContent-Length: 2\r\n\r\n{}");
        assert_eq!((post.status, post.header("Allow")), (405, Some("GET, HEAD")));
        assert_eq!(redirect("PUT / HTTP/1.0\r\n\r\n").status, 501);
    }

    #[test]
    fn activation_requires_systemd_variables() {
        let pid = std::process::id().to_string();
        assert!(activation_env(None, None).is_err());
        assert!(activation_env(Some("1"), Some("1")).is_err());
        assert!(activation_env(Some(&pid), Some("2")).is_err());
        assert!(activation_env(Some(&pid), Some("1")).is_ok());
    }

    fn bound_socket(listen: bool, device: Option<&str>) -> (RawFd, SocketAddrV4) {
        unsafe {
            let fd = libc::socket(libc::AF_INET, libc::SOCK_STREAM, 0);
            assert!(fd >= 0);
            if let Some(device) = device {
                let name = device.as_bytes();
                assert_eq!(libc::setsockopt(fd, libc::SOL_SOCKET, libc::SO_BINDTODEVICE, name.as_ptr() as *const libc::c_void, name.len() as libc::socklen_t), 0, "SO_BINDTODEVICE needs root/CAP_NET_RAW");
            }
            let mut address: libc::sockaddr_in = std::mem::zeroed();
            address.sin_family = libc::AF_INET as libc::sa_family_t;
            address.sin_addr.s_addr = u32::from(Ipv4Addr::LOCALHOST).to_be();
            assert_eq!(libc::bind(fd, &address as *const _ as *const libc::sockaddr, std::mem::size_of::<libc::sockaddr_in>() as libc::socklen_t), 0);
            if listen {
                assert_eq!(libc::listen(fd, 1), 0);
            }
            (fd, local_address(fd).unwrap())
        }
    }

    #[test]
    fn listener_must_be_bound_listening_and_device_isolated() {
        let (fd, address) = bound_socket(true, Some("lo"));
        assert!(check_listener(fd, address, "lo").is_ok());
        assert!(check_listener(fd, address, "phusb0").is_err(), "wrong device");
        assert!(check_listener(fd, SocketAddrV4::new(USB_ADDRESS, address.port()), "lo").is_err(), "wrong address");
        assert!(check_listener(fd, SocketAddrV4::new(*address.ip(), address.port().wrapping_add(1)), "lo").is_err(), "wrong port");
        unsafe { libc::close(fd) };
        let (fd, address) = bound_socket(false, Some("lo"));
        assert!(check_listener(fd, address, "lo").is_err(), "not listening");
        unsafe { libc::close(fd) };
        let (fd, address) = bound_socket(true, None);
        assert!(check_listener(fd, address, "lo").is_err(), "no device binding");
        unsafe { libc::close(fd) };
    }
}
