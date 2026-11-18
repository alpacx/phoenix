//! Bound HTTPS upload of synthetic sparse payloads; only fully acknowledged
//! requests count (uploadcheck.py).
use crate::error::{invalid, Result};
use crate::json::{json, Map, Value};
use crate::lan::{Proc, Spawn};
use crate::py;
use std::fs::{File, OpenOptions};
use std::os::unix::fs::OpenOptionsExt;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

pub const ENDPOINT: &str = "https://speed.cloudflare.com/__up";

/// `size_upload http_code` must report the whole payload with HTTP 200.
pub fn acknowledged(code: i32, output: &str, expected: u64) -> Result<u64> {
    let parts = py::split_ws(output);
    if parts.len() != 2 {
        return invalid("upload_not_acknowledged");
    }
    let size: f64 = py::strip(parts[0]).parse().or_else(|_| invalid("upload_not_acknowledged"))?;
    if code != 0 || parts[1] != "200" || !size.is_finite() || size != expected as f64 {
        return invalid("upload_not_acknowledged");
    }
    Ok(size as u64)
}

/// Sparse zero-filled temporary file: bounded size, no user data or bulk
/// disk writes; removed when dropped.
struct Payload {
    path: PathBuf,
    file: File,
}

impl Payload {
    fn create() -> std::io::Result<Payload> {
        loop {
            let path = std::env::temp_dir().join(format!("phoenix-upload-{}", py::token_hex(6)));
            match OpenOptions::new().read(true).write(true).create_new(true).mode(0o600).custom_flags(libc::O_NOFOLLOW).open(&path) {
                Ok(file) => return Ok(Payload { path, file }),
                Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(e) => return Err(e),
            }
        }
    }
}

impl Drop for Payload {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.path);
    }
}

/// Returns upload_mbps/upload_mb/upload_seconds/upload_server/upload_error/upload_peak_c.
pub fn run(curl: &str, name: &str, stop: &AtomicBool, temperature: &dyn Fn() -> Vec<f64>, duration: f64, streams: usize) -> Map<String, Value> {
    run_with(curl, name, stop, temperature, duration, streams, &(Arc::new(crate::lan::os_spawn) as Spawn))
}

struct Shared<'a> {
    curl: &'a str,
    name: &'a str,
    stop: &'a AtomicBool,
    abort: AtomicBool,
    deadline: f64,
    spawn: &'a Spawn,
}

impl Shared<'_> {
    fn halted(&self) -> bool {
        self.abort.load(Ordering::SeqCst) || self.stop.load(Ordering::SeqCst)
    }

    /// One stream: sequential POSTs with adaptive size until the deadline.
    fn transfer(&self, count: &Mutex<u64>, current: &mut Option<Box<dyn Proc>>) -> Result<()> {
        let payload = Payload::create()?;
        let mut size: u64 = 256 * 1024;
        while !self.halted() && py::monotonic() < self.deadline {
            payload.file.set_len(size)?;
            let remaining = self.deadline - py::monotonic();
            if remaining <= 0.05 {
                break;
            }
            let sent_at = py::monotonic();
            let argv: Vec<String> = [
                self.curl, "--disable", "-4", "--interface", &format!("if!{}", self.name),
                "--noproxy", "*", "--proto", "=https", "--connect-timeout", "5",
                "--max-time", &remaining.to_string(), "--silent", "--output", "/dev/null",
                "--request", "POST", "--header", "Content-Type: application/octet-stream",
                "--header", "Expect:", "--upload-file", &payload.path.to_string_lossy(),
                "--write-out", "%{size_upload} %{http_code}", ENDPOINT,
            ]
            .iter()
            .map(|s| s.to_string())
            .collect();
            *current = Some((self.spawn)(&argv, true)?);
            let process = current.as_mut().expect("just spawned");
            while process.wait_timeout(0.1).is_none() {
                if self.halted() || py::monotonic() >= self.deadline {
                    process.terminate();
                    if process.wait_timeout(1.0).is_none() {
                        process.kill();
                        process.wait_timeout(5.0);
                    }
                    break;
                }
            }
            let code = process.poll();
            let output = process.stdout(1024);
            if code == Some(0) {
                if !output.is_ascii() {
                    return invalid("upload_not_acknowledged");
                }
                *count.lock().unwrap() += acknowledged(0, &String::from_utf8_lossy(&output), size)?;
                let elapsed = (py::monotonic() - sent_at).max(0.001);
                size = ((size as f64 / elapsed * 0.5) as u64).clamp(16 * 1024, 16 * 1024 * 1024);
            } else if py::monotonic() >= self.deadline - 0.1 || self.halted() {
                break; // Partial requests are deliberately excluded.
            } else {
                return invalid("upload_failed");
            }
        }
        Ok(())
    }
}

