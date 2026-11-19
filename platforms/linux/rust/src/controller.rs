//! Serialized control plane; accepted configuration is not proof of
//! connectivity (controller.py).
//!
//! Locking: `op` serializes operations like Python's `self.lock`; `state`
//! holds the fields status calls read and is only held for short sections.
//! Order: op → lan/station mutexes → state. Never call a tool while holding
//! `state`.
use crate::error::{conflict, invalid, unavailable, Error, Result};
use crate::firewall::Mode;
use crate::history::History;
use crate::json::{self, json, Map, Value};
use crate::lan::Lan;
use crate::nord::{self, Country, Location};
use crate::py::{self, Clock};
use crate::rotation::{choose_country, Rotation};
use crate::runtime::Runtime;
use crate::speedcheck::{self, Measurement};
use crate::station::{self, Station};
use crate::store::ConfigStore;
use crate::updates::Updates;
use crate::vault::Vault;
use crate::wireguard::{self, Profile};
use std::path::Path;
use std::sync::{Arc, Mutex, MutexGuard};

pub struct State {
    pub busy: bool,
    pub closing: bool,
    pub updating: bool,
    /// Private VPN settings (vpn-private.json).
    pub settings: Map<String, Value>,
    pub timer: Rotation,
    pub error: String,
    pub exit_ip: String,
    pub exit_country: String,
    pub api_verified: bool,
    pub connected_recorded: bool,
    pub location: Location,
    pub enabled: bool,
    pub want_connected: bool,
    pub retry_at: Option<f64>,
    pub retry_count: u32,
    pub connect_started: f64,
    pub hotspot_enabled: bool,
    pub ap_suspended: bool,
    /// Failover, per WireGuard group: when its member in use was activated
    /// (monotonic seconds) and how many members failed since the last
    /// handshake.
    pub group_since: Vec<f64>,
    pub group_tries: Vec<usize>,
}

impl State {
    fn text(&self, key: &str) -> &str {
        self.settings.get(key).and_then(Value::as_str).unwrap_or("")
    }
    fn provider(&self) -> &str {
        self.text("provider")
    }
    fn raw(&self, key: &str, default: Value) -> Value {
        self.settings.get(key).cloned().unwrap_or(default)
    }
    fn schedule_retry(&mut self, now: f64) {
        if self.want_connected {
            self.retry_count += 1;
            let exponent = (self.retry_count - 1).min(4);
            self.retry_at = Some(now + (5.0 * f64::from(1u32 << exponent)).min(60.0));
        }
    }
}

pub struct Controller {
    /// Python `self.lock`: one operation at a time.
    pub op: Mutex<()>,
    pub state: Mutex<State>,
    pub measurement: Arc<Measurement>,
    pub store: ConfigStore,
    pub vault: Vault,
    pub hotspot_vault: Vault,
    pub history: History,
    pub countries: Vec<Country>,
    pub runtime: Option<Runtime>,
    pub access_point: Mutex<Option<Lan>>,
    pub usb_lan: Mutex<Option<Lan>>,
    pub station: Mutex<Option<Station>>,
    pub updates: Option<Updates>,
    pub base_ap: Option<String>,
    clock: Clock,
}

fn fixed_country(value: Option<&Value>) -> Result<String> {
    match value {
        None => Ok(String::new()),
        Some(Value::String(s)) => Ok(s.clone()),
        // Python only tested truthiness: null/false/0 meant "no fixed country".
        Some(other) if !json::truthy(Some(other)) => Ok(String::new()),
        Some(_) => invalid("country_unavailable_or_excluded"),
    }
}

fn valid_token(token: &Value) -> Result<String> {
    match token {
        Value::String(t) if py::len_chars(t) <= 512 && !t.chars().any(|c| (c as u32) < 33) => Ok(t.clone()),
        _ => invalid("invalid_token"),
    }
}

impl Controller {
    pub fn new(directory: &Path, countries: &Value, runtime: Option<Runtime>) -> Result<Controller> {
        Self::with_clocks(directory, countries, runtime, py::monotonic_clock(), py::wall_clock())
    }

    /// `clock`: monotonic (rotation, retries); `wall`: history timestamps.
    pub fn with_clocks(directory: &Path, countries: &Value, runtime: Option<Runtime>, clock: Clock, wall: Clock) -> Result<Controller> {
        let store = ConfigStore::open(directory)?;
        let vault = Vault::new(directory);
        let history = History::new(&store, wall)?;
        let settings = match vault.load()? {
            Value::Object(map) => map,
            _ => return invalid("invalid_private_file"),
        };
        let base_ap = runtime.as_ref().map(|r| r.names().ap);
        let controller = Controller {
            op: Mutex::new(()),
            state: Mutex::new(State {
                busy: false,
                closing: false,
                updating: false,
                settings,
                timer: Rotation::new(clock.clone()),
                error: String::new(),
                exit_ip: String::new(),
                exit_country: String::new(),
                api_verified: false,
                connected_recorded: false,
                location: Location::default(),
                enabled: false,
                want_connected: false,
                retry_at: None,
                retry_count: 0,
                connect_started: 0.0,
                hotspot_enabled: true,
                ap_suspended: false,
                group_since: Vec::new(),
                group_tries: Vec::new(),
            }),
            measurement: Arc::new(Measurement::new()),
            store,
            vault,
            hotspot_vault: Vault::named(directory, "hotspot-private.json"),
            history,
            countries: nord::countries(countries)?,
            runtime,
            access_point: Mutex::new(None),
            usb_lan: Mutex::new(None),
            station: Mutex::new(None),
            updates: None,
            base_ap,
            clock,
        };
        // Reboot always starts blocked; explicit connect restores the saved profile.
        if let Some(runtime) = &controller.runtime {
            runtime.block(&controller.policy()?)?;
        }
        Ok(controller)
    }

    fn now(&self) -> f64 {
        (self.clock)()
    }

