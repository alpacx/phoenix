//! Password administration, persistent account lockout and ephemeral
//! sessions (admin_auth.py). admin-password.json keeps the Python format:
//! {salt, hash: scrypt(N=16384, r=8, p=1, 64 bytes) hex, must_change,
//! failures, locked_until}. Sessions live only in memory.
use crate::error::{invalid, Error, Result};
use crate::json::{self, json, Map, Value};
use crate::py::{self, Clock};
use crate::vault::Vault;
use ring::digest::{digest, SHA256};
use std::path::Path;
use std::sync::Mutex;

const MAX_SESSIONS: usize = 32;
const INITIAL_PASSWORD: &str = "phoenix";

struct Session {
    key: String,
    expires: f64,
    must_change: bool,
}

pub struct AdminAuth {
    vault: Vault,
    clock: Clock,
    sessions: Mutex<Vec<Session>>,
}

fn derive(password: &str, salt: &str) -> Result<String> {
    let salt = py::unhex(salt).ok_or_else(|| Error::Invalid("invalid_password_state".into()))?;
    let params = scrypt::Params::new(14, 8, 1, 64).map_err(|_| Error::Invalid("scrypt_parameters".into()))?;
    let mut out = [0u8; 64];
    scrypt::scrypt(password.as_bytes(), &salt, &params, &mut out).map_err(|_| Error::Invalid("scrypt_failed".into()))?;
    Ok(py::hex(&out))
}

/// hmac.compare_digest: no early exit on the first differing byte.
pub(crate) fn equal(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    a.iter().zip(b).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}

fn key(session: Option<&Value>) -> String {
    match session {
        Some(Value::String(s)) if s.chars().count() <= 128 => py::hex(digest(&SHA256, s.as_bytes()).as_ref()),
        _ => String::new(),
    }
}

fn text<'a>(state: &'a Map<String, Value>, name: &str) -> Result<&'a str> {
    state.get(name).and_then(Value::as_str).ok_or_else(|| Error::Invalid("invalid_password_state".into()))
}

fn number(state: &Map<String, Value>, name: &str) -> Result<f64> {
    state.get(name).and_then(Value::as_f64).ok_or_else(|| Error::Invalid("invalid_password_state".into()))
}

fn float(value: f64) -> Value {
    serde_json::Number::from_f64(value).map(Value::Number).unwrap_or(json!(0))
}

impl AdminAuth {
    /// `clock` is wall time. Creates admin-password.json ("phoenix") if missing.
    pub fn new(directory: &Path, clock: Clock) -> Result<AdminAuth> {
        let vault = Vault::named(directory, "admin-password.json");
        if !crate::fsutil::exists(&vault.path) {
            let salt = py::token_hex(16);
            let hash = derive(INITIAL_PASSWORD, &salt)?;
            vault.save(&json!({"salt": salt, "hash": hash, "must_change": true, "failures": 0, "locked_until": 0}))?;
        }
        Ok(AdminAuth { vault, clock, sessions: Mutex::new(Vec::new()) })
    }

    fn now(&self) -> f64 {
        (self.clock)()
    }

    fn lookup(&self, sessions: &mut Vec<Session>, token: Option<&Value>) -> Option<bool> {
        let now = self.now();
        sessions.retain(|s| s.expires > now);
        let wanted = key(token);
        sessions.iter().find(|s| s.key == wanted).map(|s| s.must_change)
    }

    fn issue(&self, sessions: &mut Vec<Session>, must_change: bool) -> Value {
        if sessions.len() >= MAX_SESSIONS {
            sessions.remove(0);
        }
        let token = py::token_urlsafe(32);
        let lifetime = if must_change { 600.0 } else { 3600.0 };
        sessions.push(Session { key: key(Some(&Value::String(token.clone()))), expires: self.now() + lifetime, must_change });
        json!({"ok": true, "session": token, "must_change": must_change})
    }

