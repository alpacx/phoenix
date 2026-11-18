//! HTTP/1.0 request handling shared by the HTTPS frontend and the loopback
//! development server (server.py handler + auth_http.py). One request per
//! connection; the caller sets socket timeouts. No access logs: requests may
//! carry credentials.
use crate::auth::equal;
use crate::error::{invalid, Error, Result};
use crate::json::{self, json, truthy, Map, Value};
use crate::py;
use crate::rpc::Api;
use crate::web;
use base64::Engine;
use std::io::{self, ErrorKind, Read, Write};
use std::net::TcpStream;
use std::time::{Duration, Instant};

const MAX_LINE: usize = 65536;
const MAX_HEADERS: usize = 100;
const MAX_UPLOAD: usize = 20 * 1024 * 1024;
const MAX_JSON: usize = 16384;
const MAX_AUTH_BODY: usize = 4096;
const COOKIE: &str = "__Host-phoenix";
const CSP: &str = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'";

pub struct Settings {
    /// Expected Host header, e.g. "127.0.0.1:8443" or "192.168.7.1".
    pub authority: String,
    pub tls: bool,
    pub password_auth: bool,
    pub allow_bearer: bool,
    /// 64 lowercase hex characters.
    pub token: String,
    /// Name of the release directory this binary runs from (healthz).
    pub release_id: String,
}

/// Budget for one connection: TLS handshake, request and response together.
pub const CONNECTION_DEADLINE: Duration = Duration::from_secs(10);
/// Authenticated firmware bodies may need longer over slow tunnels.
pub const UPLOAD_DEADLINE: Duration = Duration::from_secs(300);
/// Longest single read/write wait (Python settimeout(5)).
pub const STEP_TIMEOUT: Duration = Duration::from_secs(5);

/// A connection the handler may grant more time (authenticated uploads only).
pub trait Stream: Read + Write {
    fn extend_deadline(&mut self, _total: Duration) {}
}

/// TCP stream with an absolute deadline: every read/write waits at most the
/// remaining time, so a peer trickling bytes cannot hold a server thread
/// past the deadline (per-operation timeouts alone allow that).
pub struct Deadlined {
    pub stream: TcpStream,
    deadline: Instant,
}

impl Deadlined {
    pub fn new(stream: TcpStream, total: Duration) -> Self {
        Deadlined { stream, deadline: Instant::now() + total }
    }

    fn arm(&self, write: bool) -> io::Result<()> {
        let left = self.deadline.saturating_duration_since(Instant::now());
        if left.is_zero() {
            return Err(io::Error::new(ErrorKind::TimedOut, "connection deadline"));
        }
        let step = Some(left.min(STEP_TIMEOUT));
        if write {
            self.stream.set_write_timeout(step)
        } else {
            self.stream.set_read_timeout(step)
        }
    }
}

impl Read for Deadlined {
    fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
        self.arm(false)?;
        self.stream.read(buf)
    }
}

impl Write for Deadlined {
    fn write(&mut self, buf: &[u8]) -> io::Result<usize> {
        self.arm(true)?;
        self.stream.write(buf)
    }
    fn flush(&mut self) -> io::Result<()> {
        self.stream.flush()
    }
}

impl Stream for Deadlined {
    fn extend_deadline(&mut self, total: Duration) {
        self.deadline = Instant::now() + total;
    }
}

impl Stream for rustls::StreamOwned<rustls::ServerConnection, Deadlined> {
    fn extend_deadline(&mut self, total: Duration) {
        self.sock.extend_deadline(total);
    }
}

/// Buffered reader over a connection that can still be written to.
pub(crate) struct Conn<'a, S> {
    stream: &'a mut S,
    buf: Vec<u8>,
    pos: usize,
}

pub(crate) enum Line {
    /// Bytes read, including the terminating newline when present.
    Data(Vec<u8>),
    /// More than the limit without a newline.
    TooLong,
}

impl<'a, S: Read + Write> Conn<'a, S> {
    pub(crate) fn new(stream: &'a mut S) -> Self {
        Conn { stream, buf: Vec::new(), pos: 0 }
    }

    fn fill(&mut self) -> io::Result<usize> {
        if self.pos == self.buf.len() {
            self.buf.clear();
            self.pos = 0;
        }
        let mut chunk = [0u8; 8192];
        loop {
            match self.stream.read(&mut chunk) {
                Ok(n) => {
                    self.buf.extend_from_slice(&chunk[..n]);
                    return Ok(n);
                }
                Err(e) if e.kind() == ErrorKind::Interrupted => continue,
                Err(e) => return Err(e),
            }
        }
    }

    /// Python `readline(limit + 1)`: empty data means the peer closed.
    pub(crate) fn read_line(&mut self, limit: usize) -> io::Result<Line> {
        let mut line = Vec::new();
        loop {
            if self.pos < self.buf.len() {
                let available = &self.buf[self.pos..];
                let take = match available.iter().position(|&b| b == b'\n') {
                    Some(i) => i + 1,
                    None => available.len(),
                };
                let take = take.min(limit + 1 - line.len());
                line.extend_from_slice(&available[..take]);
                self.pos += take;
                if line.last() == Some(&b'\n') {
                    return Ok(Line::Data(line));
                }
                if line.len() > limit {
                    return Ok(Line::TooLong);
                }
            } else if self.fill()? == 0 {
                return Ok(Line::Data(line));
            }
        }
    }

    /// Up to `size` body bytes; fewer only when the peer closed early.
    pub(crate) fn read_body(&mut self, size: usize) -> io::Result<Vec<u8>> {
        let mut out = Vec::with_capacity(size.min(65536));
        while out.len() < size {
            if self.pos == self.buf.len() && self.fill()? == 0 {
                break;
            }
            let take = (self.buf.len() - self.pos).min(size - out.len());
            out.extend_from_slice(&self.buf[self.pos..self.pos + take]);
            self.pos += take;
        }
        Ok(out)
    }

    pub(crate) fn write_all(&mut self, data: &[u8]) {
        // The client may be gone; there is nobody left to report to.
        let _ = self.stream.write_all(data).and_then(|_| self.stream.flush());
    }
}

pub(crate) struct Request {
    pub method: String,
    pub target: String,
    pub headers: Vec<(String, String)>,
}

impl Request {
    pub(crate) fn all(&self, name: &str) -> Vec<&str> {
        self.headers.iter().filter(|(n, _)| n.eq_ignore_ascii_case(name)).map(|(_, v)| v.as_str()).collect()
    }

    pub(crate) fn get(&self, name: &str) -> Option<&str> {
        self.headers.iter().find(|(n, _)| n.eq_ignore_ascii_case(name)).map(|(_, v)| v.as_str())
    }

