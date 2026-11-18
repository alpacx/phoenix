//! Privileged worker entry point (server.py main). With --worker-socket it
//! serves the allowlisted RPC for the unprivileged frontend; without it, a
//! loopback-only HTTP development server (not a production service).
use crate::args::{usage_error, Args};
use crate::controller::Controller;
use crate::error::{invalid, Error, Result};
use crate::json::{self, Value};
use crate::lan::Lan;
use crate::local_api::LocalApi;
use crate::runner::{Runner, SharedRunner, SystemRunner};
use crate::runtime::Runtime;
use crate::station::Station;
use crate::{fsutil, http, py, rpc, signals, stop_guard, updates, web};
use std::io::Write;
use std::os::fd::AsRawFd;
use std::os::unix::fs::OpenOptionsExt;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

const IP_FORWARD: &str = "/proc/sys/net/ipv4/ip_forward";
const PRIORITIES: [&str; 4] = ["17690", "17691", "17710", "17711"];

fn model() -> String {
    std::fs::read_to_string("/proc/device-tree/model").unwrap_or_default().trim_matches(|c| c == '\0' || c == '\n').to_string()
}

fn web_uid(name: &str) -> Result<u32> {
    let cname = std::ffi::CString::new(name).map_err(|_| Error::Invalid("invalid_web_user".into()))?;
    let entry = unsafe { libc::getpwnam(cname.as_ptr()) };
    if entry.is_null() {
        return invalid("unknown_web_user");
    }
    Ok(unsafe { (*entry).pw_uid })
}

/// Create the admin token on first start, then validate owner/mode/format.
fn admin_token(state_dir: &Path) -> Result<String> {
    let path = state_dir.join("admin-token");
    if !fsutil::exists(&path) {
        let mut file = std::fs::OpenOptions::new().write(true).create_new(true).mode(0o600).custom_flags(libc::O_NOFOLLOW).open(&path)?;
        file.write_all(py::token_hex(32).as_bytes())?;
    }
    let data = fsutil::read_private(&path, "admin_token_permissions")?;
    let token = String::from_utf8(data).map_err(|_| Error::Invalid("admin_token_format".into()))?;
    let token = py::strip(&token).to_string();
    if token.len() != 64 || !token.bytes().all(|b| matches!(b, b'0'..=b'9' | b'a'..=b'f')) {
        return invalid("admin_token_format");
    }
    Ok(token)
}

fn set_forwarding(value: &str) -> Result<()> {
    std::fs::write(IP_FORWARD, value)?;
    Ok(())
}

struct Owned {
    ap: bool,
    usb: bool,
}

/// Network setup after the controller exists (Python order preserved).
fn attach(controller: &mut Controller, config: &Value, state_dir: &Path, owned: &mut Owned) -> Result<()> {
    let Some(runtime) = &controller.runtime else {
        return Ok(());
    };
    let run: SharedRunner = runtime.run.clone();
    let config = json::object(config)?;
    runtime.disconnect(&controller.policy()?)?;
    for priority in PRIORITIES {
        run.optional(&["ip", "rule", "del", "priority", priority])?;
    }
    if let Some(path) = config.get("updates_config").filter(|v| json::truthy(Some(v))) {
        if path.as_str() != Some("/etc/phoenix/updates.json") {
            return invalid("unexpected_updates_config_path");
        }
        controller.updates = Some(updates::from_config(Path::new("/etc/phoenix/updates.json"))?);
    }
    let names = runtime.names();
    let has_ap_config = json::truthy(config.get("access_point"));
    if let Some(name) = config.get("station_interface").filter(|v| json::truthy(Some(v))) {
        let name = crate::firewall::interface_value(name)?;
        if [&names.uplink, &names.usb, &names.vpn].contains(&&name) {
            return invalid("station_interface_role_conflict");
        }
        let mut station = Station::new(&name, &state_dir.join("wifi"), run.clone(), Some(Path::new("/run/NetworkManager/system-connections")))?;
        station.prepare_startup(has_ap_config && Some(&name) == controller.base_ap.as_ref())?;
        *controller.station.lock().unwrap_or_else(|e| e.into_inner()) = Some(station);
    }
    if let Some(usb) = config.get("usb_gadget").and_then(Value::as_object) {
        if json::truthy(usb.get("enabled")) {
            let dns = json::str_or(usb, "dns", "103.86.96.100")?;
            let mut lan = Lan::usb(&names.usb, dns, Path::new("/run/phoenix/usb"), run.clone())?;
            lan.start()?;
            *controller.usb_lan.lock().unwrap_or_else(|e| e.into_inner()) = Some(lan);
            owned.usb = true;
        }
    }
    if has_ap_config {
        let settings = json::object(config.get("access_point").unwrap_or(&Value::Null))?;
        let password_file = json::field(settings, "password_file")?.as_str().ok_or_else(|| Error::Invalid("wifi_secret_path".into()))?;
        let secret = fsutil::read_private_limited(Path::new(password_file), 65, "wifi_secret_permissions")?;
        let secret = String::from_utf8(secret).map_err(|_| Error::Invalid("wifi_secret_format".into()))?;
        let password = secret.trim_end_matches('\n').to_string();
        let saved = controller.hotspot_vault.load_object()?;
        let enabled = match saved.get("enabled") {
            None => true,
            Some(Value::Bool(b)) => *b,
            Some(_) => return invalid("invalid_hotspot_state"),
        };
        controller.st().hotspot_enabled = enabled;
        let ssid = match saved.get("ssid") {
            Some(Value::String(s)) => s.clone(),
            Some(_) => return invalid("invalid_ssid"),
            None => json::field(settings, "ssid")?.as_str().ok_or_else(|| Error::Invalid("invalid_ssid".into()))?.to_string(),
        };
        let password = match saved.get("password") {
            Some(Value::String(p)) => p.clone(),
            Some(_) => return invalid("invalid_wifi_password"),
            None => password,
        };
        let country = json::field(settings, "country")?.as_str().ok_or_else(|| Error::Invalid("invalid_regulatory_country".into()))?;
        let dns = json::str_or(settings, "dns", "103.86.96.100")?;
        let mut ap = Lan::access_point(&names.ap, &ssid, &password, country, dns, Path::new("/run/phoenix/ap"), run.clone())?;
        if enabled {
            ap.start()?;
        }
        *controller.access_point.lock().unwrap_or_else(|e| e.into_inner()) = Some(ap);
        owned.ap = true;
    }
    run.optional(&["nft", "delete", "table", "inet", "phoenix_stop"])?;
    set_forwarding("1")
}

