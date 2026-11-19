//! NordVPN provisioning/catalog adapter, same API flow as ESP32 (nord.py).
//! The token is used for a single request and never persisted.
use crate::error::{invalid, Error, Result};
use crate::json::{self, Value};
use crate::rotation::choose_country;
use crate::wireguard::{key, parse, Profile};
use base64::Engine;

/// (path, token) -> JSON. Production: Runtime::nord_request.
pub type Request<'a> = &'a dyn Fn(&str, Option<&str>) -> Result<Value>;
/// (path, headers) -> JSON. Production: uplink_http::get bound to the uplink.
pub type Transport<'a> = &'a dyn Fn(&str, &[(String, String)]) -> Result<Value>;

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Location {
    pub id: i64,
    pub country: String,
    pub server: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Country {
    pub code: String,
    pub id: i64,
}

/// Parse countries.json entries ({"id","code",...}).
pub fn countries(catalog: &Value) -> Result<Vec<Country>> {
    let Some(items) = catalog.as_array() else {
        return invalid("invalid_country_catalog");
    };
    items
        .iter()
        .map(|item| match (item.get("code").and_then(Value::as_str), item.get("id")) {
            (Some(code), Some(id)) if json::is_int(id) => Ok(Country { code: code.to_string(), id: id.as_i64().unwrap_or(0) }),
            _ => invalid("invalid_country_catalog"),
        })
        .collect()
}

fn valid_token(token: &str) -> bool {
    (1..=512).contains(&token.chars().count()) && !token.chars().any(|c| (c as u32) < 33)
}

/// Any transport failure becomes Invalid("nord_api_failed").
pub fn get(path: &str, token: Option<&str>, transport: Transport) -> Result<Value> {
    if !path.starts_with("/v1/") {
        return invalid("invalid_api_path");
    }
    let mut headers = vec![("Accept".to_string(), "application/json".to_string())];
    if let Some(token) = token.filter(|t| !t.is_empty()) {
        if !valid_token(token) {
            return invalid("invalid_token");
        }
        let credentials = base64::engine::general_purpose::STANDARD.encode(format!("token:{token}"));
        headers.push(("Authorization".to_string(), format!("Basic {credentials}")));
    }
    transport(path, &headers).map_err(|_| Error::Invalid("nord_api_failed".into()))
}

pub fn provision(token: &str, request: Request) -> Result<String> {
    let result = request("/v1/users/services/credentials", Some(token))?;
    let Some(object) = result.as_object() else {
        return invalid("invalid_credentials");
    };
    match object.get("nordlynx_private_key") {
        None => key(""),
        Some(Value::String(value)) => key(value),
        Some(_) => invalid("invalid_key"),
    }
}

/// Python `str(value)` for the scalar JSON values Nord may return.
fn text(value: &Value) -> Option<String> {
    match value {
        Value::String(s) => Some(s.clone()),
        Value::Number(n) => Some(n.to_string()),
        Value::Bool(true) => Some("True".into()),
        Value::Bool(false) => Some("False".into()),
        Value::Null => Some("None".into()),
        _ => None,
    }
}

/// Candidate from one recommendation entry; None skips it (Python's
/// KeyError/ValueError/TypeError/IndexError/StopIteration handling).
fn candidate(server: &Value, country: &str, private_key: &str) -> Option<(Profile, Location)> {
    let server = server.as_object()?;
    if server.get("status")?.as_str() != Some("online") {
        return None;
    }
    let code = server.get("locations")?.as_array()?.first()?.as_object()?.get("country")?.as_object()?.get("code")?;
    if code.as_str() != Some(country) {
        return None;
    }
    let mut public = None;
    'technologies: for technology in server.get("technologies")?.as_array()? {
        let technology = technology.as_object()?;
        if technology.get("identifier")?.as_str() != Some("wireguard_udp") {
            continue;
        }
        for meta in technology.get("metadata")?.as_array()? {
            let meta = meta.as_object()?;
            if meta.get("name")?.as_str() == Some("public_key") {
                public = Some(meta.get("value")?);
                break 'technologies;
            }
        }
    }
    let public = text(public?)?;
    let id = server.get("id")?;
    if !json::is_int(id) || id.as_i64()? <= 0 {
        return None;
    }
    let station = text(server.get("station")?)?;
    let profile = parse(&format!(
        "[Interface]\nPrivateKey={private_key}\nAddress=10.5.0.2/32\nDNS=103.86.96.100\nMTU=1380\n[Peer]\nPublicKey={public}\nEndpoint={station}:51820\nAllowedIPs=0.0.0.0/0\nPersistentKeepalive=25\n"
    ))
    .ok()?;
    let name: String = text(server.get("name")?)?.chars().take(63).collect();
    Some((profile, Location { id: id.as_i64()?, country: country.to_string(), server: name }))
}

