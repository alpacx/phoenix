//! SIGTERM/SIGINT set a process-wide stop flag polled by accept loops.
use std::sync::atomic::{AtomicBool, Ordering};

static STOP: AtomicBool = AtomicBool::new(false);

extern "C" fn handler(_: libc::c_int) {
    STOP.store(true, Ordering::SeqCst);
}

pub fn install() {
    unsafe {
        libc::signal(libc::SIGTERM, handler as extern "C" fn(libc::c_int) as libc::sighandler_t);
        libc::signal(libc::SIGINT, handler as extern "C" fn(libc::c_int) as libc::sighandler_t);
    }
}

pub fn stopping() -> bool {
    STOP.load(Ordering::SeqCst)
}

pub fn request_stop() {
    STOP.store(true, Ordering::SeqCst);
}

/// Wait until `fd` is readable, the timeout elapses or a stop is requested.
/// Returns true when readable. Used by single-threaded accept loops.
pub fn wait_readable(fd: std::os::fd::RawFd, timeout_ms: i32) -> bool {
    let mut pfd = libc::pollfd { fd, events: libc::POLLIN, revents: 0 };
    let ready = unsafe { libc::poll(&mut pfd, 1, timeout_ms) };
    ready > 0 && pfd.revents & libc::POLLIN != 0
}