    /// email.message get_content_type(): lowercased media type, default text/plain.
    pub(crate) fn content_type(&self) -> String {
        let value = self.get("Content-Type").unwrap_or("text/plain");
        let media = value.split(';').next().unwrap_or("").trim().to_ascii_lowercase();
        if media.matches('/').count() == 1 {
            media
        } else {
            "text/plain".into()
        }
    }

    /// `self.headers.get('Transfer-Encoding')` is truthy.
    fn transfer_encoding(&self) -> bool {
        self.get("Transfer-Encoding").map(|v| !v.is_empty()).unwrap_or(false)
    }

    pub(crate) fn path(&self) -> &str {
        split_target(&self.target).0
    }

    fn query(&self) -> &str {
        split_target(&self.target).1
    }
}

/// urllib.parse.urlsplit(target) -> (path, query).
fn split_target(target: &str) -> (&str, &str) {
    let without_fragment = target.split('#').next().unwrap_or("");
    let (mut rest, query) = without_fragment.split_once('?').unwrap_or((without_fragment, ""));
    if let Some(i) = rest.find(':') {
        let scheme = &rest[..i];
        if i > 0 && scheme.as_bytes()[0].is_ascii_alphabetic() && scheme.bytes().all(|b| b.is_ascii_alphanumeric() || b"+-.".contains(&b)) {
            rest = &rest[i + 1..];
        }
    }
    if let Some(after) = rest.strip_prefix("//") {
        rest = after.find('/').map(|i| &after[i..]).unwrap_or("");
    }
    (rest, query)
}

pub(crate) enum ParseError {
    /// Connection closed, timed out or sent an empty request line: no reply.
    Closed,
    Status(u16, &'static str),
}

fn latin1(bytes: &[u8]) -> String {
    bytes.iter().map(|&b| b as char).collect()
}

fn trim_newline(mut line: &[u8]) -> &[u8] {
    while let Some((&last, head)) = line.split_last() {
        if last == b'\n' || last == b'\r' {
            line = head;
        } else {
            break;
        }
    }
    line
}

/// BaseHTTPRequestHandler.parse_request + http.client.parse_headers.
pub(crate) fn read_request<S: Read + Write>(conn: &mut Conn<S>) -> std::result::Result<Request, ParseError> {
    let raw = match conn.read_line(MAX_LINE) {
        Ok(Line::Data(line)) if line.is_empty() => return Err(ParseError::Closed),
        Ok(Line::Data(line)) => line,
        Ok(Line::TooLong) => return Err(ParseError::Status(414, "Request-URI Too Long")),
        Err(_) => return Err(ParseError::Closed),
    };
    let request_line = latin1(trim_newline(&raw));
    let words = py::split_ws(&request_line);
    if words.is_empty() {
        return Err(ParseError::Closed);
    }
    if words.len() >= 3 {
        let version = words[words.len() - 1];
        let numbers: Option<Vec<&str>> = version.strip_prefix("HTTP/").map(|v| v.split('.').collect());
        let valid = matches!(&numbers, Some(parts) if parts.len() == 2 && parts.iter().all(|p| py::is_digits(p) && p.len() <= 10));
        if !valid {
            return Err(ParseError::Status(400, "Bad request version"));
        }
        let major: u64 = numbers.as_ref().and_then(|p| p[0].parse().ok()).unwrap_or(0);
        if major >= 2 {
            return Err(ParseError::Status(505, "Invalid HTTP version"));
        }
    }
    if !(2..=3).contains(&words.len()) {
        return Err(ParseError::Status(400, "Bad request syntax"));
    }
    if words.len() == 2 && words[0] != "GET" {
        return Err(ParseError::Status(400, "Bad HTTP/0.9 request type"));
    }
    let method = words[0].to_string();
    let mut target = words[1].to_string();
    if target.starts_with("//") {
        // gh-87389: a leading "//" must not read as a network-path reference.
        target = format!("/{}", target.trim_start_matches('/'));
    }
    let mut headers = Vec::new();
    loop {
        let line = match conn.read_line(MAX_LINE) {
            Ok(Line::Data(line)) => line,
            Ok(Line::TooLong) => return Err(ParseError::Status(431, "Line too long")),
            Err(_) => return Err(ParseError::Closed),
        };
        if line.is_empty() || line == b"\r\n" || line == b"\n" {
            break;
        }
        if headers.len() >= MAX_HEADERS {
            return Err(ParseError::Status(431, "Too many headers"));
        }
        let line = latin1(trim_newline(&line));
        let Some((name, value)) = line.split_once(':') else {
            return Err(ParseError::Status(400, "Bad header"));
        };
        // Folded or malformed header names (obsolete line folding included) are refused.
        if name.is_empty() || !name.chars().all(|c| ('\x21'..='\x7e').contains(&c)) {
            return Err(ParseError::Status(400, "Bad header"));
        }
        headers.push((name.to_string(), value.trim_start_matches([' ', '\t']).to_string()));
    }
    Ok(Request { method, target, headers })
}

fn reason(code: u16) -> &'static str {
    match code {
        200 => "OK",
        202 => "Accepted",
        308 => "Permanent Redirect",
        400 => "Bad Request",
        401 => "Unauthorized",
        403 => "Forbidden",
        404 => "Not Found",
        405 => "Method Not Allowed",
        409 => "Conflict",
        411 => "Length Required",
        413 => "Request Entity Too Large",
        414 => "Request-URI Too Long",
        415 => "Unsupported Media Type",
        429 => "Too Many Requests",
        431 => "Request Header Fields Too Large",
        500 => "Internal Server Error",
        501 => "Not Implemented",
        503 => "Service Unavailable",
        505 => "HTTP Version Not Supported",
        _ => "",
    }
}

/// Status line, Server header, `headers`, then `body`.
pub(crate) fn write_response<S: Read + Write>(conn: &mut Conn<S>, code: u16, headers: &[(&str, &str)], body: &[u8]) {
    let mut out = format!("HTTP/1.0 {code} {}\r\nServer: Phoenix\r\n", reason(code));
    for (name, value) in headers {
        out.push_str(name);
        out.push_str(": ");
        out.push_str(value);
        out.push_str("\r\n");
    }
    out.push_str("\r\n");
    let mut data = out.into_bytes();
    data.extend_from_slice(body);
    conn.write_all(&data);
}

