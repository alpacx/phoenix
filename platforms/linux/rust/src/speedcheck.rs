//! Native HTTPS download and upload benchmark via curl; no automatic
//! interface or server fallback (speedcheck.py).
use crate::error::{invalid, Result};
use crate::firewall::interface;
use crate::json::{json, Map, Value};
use crate::lan::{self, Proc, Spawn};
use crate::py;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

pub const ENDPOINT: &str = "https://speedtest3.serverius.net/files/1000mb.bin";
pub const STREAMS: usize = 4;
pub const DURATION: u64 = 10;
const SERVER: &str = "Serverius DC3 · HTTPS";
const LIMIT_C: f64 = 75.0;

pub fn available() -> bool {
    lan::which("curl").is_some()
}

/// Thermal zone temperatures in degrees C.
pub fn temperatures() -> Vec<f64> {
    temperatures_at(Path::new("/sys/class/thermal"))
}

/// `<dir>/thermal_zone*/temp` in millidegrees; unreadable zones are skipped.
pub fn temperatures_at(dir: &Path) -> Vec<f64> {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return Vec::new();
    };
    entries
        .flatten()
        .filter(|e| e.file_name().to_string_lossy().starts_with("thermal_zone"))
        .filter_map(|e| std::fs::read_to_string(e.path().join("temp")).ok())
        .filter_map(|text| py::strip(&text).parse::<i64>().ok())
        .map(|milli| milli as f64 / 1000.0)
        .collect()
}

fn max_peak(peak: Option<f64>, temps: &[f64]) -> Option<f64> {
    temps.iter().copied().fold(peak, |acc, t| Some(acc.map_or(t, |a| a.max(t))))
}

fn float(text: &str) -> Result<f64> {
    py::strip(text).parse::<f64>().or_else(|_| invalid("invalid_measurement"))
}

/// Per-stream curl `--write-out` samples -> download result fields.
pub fn sanitize(samples: &[(i32, String)], elapsed: f64) -> Result<Map<String, Value>> {
    if !elapsed.is_finite() || elapsed <= 0.0 || samples.len() != STREAMS {
        return invalid("invalid_measurement");
    }
    let mut total = 0.0;
    for (code, output) in samples {
        let parts = py::split_ws(output);
        if parts.len() != 3 {
            return invalid("invalid_measurement");
        }
        let (size, seconds, http) = (float(parts[0])?, float(parts[1])?, parts[2]);
        if !(*code == 0 || *code == 28)
            || http != "200"
            || !size.is_finite()
            || !seconds.is_finite()
            || size <= 0.0
            || seconds <= 0.0
            || (*code == 28 && seconds < DURATION as f64 - 0.5)
        {
            return invalid("invalid_measurement");
        }
        total += size;
    }
    let value = json!({
        "download_mbps": py::round(total * 8.0 / elapsed / 1e6, 2),
        "download_mb": py::round(total / 1e6, 1),
        "upload_mbps": null, "ping_ms": null, "streams": STREAMS,
        "engine": "curl-native", "metric": "https_download",
        "server": SERVER, "server_id": "serverius-dc3",
        "measurement_seconds": py::round(elapsed, 2),
    });
    Ok(value.as_object().cloned().unwrap_or_default())
}

pub type Temperatures = Arc<dyn Fn() -> Vec<f64> + Send + Sync>;
/// (curl, interface, stop, temperatures) -> uploadcheck::run result.
pub type Upload = Arc<dyn Fn(&str, &str, &AtomicBool, &dyn Fn() -> Vec<f64>) -> Map<String, Value> + Send + Sync>;

/// Injectable side effects (Python tests patched these).
#[derive(Clone)]
pub struct Hooks {
    pub spawn: Spawn,
    pub temperatures: Temperatures,
    pub interface_exists: Arc<dyn Fn(&str) -> bool + Send + Sync>,
    pub which: Arc<dyn Fn(&str) -> Option<String> + Send + Sync>,
    pub upload: Upload,
}

impl Default for Hooks {
    fn default() -> Self {
        Hooks {
            spawn: Arc::new(lan::os_spawn),
            temperatures: Arc::new(temperatures),
            interface_exists: Arc::new(|name| Path::new("/sys/class/net").join(name).exists()),
            which: Arc::new(lan::which),
            upload: Arc::new(|curl, name, stop, temperature| crate::uploadcheck::run(curl, name, stop, temperature, DURATION as f64, STREAMS)),
        }
    }
}

struct State {
    started: Option<f64>,
    value: Map<String, Value>,
}

pub struct Measurement {
    state: Mutex<State>,
    stop: AtomicBool,
    hooks: Hooks,
}

impl Measurement {
    pub fn new() -> Self {
        Self::with_hooks(Hooks::default())
    }