    /// None when the password is right; otherwise the error reply.
    fn check_password(&self, state: &mut Map<String, Value>, password: Option<&Value>) -> Result<Option<Value>> {
        let locked_until = number(state, "locked_until")?;
        if locked_until > self.now() {
            return Ok(Some(json!({"ok": false, "error": "login_locked", "retry_after": (locked_until - self.now()).ceil() as i64})));
        }
        let valid = match password {
            Some(Value::String(p)) if p.len() <= 512 => equal(text(state, "hash")?.as_bytes(), derive(p, text(state, "salt")?)?.as_bytes()),
            _ => false,
        };
        if !valid {
            let failures = state.get("failures").and_then(Value::as_i64).ok_or_else(|| Error::Invalid("invalid_password_state".into()))? + 1;
            state.insert("failures".into(), json!(failures));
            if failures >= 3 {
                state.insert("failures".into(), json!(0));
                state.insert("locked_until".into(), float(self.now() + 300.0));
            }
            self.vault.save(&Value::Object(state.clone()))?;
            let locked_until = number(state, "locked_until")?;
            let locked = locked_until > self.now();
            return Ok(Some(json!({
                "ok": false,
                "error": if locked { "login_locked" } else { "invalid_password" },
                "retry_after": ((locked_until - self.now()).ceil() as i64).max(0),
            })));
        }
        state.insert("failures".into(), json!(0));
        state.insert("locked_until".into(), json!(0));
        self.vault.save(&Value::Object(state.clone()))?;
        Ok(None)
    }