/// BaseHTTPRequestHandler.send_error: short HTML page, connection closes.
pub(crate) fn send_error<S: Read + Write>(conn: &mut Conn<S>, code: u16, message: &str) {
    let body = format!(
        "<!DOCTYPE HTML>\n<html lang=\"en\">\n<head><meta charset=\"utf-8\"><title>Error response</title></head>\n<body><h1>Error response</h1><p>Error code: {code}</p><p>Message: {message}.</p></body>\n</html>\n"
    );
    let length = body.len().to_string();
    write_response(conn, code, &[("Connection", "close"), ("Content-Type", "text/html;charset=utf-8"), ("Content-Length", &length)], body.as_bytes());
}

/// http.cookies.SimpleCookie lookup of one cookie; "" when absent or invalid.
fn cookie_value(header: &str, wanted: &str) -> String {
    const RESERVED: [&str; 9] = ["expires", "path", "comment", "domain", "max-age", "secure", "httponly", "version", "samesite"];
    let mut found = String::new();
    let mut morsel_seen = false;
    for item in header.split(';') {
        let item = item.trim();
        if item.is_empty() {
            continue;
        }
        let (key, value) = match item.split_once('=') {
            Some((k, v)) => (k.trim(), Some(v.trim())),
            None => (item, None),
        };
        if key.is_empty() || key.starts_with('$') {
            continue;
        }
        if RESERVED.contains(&key.to_ascii_lowercase().as_str()) {
            if !morsel_seen {
                return String::new();
            }
            continue;
        }
        let Some(value) = value else {
            return String::new();
        };
        morsel_seen = true;
        if key == wanted {
            let unquoted = value.strip_prefix('"').and_then(|v| v.strip_suffix('"')).unwrap_or(value);
            found = unquoted.to_string();
        }
    }
    found
}

/// urllib.parse.unquote_plus (UTF-8, invalid sequences replaced).
fn unquote_plus(text: &str) -> String {
    let bytes = text.as_bytes();
    let mut out = Vec::with_capacity(bytes.len());
    let mut i = 0;
    while i < bytes.len() {
        match bytes[i] {
            b'+' => out.push(b' '),
            b'%' if i + 2 < bytes.len() && bytes[i + 1].is_ascii_hexdigit() && bytes[i + 2].is_ascii_hexdigit() => {
                let pair = [bytes[i + 1], bytes[i + 2]];
                let digits = std::str::from_utf8(&pair).unwrap_or("00");
                out.push(u8::from_str_radix(digits, 16).unwrap_or(0));
                i += 2;
            }
            b => out.push(b),
        }
        i += 1;
    }
    String::from_utf8_lossy(&out).into_owned()
}

/// First non-blank value of `name` in a query string (urllib.parse.parse_qs).
fn query_value(query: &str, name: &str) -> Option<String> {
    for pair in query.split('&') {
        let Some((key, value)) = pair.split_once('=') else {
            continue;
        };
        if value.is_empty() {
            continue;
        }
        if unquote_plus(key) == name {
            return Some(unquote_plus(value));
        }
    }
    None
}

/// Python int(text) for base-10 strings.
fn python_int(text: &str) -> Option<i64> {
    let text = py::strip(text);
    let (negative, digits) = match text.as_bytes().first() {
        Some(b'-') => (true, &text[1..]),
        Some(b'+') => (false, &text[1..]),
        _ => (false, text),
    };
    let bytes = digits.as_bytes();
    if bytes.is_empty() || !bytes.iter().all(|b| b.is_ascii_digit() || *b == b'_') || bytes[0] == b'_' || bytes[bytes.len() - 1] == b'_' || digits.contains("__") {
        return None;
    }
    let value: i64 = digits.replace('_', "").parse().ok()?;
    Some(if negative { -value } else { value })
}

fn content_length(request: &Request) -> Option<u64> {
    let lengths = request.all("Content-Length");
    if lengths.len() != 1 || !py::is_digits(lengths[0]) {
        return None;
    }
    // Overflow means "too large", never "absent".
    Some(lengths[0].parse::<u64>().unwrap_or(u64::MAX))
}

struct Exchange<'c, 'a, S> {
    conn: &'c mut Conn<'a, S>,
    request: Request,
    settings: &'c Settings,
    api: &'c dyn Api,
}

impl<'c, 'a, S: Stream> Exchange<'c, 'a, S> {
    fn reply_bytes(&mut self, code: u16, data: &[u8], content_type: &str, extra: &[(&str, String)]) {
        let length = data.len().to_string();
        let mut headers: Vec<(&str, &str)> = vec![
            ("Content-Type", content_type),
            ("Content-Length", &length),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("Referrer-Policy", "no-referrer"),
            ("Content-Security-Policy", CSP),
        ];
        headers.extend(extra.iter().map(|(n, v)| (*n, v.as_str())));
        headers.push(("Connection", "close"));
        write_response(self.conn, code, &headers, data);
    }

    fn reply(&mut self, code: u16, value: &Value) {
        self.reply_with(code, value, &[]);
    }

    fn reply_with(&mut self, code: u16, value: &Value, extra: &[(&str, String)]) {
        self.reply_bytes(code, json::dumps(value).as_bytes(), "application/json", extra);
    }

    fn error(&mut self, code: u16, error: &str) {
        self.reply(code, &json!({ "error": error }));
    }

    fn valid_origin(&mut self, require_origin: bool) -> bool {
        if ["Host", "Origin", "Authorization"].iter().any(|name| self.request.all(name).len() > 1) {
            self.error(400, "duplicate_security_header");
            return false;
        }
        if self.request.get("Host") != Some(self.settings.authority.as_str()) {
            self.error(403, "host_not_allowed");
            return false;
        }
        let origin = self.request.get("Origin").unwrap_or("");
        let expected = format!("{}://{}", if self.settings.tls { "https" } else { "http" }, self.settings.authority);
        if (require_origin && origin.is_empty()) || (!origin.is_empty() && origin != expected) {
            self.error(403, "origin_not_allowed");
            return false;
        }
        true
    }

    fn session(&self) -> String {
        let cookies = self.request.all("Cookie");
        if cookies.len() > 1 {
            return String::new();
        }
        cookie_value(cookies.first().copied().unwrap_or(""), COOKIE)
    }

    fn authorized(&mut self) -> bool {
        if !self.valid_origin(false) {
            return false;
        }
        let auth = self.request.get("Authorization").unwrap_or("").to_string();
        if self.settings.password_auth && (auth.is_empty() || !self.settings.allow_bearer) {
            if !self.valid_origin(self.request.method == "POST") {
                return false;
            }
            let mut args = Map::new();
            args.insert("session".into(), Value::String(self.session()));
            if let Ok(value) = self.api.call("auth_check", args) {
                if truthy(value.get("ok")) {
                    return true;
                }
            }
            self.error(401, "authentication_required");
            return false;
        }
        if !equal(auth.as_bytes(), format!("Bearer {}", self.settings.token).as_bytes()) {
            self.error(401, "authentication_required");
            return false;
        }
        true
    }