    pub fn st(&self) -> MutexGuard<'_, State> {
        self.state.lock().unwrap_or_else(|e| e.into_inner())
    }

    fn lock_op(&self) -> MutexGuard<'_, ()> {
        self.op.lock().unwrap_or_else(|e| e.into_inner())
    }

    /// Non-blocking acquisition; Conflict when another operation runs.
    pub fn try_op(&self) -> Result<MutexGuard<'_, ()>> {
        match self.op.try_lock() {
            Ok(guard) => Ok(guard),
            Err(std::sync::TryLockError::Poisoned(e)) => Ok(e.into_inner()),
            Err(std::sync::TryLockError::WouldBlock) => conflict("command_in_progress"),
        }
    }

    pub fn runtime(&self) -> Result<&Runtime> {
        self.runtime.as_ref().ok_or_else(|| Error::Unavailable("target_network_not_initialized".into()))
    }

    pub fn require_idle(&self) -> Result<()> {
        let st = self.st();
        if st.busy || st.closing || st.updating {
            return conflict("command_in_progress");
        }
        Ok(())
    }

    fn codes(&self) -> Vec<String> {
        self.countries.iter().map(|c| c.code.clone()).collect()
    }

    pub fn country_codes(&self) -> Vec<String> {
        self.codes()
    }

    pub fn hotspot_status(&self) -> Value {
        let (hotspot_enabled, suspended) = {
            let st = self.st();
            (st.hotspot_enabled, st.ap_suspended)
        };
        let mut guard = self.access_point.lock().unwrap_or_else(|e| e.into_inner());
        match guard.as_mut() {
            None => json!({"available": false, "enabled": false, "active": false, "radio_state": "DISABLED",
                           "clients": 0, "ssid": "", "password_configured": false, "suspended": suspended}),
            Some(ap) => {
                let (state, clients) = ap.radio_status();
                let active = ap.healthy() && state == "ENABLED";
                json!({"available": true, "enabled": hotspot_enabled, "active": active, "radio_state": state,
                       "clients": clients, "ssid": ap.ssid, "password_configured": !ap.password.is_empty(),
                       "suspended": suspended})
            }
        }
    }

    pub fn configure_hotspot(&self, body: &Value) -> Result<Value> {
        let _op = self.try_op()?;
        {
            let mut guard = self.access_point.lock().unwrap_or_else(|e| e.into_inner());
            let Some(ap) = guard.as_mut() else {
                return unavailable("hotspot_unavailable");
            };
            self.require_idle()?;
            let body = match body {
                Value::Object(map) if map.keys().all(|k| ["enabled", "ssid", "password"].contains(&k.as_str())) => map,
                _ => return invalid("invalid_hotspot_configuration"),
            };
            let enabled = json::boolean(json::field(body, "enabled")?)?;
            let ssid = match json::field(body, "ssid")? {
                Value::String(s) => s.clone(),
                _ => return invalid("invalid_ssid"),
            };
            let password = match body.get("password") {
                None => String::new(),
                Some(Value::String(p)) => p.clone(),
                Some(_) => return invalid("invalid_wifi_password"),
            };
            let password = if password.is_empty() { ap.password.clone() } else { password };
            crate::access_point::render(&ap.name, &ssid, &password, &ap.country, &ap.dns)?;
            let previous_enabled = {
                let st = self.st();
                if enabled && st.ap_suspended {
                    return invalid("hotspot_conflicts_with_wifi_uplink");
                }
                st.hotspot_enabled
            };
            let previous = (ap.ssid.clone(), ap.password.clone(), ap.active);
            let attempt = (|| -> Result<()> {
                if ap.active {
                    ap.stop();
                }
                ap.ssid = ssid.clone();
                ap.password = password.clone();
                if enabled {
                    ap.start()?;
                }
                self.hotspot_vault.save(&json!({"enabled": enabled, "ssid": ssid, "password": password}))?;
                self.st().hotspot_enabled = enabled;
                Ok(())
            })();
            if let Err(error) = attempt {
                ap.stop();
                ap.ssid = previous.0;
                ap.password = previous.1;
                self.st().hotspot_enabled = previous_enabled;
                if previous.2 {
                    ap.start()?;
                }
                return Err(error);
            }
        }
        Ok(self.hotspot_status())
    }

    pub fn validate_command(&self, body: &Value) -> Result<()> {
        let body = json::object(body)?;
        let action = body.get("action").and_then(Value::as_str).unwrap_or("");
        match action {
            "wifi" => {
                if self.station.lock().unwrap_or_else(|e| e.into_inner()).is_none() {
                    return unavailable("wifi_not_configured");
                }
                station::validate(&Value::Object(body.clone()))
            }
            "uplink" => {
                let uplink = body.get("uplink").and_then(Value::as_str);
                if !matches!(uplink, Some("wifi" | "ethernet")) {
                    return invalid("invalid_uplink");
                }
                let guard = self.station.lock().unwrap_or_else(|e| e.into_inner());
                if uplink == Some("wifi") && !guard.as_ref().map(Station::has_profile).unwrap_or(false) {
                    return invalid("wifi_profile_required");
                }
                Ok(())
            }
            "wireguard" => match body.get("profile").unwrap_or(&json!("")) {
                Value::String(text) => wireguard::parse(text).map(|_| ()),
                _ => invalid("invalid_profile"),
            },
            "nordvpn" => {
                json::boolean(body.get("rotation").unwrap_or(&Value::Null))?;
                json::integer(body.get("interval").unwrap_or(&Value::Null), 30, 86400)?;
                let exclude = json::boolean(body.get("exclude_restricted").unwrap_or(&json!(false)))?;
                choose_country(&self.codes(), &fixed_country(body.get("country"))?, "", exclude, &mut py::choice)?;
                let token = valid_token(body.get("token").unwrap_or(&json!("")))?;
                if token.is_empty() {
                    wireguard::key(self.st().text("nord_key"))?;
                }
                Ok(())
            }
            "connect" | "rotate" => {
                let st = self.st();
                if !matches!(st.provider(), "wireguard" | "nordvpn") {
                    return invalid("profile_required");
                }
                if action == "rotate" && st.provider() != "nordvpn" {
                    return invalid("nordvpn_required");
                }
                Ok(())
            }
            "verify_exit" | "catalog_test" | "disconnect" | "direct" | "forget" => Ok(()),
            _ => invalid("unsupported_action"),
        }
    }

    /// Accepts a command and runs it in the background (202 semantics).
    pub fn submit(self: &Arc<Self>, body: &Value) -> Result<Value> {
        self.runtime()?;
        let _op = self.try_op()?;
        self.require_idle()?;
        self.validate_command(body)?;
        let body = body.clone();
        self.st().busy = true;
        let controller = Arc::clone(self);
        std::thread::spawn(move || {
            let _op = controller.lock_op();
            if let Err(error) = controller.command(&body) {
                controller.command_failed(body.get("action").and_then(Value::as_str).unwrap_or(""), &error);
            }
            controller.st().busy = false;
        });
        Ok(json!({"accepted": true}))
    }

    fn command_failed(&self, action: &str, error: &Error) {
        let now = self.now();
        if matches!(action, "verify_exit" | "catalog_test") {
            let mut st = self.st();
            if action == "verify_exit" {
                st.error = "exit_check_failed".into();
                st.exit_ip.clear();
                st.exit_country.clear();
            } else {
                st.error = "nord_api_unavailable".into();
                st.api_verified = false;
            }
            return;
        }
        {
            let mut st = self.st();
            st.error = vpn_failure(error).into();
            if matches!(action, "wifi" | "uplink") {
                st.want_connected = false;
                st.retry_at = None;
                st.error = "network_setup_failed".into();
            }
            st.schedule_retry(now);
            st.enabled = false;
            st.timer.disconnected();
        }
        let blocked = self.policy().and_then(|p| self.runtime()?.block(&p));
        if blocked.is_err() {
            if let Some(runtime) = &self.runtime {
                runtime.set_enforced(false);
            }
            self.st().error = "firewall_enforcement_failed".into();
        }
    }

    pub fn start_speedtest(self: &Arc<Self>) -> Result<Value> {
        let _op = self.lock_op();
        let runtime = self.runtime()?;
        self.require_idle()?;
        if !speedcheck::available() {
            return unavailable("speedtest_not_installed");
        }
        let mode = runtime.mode();
        if !matches!(mode, Mode::Vpn | Mode::Direct) || (mode == Mode::Vpn && !runtime.handshake()) {
            return invalid("speedtest_connection_required");
        }
        let names = runtime.names();
        let name = if mode == Mode::Vpn { names.vpn } else { names.uplink };
        let destination = if mode == Mode::Vpn { self.st().location.server.clone() } else { name.clone() };
        self.measurement.prepare(mode.as_str(), &name, &destination)?;
        self.st().busy = true;
        let controller = Arc::clone(self);
        std::thread::spawn(move || {
            controller.measurement.run(&name);
            let _op = controller.lock_op();
            controller.st().busy = false;
        });
        Ok(self.measurement.status())
    }

    pub fn shutdown(&self) {
        self.measurement.cancel();
        let _op = self.lock_op();
        {
            let mut st = self.st();
            st.closing = true;
            st.want_connected = false;
            st.enabled = false;
            st.retry_at = None;
            st.timer.disconnected();
        }
        if let Some(runtime) = &self.runtime {
            if let Ok(policy) = self.policy() {
                let _ = runtime.disconnect(&policy);
            }
            if runtime.selected_route() {
                for priority in ["17690", "17691", "17710", "17711"] {
                    let _ = runtime.run.optional(&["ip", "rule", "del", "priority", priority]);
                }
            }
        }
        let mut station = self.station.lock().unwrap_or_else(|e| e.into_inner());
        if let Some(station) = station.as_mut() {
            station.disconnect();
            let has_ap = self.access_point.lock().unwrap_or_else(|e| e.into_inner()).is_some();
            if has_ap && self.st().ap_suspended && Some(&station.name) == self.base_ap.as_ref() {
                if let Some(runtime) = &self.runtime {
                    let _ = runtime.run.run(&["nmcli", "device", "set", &station.name, "managed", "no"]);
                }
            }
        }
    }

    /// Saved policy plus revision and runtime-only `active` flags.
    pub fn policy(&self) -> Result<Value> {
        let saved = self.store.load()?;
        let mut policy = json::object(&saved.desired)?
            .get("policy")
            .cloned()
            .unwrap_or_else(|| json!({"default_allow": true, "rules": [], "forwards": []}));
        let (enforced, mode) = match &self.runtime {
            Some(runtime) => {
                let state = runtime.state();
                (state.enforced, Some(state.mode))
            }
            None => (false, None),
        };
        let object = policy.as_object_mut().ok_or_else(|| Error::Invalid("invalid_policy".into()))?;
        object.insert("revision".into(), json!(saved.revision));
        let forwards = object.get_mut("forwards").and_then(Value::as_array_mut).ok_or_else(|| Error::Invalid("invalid_policy".into()))?;
        for forward in forwards {
            let f = forward.as_object_mut().ok_or_else(|| Error::Invalid("invalid_policy".into()))?;
            let wanted = if json::truthy(f.get("vpn")) { Mode::Vpn } else { Mode::Direct };
            let active = enforced && mode == Some(wanted) && json::truthy(f.get("enabled"));
            f.insert("active".into(), json!(active));
        }
        Ok(policy)
    }

    /// Caller holds `op` (the RPC layer acquires it without blocking).
    pub fn save_policy(&self, body: &Value) -> Result<Value> {
        let runtime = self.runtime()?;
        self.require_idle()?;
        let policy = crate::policy::validate(body)?;
        let current = self.store.load()?;
        if policy.get("revision").and_then(Value::as_i64) != Some(current.revision) {
            return conflict("revision_conflict_reload");
        }
        let mode = runtime.mode();
        runtime.block(&self.policy()?)?;
        let mut desired = json::object(&current.desired)?.clone();
        desired.insert("policy".into(), policy.clone());
        // Save only after the drop barrier. Apply failure leaves traffic blocked.
        self.store.save(current.revision, &Value::Object(desired), &|d| crate::policy::validate(d.get("policy").unwrap_or(&Value::Null)).map(|_| ()))?;
        if let Err(error) = runtime.firewall(&policy, mode) {
            runtime.block(&policy)?;
            return Err(error);
        }
        self.policy()
    }

    fn connect_now(&self) -> Result<()> {
        let runtime = self.runtime()?;
        let (settings, previous) = {
            let mut st = self.st();
            if !matches!(st.provider(), "wireguard" | "nordvpn") {
                return invalid("profile_required");
            }
            st.want_connected = true;
            st.retry_at = None;
            st.connect_started = (self.clock)();
            (st.settings.clone(), st.location.clone())
        };
        runtime.block(&self.policy()?)?;
        {
            let mut st = self.st();
            st.exit_ip.clear();
            st.exit_country.clear();
            st.enabled = false;
            st.timer.disconnected();
            st.connected_recorded = false;
        }
        let text = |key: &str| settings.get(key).and_then(Value::as_str).unwrap_or("").to_string();
        let profile: Profile = if text("provider") == "nordvpn" {
            let exclude = settings.get("exclude_restricted").map(json::boolean).transpose()?.unwrap_or(false);
            let fixed = fixed_country(settings.get("country"))?;
            let request = |path: &str, token: Option<&str>| runtime.nord_request(path, token);
            let (profile, location) = nord::select(&text("nord_key"), &self.countries, &fixed, &previous.country, exclude, previous.id, &request, &mut py::choice)?;
            self.st().location = location;
            profile
        } else {
            let profile = wireguard::parse(&text("profile"))?;
            self.st().location = Location { id: 0, country: String::new(), server: profile.primary().endpoint.clone() };
            // Host names are resolved again at every (re)connect.
            runtime.resolve_endpoint(&profile)?
        };
        if let Some(ap) = self.access_point.lock().unwrap_or_else(|e| e.into_inner()).as_mut() {
            ap.set_dns(&profile.dns_text())?;
        }
        if let Some(usb) = self.usb_lan.lock().unwrap_or_else(|e| e.into_inner()).as_mut() {
            usb.set_dns(&profile.dns_text())?;
        }
        runtime.connect(&self.policy()?, &profile)?;
        let now = self.now();
        let mut st = self.st();
        st.enabled = true;
        st.error.clear();
        st.group_since = vec![now; profile.groups.len()];
        st.group_tries = vec![0; profile.groups.len()];
        Ok(())
    }

    fn network_command(&self, body: &Map<String, Value>) -> Result<()> {
        let runtime = self.runtime()?;
        let action = body.get("action").and_then(Value::as_str).unwrap_or("");
        let desired = if action == "wifi" { "wifi" } else { body.get("uplink").and_then(Value::as_str).unwrap_or("") };
        let resume_vpn = self.st().want_connected;
        let resume_direct = runtime.mode() == Mode::Direct;
        runtime.disconnect(&self.policy()?)?;
        {
            let mut st = self.st();
            st.enabled = false;
            st.timer.disconnected();
            st.retry_at = None;
        }
        let mut station_guard = self.station.lock().unwrap_or_else(|e| e.into_inner());
        if desired == "wifi" {
            let station = station_guard.as_mut().ok_or_else(|| Error::Unavailable("wifi_not_configured".into()))?;
            if Some(&station.name) == self.base_ap.as_ref() {
                if let Some(ap) = self.access_point.lock().unwrap_or_else(|e| e.into_inner()).as_mut() {
                    if ap.active {
                        ap.stop();
                    }
                }
                self.st().ap_suspended = true;
            }
            let gateway = if action == "wifi" { station.connect(&Value::Object(body.clone()))? } else { station.reconnect()? };
            let suspended = self.st().ap_suspended;
            let ap_name = if suspended { Some("phapoff") } else { self.base_ap.as_deref() };
            runtime.select_uplink(&self.policy()?, &station.name.clone(), "wifi", Some(&gateway), ap_name)?;
        } else {
            if let Some(station) = station_guard.as_mut() {
                station.disconnect();
            }
            let ethernet = runtime.state().ethernet_name;
            runtime.select_uplink(&self.policy()?, &ethernet, "ethernet", None, self.base_ap.as_deref())?;
            let (suspended, hotspot_enabled) = {
                let st = self.st();
                (st.ap_suspended, st.hotspot_enabled)
            };
            let mut ap_guard = self.access_point.lock().unwrap_or_else(|e| e.into_inner());
            if let (true, true, Some(ap), Some(station)) = (suspended, hotspot_enabled, ap_guard.as_mut(), station_guard.as_ref()) {
                runtime.run.run(&["nmcli", "device", "set", &station.name, "managed", "no"])?;
                ap.start()?;
            }
            self.st().ap_suspended = false;
        }
        drop(station_guard);
        if resume_vpn {
            self.connect_now()?;
        } else if resume_direct {
            runtime.direct(&self.policy()?)?;
        }
        Ok(())
    }

    /// Runs with `op` held (background worker thread).
    pub fn command(&self, body: &Value) -> Result<Value> {
        let runtime = self.runtime()?;
        let body = json::object(body)?;
        let action = body.get("action").and_then(Value::as_str).unwrap_or("");
        match action {
            "wifi" | "uplink" => self.network_command(body)?,
            "wireguard" => {
                let profile = json::field(body, "profile")?.as_str().ok_or_else(|| Error::Invalid("invalid_profile".into()))?;
                wireguard::parse(profile)?;
                let settings = json!({"provider": "wireguard", "profile": profile, "rotation": false});
                self.vault.save(&settings)?;
                self.st().settings = settings.as_object().cloned().unwrap_or_default();
                self.connect_now()?;
            }
            "nordvpn" => {
                let fixed = fixed_country(body.get("country"))?;
                let rotation = json::boolean(json::field(body, "rotation")?)?;
                let interval = json::integer(json::field(body, "interval")?, 30, 86400)?;
                let exclude = json::boolean(body.get("exclude_restricted").unwrap_or(&json!(false)))?;
                choose_country(&self.codes(), &fixed, "", exclude, &mut py::choice)?;
                let token = valid_token(body.get("token").unwrap_or(&json!("")))?;
                let private = if !token.is_empty() {
                    let request = |path: &str, token: Option<&str>| runtime.nord_request(path, token);
                    nord::provision(&token, &request)?
                } else {
                    self.st().text("nord_key").to_string()
                };
                wireguard::key(&private)?;
                let settings = json!({"provider": "nordvpn", "nord_key": private, "country": fixed,
                                      "rotation": rotation, "interval": interval, "exclude_restricted": exclude});
                self.vault.save(&settings)?;
                self.st().settings = settings.as_object().cloned().unwrap_or_default();
                self.connect_now()?;
            }
            "connect" | "rotate" => {
                if action == "rotate" && self.st().provider() != "nordvpn" {
                    return invalid("nordvpn_required");
                }
                self.connect_now()?;
            }
            "verify_exit" => {
                let (ip, country) = runtime.verify_exit()?;
                let mut st = self.st();
                st.exit_ip = ip;
                st.exit_country = country;
            }
            "catalog_test" => {
                let result = runtime.nord_request("/v1/servers/countries", None)?;
                if !matches!(&result, Value::Array(items) if !items.is_empty()) {
                    return invalid("nord_api_unavailable");
                }
                self.st().api_verified = true;
            }
            "disconnect" | "direct" | "forget" => {
                {
                    let mut st = self.st();
                    st.want_connected = false;
                    st.retry_at = None;
                }
                runtime.block(&self.policy()?)?;
                {
                    let mut st = self.st();
                    st.enabled = false;
                    st.exit_ip.clear();
                    st.exit_country.clear();
                    st.timer.disconnected();
                }
                if action == "direct" {
                    if let Some(ap) = self.access_point.lock().unwrap_or_else(|e| e.into_inner()).as_mut() {
                        let dns = ap.default_dns.clone();
                        ap.set_dns(&dns)?;
                    }
                    if let Some(usb) = self.usb_lan.lock().unwrap_or_else(|e| e.into_inner()).as_mut() {
                        let dns = usb.default_dns.clone();
                        usb.set_dns(&dns)?;
                    }
                    runtime.direct(&self.policy()?)?;
                } else {
                    runtime.disconnect(&self.policy()?)?;
                }
                if action == "forget" {
                    self.vault.save(&json!({}))?;
                    self.st().settings = Map::new();
                }
            }
            _ => return unavailable("action_not_implemented"),
        }
        self.st().error.clear();
        Ok(self.vpn_status())
    }

    /// One supervision step (every second). An error means even the drop
    /// barrier failed: the caller must fail closed.
    pub fn tick(&self) -> Result<()> {
        let _op = self.lock_op();
        let Some(runtime) = &self.runtime else {
            return Ok(());
        };
        {
            let st = self.st();
            if st.busy || st.closing || st.updating {
                return Ok(());
            }
        }
        match self.supervise(runtime) {
            Ok(()) => Ok(()),
            Err(error) => {
                let now = self.now();
                {
                    let mut st = self.st();
                    st.error = vpn_failure(&error).into();
                    st.schedule_retry(now);
                    st.enabled = false;
                    st.timer.disconnected();
                }
                runtime.block(&self.policy()?)
            }
        }
    }

    fn fail_lan(&self, runtime: &Runtime, error: &str) -> Result<()> {
        {
            let mut st = self.st();
            st.want_connected = false;
            st.enabled = false;
            st.retry_at = None;
            st.error = error.into();
        }
        runtime.block(&self.policy()?)
    }

    fn supervise(&self, runtime: &Runtime) -> Result<()> {
        let usb_failed = self.usb_lan.lock().unwrap_or_else(|e| e.into_inner()).as_mut().map(|usb| !usb.healthy()).unwrap_or(false);
        if usb_failed {
            return self.fail_lan(runtime, "usb_dhcp_service_failed");
        }
        let (hotspot_enabled, suspended) = {
            let st = self.st();
            (st.hotspot_enabled, st.ap_suspended)
        };
        if hotspot_enabled && !suspended {
            let ap_failed = self.access_point.lock().unwrap_or_else(|e| e.into_inner()).as_mut().map(|ap| !ap.healthy()).unwrap_or(false);
            if ap_failed {
                return self.fail_lan(runtime, "ap_service_failed");
            }
        }
        let retry_due = self.st().retry_at.map(|at| self.now() >= at).unwrap_or(false);
        if retry_due {
            self.connect_now()?;
        }
        if !self.st().enabled {
            return Ok(());
        }
        let failover = self.failover(runtime)?;
        let connected = runtime.handshake();
        let record = {
            let mut st = self.st();
            if connected {
                st.retry_count = 0;
            }
            (connected && !st.connected_recorded).then(|| st.location.clone())
        };
        if let Some(location) = record {
            self.history.add_confirmed(&location.country, &location.server, location.id)?;
            let mut st = self.st();
            st.connected_recorded = true;
            let rotation = json::boolean(&st.raw("rotation", json!(false)))?;
            let interval = json::integer(&st.raw("interval", json!(300)), i64::MIN, i64::MAX)?;
            st.timer.connected(rotation, interval)?;
        }
        if !connected {
            let now = self.now();
            let expired = {
                let mut st = self.st();
                let had_session = st.connected_recorded;
                st.timer.disconnected();
                st.connected_recorded = false;
                match failover {
                    // Alternates get their turn before a full reconnect.
                    Some(exhausted) => exhausted,
                    None => had_session || now - st.connect_started > 30.0,
                }
            };
            if expired {
                runtime.block(&self.policy()?)?;
                let mut st = self.st();
                st.enabled = false;
                st.schedule_retry(now);
            }
        }
        if self.st().timer.due() {
            self.connect_now()?;
        }
        Ok(())
    }

    /// Failover step for profiles with alternate peers (None otherwise):
    /// a group whose member in use has had no recent handshake for
    /// FAILOVER_AFTER seconds since its activation moves to the next member;
    /// other groups are untouched. Returns whether the decisive groups (the
    /// Internet exit, else every group) have tried all their members, which
    /// replaces the single-peer 30 s reconnect rule.
    fn failover(&self, runtime: &Runtime) -> Result<Option<bool>> {
        let Some((profile, ages)) = runtime.group_handshakes() else {
            return Ok(None);
        };
        if !profile.has_failover() {
            return Ok(None);
        }
        let now = self.now();
        let groups = profile.groups.len();
        {
            let mut st = self.st();
            if st.group_since.len() != groups {
                st.group_since = vec![now; groups];
                st.group_tries = vec![0; groups];
            }
        }
        for (group, age) in ages.iter().enumerate() {
            let members = profile.groups[group].len();
            {
                let mut st = self.st();
                if Runtime::recent(*age) {
                    st.group_tries[group] = 0;
                    continue;
                }
                // The exit group stops after one round: then a full reconnect
                // (with backoff) starts again from its first member. Other
                // groups keep rotating while the tunnel is up.
                let exit = profile.exit_group() == Some(group);
                if now - st.group_since[group] <= FAILOVER_AFTER || (exit && st.group_tries[group] >= members) {
                    continue;
                }
                st.group_tries[group] += 1;
                st.group_since[group] = now;
                if members == 1 {
                    continue;
                }
            }
            match runtime.switch_member(group) {
                Ok(()) => {}
                // The group stays without a peer; the next switch moves on.
                Err(error) if error.code() == "endpoint_resolution_failed" => {}
                Err(error) => return Err(error),
            }
            if profile.exit_group() == Some(group) {
                if let Some(current) = runtime.profile() {
                    let mut st = self.st();
                    st.location.server = current.primary().configured_endpoint();
                    st.connected_recorded = false;
                }
            }
        }
        let st = self.st();
        let exhausted = |g: usize| st.group_tries[g] >= profile.groups[g].len();
        Ok(Some(match profile.exit_group() {
            Some(group) => exhausted(group),
            None => (0..groups).all(exhausted),
        }))
    }

    /// Dry run of a WireGuard profile for the panel: the specific rejection
    /// code or the non-secret notes. Nothing is stored or applied.
    pub fn wireguard_check(&self, profile: Option<&Value>) -> Value {
        match profile.and_then(Value::as_str).map(wireguard::parse) {
            Some(Ok(parsed)) => json!({"valid": true, "notes": parsed.notes, "details": profile_details(&parsed)}),
            Some(Err(error)) => json!({"valid": false, "error": error.code()}),
            None => json!({"valid": false, "error": "invalid_profile"}),
        }
    }

    pub fn vpn_status(&self) -> Value {
        let (busy, enabled) = {
            let st = self.st();
            (st.busy, st.enabled)
        };
        let tunnel = if !busy && enabled { self.runtime.as_ref().and_then(Runtime::group_handshakes) } else { None };
        let handshake = tunnel.as_ref().map(|(profile, ages)| Runtime::connected(profile, ages)).unwrap_or(false);
        let direct = self.runtime.as_ref().map(|r| r.mode() == Mode::Direct).unwrap_or(false);
        let measuring = busy && self.measurement.status().get("state").and_then(Value::as_str) == Some("running");
        let endpoint = self.runtime.as_ref().and_then(Runtime::profile).map(|p| p.primary().endpoint.clone()).unwrap_or_default();
        let profile_text = {
            let st = self.st();
            (st.provider() == "wireguard").then(|| st.text("profile").to_string())
        };
        let stored = profile_text.and_then(|text| wireguard::parse(&text).ok());
        let notes = stored.as_ref().map(|p| p.notes.clone()).unwrap_or_default();
        let details = stored.as_ref().map(profile_details).unwrap_or_else(|| json!({}));
        // Custom WireGuard only: the tunnel in use when there is one, else the
        // saved profile with its first members and no handshakes.
        let peers = stored.as_ref().map(|saved| match &tunnel {
            Some((profile, ages)) if profile.peers.len() == saved.peers.len() => peers_json(profile, Some(ages)),
            _ => peers_json(saved, None),
        });
        let st = self.st();
        let state = if measuring {
            "measuring"
        } else if busy {
            "provisioning"
        } else if !st.error.is_empty() {
            "error"
        } else if direct {
            "direct"
        } else if handshake {
            "connected"
        } else if enabled {
            "connecting"
        } else {
            "blocked"
        };
        json!({
            "provider": st.raw("provider", json!("")), "enabled": st.enabled, "state": state,
            "busy": st.busy, "error": st.error, "country": st.raw("country", json!("")),
            "server": st.location.server, "server_country": st.location.country,
            "account_configured": json::truthy(st.settings.get("nord_key")),
            "rotation": st.raw("rotation", json!(false)), "interval": st.raw("interval", json!(300)),
            "exclude_restricted": st.raw("exclude_restricted", json!(false)),
            "next_rotation_seconds": st.timer.remaining(), "exit_ip": st.exit_ip, "exit_country": st.exit_country,
            "api_verified": st.api_verified, "endpoint": endpoint, "profile_notes": notes,
            "profile_details": details, "peers": peers,
        })
    }
}