    pub fn with_hooks(hooks: Hooks) -> Self {
        let mut value = Map::new();
        value.insert("state".into(), json!("idle"));
        Measurement { state: Mutex::new(State { started: None, value }), stop: AtomicBool::new(false), hooks }
    }

    pub fn status(&self) -> Value {
        let state = self.state.lock().unwrap();
        let mut value = state.value.clone();
        if value.get("state").and_then(Value::as_str) == Some("running") {
            let elapsed = state.started.map(|s| (py::monotonic() - s) as i64).unwrap_or(0);
            value.insert("elapsed_seconds".into(), json!(elapsed));
        }
        Value::Object(value)
    }

    pub fn is_running(&self) -> bool {
        self.state.lock().unwrap().value.get("state").and_then(Value::as_str) == Some("running")
    }

    pub fn prepare(&self, mode: &str, name: &str, destination: &str) -> Result<()> {
        interface(name)?;
        let mut state = self.state.lock().unwrap();
        if let Some(started) = state.started {
            if py::monotonic() - started < 60.0 {
                return invalid("speedtest_cooldown");
            }
        }
        self.stop.store(false, Ordering::SeqCst);
        state.started = Some(py::monotonic());
        let value = json!({
            "state": "running", "mode": mode, "destination": destination,
            "server": SERVER, "engine": "curl-native",
            "started_at": py::wall() as i64, "elapsed_seconds": 0, "phase": "download",
        });
        state.value = value.as_object().cloned().unwrap_or_default();
        Ok(())
    }

    pub fn cancel(&self) {
        self.stop.store(true, Ordering::SeqCst);
    }

    fn started(&self) -> f64 {
        self.state.lock().unwrap().started.unwrap_or_else(py::monotonic)
    }

    /// Blocking; always leaves a final state (complete/error/cancelled).
    pub fn run(&self, name: &str) {
        let mut processes: Vec<Box<dyn Proc>> = Vec::new();
        let mut peak: Option<f64> = None;
        let mut result: Map<String, Value> = Map::new();
        let outcome = self.measure(name, &mut processes, &mut peak, &mut result);
        let error = match outcome {
            Ok(error) => error,
            Err(_) => "measurement_failed".to_string(),
        };
        // Every child is stopped, including partial startup and cancellation.
        for process in processes.iter_mut() {
            if process.poll().is_none() {
                process.terminate();
            }
        }
        for process in processes.iter_mut() {
            if process.wait_timeout(1.0).is_none() {
                process.kill();
                process.wait_timeout(1.0);
            }
        }
        let started = self.started();
        let mut state = self.state.lock().unwrap();
        for (key, value) in result {
            state.value.insert(key, value);
        }
        let final_state = if error == "cancelled" {
            "cancelled"
        } else if !error.is_empty() {
            "error"
        } else {
            "complete"
        };
        state.value.insert("state".into(), json!(final_state));
        state.value.insert("error".into(), json!(error));
        state.value.insert("peak_c".into(), peak.map(|p| json!(py::round(p, 1))).unwrap_or(Value::Null));
        state.value.insert("elapsed_seconds".into(), json!((py::monotonic() - started) as i64));
    }