    /// auth_http.route: true when the request was an auth endpoint (answered).
    fn auth_route(&mut self) -> bool {
        let path = self.request.path().to_string();
        if !path.starts_with("/api/v1/auth/") || !self.settings.password_auth {
            return false;
        }
        let post = self.request.method == "POST";
        if !self.valid_origin(post) {
            return true;
        }
        let action = path.rsplit('/').next().unwrap_or("").to_string();
        if !matches!((self.request.method.as_str(), action.as_str()), ("GET", "status") | ("POST", "login") | ("POST", "logout") | ("POST", "password")) {
            self.error(405, "method_not_allowed");
            return true;
        }
        if self.auth_exchange(&action, post).is_err() {
            self.error(503, "authentication_unavailable");
        }
        true
    }

    fn auth_exchange(&mut self, action: &str, post: bool) -> Result<()> {
        let mut args = Map::new();
        if post {
            let length = content_length(&self.request);
            let acceptable = matches!(length, Some(n) if 0 < n && n <= MAX_AUTH_BODY as u64);
            if self.request.transfer_encoding() || !acceptable || self.request.content_type() != "application/json" {
                self.error(400, "invalid_request");
                return Ok(());
            }
            let body = self.conn.read_body(length.unwrap_or(0) as usize)?;
            args = match json::loads(&body)? {
                Value::Object(map) => map,
                _ => return invalid("object_required"),
            };
        }
        args.insert("session".into(), Value::String(self.session()));
        let mut value = match self.api.call(&format!("auth_{action}"), args)? {
            Value::Object(map) => map,
            _ => return invalid("invalid_auth_reply"),
        };
        let new_session = value.shift_remove("session").filter(|v| !v.is_null());
        let mut headers = Vec::new();
        if new_session.is_some() || action == "logout" {
            let token = match &new_session {
                Some(Value::String(s)) => s.clone(),
                Some(other) if !truthy(Some(other)) => String::new(),
                None => String::new(),
                Some(_) => return invalid("invalid_auth_reply"),
            };
            let max_age = if action == "logout" {
                "0"
            } else if truthy(value.get("must_change")) {
                "600"
            } else {
                "3600"
            };
            headers.push(("Set-Cookie", format!("{COOKIE}={token}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age={max_age}")));
        }
        let mut code = 200;
        if value.get("ok") == Some(&Value::Bool(false)) {
            code = if value.get("error").and_then(Value::as_str) == Some("login_locked") { 429 } else { 401 };
            if code == 429 {
                let retry = match value.get("retry_after") {
                    Some(Value::Number(n)) => n.to_string(),
                    Some(Value::String(s)) => s.clone(),
                    _ => return invalid("invalid_auth_reply"),
                };
                headers.push(("Retry-After", retry));
            }
        }
        self.reply_with(code, &Value::Object(value), &headers);
        Ok(())
    }

    fn get(&mut self) {
        if self.auth_route() {
            return;
        }
        let path = self.request.path().to_string();
        if path == "/healthz" {
            match self.api.call("health", Map::new()) {
                Ok(Value::Object(mut health)) => {
                    let ready = truthy(health.get("ready")) && health.get("release_id").and_then(Value::as_str) == Some(self.settings.release_id.as_str());
                    health.insert("ready".into(), Value::Bool(ready));
                    self.reply(200, &Value::Object(health));
                }
                _ => self.reply(503, &json!({"ready": false})),
            }
            return;
        }
        if let Some((body, mime)) = web::asset(&path) {
            self.reply_bytes(200, body, mime, &[]);
            return;
        }
        if !self.authorized() {
            return;
        }
        let method = match path.as_str() {
            "/api/v1/hotspot" => Some("hotspot"),
            "/api/v1/speedtest" => Some("speedtest"),
            "/api/v1/capabilities" => Some("capabilities"),
            "/api/v1/wifi/scan" => Some("scan"),
            "/api/v1/firmware" => Some("firmware"),
            "/api/v1/preflight" => Some("preflight"),
            "/api/v1/status" => Some("status"),
            "/api/v1/policy" => Some("policy"),
            "/api/v1/vpn" => Some("vpn"),
            _ => None,
        };
        let result = match method {
            Some(method) => self.api.call(method, Map::new()),
            None if path == "/api/v1/vpn/history" => {
                let before = query_value(self.request.query(), "before").unwrap_or_else(|| "0".into());
                match python_int(&before) {
                    Some(before) => {
                        let mut args = Map::new();
                        args.insert("before".into(), json!(before));
                        self.api.call("history", args)
                    }
                    None => invalid("invalid_cursor"),
                }
            }
            None => {
                self.error(404, "not_found");
                return;
            }
        };
        match result {
            Ok(value) => self.reply(200, &value),
            Err(Error::Unavailable(_)) => self.error(503, "target_network_not_initialized"),
            Err(Error::Invalid(_)) => self.error(400, "invalid_request"),
            Err(_) => self.error(500, "operation_failed"),
        }
    }

    fn post_result(&mut self) -> Result<(u16, Value)> {
        let path = self.request.path().to_string();
        let content_type = self.request.content_type();
        if path == "/api/v1/firmware" && content_type == "application/octet-stream" {
            let Some(size) = content_length(&self.request).filter(|_| !self.request.transfer_encoding()) else {
                return Ok((411, json!({"error": "content_length_required"})));
            };
            if size == 0 || size > MAX_UPLOAD as u64 {
                return Ok((413, json!({"error": "update_too_large"})));
            }
            // Authorized above: only an authenticated client gets the longer budget.
            self.conn.stream.extend_deadline(UPLOAD_DEADLINE);
            let data = self.conn.read_body(size as usize)?;
            if data.len() as u64 != size {
                return invalid("incomplete_update");
            }
            let mut args = Map::new();
            args.insert("data".into(), Value::String(base64::engine::general_purpose::STANDARD.encode(&data)));
            drop(data);
            return Ok((202, self.api.call("upload", args)?));
        }
        if self.request.transfer_encoding() || content_type != "application/json" {
            return Ok((415, json!({"error": "json_required"})));
        }
        let Some(length) = content_length(&self.request) else {
            return Ok((411, json!({"error": "content_length_required"})));
        };
        if length == 0 || length > MAX_JSON as u64 {
            return Ok((413, json!({"error": "body_too_large"})));
        }
        let data = self.conn.read_body(length as usize)?;
        let Value::Object(mut body) = json::loads(&data)? else {
            return invalid("object_required");
        };
        match path.as_str() {
            "/api/v1/speedtest" => {
                let action = match body.get("action").and_then(Value::as_str) {
                    Some(a @ ("start" | "cancel")) if body.len() == 1 => a.to_string(),
                    _ => return invalid("invalid_speedtest_action"),
                };
                Ok((202, self.api.call(&format!("speedtest_{action}"), Map::new())?))
            }
            "/api/v1/hotspot" => Ok((200, self.api.call("save_hotspot", body)?)),
            "/api/v1/policy" => Ok((200, self.api.call("save_policy", body)?)),
            "/api/v1/wifi" | "/api/v1/uplink" => {
                let action = path.rsplit('/').next().unwrap_or("").to_string();
                body.insert("action".into(), Value::String(action));
                Ok((202, self.api.call("command", body)?))
            }
            "/api/v1/vpn" => Ok((202, self.api.call("command", body)?)),
            _ => Ok((501, json!({"error": "endpoint_not_implemented"}))),
        }
    }