/// Seconds without a recent handshake before a failover group moves on.
const FAILOVER_AFTER: f64 = 30.0;

/// Non-secret details for the notes: uncovered DNS servers, peer counts.
fn profile_details(profile: &Profile) -> Value {
    let mut details = Map::new();
    if !profile.dns_outside.is_empty() {
        details.insert("dns_outside_allowed_ips".into(), json!(profile.dns_outside));
    }
    if profile.peers.len() > 1 {
        details.insert("multiple_peers".into(), json!({"peers": profile.peers.len(), "groups": profile.groups.len()}));
    }
    Value::Object(details)
}

/// Per peer, file order: group, public fingerprint, endpoint as written (and
/// resolved address when in use), AllowedIPs, whether it is the member in
/// use and its latest handshake age. Never keys.
fn peers_json(profile: &Profile, ages: Option<&Vec<Option<f64>>>) -> Value {
    let mut peers = Vec::new();
    for (group, members) in profile.groups.iter().enumerate() {
        for &index in members {
            let peer = &profile.peers[index];
            let active = profile.active_index(group) == index;
            let age = if active { ages.and_then(|a| a[group]).map(|a| a.max(0.0).round() as i64) } else { None };
            let address = if active && ages.is_some() { peer.endpoint_ip().map(|ip| ip.to_string()) } else { None };
            peers.push((index, json!({
                "group": group, "public_key_fingerprint": peer.fingerprint(), "endpoint": peer.configured_endpoint(),
                "address": address, "allowed_ips": peer.allowed_ips, "active": active,
                "latest_handshake_age_s": age, "connected": active && Runtime::recent(ages.and_then(|a| a[group])),
            })));
        }
    }
    peers.sort_by_key(|(index, _)| *index);
    Value::Array(peers.into_iter().map(|(_, peer)| peer).collect())
}