fn serve_http(port: u16, token: String, token_path: &Path, api: &LocalApi) -> Result<()> {
    let listener = std::net::TcpListener::bind(("127.0.0.1", port))?;
    let port = listener.local_addr()?.port();
    println!("Phoenix administration: http://127.0.0.1:{port}; token file: {}", token_path.display());
    let settings = http::Settings {
        authority: format!("127.0.0.1:{port}"),
        tls: false,
        password_auth: false,
        allow_bearer: true,
        token,
        release_id: http::release_id(),
    };
    while !signals::stopping() {
        if !signals::wait_readable(listener.as_raw_fd(), 500) {
            continue;
        }
        if let Ok((stream, _)) = listener.accept() {
            http::handle(&mut http::Deadlined::new(stream, http::CONNECTION_DEADLINE), &settings, api);
        }
    }
    Ok(())
}

pub fn main(argv: &[String]) -> i32 {
    let args = match Args::parse(argv, &["state-dir", "port", "target-config", "worker-socket", "web-user"], &[]) {
        Ok(args) => args,
        Err(message) => return usage_error(&message),
    };
    let Ok(state_dir) = args.require("state-dir").map(PathBuf::from) else {
        return usage_error("--state-dir is required");
    };
    let port: u16 = match args.get("port").unwrap_or("8085").parse() {
        Ok(port) => port,
        Err(_) => return usage_error("--port must be a port number"),
    };
    let socket = args.get("worker-socket").map(PathBuf::from);
    let web_user = args.get("web-user").unwrap_or("phoenix-web").to_string();
    if socket.is_some() && args.get("target-config").is_none() {
        eprintln!("Worker requires an identified target");
        return 1;
    }
    signals::install();
    match run(&args, &state_dir, port, socket.as_deref(), &web_user) {
        Ok(()) => 0,
        Err(error) => {
            eprintln!("phoenix control: {error}");
            1
        }
    }
}

fn run(args: &Args, state_dir: &Path, port: u16, socket: Option<&Path>, web_user: &str) -> Result<()> {
    let mut config = Value::Null;
    let mut runtime = None;
    if let Some(path) = args.get("target-config") {
        config = json::loads(&std::fs::read(path)?)?;
        let expected = json::object(&config)?.get("expected_model").and_then(Value::as_str).unwrap_or("");
        if expected.is_empty() || expected != model() {
            eprintln!("Target model mismatch");
            return invalid("target_model_mismatch");
        }
        let runner: SharedRunner = Arc::new(SystemRunner::new()?);
        let interfaces = json::field(json::object(&config)?, "interfaces")?;
        let built = Runtime::new(interfaces, runner, py::wall_clock())?;
        // Establish a barrier even if persistent configuration is corrupt.
        built.block(&crate::json::json!({"revision": 0, "default_allow": false, "rules": [], "forwards": []}))?;
        runtime = Some(built);
    }
    let has_runtime = runtime.is_some();
    let mut controller = Controller::new(state_dir, &web::countries(), runtime)?;
    let token = admin_token(state_dir)?;
    let web_uid = match socket {
        Some(_) => Some(web_uid(web_user)?),
        None => None,
    };
    let mut owned = Owned { ap: false, usb: false };
    let setup = attach(&mut controller, &config, state_dir, &mut owned);
    let controller = Arc::new(controller);
    let api = LocalApi::new(Arc::clone(&controller));
    let stop = Arc::new(AtomicBool::new(false));
    let result = setup.and_then(|()| {
        let ticker = {
            let controller = Arc::clone(&controller);
            let stop = Arc::clone(&stop);
            std::thread::spawn(move || {
                while !stop.load(Ordering::SeqCst) {
                    std::thread::sleep(Duration::from_secs(1));
                    if stop.load(Ordering::SeqCst) {
                        break;
                    }
                    if controller.tick().is_err() {
                        // Even the drop barrier failed: fail closed and let systemd restart us.
                        if let Some(runtime) = &controller.runtime {
                            let _ = stop_guard::block(runtime.run.as_ref() as &dyn Runner, Path::new(IP_FORWARD));
                            std::process::exit(1);
                        }
                    }
                }
            })
        };
        let served = match (socket, web_uid) {
            (Some(path), Some(uid)) => rpc::serve(path, &api, uid),
            _ => serve_http(port, token, &state_dir.join("admin-token"), &api),
        };
        stop.store(true, Ordering::SeqCst);
        let _ = ticker.join();
        served
    });
    stop.store(true, Ordering::SeqCst);
    controller.shutdown();
    if has_runtime {
        let _ = set_forwarding("0");
    }
    if owned.ap {
        if let Some(ap) = controller.access_point.lock().unwrap_or_else(|e| e.into_inner()).as_mut() {
            ap.stop();
        }
    }
    if owned.usb {
        if let Some(usb) = controller.usb_lan.lock().unwrap_or_else(|e| e.into_inner()).as_mut() {
            usb.stop();
        }
    }
    result
}
