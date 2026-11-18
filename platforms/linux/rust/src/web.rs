//! The single shared UI (shared/web), embedded at build time.
use crate::json::Value;

pub const INDEX_HTML: &[u8] = include_bytes!("../../../../shared/web/index.html");
pub const APP_JS: &[u8] = include_bytes!("../../../../shared/web/app.js");
pub const APP_CSS: &[u8] = include_bytes!("../../../../shared/web/app.css");
pub const COUNTRIES_JSON: &[u8] = include_bytes!("../../../../shared/web/countries.json");

/// Static assets served without authentication: (body, content type).
pub fn asset(path: &str) -> Option<(&'static [u8], &'static str)> {
    match path {
        "/" => Some((INDEX_HTML, "text/html; charset=utf-8")),
        "/app.js" => Some((APP_JS, "text/javascript; charset=utf-8")),
        "/app.css" => Some((APP_CSS, "text/css; charset=utf-8")),
        "/countries.json" => Some((COUNTRIES_JSON, "application/json; charset=utf-8")),
        _ => None,
    }
}

/// Country catalog `[{"id", "name", "code"}]` used by the controller.
pub fn countries() -> Value {
    crate::json::parse(COUNTRIES_JSON).expect("embedded countries.json is valid")
}