    /// Returns the error code ("" on success); Err means measurement_failed.
    fn measure(&self, name: &str, processes: &mut Vec<Box<dyn Proc>>, peak: &mut Option<f64>, result: &mut Map<String, Value>) -> Result<String> {
        let name = interface(name)?;
        if !(self.hooks.interface_exists)(&name) {
            return invalid("missing_interface");
        }
        let curl = (self.hooks.which)("curl").ok_or_else(|| crate::error::Error::Invalid("curl_missing".into()))?;
        *peak = max_peak(None, &(self.hooks.temperatures)());
        if peak.is_some_and(|p| p >= LIMIT_C) {
            return Ok("temperature_limit".into());
        }
        if self.stop.load(Ordering::SeqCst) {
            return Ok("cancelled".into());
        }
        let start = py::monotonic();
        for _ in 0..STREAMS {
            // --disable first: ignore .curlrc. No proxy, redirect or retry.
            let argv: Vec<String> = [
                curl.as_str(), "--disable", "-4", "--interface", &format!("if!{name}"),
                "--noproxy", "*", "--proto", "=https", "--connect-timeout", "5",
                "--max-time", &DURATION.to_string(), "--silent", "--output", "/dev/null",
                "--write-out", "%{size_download} %{time_total} %{http_code}", ENDPOINT,
            ]
            .iter()
            .map(|s| s.to_string())
            .collect();
            processes.push((self.hooks.spawn)(&argv, true)?);
        }
        let started = self.started();
        let mut error = String::new();
        while processes.iter_mut().any(|p| p.poll().is_none()) {
            let temps = (self.hooks.temperatures)();
            *peak = max_peak(*peak, &temps);
            if self.stop.load(Ordering::SeqCst) {
                error = "cancelled".into();
            } else if peak.is_some_and(|p| p >= LIMIT_C) {
                error = "temperature_limit".into();
            } else if py::monotonic() - started >= 20.0 {
                error = "time_limit".into();
            }
            if !error.is_empty() {
                return Ok(error);
            }
            std::thread::sleep(Duration::from_millis(100));
        }
        let elapsed = py::monotonic() - start;
        let mut samples = Vec::new();
        for process in processes.iter_mut() {
            let code = process.poll().unwrap_or(-1);
            let output = process.stdout(1024);
            if !output.is_ascii() {
                return invalid("invalid_measurement");
            }
            samples.push((code, String::from_utf8_lossy(&output).into_owned()));
        }
        *result = sanitize(&samples, elapsed)?;
        {
            let mut state = self.state.lock().unwrap();
            for (key, value) in result.iter() {
                state.value.insert(key.clone(), value.clone());
            }
            state.value.insert("phase".into(), json!("upload"));
        }
        let temperatures = self.hooks.temperatures.clone();
        let mut uploaded = (self.hooks.upload)(&curl, &name, &self.stop, &move || temperatures());
        let upload_peak = uploaded.shift_remove("upload_peak_c").and_then(|v| v.as_f64());
        if let Some(upload_peak) = upload_peak {
            *peak = Some(peak.map_or(upload_peak, |p| p.max(upload_peak)));
        }
        let upload_seconds = uploaded.get("upload_seconds").and_then(Value::as_f64).unwrap_or(0.0);
        let upload_error = uploaded.get("upload_error").and_then(Value::as_str).unwrap_or("").to_string();
        for (key, value) in uploaded {
            result.insert(key, value);
        }
        let download_seconds = result.get("measurement_seconds").cloned().unwrap_or(Value::Null);
        result.insert("download_seconds".into(), download_seconds);
        result.insert("measurement_seconds".into(), json!(py::round(elapsed + upload_seconds, 2)));
        result.insert("metric".into(), json!("https_download_upload"));
        if upload_error == "cancelled" || upload_error == "temperature_limit" {
            error = upload_error;
        }
        Ok(error)
    }
}

impl Default for Measurement {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn samples(code: i32, out: &str, n: usize) -> Vec<(i32, String)> {
        vec![(code, out.to_string()); n]
    }

    #[test]
    fn result_conversion_and_no_client_metadata() {
        let value = sanitize(&samples(28, "100000000 10.0 200", 4), 10.0).unwrap();
        assert_eq!(value["download_mbps"], json!(320.0));
        assert_eq!(value["download_mb"], json!(400.0));
        assert!(value["upload_mbps"].is_null() && value["ping_ms"].is_null());
        for bad in ["nan 10 200", "inf 10 200", "-1 10 200", "1 10 302", "1 10 500", "1 0.1 200", "1 10", "x 10 200"] {
            assert!(sanitize(&samples(28, bad, 4), 10.0).is_err(), "{bad}");
        }
        assert!(sanitize(&samples(7, "1000 10 200", 4), 10.0).is_err());
        assert!(sanitize(&samples(28, "1000 10 200", 1), 10.0).is_err());
        assert!(sanitize(&samples(0, "1000 1 200", 4), 0.0).is_err());
    }

    #[test]
    fn cooldown_and_interface_validation() {
        let m = Measurement::new();
        assert!(m.prepare("vpn", "../eth0", "").is_err());
        m.prepare("vpn", "phwg0", "Example").unwrap();
        assert!(m.prepare("vpn", "phwg0", "Example").is_err());
        assert_eq!(m.status()["mode"], "vpn");
        assert_eq!(m.status()["state"], "running");
        assert!(m.is_running());
    }

    struct Fake {
        code: Option<i32>,
        out: &'static str,
        log: Arc<Mutex<Vec<String>>>,
    }

    impl Proc for Fake {
        fn poll(&mut self) -> Option<i32> {
            self.code
        }
        fn terminate(&mut self) {
            if self.code.is_none() {
                self.code = Some(-15);
                self.log.lock().unwrap().push("terminate".into());
            }
        }
        fn kill(&mut self) {
            self.code = Some(-9);
        }
        fn stdout(&mut self, _: usize) -> Vec<u8> {
            self.out.as_bytes().to_vec()
        }
    }

    fn hooks(temps: f64, spawn: Spawn) -> Hooks {
        Hooks {
            spawn,
            temperatures: Arc::new(move || vec![temps]),
            interface_exists: Arc::new(|_| true),
            which: Arc::new(|_| Some("/usr/bin/curl".into())),
            upload: Arc::new(|_, _, _, _| {
                json!({"upload_mbps": 12.5, "upload_mb": 15.6, "upload_seconds": 10.01, "upload_server": "Cloudflare · HTTPS", "upload_error": "", "upload_peak_c": 61.0})
                    .as_object()
                    .cloned()
                    .unwrap()
            }),
        }
    }

