//! In-process dispatch of the allowlisted control methods (rpc.py LocalAPI).
//! No shell, argv or file-read methods exist. The frontend reaches this only
//! through the Unix socket after the kernel peer-UID check.
use crate::auth::AdminAuth;
use crate::controller::Controller;
use crate::error::{conflict, invalid, unavailable, Error, Result};
use crate::json::{json, Map, Value};
use crate::rpc::Api;
use base64::Engine;
use std::sync::{Arc, OnceLock};

pub struct LocalApi {
    pub controller: Arc<Controller>,
    auth: OnceLock<AdminAuth>,
}

impl LocalApi {
    pub fn new(controller: Arc<Controller>) -> Self {
        LocalApi { controller, auth: OnceLock::new() }
    }

    fn auth(&self) -> Result<&AdminAuth> {
        if let Some(auth) = self.auth.get() {
            return Ok(auth);
        }
        // Created lazily like Python: the password file appears on first use.
        let auth = AdminAuth::new(self.controller.vault.path.parent().unwrap_or(std::path::Path::new(".")), crate::py::wall_clock())?;
        Ok(self.auth.get_or_init(|| auth))
    }

    fn history_cursor(args: &Map<String, Value>) -> Result<i64> {
        match args.get("before") {
            None => Ok(0),
            Some(Value::Number(n)) if n.is_i64() => Ok(n.as_i64().unwrap_or(0)),
            Some(Value::String(s)) if crate::py::is_digits(crate::py::strip(s)) => crate::py::strip(s).parse().map_err(|_| Error::Invalid("invalid_cursor".into())),
            _ => invalid("invalid_cursor"),
        }
    }

    fn upload(&self, args: &Map<String, Value>) -> Result<Value> {
        let c = &self.controller;
        let Some(updates) = &c.updates else {
            return unavailable("updates_not_configured");
        };
        let encoded = args.get("data").and_then(Value::as_str).ok_or_else(|| Error::Invalid("invalid_update".into()))?;
        let data = base64::engine::general_purpose::STANDARD.decode(encoded).map_err(|_| Error::Invalid("invalid_update".into()))?;
        if data.is_empty() || data.len() > crate::updates::MAX_UPLOAD {
            return invalid("update_too_large");
        }
        let _op = c.try_op()?;
        c.require_idle()?;
        let value = updates.stage(&data)?;
        {
            let mut st = c.st();
            st.updating = true;
            st.want_connected = false;
            st.enabled = false;
            st.retry_at = None;
            st.timer.disconnected();
        }
        let runtime = c.runtime()?;
        runtime.block(&c.policy()?)?;
        runtime.run.run(&["systemctl", "start", "--no-block", "phoenix-update.service"])?;
        Ok(value)
    }
}

impl Api for LocalApi {
    fn call(&self, method: &str, args: Map<String, Value>) -> Result<Value> {
        let c = &self.controller;
        if let Some(action) = method.strip_prefix("auth_") {
            if matches!(action, "status" | "check" | "login" | "logout" | "password") {
                return self.auth()?.call(action, &args);
            }
        }
        match method {
            "health" => Ok(json!({"ready": !c.st().closing, "release_id": crate::http::release_id()})),
            "capabilities" => {
                let network = c.runtime.is_some();
                Ok(json!({
                    "network_initialized": network,
                    "speedtest": network && crate::speedcheck::available(),
                    "hotspot_configuration": c.access_point.lock().unwrap_or_else(|e| e.into_inner()).is_some(),
                    "wifi_provisioning": c.station.lock().unwrap_or_else(|e| e.into_inner()).is_some(),
                    "usb_provisioning": false,
                    "firmware_update": c.updates.is_some(),
                    "exit_ip_verification": network,
                    "catalog_test": network,
                    // Any wg/wg-quick client profile (IPv4 parts used, hooks never run).
                    "wireguard_import": "extended",
                }))
            }
            "hotspot" => Ok(c.hotspot_status()),
            "save_hotspot" => c.configure_hotspot(&Value::Object(args)),
            "speedtest" => Ok(c.measurement.status()),
            "speedtest_start" => c.start_speedtest(),
            "speedtest_cancel" => {
                c.measurement.cancel();
                Ok(json!({"accepted": true}))
            }
            "status" => {
                let mut status = c.runtime()?.status()?;
                let has_ap = c.access_point.lock().unwrap_or_else(|e| e.into_inner()).is_some();
                if has_ap {
                    let active = c.hotspot_status()["active"].clone();
                    if let Some(object) = status.as_object_mut() {
                        object.insert("ap_active".into(), active);
                    }
                }
                Ok(status)
            }
            "policy" => c.policy(),
            "save_policy" => {
                let _op = match c.op.try_lock() {
                    Ok(guard) => guard,
                    Err(_) => return conflict("command_in_progress"),
                };
                c.save_policy(&Value::Object(args))
            }
            "vpn" => Ok(c.vpn_status()),
            "wireguard_check" => Ok(c.wireguard_check(args.get("profile"))),
            "command" => c.submit(&Value::Object(args)),
            "history" => c.history.page(Self::history_cursor(&args)?),
            "preflight" => Ok(crate::preflight::inspect()),
            "scan" => {
                let station = c.station.lock().unwrap_or_else(|e| e.into_inner());
                let Some(station) = station.as_ref() else {
                    return unavailable("scan_unavailable");
                };
                let ap_active = c.access_point.lock().unwrap_or_else(|e| e.into_inner()).as_ref().map(|ap| ap.active).unwrap_or(false);
                if ap_active && Some(&station.name) == c.base_ap.as_ref() {
                    return unavailable("scan_unavailable");
                }
                station.scan()
            }
            "firmware" => match &c.updates {
                Some(updates) => updates.status(),
                None => unavailable("updates_not_configured"),
            },
            "upload" => self.upload(&args),
            _ => invalid("unknown_rpc_method"),
        }
    }
}