    fn post(&mut self) {
        if self.auth_route() || !self.authorized() {
            return;
        }
        match self.post_result() {
            Ok((code, value)) => self.reply(code, &value),
            Err(Error::Conflict(_)) => self.error(409, "revision_conflict_reload"),
            Err(Error::Unavailable(_)) => self.error(503, "capability_unavailable"),
            Err(Error::Invalid(_)) => self.error(400, "invalid_configuration"),
            Err(_) => self.error(500, "operation_failed"),
        }
    }
}

/// Serve exactly one request on `stream` (connection closes afterwards).
pub fn handle<S: Stream>(stream: &mut S, settings: &Settings, api: &dyn Api) {
    let mut conn = Conn::new(stream);
    let request = match read_request(&mut conn) {
        Ok(request) => request,
        Err(ParseError::Closed) => return,
        Err(ParseError::Status(code, message)) => {
            send_error(&mut conn, code, message);
            return;
        }
    };
    let method = request.method.clone();
    let mut exchange = Exchange { conn: &mut conn, request, settings, api };
    match method.as_str() {
        "GET" => exchange.get(),
        "POST" => exchange.post(),
        _ => send_error(exchange.conn, 501, "Unsupported method"),
    }
}

/// Directory name of the release containing the running executable
/// (Python: Path(__file__).resolve().parents[4].name).
pub fn release_id() -> String {
    std::env::current_exe()
        .ok()
        .and_then(|exe| exe.parent()?.parent()?.file_name().map(|name| name.to_string_lossy().into_owned()))
        .unwrap_or_default()
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use crate::auth::AdminAuth;
    use crate::fsutil::testdir::TempDir;
    use std::io::Cursor;
    use std::sync::Mutex;

    /// In-memory connection: reads `input`, collects everything written.
    pub(crate) struct Mock {
        input: Cursor<Vec<u8>>,
        pub output: Vec<u8>,
    }

    impl Mock {
        pub(crate) fn new(input: &[u8]) -> Self {
            Mock { input: Cursor::new(input.to_vec()), output: Vec::new() }
        }
    }

    impl Read for Mock {
        fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
            self.input.read(buf)
        }
    }

    impl Stream for Mock {}

    impl Write for Mock {
        fn write(&mut self, buf: &[u8]) -> io::Result<usize> {
            self.output.extend_from_slice(buf);
            Ok(buf.len())
        }
        fn flush(&mut self) -> io::Result<()> {
            Ok(())
        }
    }

    pub(crate) struct Response {
        pub status: u16,
        pub headers: Vec<(String, String)>,
        pub body: Vec<u8>,
    }

    impl Response {
        pub(crate) fn parse(raw: &[u8]) -> Response {
            let split = raw.windows(4).position(|w| w == b"\r\n\r\n").expect("header end");
            let head = String::from_utf8_lossy(&raw[..split]).into_owned();
            let mut lines = head.split("\r\n");
            let status = lines.next().unwrap().split(' ').nth(1).unwrap().parse().unwrap();
            let headers = lines.map(|l| l.split_once(": ").unwrap()).map(|(a, b)| (a.to_string(), b.to_string())).collect();
            Response { status, headers, body: raw[split + 4..].to_vec() }
        }
        pub(crate) fn header(&self, name: &str) -> Option<&str> {
            self.headers.iter().find(|(n, _)| n.eq_ignore_ascii_case(name)).map(|(_, v)| v.as_str())
        }
        fn json(&self) -> Value {
            json::parse(&self.body).unwrap()
        }
    }

    type Handler = dyn Fn(&str, Map<String, Value>) -> Result<Value> + Send + Sync;

    struct FakeApi {
        calls: Mutex<Vec<(String, Map<String, Value>)>>,
        handler: Box<Handler>,
    }

    impl FakeApi {
        fn new(handler: impl Fn(&str, Map<String, Value>) -> Result<Value> + Send + Sync + 'static) -> Self {
            FakeApi { calls: Mutex::new(Vec::new()), handler: Box::new(handler) }
        }
        fn methods(&self) -> Vec<String> {
            self.calls.lock().unwrap().iter().map(|(m, _)| m.clone()).collect()
        }
    }

    impl Api for FakeApi {
        fn call(&self, method: &str, args: Map<String, Value>) -> Result<Value> {
            self.calls.lock().unwrap().push((method.to_string(), args.clone()));
            (self.handler)(method, args)
        }
    }

    fn bearer_settings() -> Settings {
        Settings { authority: "127.0.0.1:8085".into(), tls: false, password_auth: false, allow_bearer: true, token: "a".repeat(64), release_id: "factory".into() }
    }

    /// A peer sending one byte every 300 ms never trips the 5 s per-read
    /// timeout; the absolute deadline must still end the connection.
    #[test]
    fn trickling_client_is_cut_off_at_the_deadline() {
        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let address = listener.local_addr().unwrap();
        let client = std::thread::spawn(move || {
            let mut stream = TcpStream::connect(address).unwrap();
            for byte in b"GET /healthz HTTP/1.1\r\nHost: 127.0.0.1:8085\r\n".iter().cycle().take(40) {
                if stream.write_all(&[*byte]).is_err() {
                    return;
                }
                std::thread::sleep(Duration::from_millis(300));
            }
        });
        let (stream, _) = listener.accept().unwrap();
        let api = FakeApi::new(|_, _| Ok(json!({"ready": true, "release_id": "factory"})));
        let started = Instant::now();
        handle(&mut Deadlined::new(stream, Duration::from_secs(1)), &bearer_settings(), &api);
        assert!(started.elapsed() < Duration::from_secs(3), "held for {:?}", started.elapsed());
        assert!(api.methods().is_empty());
        drop(client);
    }

    fn usb_settings() -> Settings {
        Settings { authority: "192.168.7.1".into(), tls: true, password_auth: true, allow_bearer: false, token: "a".repeat(64), release_id: "factory".into() }
    }

    fn exchange(settings: &Settings, api: &dyn Api, raw: &str) -> Response {
        let mut mock = Mock::new(raw.as_bytes());
        handle(&mut mock, settings, api);
        Response::parse(&mock.output)
    }

    fn get(settings: &Settings, api: &dyn Api, path: &str, headers: &[(&str, &str)]) -> Response {
        let mut raw = format!("GET {path} HTTP/1.1\r\n");
        for (n, v) in headers {
            raw += &format!("{n}: {v}\r\n");
        }
        exchange(settings, api, &(raw + "\r\n"))
    }

    fn post(settings: &Settings, api: &dyn Api, path: &str, headers: &[(&str, &str)], body: &str) -> Response {
        let mut raw = format!("POST {path} HTTP/1.1\r\nContent-Length: {}\r\n", body.len());
        for (n, v) in headers {
            raw += &format!("{n}: {v}\r\n");
        }
        exchange(settings, api, &(raw + "\r\n" + body))
    }

    fn policy_api() -> FakeApi {
        FakeApi::new(|method, _| match method {
            "policy" => Ok(json!({"revision": 0})),
            "status" => Err(Error::Unavailable("target_network_not_initialized".into())),
            "save_policy" => invalid("invalid_policy"),
            "history" => Ok(json!({"entries": []})),
            "health" => Ok(json!({"ready": true, "release_id": "factory"})),
            _ => invalid("unknown_rpc_method"),
        })
    }

    const HOST: (&str, &str) = ("Host", "127.0.0.1:8085");

    #[test]
    fn bearer_auth_and_unavailable_status() {
        let (s, api) = (bearer_settings(), policy_api());
        let token = format!("Bearer {}", "a".repeat(64));
        assert_eq!(get(&s, &api, "/api/v1/policy", &[HOST]).status, 401);
        assert_eq!(get(&s, &api, "/api/v1/policy", &[HOST, ("Authorization", &format!("Bearer {}", "b".repeat(64)))]).status, 401);
        let ok = get(&s, &api, "/api/v1/policy", &[HOST, ("Authorization", &token)]);
        assert_eq!((ok.status, ok.json()), (200, json!({"revision": 0})));
        assert_eq!(ok.header("Content-Security-Policy"), Some(CSP));
        assert_eq!(ok.header("Cache-Control"), Some("no-store"));
        let unavailable = get(&s, &api, "/api/v1/status", &[HOST, ("Authorization", &token)]);
        assert_eq!((unavailable.status, unavailable.json()), (503, json!({"error": "target_network_not_initialized"})));
        assert_eq!(get(&s, &api, "/api/v1/policy", &[HOST, ("Authorization", &token), ("Origin", "https://untrusted.example")]).status, 403);
        assert_eq!(get(&s, &api, "/api/v1/policy", &[("Host", "evil.test"), ("Authorization", &token)]).status, 403);
        assert_eq!(get(&s, &api, "/api/v1/missing", &[HOST, ("Authorization", &token)]).status, 404);
        assert_eq!(get(&s, &api, "/api/v1/vpn/history?before=12", &[HOST, ("Authorization", &token)]).status, 200);
        assert_eq!(api.calls.lock().unwrap().last().unwrap().1["before"], 12);
        assert_eq!(get(&s, &api, "/api/v1/vpn/history?before=x", &[HOST, ("Authorization", &token)]).status, 400);
    }

    #[test]
    fn shared_assets_traversal_and_health() {
        let (s, api) = (bearer_settings(), policy_api());
        let index = get(&s, &api, "/", &[HOST]);
        assert_eq!(index.status, 200);
        assert!(String::from_utf8_lossy(&index.body).to_lowercase().contains("phoenix"));
        assert_eq!(index.header("Referrer-Policy"), Some("no-referrer"));
        assert!(index.header("Content-Security-Policy").unwrap().contains("script-src 'self'"));
        assert_eq!(get(&s, &api, "/../../AGENTS.md", &[HOST]).status, 401);
        let health = get(&s, &api, "/healthz", &[]);
        assert_eq!((health.status, health.json()["ready"].clone()), (200, json!(true)));
        let other = Settings { release_id: "other".into(), ..bearer_settings() };
        assert_eq!(get(&other, &api, "/healthz", &[]).json()["ready"], false);
        let down = FakeApi::new(|_, _| Err(Error::Io("io_connectionrefused".into())));
        let failed = get(&s, &down, "/healthz", &[]);
        assert_eq!((failed.status, failed.json()), (503, json!({"ready": false})));
    }

    #[test]
    fn invalid_json_and_unsupported_operation() {
        let (s, api) = (bearer_settings(), policy_api());
        let token = format!("Bearer {}", "a".repeat(64));
        let json_headers = [HOST, ("Authorization", token.as_str()), ("Content-Type", "application/json")];
        assert_eq!(post(&s, &api, "/api/v1/policy", &json_headers, r#"{"revision":0,"revision":1}"#).status, 400);
        assert_eq!(post(&s, &api, "/api/v1/firmware", &json_headers, "{}").status, 501);
        assert_eq!(post(&s, &api, "/api/v1/policy", &[HOST, ("Authorization", &token), ("Content-Type", "text/plain")], "{}").status, 415);
        assert_eq!(post(&s, &api, "/api/v1/policy", &json_headers, "[]").status, 400);
        assert_eq!(post(&s, &api, "/api/v1/policy", &json_headers, &format!("{{\"x\":\"{}\"}}", "a".repeat(16384))).status, 413);
        let chunked = exchange(&s, &api, &format!("POST /api/v1/policy HTTP/1.1\r\nHost: 127.0.0.1:8085\r\nAuthorization: {token}\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n{{}}\r\n0\r\n\r\n"));
        assert_eq!(chunked.status, 415);
        let no_length = exchange(&s, &api, &format!("POST /api/v1/policy HTTP/1.1\r\nHost: 127.0.0.1:8085\r\nAuthorization: {token}\r\nContent-Type: Application/JSON; charset=utf-8\r\n\r\n{{}}"));
        assert_eq!(no_length.status, 411);
        let speed = post(&s, &api, "/api/v1/speedtest", &json_headers, r#"{"action":"start","x":1}"#);
        assert_eq!(speed.status, 400);
        assert!(!api.methods().iter().any(|m| m.starts_with("speedtest")));
    }

    #[test]
    fn command_routes_and_error_mapping() {
        let s = bearer_settings();
        let api = FakeApi::new(|method, args| match method {
            "command" if args.get("action") == Some(&json!("uplink")) => Ok(json!({"accepted": true})),
            "command" => Err(Error::Conflict("command_in_progress".into())),
            "save_hotspot" => Err(Error::Unavailable("hotspot_unavailable".into())),
            "save_policy" => Err(Error::Network("command_failed:nft".into())),
            "speedtest_cancel" => Ok(json!({"accepted": true})),
            _ => invalid("unknown"),
        });
        let token = format!("Bearer {}", "a".repeat(64));
        let h = [HOST, ("Authorization", token.as_str()), ("Content-Type", "application/json")];
        assert_eq!(post(&s, &api, "/api/v1/uplink", &h, r#"{"uplink":"wifi","action":"x"}"#).status, 202);
        assert_eq!(api.calls.lock().unwrap().last().unwrap().1["action"], "uplink");
        assert_eq!(post(&s, &api, "/api/v1/vpn", &h, r#"{"action":"connect"}"#).status, 409);
        assert_eq!(post(&s, &api, "/api/v1/hotspot", &h, "{}").status, 503);
        assert_eq!(post(&s, &api, "/api/v1/policy", &h, "{}").status, 500);
        assert_eq!(post(&s, &api, "/api/v1/speedtest", &h, r#"{"action":"cancel"}"#).status, 202);
    }

    #[test]
    fn firmware_upload_is_forwarded_base64() {
        let s = bearer_settings();
        let api = FakeApi::new(|_, args| Ok(json!({"phase": "staged", "size": args["data"].as_str().unwrap().len()})));
        let token = format!("Bearer {}", "a".repeat(64));
        let h = [HOST, ("Authorization", token.as_str()), ("Content-Type", "application/octet-stream")];
        let ok = post(&s, &api, "/api/v1/firmware", &h, "abc");
        assert_eq!((ok.status, ok.json()["size"].clone()), (202, json!(4)));
        assert_eq!(api.calls.lock().unwrap()[0].1["data"], "YWJj");
        let partial = exchange(&s, &api, &format!("POST /api/v1/firmware HTTP/1.1\r\nHost: 127.0.0.1:8085\r\nAuthorization: {token}\r\nContent-Type: application/octet-stream\r\nContent-Length: 10\r\n\r\nabc"));
        assert_eq!(partial.status, 400);
        let big = exchange(&s, &api, &format!("POST /api/v1/firmware HTTP/1.1\r\nHost: 127.0.0.1:8085\r\nAuthorization: {token}\r\nContent-Type: application/octet-stream\r\nContent-Length: {}\r\n\r\n", MAX_UPLOAD + 1));
        assert_eq!(big.status, 413);
        let none = exchange(&s, &api, &format!("POST /api/v1/firmware HTTP/1.1\r\nHost: 127.0.0.1:8085\r\nAuthorization: {token}\r\nContent-Type: application/octet-stream\r\n\r\n"));
        assert_eq!(none.status, 411);
    }

    #[test]
    fn duplicate_security_headers_and_malformed_requests() {
        let (s, api) = (bearer_settings(), policy_api());
        let dup = get(&s, &api, "/api/v1/policy", &[HOST, ("Authorization", &format!("Bearer {}", "a".repeat(64))), ("Authorization", &format!("Bearer {}", "b".repeat(64)))]);
        assert_eq!((dup.status, dup.json()), (400, json!({"error": "duplicate_security_header"})));
        assert_eq!(get(&s, &api, "/api/v1/policy", &[HOST, HOST]).status, 400);
        assert_eq!(exchange(&s, &api, "GET / HTTP/2.0\r\n\r\n").status, 505);
        assert_eq!(exchange(&s, &api, "GET / HTTX/1.0\r\n\r\n").status, 400);
        assert_eq!(exchange(&s, &api, "GET / x HTTP/1.0\r\n\r\n").status, 400);
        assert_eq!(exchange(&s, &api, "POST /\r\n\r\n").status, 400);
        assert_eq!(exchange(&s, &api, "HEAD / HTTP/1.0\r\n\r\n").status, 501);
        assert_eq!(exchange(&s, &api, "GET / HTTP/1.0\r\n folded\r\n\r\n").status, 400);
        assert_eq!(exchange(&s, &api, "GET / HTTP/1.0\r\nBad Header: x\r\n\r\n").status, 400);
        assert_eq!(exchange(&s, &api, &format!("GET /{} HTTP/1.0\r\n\r\n", "a".repeat(MAX_LINE))).status, 414);
        assert_eq!(exchange(&s, &api, &format!("GET / HTTP/1.0\r\nX: {}\r\n\r\n", "a".repeat(MAX_LINE))).status, 431);
        let many: String = (0..101).map(|i| format!("X{i}: y\r\n")).collect();
        assert_eq!(exchange(&s, &api, &format!("GET / HTTP/1.0\r\n{many}\r\n")).status, 431);
        let mut mock = Mock::new(b"");
        handle(&mut mock, &s, &api);
        assert!(mock.output.is_empty());
        let mut mock = Mock::new(b"GET / HTTP/1.0\r\nHost: x");
        handle(&mut mock, &s, &api);
        assert_eq!(Response::parse(&mock.output).status, 200, "headers ended by EOF still serve assets");
        // gh-87389: "//api/..." is a path, not a network reference.
        let token = format!("Bearer {}", "a".repeat(64));
        assert_eq!(get(&s, &api, "//api/v1/policy", &[HOST, ("Authorization", &token)]).status, 200);
    }

    #[test]
    fn url_helpers() {
        assert_eq!(split_target("/a/b?c=1#x"), ("/a/b", "c=1"));
        assert_eq!(split_target("http://h/x?y"), ("/x", "y"));
        assert_eq!(split_target("/x#a?b"), ("/x", ""));
        assert_eq!(query_value("a=1&before=&before=+7&before=9", "before").as_deref(), Some(" 7"));
        assert_eq!(query_value("bef%6Fre=3", "before").as_deref(), Some("3"));
        assert_eq!(query_value("before", "before"), None);
        assert_eq!(python_int(" 7"), Some(7));
        assert_eq!(python_int("-1_0"), Some(-10));
        assert_eq!(python_int("1__0"), None);
        assert_eq!(python_int(""), None);
        assert_eq!(unquote_plus("a%2"), "a%2");
        assert_eq!(unquote_plus("%zz%41"), "%zzA");
        assert_eq!(cookie_value("a=b; __Host-phoenix=tok", COOKIE), "tok");
        assert_eq!(cookie_value("__Host-phoenix=\"tok\"", COOKIE), "tok");
        assert_eq!(cookie_value("Path=/; __Host-phoenix=tok", COOKIE), "");
        assert_eq!(cookie_value("flag; __Host-phoenix=tok", COOKIE), "");
        assert_eq!(cookie_value("__Host-phoenix=a; __Host-phoenix=b", COOKIE), "b");
    }

    /// LocalAPI-style dispatch over a real AdminAuth for the password flow.
    struct AuthApi {
        auth: AdminAuth,
    }

    impl Api for AuthApi {
        fn call(&self, method: &str, args: Map<String, Value>) -> Result<Value> {
            match method.strip_prefix("auth_") {
                Some(action) => self.auth.call(action, &args),
                None if method == "policy" => Ok(json!({"revision": 0})),
                None => invalid("unknown_rpc_method"),
            }
        }
    }

    fn auth_api(dir: &TempDir) -> AuthApi {
        AuthApi { auth: AdminAuth::new(dir.path(), crate::py::wall_clock()).unwrap() }
    }

    fn usb_request(api: &dyn Api, path: &str, body: Option<&str>, cookie: &str, origin: &str, extra: &[(&str, &str)]) -> Response {
        let mut headers = vec![("Host", "192.168.7.1"), ("Origin", origin), ("Content-Type", "application/json"), ("Cookie", cookie)];
        headers.extend_from_slice(extra);
        let path = format!("/api/v1/{path}");
        match body {
            None => get(&usb_settings(), api, &path, &headers),
            Some(body) => post(&usb_settings(), api, &path, &headers, body),
        }
    }

    fn cookie_of(response: &Response) -> String {
        response.header("Set-Cookie").unwrap().split(';').next().unwrap().to_string()
    }

    #[test]
    fn password_flow_and_csrf_logout() {
        let dir = TempDir::new();
        let api = auth_api(&dir);
        let origin = "https://192.168.7.1";
        assert_eq!(usb_request(&api, "auth/status", None, "", origin, &[]).json()["password_login"], true);
        let login = usb_request(&api, "auth/login", Some(r#"{"password":"phoenix"}"#), "", origin, &[]);
        assert_eq!(login.status, 200);
        assert!(login.json().get("session").is_none());
        let set_cookie = login.header("Set-Cookie").unwrap();
        assert!(set_cookie.contains("; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=600"), "{set_cookie}");
        let cookie = cookie_of(&login);
        assert_eq!(usb_request(&api, "policy", None, &cookie, origin, &[]).status, 401);
        let change = r#"{"current_password":"phoenix","new_password":"test password phrase"}"#;
        assert_eq!(usb_request(&api, "auth/password", Some(change), &cookie, "https://evil.test", &[]).status, 403);
        let changed = usb_request(&api, "auth/password", Some(change), &cookie, origin, &[]);
        assert_eq!(changed.status, 200);
        assert!(changed.header("Set-Cookie").unwrap().ends_with("Max-Age=3600"));
        let cookie = cookie_of(&changed);
        assert_eq!(usb_request(&api, "policy", None, &cookie, origin, &[]).status, 200);
        let logout = usb_request(&api, "auth/logout", Some("{}"), &cookie, origin, &[]);
        assert_eq!(logout.header("Set-Cookie"), Some("__Host-phoenix=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0"));
        assert_eq!(usb_request(&api, "policy", None, &cookie, origin, &[]).status, 401);
        assert_eq!(usb_request(&api, "auth/login", None, "", origin, &[]).status, 405);
        assert_eq!(usb_request(&api, "auth/login", Some("[]"), "", origin, &[]).status, 503);
        let bad_type = exchange(&usb_settings(), &api, "POST /api/v1/auth/login HTTP/1.1\r\nHost: 192.168.7.1\r\nOrigin: https://192.168.7.1\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\n{}");
        assert_eq!(bad_type.status, 400);
    }

    #[test]
    fn lockout_and_usb_token_bypass_rejected() {
        let dir = TempDir::new();
        let api = auth_api(&dir);
        let origin = "https://192.168.7.1";
        let mut last = None;
        for _ in 0..3 {
            last = Some(usb_request(&api, "auth/login", Some(r#"{"password":"wrong"}"#), "", origin, &[]));
        }
        let last = last.unwrap();
        assert_eq!((last.status, last.header("Retry-After")), (429, Some("300")));
        assert_eq!(usb_request(&api, "auth/login", Some(r#"{"password":"phoenix"}"#), "", origin, &[]).status, 429);
        let bearer = format!("Bearer {}", "a".repeat(64));
        assert_eq!(usb_request(&api, "policy", None, "", origin, &[("Authorization", &bearer)]).status, 401);
        assert_eq!(usb_request(&api, "auth/login", Some(r#"{"password":"phoenix"}"#), "", "", &[]).status, 403);
    }

    #[test]
    fn direct_api_requires_token_and_exact_origin() {
        // USB frontend without password mode: bearer and exact https origin.
        let s = Settings { password_auth: false, ..usb_settings() };
        let api = FakeApi::new(|_, _| Ok(json!({"test": true})));
        let bearer = format!("Bearer {}", "a".repeat(64));
        assert_eq!(get(&s, &api, "/api/v1/status", &[("Host", "192.168.7.1")]).status, 401);
        assert_eq!(get(&s, &api, "/api/v1/status", &[("Host", "192.168.7.1"), ("Authorization", &bearer), ("Origin", "http://192.168.7.1")]).status, 403);
        assert_eq!(get(&s, &api, "/api/v1/status", &[("Host", "192.168.7.1"), ("Authorization", &bearer), ("Origin", "https://192.168.7.1")]).status, 200);
        assert_eq!(get(&s, &api, "/api/v1/status", &[("Host", "evil.test"), ("Authorization", &bearer), ("Origin", "https://192.168.7.1")]).status, 403);
        // Loopback HTTPS frontend: password mode with bearer still accepted.
        let loopback = Settings { authority: "127.0.0.1:8443".into(), tls: true, password_auth: true, allow_bearer: true, token: "a".repeat(64), release_id: String::new() };
        let deny = FakeApi::new(|method, _| if method == "auth_check" { Ok(json!({"ok": false})) } else { Ok(json!({})) });
        assert_eq!(get(&loopback, &deny, "/api/v1/status", &[("Host", "127.0.0.1:8443"), ("Authorization", &bearer)]).status, 200);
        assert_eq!(get(&loopback, &deny, "/api/v1/status", &[("Host", "127.0.0.1:8443")]).status, 401);
    }
}