    /// action: status | check | logout | login | password.
    pub fn call(&self, action: &str, args: &Map<String, Value>) -> Result<Value> {
        let mut sessions = self.sessions.lock().unwrap_or_else(|e| e.into_inner());
        let mut state = self.vault.load_object()?;
        let token = args.get("session");
        let session = self.lookup(&mut sessions, Some(token.unwrap_or(&json!(""))));
        match action {
            "status" => Ok(json!({"password_login": true, "authenticated": session.is_some(), "must_change": session == Some(true)})),
            "check" => Ok(json!({"ok": session == Some(false)})),
            "logout" => {
                let wanted = key(Some(token.unwrap_or(&json!(""))));
                sessions.retain(|s| s.key != wanted);
                Ok(json!({"ok": true}))
            }
            "login" => match self.check_password(&mut state, args.get("password"))? {
                Some(error) => Ok(error),
                None => {
                    let must_change = json::truthy(state.get("must_change"));
                    Ok(self.issue(&mut sessions, must_change))
                }
            },
            "password" => {
                if session.is_none() {
                    return Ok(json!({"ok": false, "error": "authentication_required"}));
                }
                let new_password = match args.get("new_password") {
                    Some(Value::String(p)) if (12..=128).contains(&py::len_chars(p)) && p != INITIAL_PASSWORD => p,
                    _ => return Ok(json!({"ok": false, "error": "password_too_short"})),
                };
                if let Some(error) = self.check_password(&mut state, args.get("current_password"))? {
                    return Ok(error);
                }
                if equal(text(&state, "hash")?.as_bytes(), derive(new_password, text(&state, "salt")?)?.as_bytes()) {
                    return Ok(json!({"ok": false, "error": "password_unchanged"}));
                }
                let salt = py::token_hex(16);
                let hash = derive(new_password, &salt)?;
                self.vault.save(&json!({"salt": salt, "hash": hash, "must_change": false, "failures": 0, "locked_until": 0}))?;
                sessions.clear();
                Ok(self.issue(&mut sessions, false))
            }
            _ => invalid("unknown_auth_action"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fsutil::testdir::TempDir;
    use std::os::unix::fs::MetadataExt;
    use std::sync::atomic::{AtomicI64, Ordering};
    use std::sync::Arc;

    struct Fixture {
        dir: TempDir,
        now: Arc<AtomicI64>,
        auth: AdminAuth,
    }

    impl Fixture {
        fn new() -> Self {
            let dir = TempDir::new();
            let now = Arc::new(AtomicI64::new(1000));
            let auth = AdminAuth::new(dir.path(), Self::clock(&now)).unwrap();
            Fixture { dir, now, auth }
        }
        fn clock(now: &Arc<AtomicI64>) -> Clock {
            let now = now.clone();
            Arc::new(move || now.load(Ordering::SeqCst) as f64)
        }
        fn restart(&mut self) {
            self.auth = AdminAuth::new(self.dir.path(), Self::clock(&self.now)).unwrap();
        }
        fn call(&self, action: &str, args: Value) -> Value {
            self.auth.call(action, args.as_object().unwrap()).unwrap()
        }
    }

    fn with(base: &Value, extra: Value) -> Value {
        let mut out = base.as_object().unwrap().clone();
        out.extend(extra.as_object().unwrap().clone());
        Value::Object(out)
    }

    #[test]
    fn python_scrypt_vectors() {
        assert_eq!(
            derive("phoenix", "00112233445566778899aabbccddeeff").unwrap(),
            "681be17c8bdc71b527c9f61c9fad4f157bc3591c02048d3cf68a9bd3a931164ec5324549df0808e877785aa2e652f4132dc497bad7e3303df68dcb49e80d24da"
        );
        assert_eq!(
            derive("pässwörd long", "ffeeddccbbaa99887766554433221100").unwrap(),
            "35843f8f1a2cb105f9c1df81d2f96b42324d5291e7d478970be826d97d12cba8477cbf96d371bda16e9628534263af02655267e866d6fc872ba763a0efb8bab4"
        );
    }

    #[test]
    fn initial_session_cannot_admin_and_change_revokes_all_sessions() {
        let f = Fixture::new();
        let first = f.call("login", json!({"password": "phoenix"}));
        let second = f.call("login", json!({"password": "phoenix"}));
        assert_eq!(first["must_change"], true);
        assert_eq!(f.call("check", first.clone())["ok"], false);
        let result = f.call("password", with(&first, json!({"current_password": "phoenix", "new_password": "a long test phrase"})));
        assert_eq!(f.call("check", result.clone())["ok"], true);
        assert_eq!(f.call("check", second)["ok"], false);
        assert_eq!(f.call("login", json!({"password": "phoenix"}))["ok"], false);
        assert_eq!(f.call("login", json!({"password": "a long test phrase"}))["ok"], true);
        let path = f.dir.path().join("admin-password.json");
        let stored = std::fs::read_to_string(&path).unwrap();
        assert!(!stored.contains("a long test phrase") && !stored.contains("phoenix"));
        assert_eq!(std::fs::metadata(&path).unwrap().mode() & 0o777, 0o600);
    }

    #[test]
    fn third_failure_locks_even_correct_password_and_survives_restart() {
        let mut f = Fixture::new();
        for _ in 0..2 {
            assert_eq!(f.call("login", json!({"password": "wrong"}))["error"], "invalid_password");
        }
        let result = f.call("login", json!({"password": "wrong"}));
        assert_eq!(result["retry_after"], 300);
        f.restart();
        assert_eq!(f.call("login", json!({"password": "phoenix"}))["error"], "login_locked");
        f.now.fetch_add(300, Ordering::SeqCst);
        assert_eq!(f.call("login", json!({"password": "phoenix"}))["ok"], true);
    }

    #[test]
    fn session_expiry_logout_and_restart() {
        let mut f = Fixture::new();
        let result = f.call("login", json!({"password": "phoenix"}));
        f.now.fetch_add(601, Ordering::SeqCst);
        assert_eq!(f.call("status", result)["authenticated"], false);
        let result = f.call("login", json!({"password": "phoenix"}));
        assert_eq!(f.call("status", result.clone())["must_change"], true);
        f.call("logout", result.clone());
        assert_eq!(f.call("status", result)["authenticated"], false);
        let result = f.call("login", json!({"password": "phoenix"}));
        f.restart();
        assert_eq!(f.call("status", result)["authenticated"], false);
    }

    #[test]
    fn change_requires_session_current_password_and_length() {
        let f = Fixture::new();
        assert_eq!(f.call("password", json!({"new_password": "a long test phrase"}))["ok"], false);
        let session = f.call("login", json!({"password": "phoenix"}));
        assert_eq!(f.call("password", with(&session, json!({"current_password": "phoenix", "new_password": "short"})))["ok"], false);
        assert_eq!(f.call("password", with(&session, json!({"current_password": "phoenix", "new_password": "phoenix"})))["error"], "password_too_short");
        let mut result = json!({});
        for _ in 0..3 {
            result = f.call("password", with(&session, json!({"current_password": "wrong", "new_password": "a long test phrase"})));
        }
        assert_eq!(result["error"], "login_locked");
        assert!(f.auth.call("other", &Map::new()).is_err());
    }

    #[test]
    fn session_limit_and_odd_tokens() {
        let f = Fixture::new();
        let first = f.call("login", json!({"password": "phoenix"}));
        {
            // Issue directly: 32 more scrypt logins are slow in debug builds.
            let mut sessions = f.auth.sessions.lock().unwrap();
            for _ in 0..31 {
                f.auth.issue(&mut sessions, false);
            }
        }
        assert_eq!(f.call("status", first.clone())["authenticated"], true);
        f.auth.issue(&mut f.auth.sessions.lock().unwrap(), false);
        assert_eq!(f.call("status", first)["authenticated"], false);
        assert_eq!(f.call("status", json!({"session": 5}))["authenticated"], false);
        assert_eq!(f.call("status", json!({"session": "x".repeat(129)}))["authenticated"], false);
        assert_eq!(f.call("login", json!({"password": 12345678}))["error"], "invalid_password");
        assert_eq!(f.call("login", json!({"password": "x".repeat(513)}))["error"], "invalid_password");
    }
}