pub fn run_with(curl: &str, name: &str, stop: &AtomicBool, temperature: &dyn Fn() -> Vec<f64>, duration: f64, streams: usize, spawn: &Spawn) -> Map<String, Value> {
    let start = py::monotonic();
    let shared = Shared { curl, name, stop, abort: AtomicBool::new(false), deadline: start + duration, spawn };
    let counts: Vec<Mutex<u64>> = (0..streams).map(|_| Mutex::new(0)).collect();
    let failures = Mutex::new(Vec::<String>::new());
    let mut peak: Option<f64> = None;
    let mut error = String::new();
    std::thread::scope(|scope| {
        let workers: Vec<_> = counts
            .iter()
            .map(|count| {
                let (shared, failures) = (&shared, &failures);
                scope.spawn(move || {
                    let mut current: Option<Box<dyn Proc>> = None;
                    if shared.transfer(count, &mut current).is_err() {
                        failures.lock().unwrap().push("upload_failed".into());
                        shared.abort.store(true, Ordering::SeqCst);
                    }
                    if let Some(process) = current.as_mut() {
                        if process.poll().is_none() {
                            process.kill();
                            process.wait_timeout(5.0);
                        }
                    }
                })
            })
            .collect();
        while workers.iter().any(|w| !w.is_finished()) {
            for t in temperature() {
                peak = Some(peak.map_or(t, |p: f64| p.max(t)));
            }
            if stop.load(Ordering::SeqCst) {
                error = "cancelled".into();
            } else if peak.is_some_and(|p| p >= 75.0) {
                error = "temperature_limit".into();
            }
            if !error.is_empty() {
                shared.abort.store(true, Ordering::SeqCst);
            }
            let pause = if shared.abort.load(Ordering::SeqCst) { 20 } else { 100 };
            std::thread::sleep(Duration::from_millis(pause));
        }
    });
    let elapsed = py::monotonic() - start;
    let total: u64 = counts.iter().map(|c| *c.lock().unwrap()).sum();
    if error.is_empty() {
        error = failures.lock().unwrap().first().cloned().unwrap_or_default();
    }
    if error.is_empty() && total == 0 {
        error = "upload_failed".into();
    }
    let value = json!({
        "upload_mbps": if error.is_empty() { json!(py::round(total as f64 * 8.0 / elapsed / 1e6, 2)) } else { Value::Null },
        "upload_mb": py::round(total as f64 / 1e6, 1),
        "upload_seconds": py::round(elapsed, 2),
        "upload_server": "Cloudflare · HTTPS",
        "upload_error": error,
        "upload_peak_c": peak,
    });
    value.as_object().cloned().unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_full_successful_requests_count() {
        assert_eq!(acknowledged(0, "1024 200", 1024).unwrap(), 1024);
        for (code, out) in [(28, "1024 200"), (0, "1024 413"), (0, "nan 200"), (0, "512 200"), (0, "1024 302"), (0, "1024")] {
            assert!(acknowledged(code, out, 1024).is_err(), "{code} {out}");
        }
    }

    struct Fake {
        size: u64,
        polls: u32,
    }

    impl Proc for Fake {
        fn poll(&mut self) -> Option<i32> {
            self.polls += 1;
            (self.polls > 2).then_some(0)
        }
        fn terminate(&mut self) {}
        fn kill(&mut self) {}
        fn stdout(&mut self, _: usize) -> Vec<u8> {
            format!("{} 200", self.size).into_bytes()
        }
    }

    #[test]
    fn native_upload_is_bound_and_uses_only_synthetic_payload() {
        let commands = Arc::new(Mutex::new(Vec::<Vec<String>>::new()));
        let c = commands.clone();
        let spawn: Spawn = Arc::new(move |argv: &[String], capture| {
            assert!(capture);
            let file = &argv[argv.iter().position(|a| a == "--upload-file").unwrap() + 1];
            let size = std::fs::metadata(file).unwrap().len();
            c.lock().unwrap().push(argv.to_vec());
            std::thread::sleep(Duration::from_millis(20));
            Ok(Box::new(Fake { size, polls: 0 }) as Box<dyn Proc>)
        });
        let stop = AtomicBool::new(false);
        let result = run_with("/usr/bin/curl", "phwg0", &stop, &|| vec![50.0], 0.3, 4, &spawn);
        assert!(result["upload_mbps"].as_f64().unwrap() > 0.0, "{result:?}");
        assert_eq!(result["upload_error"], "");
        assert_eq!(result["upload_peak_c"], json!(50.0));
        let commands = commands.lock().unwrap();
        assert!(!commands.is_empty());
        assert!(commands.iter().all(|c| c.contains(&"if!phwg0".to_string()) && c.contains(&"--noproxy".to_string()) && c.contains(&"--request".to_string())));
        assert!(commands.iter().all(|c| !std::path::Path::new(&c[c.iter().position(|a| a == "--upload-file").unwrap() + 1]).exists()));
    }

    #[test]
    fn cancelled_upload_does_not_report_speed() {
        let stop = AtomicBool::new(true);
        let spawn: Spawn = Arc::new(|_: &[String], _| panic!("no transfer after cancel"));
        let result = run_with("/usr/bin/curl", "phwg0", &stop, &|| vec![50.0], 0.1, 4, &spawn);
        assert!(result["upload_mbps"].is_null());
        assert_ne!(result["upload_error"], "");
    }

    #[test]
    fn failed_request_aborts_and_reports_error() {
        struct Failing;
        impl Proc for Failing {
            fn poll(&mut self) -> Option<i32> {
                Some(7)
            }
            fn terminate(&mut self) {}
            fn kill(&mut self) {}
        }
        let spawn: Spawn = Arc::new(|_: &[String], _| Ok(Box::new(Failing) as Box<dyn Proc>));
        let stop = AtomicBool::new(false);
        let result = run_with("/usr/bin/curl", "phwg0", &stop, &|| vec![], 2.0, 2, &spawn);
        assert_eq!(result["upload_error"], "upload_failed");
        assert!(result["upload_mbps"].is_null());
        assert!(result["upload_peak_c"].is_null());
    }
}