#[allow(clippy::too_many_arguments)]
pub fn select(private_key: &str, countries: &[Country], fixed: &str, previous: &str, exclude: bool, previous_server: i64, request: Request, choice: &mut dyn FnMut(usize) -> usize) -> Result<(Profile, Location)> {
    let private_key = key(private_key)?;
    let codes: Vec<String> = countries.iter().map(|c| c.code.clone()).collect();
    let country = choose_country(&codes, fixed, previous, exclude, choice)?;
    // Later duplicates win, as with Python's dict comprehension.
    let id = countries.iter().rev().find(|c| c.code == country).map(|c| c.id).unwrap_or(0);
    let path = format!("/v1/servers/recommendations?filters%5Bservers_technologies%5D%5Bidentifier%5D=wireguard_udp&filters%5Bcountry_id%5D={id}&limit=5");
    let result = request(&path, None)?;
    let Some(servers) = result.as_array() else {
        return invalid("invalid_catalog");
    };
    let candidates: Vec<(Profile, Location)> = servers.iter().take(5).filter_map(|s| candidate(s, &country, &private_key)).collect();
    if candidates.is_empty() {
        return invalid("no_server_in_selected_country");
    }
    let alternatives: Vec<&(Profile, Location)> = candidates.iter().filter(|c| c.1.id != previous_server).collect();
    let pool: Vec<&(Profile, Location)> = if alternatives.is_empty() { candidates.iter().collect() } else { alternatives };
    Ok(pool[choice(pool.len())].clone())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::json::json;
    use std::cell::RefCell;

    const KEY: &str = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=";

    fn server(id: i64, status: &str, code: &str) -> Value {
        json!({"status": status, "id": id, "name": "Test", "station": "192.0.2.1",
               "locations": [{"country": {"code": code}}],
               "technologies": [{"identifier": "openvpn_udp"}, {"identifier": "wireguard_udp", "metadata": [{"name": "public_key", "value": KEY}]}]})
    }

    fn catalog() -> Vec<Country> {
        countries(&json!([{"code": "IT", "id": 106, "name": "Italy"}, {"code": "US", "id": 228}])).unwrap()
    }

    #[test]
    fn wrong_country_and_offline_servers_rejected() {
        let paths = RefCell::new(Vec::new());
        let one = |s: Value| {
            let paths = &paths;
            move |path: &str, token: Option<&str>| {
                assert!(token.is_none());
                paths.borrow_mut().push(path.to_string());
                Ok(json!([s.clone()]))
            }
        };
        let mut first = |_: usize| 0;
        let (profile, info) = select(KEY, &catalog(), "IT", "", false, 0, &one(server(1, "online", "IT")), &mut first).unwrap();
        assert_eq!(info, Location { id: 1, country: "IT".into(), server: "Test".into() });
        assert_eq!(profile.primary().endpoint, "192.0.2.1:51820");
        assert_eq!(profile.primary().keepalive, 25);
        assert_eq!(paths.borrow()[0], "/v1/servers/recommendations?filters%5Bservers_technologies%5D%5Bidentifier%5D=wireguard_udp&filters%5Bcountry_id%5D=106&limit=5");
        assert!(select(KEY, &catalog(), "US", "", false, 0, &one(server(1, "online", "IT")), &mut first).is_err());
        assert!(select(KEY, &catalog(), "IT", "", false, 0, &one(server(1, "offline", "IT")), &mut first).is_err());
        assert!(select(KEY, &catalog(), "IT", "", false, 0, &one(server(0, "online", "IT")), &mut first).is_err());
        let mut bad = server(1, "online", "IT");
        bad["id"] = json!(true);
        assert!(select(KEY, &catalog(), "IT", "", false, 0, &one(bad), &mut first).is_err());
        assert!(select("short", &catalog(), "IT", "", false, 0, &one(server(1, "online", "IT")), &mut first).is_err());
        let not_list = |_: &str, _: Option<&str>| Ok(json!({}));
        assert_eq!(select(KEY, &catalog(), "IT", "", false, 0, &not_list, &mut first).unwrap_err().code(), "invalid_catalog");
    }

    #[test]
    fn avoids_previous_server_and_skips_malformed_entries() {
        let mut long = server(3, "online", "IT");
        long["name"] = json!("n".repeat(80));
        let list = json!(["junk", {"status": "online"}, server(2, "online", "IT"), long, server(4, "online", "IT"), server(5, "online", "IT")]);
        let request = move |_: &str, _: Option<&str>| Ok(list.clone());
        let mut last = |n: usize| n - 1;
        let (_, info) = select(KEY, &catalog(), "IT", "", false, 3, &request, &mut last).unwrap();
        // Only the first five entries are considered; 3 is excluded as previous.
        assert_eq!(info.id, 4);
        let mut first = |_: usize| 0;
        let (_, info) = select(KEY, &catalog(), "IT", "", false, 2, &request, &mut first).unwrap();
        assert_eq!(info.id, 3);
        assert_eq!(info.server.chars().count(), 63);
        let only = json!([server(2, "online", "IT")]);
        let request = move |_: &str, _: Option<&str>| Ok(only.clone());
        assert_eq!(select(KEY, &catalog(), "IT", "", false, 2, &request, &mut first).unwrap().1.id, 2);
    }

    #[test]
    fn credentials_missing_key() {
        assert!(provision("not-a-real-token", &|_, _| Ok(json!({}))).is_err());
        assert!(provision("t", &|_, _| Ok(json!([]))).is_err());
        assert_eq!(provision("t", &|_, token| {
            assert_eq!(token, Some("t"));
            Ok(json!({"nordlynx_private_key": KEY}))
        }).unwrap(), KEY);
    }

    #[test]
    fn provider_never_returns_sensitive_exception() {
        let failing = |_: &str, _: &[(String, String)]| Err(Error::Network("secret-test-only".into()));
        let error = get("/v1/test", Some("secret-test-only"), &failing).unwrap_err();
        assert_eq!(error, Error::Invalid("nord_api_failed".into()));
        let seen = RefCell::new(Vec::new());
        let record = |_: &str, headers: &[(String, String)]| {
            seen.borrow_mut().extend_from_slice(headers);
            Ok(json!([]))
        };
        get("/v1/x", Some("abc"), &record).unwrap();
        assert_eq!(seen.borrow()[1], ("Authorization".to_string(), "Basic dG9rZW46YWJj".to_string()));
        get("/v1/x", Some(""), &record).unwrap();
        assert_eq!(seen.borrow().len(), 3, "empty token sends no Authorization");
        for token in ["a b", "x\n", &"x".repeat(513)] {
            assert_eq!(get("/v1/x", Some(token), &record).unwrap_err().code(), "invalid_token");
        }
        assert!(get("/v2/x", None, &record).is_err());
        assert!(countries(&json!([{"code": "IT"}])).is_err());
        assert_eq!(countries(&crate::web::countries()).unwrap().iter().find(|c| c.code == "IT").map(|c| c.id), Some(106));
    }
}