/// Panel error for a failed VPN operation: specific when it helps the user.
fn vpn_failure(error: &Error) -> &'static str {
    match error.code() {
        "endpoint_resolution_failed" => "endpoint_resolution_failed",
        _ => "vpn_operation_failed",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fsutil::testdir::TempDir;
    use crate::runner::{exit, ok, FakeRunner, SharedRunner};
    use base64::Engine;
    use std::sync::atomic::{AtomicU64, Ordering};

    fn key() -> String {
        base64::engine::general_purpose::STANDARD.encode((0u8..32).collect::<Vec<u8>>())
    }

    fn profile() -> String {
        let k = key();
        format!("[Interface]\nPrivateKey={k}\nAddress=10.5.0.2/32\nDNS=103.86.96.100\n[Peer]\nPublicKey={k}\nEndpoint=192.0.2.1:51820\nAllowedIPs=0.0.0.0/0\n")
    }

    fn runner(fail: Option<Vec<&'static str>>) -> Arc<FakeRunner> {
        let k = key();
        Arc::new(FakeRunner::with(move |argv, _| {
            if let Some(fail) = &fail {
                if argv.iter().map(String::as_str).eq(fail.iter().copied()) {
                    return exit(1);
                }
            }
            if argv.len() >= 4 && argv[..4] == ["ip", "-j", "route", "get"] {
                return ok(r#"[{"dev":"end0"}]"#);
            }
            if argv.len() >= 3 && argv[..3] == ["wg", "show", "phwg0"] {
                return ok(&format!("{k}\t1000\n"));
            }
            None
        }))
    }

    fn clock(value: &Arc<AtomicU64>) -> Clock {
        let value = value.clone();
        Arc::new(move || value.load(Ordering::SeqCst) as f64)
    }

    fn runtime(runner: Arc<FakeRunner>, wall: &Arc<AtomicU64>) -> Runtime {
        let names = json!({"ap": "wlan0", "usb": "usb0", "uplink": "end0", "vpn": "phwg0"});
        Runtime::new(&names, runner as SharedRunner, clock(wall)).unwrap()
    }

    fn controller(dir: &TempDir, runtime: Option<Runtime>, mono: &Arc<AtomicU64>, countries: Value) -> Controller {
        Controller::with_clocks(dir.path(), &countries, runtime, clock(mono), Arc::new(|| 5000.0)).unwrap()
    }

    fn base() -> Value {
        json!({"revision": 0, "default_allow": true, "rules": [], "forwards": []})
    }

    #[test]
    fn uninitialized_refuses_changes() {
        let dir = TempDir::new();
        let c = controller(&dir, None, &Arc::new(AtomicU64::new(100)), json!([]));
        assert!(matches!(c.save_policy(&base()), Err(Error::Unavailable(_))));
        assert_eq!(c.store.load().unwrap().revision, 0);
        assert_eq!(c.vpn_status()["state"], "blocked");
    }

    /// Extended import: dry-run codes/notes, hostname re-resolution at every
    /// connect, notes in the VPN status, specific error when DoH fails.
    #[test]
    fn imported_profiles_report_notes_and_resolve_names() {
        let dir = TempDir::new();
        let wall = Arc::new(AtomicU64::new(1010));
        let mono = Arc::new(AtomicU64::new(100));
        let answers = Arc::new(std::sync::Mutex::new(vec![Ok(std::net::Ipv4Addr::new(192, 0, 2, 1)), Err(Error::Network("down".into()))]));
        let a = answers.clone();
        let rt = runtime(runner(None), &wall).with_resolver(Arc::new(move |name, _, _| {
            assert_eq!(name, "vpn.example.org");
            a.lock().unwrap().remove(0)
        }));
        let c = controller(&dir, Some(rt), &mono, json!([]));
        let k = key();
        let text = format!("[Interface]\nPrivateKey={k}\nAddress=10.5.0.2/32, fd00::2/128\nPostUp=id\n[Peer]\nPublicKey={k}\nEndpoint=vpn.example.org:51820\nAllowedIPs=0.0.0.0/0, ::/0\n");
        assert_eq!(c.wireguard_check(Some(&json!(text))), json!({"valid": true, "notes": ["ignored_ipv6", "dns_fallback", "hostname_endpoint", "ignored_hooks"], "details": {}}));
        assert_eq!(c.wireguard_check(Some(&json!(format!("{text}[Peer]\n")))), json!({"valid": false, "error": "missing_profile_fields"}));
        let split = text.replace("0.0.0.0/0, ::/0", "10.88.0.0/24");
        assert_eq!(c.wireguard_check(Some(&json!(split)))["details"], json!({"dns_outside_allowed_ips": ["1.1.1.1"]}));
        assert_eq!(c.wireguard_check(None), json!({"valid": false, "error": "invalid_profile"}));
        c.command(&json!({"action": "wireguard", "profile": text})).unwrap();
        let status = c.vpn_status();
        assert_eq!(status["endpoint"], "192.0.2.1:51820");
        assert_eq!(status["server"], "vpn.example.org:51820");
        assert_eq!(status["profile_notes"], json!(["ignored_ipv6", "dns_fallback", "hostname_endpoint", "ignored_hooks"]));
        let peers = status["peers"].as_array().unwrap();
        assert_eq!(peers.len(), 1);
        assert_eq!(peers[0]["endpoint"], "vpn.example.org:51820");
        assert_eq!(peers[0]["address"], "192.0.2.1");
        assert_eq!((peers[0]["active"].clone(), peers[0]["group"].clone()), (json!(true), json!(0)));
        assert!(!crate::json::dumps(&status).contains(&k), "no keys, only a public fingerprint");
        // Reconnect resolves again; a DoH failure blocks with a specific error.
        let error = c.command(&json!({"action": "connect"})).unwrap_err();
        assert_eq!(error.code(), "endpoint_resolution_failed");
        c.command_failed("connect", &error);
        assert_eq!(c.vpn_status()["error"], "endpoint_resolution_failed");
        assert_eq!(c.runtime.as_ref().unwrap().mode(), Mode::Blocked);
        assert!(answers.lock().unwrap().is_empty());
    }

    #[test]
    fn handshake_history_restart_and_no_api_secrets() {
        let dir = TempDir::new();
        let wall = Arc::new(AtomicU64::new(1010));
        let mono = Arc::new(AtomicU64::new(100));
        let c = controller(&dir, Some(runtime(runner(None), &wall)), &mono, json!([]));
        c.command(&json!({"action": "wireguard", "profile": profile()})).unwrap();
        let status = crate::json::dumps(&c.vpn_status());
        assert!(!status.contains("private_key") && !status.contains(&key()[..20]));
        c.tick().unwrap();
        c.tick().unwrap();
        assert_eq!(c.vpn_status()["state"], "connected");
        assert_eq!(c.history.page(0).unwrap()["entries"].as_array().unwrap().len(), 1);
        let restarted = controller(&dir, Some(runtime(runner(None), &wall)), &mono, json!([]));
        assert!(!restarted.st().enabled);
        assert_eq!(restarted.runtime.as_ref().unwrap().mode(), Mode::Blocked);
        assert_eq!(restarted.st().settings["profile"], profile());
        restarted.command(&json!({"action": "forget"})).unwrap();
        let saved = std::fs::read_to_string(dir.path().join("vpn-private.json")).unwrap();
        assert!(!saved.contains("profile"));
    }

    #[test]
    fn retry_backoff_stays_blocked_and_disconnect_cancels() {
        let dir = TempDir::new();
        let wall = Arc::new(AtomicU64::new(1010));
        let mono = Arc::new(AtomicU64::new(100));
        let fake = runner(Some(vec!["ip", "link", "add", "phwg0", "type", "wireguard"]));
        let c = controller(&dir, Some(runtime(fake, &wall)), &mono, json!([]));
        {
            let mut st = c.st();
            st.settings = json!({"provider": "wireguard", "profile": profile()}).as_object().unwrap().clone();
            st.want_connected = true;
            st.retry_at = Some(0.0);
        }
        c.tick().unwrap();
        assert_eq!(c.runtime.as_ref().unwrap().mode(), Mode::Blocked);
        assert_eq!(c.st().retry_at, Some(105.0));
        assert!(!c.st().enabled);
        c.command(&json!({"action": "disconnect"})).unwrap();
        assert_eq!(c.st().retry_at, None);
        assert!(!c.st().want_connected);
    }

    #[test]
    fn repeated_provider_failures_keep_fixed_country_and_bounded_backoff() {
        let dir = TempDir::new();
        let wall = Arc::new(AtomicU64::new(1010));
        let mono = Arc::new(AtomicU64::new(100));
        // The uplink "end0" does not exist here: every bound provider request fails.
        let c = controller(&dir, Some(runtime(runner(None), &wall)), &mono, json!([{"code": "IT", "id": 100}]));
        {
            let mut st = c.st();
            st.settings = json!({"provider": "nordvpn", "nord_key": key(), "country": "IT"}).as_object().unwrap().clone();
            st.want_connected = true;
        }
        for attempt in 0..15u64 {
            let now = 100 + attempt * 100;
            mono.store(now, Ordering::SeqCst);
            c.st().retry_at = Some(now as f64 - 1.0);
            c.tick().unwrap();
            assert_eq!(c.runtime.as_ref().unwrap().mode(), Mode::Blocked);
            let st = c.st();
            assert_eq!(st.settings["country"], "IT");
            assert!(st.retry_at.unwrap() - now as f64 <= 60.0);
            assert!(!st.enabled);
        }
        c.command(&json!({"action": "disconnect"})).unwrap();
        assert_eq!(c.st().retry_at, None);
    }

    #[test]
    fn confirmed_tunnel_loss_does_not_wait_for_initial_grace() {
        let dir = TempDir::new();
        let wall = Arc::new(AtomicU64::new(1010));
        let mono = Arc::new(AtomicU64::new(100));
        let c = controller(&dir, Some(runtime(runner(None), &wall)), &mono, json!([]));
        c.command(&json!({"action": "wireguard", "profile": profile()})).unwrap();
        c.tick().unwrap();
        assert!(c.st().connected_recorded);
        wall.store(1500, Ordering::SeqCst);
        c.tick().unwrap();
        assert_eq!(c.runtime.as_ref().unwrap().mode(), Mode::Blocked);
        assert!(!c.st().enabled);
        assert!(c.st().retry_at.is_some());
    }

    /// Exit failover group: a dead first member is replaced after 30 s
    /// without touching the site group; history records the alternate. When
    /// every exit member has failed, the single-peer rule applies again:
    /// block and retry with backoff.
    #[test]
    fn failover_rotates_the_exit_group_then_reconnects() {
        let dir = TempDir::new();
        let wall = Arc::new(AtomicU64::new(1010));
        let mono = Arc::new(AtomicU64::new(100));
        let peer = |n: u8| base64::engine::general_purpose::STANDARD.encode([n; 32]);
        let handshakes = Arc::new(std::sync::Mutex::new(vec![(peer(2), 1000i64)]));
        let h = handshakes.clone();
        let fake = Arc::new(FakeRunner::with(move |argv, _| {
            if argv.len() >= 4 && argv[..4] == ["ip", "-j", "route", "get"] {
                return ok(r#"[{"dev":"end0"}]"#);
            }
            if argv.len() >= 3 && argv[..3] == ["wg", "show", "phwg0"] {
                return ok(&h.lock().unwrap().iter().map(|(k, at)| format!("{k}\t{at}\n")).collect::<String>());
            }
            None
        }));
        let rt = runtime(fake.clone(), &wall).with_resolver(Arc::new(|_, _, _| Ok(std::net::Ipv4Addr::new(192, 0, 2, 21))));
        let c = controller(&dir, Some(rt), &mono, json!([]));
        let text = crate::runtime::tests::multi_peer_text();
        assert_eq!(c.wireguard_check(Some(&json!(text)))["details"], json!({"multiple_peers": {"peers": 3, "groups": 2}}));
        c.command(&json!({"action": "wireguard", "profile": text})).unwrap();
        c.tick().unwrap();
        let status = c.vpn_status();
        assert_eq!(status["state"], "connecting", "site up, exit member silent");
        let peers = status["peers"].as_array().unwrap();
        assert_eq!(peers.iter().map(|p| (p["group"].as_u64().unwrap(), p["active"].as_bool().unwrap())).collect::<Vec<_>>(), [(0, true), (1, true), (0, false)]);
        assert_eq!(peers[1]["connected"], true);
        assert_eq!(peers[2]["endpoint"], "backup.example.org:51821");

        fake.calls.lock().unwrap().clear();
        mono.store(131, Ordering::SeqCst);
        c.tick().unwrap();
        let argvs: Vec<String> = fake.calls.lock().unwrap().iter().map(|c| c.argv.join(" ")).collect();
        assert!(argvs.contains(&format!("wg set phwg0 peer {} remove", peer(1))), "{argvs:?}");
        assert!(argvs.contains(&"wg addconf phwg0 /dev/stdin".to_string()));
        assert!(argvs.iter().all(|a| !a.contains(&peer(2)) && !a.starts_with("ip link delete")), "site group and tunnel untouched: {argvs:?}");
        assert!(c.st().enabled && c.runtime.as_ref().unwrap().mode() == Mode::Vpn, "no full reconnect while an alternate is left");
        assert_eq!(c.st().location.server, "backup.example.org:51821");

        handshakes.lock().unwrap().push((peer(3), 1005));
        c.tick().unwrap();
        let status = c.vpn_status();
        assert_eq!(status["state"], "connected");
        assert_eq!(status["endpoint"], "192.0.2.21:51821");
        let history = c.history.page(0).unwrap();
        assert_eq!(history["entries"].as_array().unwrap().len(), 1);
        assert!(crate::json::dumps(&history).contains("backup.example.org:51821"));
        assert_eq!(c.st().group_tries, vec![0, 0]);

        // Alternate lost too: one more switch (back to the first member),
        // then the round is over and the gateway blocks and retries.
        wall.store(1500, Ordering::SeqCst);
        mono.store(400, Ordering::SeqCst);
        c.tick().unwrap();
        assert!(c.st().enabled, "first failure of the round only switches");
        assert_eq!(c.runtime.as_ref().unwrap().profile().unwrap().primary().public_key, peer(1));
        assert_eq!(c.runtime.as_ref().unwrap().profile().unwrap().active, vec![0, 0], "a single-member group never switches");
        mono.store(440, Ordering::SeqCst);
        c.tick().unwrap();
        assert_eq!(c.runtime.as_ref().unwrap().mode(), Mode::Blocked);
        assert!(!c.st().enabled && c.st().retry_at.is_some());
    }

    #[test]
    fn corrupt_credentials_fail_without_exposing_contents() {
        let dir = TempDir::new();
        let path = dir.path().join("vpn-private.json");
        std::fs::write(&path, r#"{"secret":"test-only-corrupt""#).unwrap();
        std::fs::set_permissions(&path, std::os::unix::fs::PermissionsExt::from_mode(0o600)).unwrap();
        let error = Controller::new(dir.path(), &json!([]), None).err().unwrap();
        assert!(!error.to_string().contains("test-only-corrupt"));
    }

    #[test]
    fn save_policy_applies_after_barrier_and_detects_conflicts() {
        let dir = TempDir::new();
        let wall = Arc::new(AtomicU64::new(1010));
        let fake = runner(None);
        let c = controller(&dir, Some(runtime(fake.clone(), &wall)), &Arc::new(AtomicU64::new(100)), json!([]));
        fake.clear();
        let saved = c.save_policy(&base()).unwrap();
        assert_eq!(saved["revision"], 1);
        assert!(matches!(c.save_policy(&base()), Err(Error::Conflict(_))));
        let calls = fake.calls.lock().unwrap();
        let applied: Vec<_> = calls.iter().filter(|c| c.argv == ["nft", "-f", "-"]).collect();
        assert!(applied.len() >= 2, "drop barrier then the new policy");
    }

    #[test]
    fn commands_are_validated_before_acceptance() {
        let dir = TempDir::new();
        let wall = Arc::new(AtomicU64::new(1010));
        let c = Arc::new(controller(&dir, Some(runtime(runner(None), &wall)), &Arc::new(AtomicU64::new(100)), json!([{"code": "IT", "id": 1}])));
        for body in [
            json!({"action": "shell"}),
            json!({"action": "connect"}),
            json!({"action": "wireguard", "profile": "x"}),
            json!({"action": "nordvpn", "rotation": true, "interval": 10}),
            json!({"action": "nordvpn", "rotation": true, "interval": 60, "country": "XX", "token": "t"}),
            json!({"action": "nordvpn", "rotation": true, "interval": 60, "token": "bad token"}),
            json!({"action": "uplink", "uplink": "wifi"}),
            json!({"action": "wifi", "mode": "sta", "ssid": "x"}),
            json!([1]),
        ] {
            assert!(c.submit(&body).is_err(), "{body}");
        }
        assert!(!c.st().busy);
        assert_eq!(c.submit(&json!({"action": "disconnect"})).unwrap(), json!({"accepted": true}));
    }
}