    #[test]
    fn thermal_limit_terminates_worker() {
        let log = Arc::new(Mutex::new(Vec::new()));
        let spawned = log.clone();
        let m = Measurement::with_hooks(hooks(76.0, Arc::new(move |_, _| {
            spawned.lock().unwrap().push("spawn".into());
            Ok(Box::new(Fake { code: None, out: "", log: spawned.clone() }) as Box<dyn Proc>)
        })));
        m.prepare("vpn", "phwg0", "").unwrap();
        m.run("phwg0");
        assert_eq!(m.status()["error"], "temperature_limit");
        assert_eq!(m.status()["state"], "error");
        assert_eq!(m.status()["peak_c"], json!(76.0));
        assert!(log.lock().unwrap().is_empty(), "too hot: no transfer started");
    }

    #[test]
    fn cancel_stops_all_native_transfers_and_binds_interface() {
        let commands = Arc::new(Mutex::new(Vec::<Vec<String>>::new()));
        let log = Arc::new(Mutex::new(Vec::new()));
        let m = Arc::new(Mutex::new(None::<Arc<Measurement>>));
        let (c, l, mm) = (commands.clone(), log.clone(), m.clone());
        let measurement = Arc::new(Measurement::with_hooks(hooks(50.0, Arc::new(move |argv: &[String], capture| {
            assert!(capture);
            let mut c = c.lock().unwrap();
            c.push(argv.to_vec());
            if c.len() == 4 {
                mm.lock().unwrap().as_ref().unwrap().cancel();
            }
            Ok(Box::new(Fake { code: None, out: "", log: l.clone() }) as Box<dyn Proc>)
        }))));
        *m.lock().unwrap() = Some(measurement.clone());
        measurement.prepare("vpn", "phwg0", "").unwrap();
        measurement.run("phwg0");
        assert_eq!(measurement.status()["state"], "cancelled");
        assert_eq!(commands.lock().unwrap().len(), 4);
        assert_eq!(log.lock().unwrap().len(), 4, "every transfer terminated");
        assert!(commands.lock().unwrap().iter().all(|c| c[1] == "--disable" && c.contains(&"if!phwg0".to_string()) && c.contains(&"--noproxy".to_string())));
    }

    #[test]
    fn complete_measurement_merges_upload() {
        let log = Arc::new(Mutex::new(Vec::new()));
        let l = log.clone();
        let m = Measurement::with_hooks(hooks(50.0, Arc::new(move |_, _| Ok(Box::new(Fake { code: Some(28), out: "12500000 10.0 200", log: l.clone() }) as Box<dyn Proc>))));
        m.prepare("direct", "eth0", "eth0").unwrap();
        m.run("eth0");
        let status = m.status();
        assert_eq!(status["state"], "complete", "{status}");
        assert_eq!(status["error"], "");
        assert_eq!(status["metric"], "https_download_upload");
        assert_eq!(status["upload_mbps"], json!(12.5));
        assert_eq!(status["peak_c"], json!(61.0));
        assert!(status.get("upload_peak_c").is_none());
        assert!(status["download_seconds"].as_f64().unwrap() >= 0.0);
        assert_eq!(status["streams"], 4);
    }

    #[test]
    fn missing_interface_or_curl_fails() {
        let mut h = hooks(50.0, Arc::new(|_, _| Err(std::io::Error::other("no"))));
        h.interface_exists = Arc::new(|_| false);
        let m = Measurement::with_hooks(h);
        m.prepare("vpn", "phwg0", "").unwrap();
        m.run("phwg0");
        assert_eq!(m.status()["error"], "measurement_failed");
        let m = Measurement::with_hooks(hooks(50.0, Arc::new(|_, _| Err(std::io::Error::other("no")))));
        m.prepare("vpn", "phwg0", "").unwrap();
        m.run("phwg0");
        assert_eq!(m.status()["state"], "error");
    }

    #[test]
    fn thermal_zones() {
        let tmp = crate::fsutil::testdir::TempDir::new();
        for (zone, text) in [("thermal_zone0", "45000\n"), ("thermal_zone1", "51500"), ("thermal_zone2", "bad"), ("cooling_device0", "1")] {
            std::fs::create_dir(tmp.path().join(zone)).unwrap();
            std::fs::write(tmp.path().join(zone).join("temp"), text).unwrap();
        }
        let mut temps = temperatures_at(tmp.path());
        temps.sort_by(f64::total_cmp);
        assert_eq!(temps, vec![45.0, 51.5]);
        assert!(temperatures_at(&tmp.path().join("missing")).is_empty());
    }
}
