//! Small helpers reproducing Python string/number semantics that the original
//! service relied on, plus process-wide randomness and clocks.
use ring::rand::{SecureRandom, SystemRandom};
use std::sync::OnceLock;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

/// Python `str.isspace()` for a single character.
pub fn is_space(c: char) -> bool {
    c.is_whitespace() || matches!(c, '\x1c'..='\x1f')
}

/// Python `str.strip()` without arguments.
pub fn strip(s: &str) -> &str {
    s.trim_matches(is_space)
}

/// Python `str.split()` without arguments.
pub fn split_ws(s: &str) -> Vec<&str> {
    s.split(is_space).filter(|p| !p.is_empty()).collect()
}

/// Python `str.splitlines()` (line boundaries are not kept).
pub fn splitlines(s: &str) -> Vec<&str> {
    let mut lines = Vec::new();
    let mut start = 0;
    let mut chars = s.char_indices().peekable();
    while let Some((i, c)) = chars.next() {
        let boundary = matches!(c, '\n' | '\r' | '\x0b' | '\x0c' | '\x1c' | '\x1d' | '\x1e' | '\u{85}' | '\u{2028}' | '\u{2029}');
        if boundary {
            lines.push(&s[start..i]);
            let mut next = i + c.len_utf8();
            if c == '\r' {
                if let Some(&(j, '\n')) = chars.peek() {
                    chars.next();
                    next = j + 1;
                }
            }
            start = next;
        }
    }
    if start < s.len() {
        lines.push(&s[start..]);
    }
    lines
}

/// Python `len(str)`: code points, not bytes.
pub fn len_chars(s: &str) -> usize {
    s.chars().count()
}

/// Python `str.isdigit()` restricted to ASCII digits (stricter than Python).
pub fn is_digits(s: &str) -> bool {
    !s.is_empty() && s.bytes().all(|b| b.is_ascii_digit())
}

/// Python `round(x, digits)` for display values (half away from zero).
pub fn round(x: f64, digits: i32) -> f64 {
    let scale = 10f64.powi(digits);
    (x * scale).round() / scale
}

pub fn hex(data: &[u8]) -> String {
    data.iter().map(|b| format!("{b:02x}")).collect()
}

pub fn unhex(text: &str) -> Option<Vec<u8>> {
    if !text.len().is_multiple_of(2) || !text.bytes().all(|b| b.is_ascii_hexdigit()) {
        return None;
    }
    (0..text.len()).step_by(2).map(|i| u8::from_str_radix(&text[i..i + 2], 16).ok()).collect()
}

fn rng() -> &'static SystemRandom {
    static RNG: OnceLock<SystemRandom> = OnceLock::new();
    RNG.get_or_init(SystemRandom::new)
}

pub fn random_bytes(len: usize) -> Vec<u8> {
    let mut out = vec![0u8; len];
    rng().fill(&mut out).expect("system randomness unavailable");
    out
}

/// Python `secrets.token_hex(n)`.
pub fn token_hex(n: usize) -> String {
    hex(&random_bytes(n))
}

/// Python `secrets.token_urlsafe(n)`.
pub fn token_urlsafe(n: usize) -> String {
    use base64::Engine;
    base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(random_bytes(n))
}

/// Python `secrets.choice` index: uniform in [0, len). Panics on len == 0.
pub fn choice(len: usize) -> usize {
    assert!(len > 0, "choice from empty sequence");
    let len = len as u64;
    let zone = u64::MAX - (u64::MAX % len);
    loop {
        let mut buf = [0u8; 8];
        rng().fill(&mut buf).expect("system randomness unavailable");
        let value = u64::from_le_bytes(buf);
        if value < zone {
            return (value % len) as usize;
        }
    }
}

/// Seconds clock, injectable in tests (Python `time.monotonic`/`time.time`).
pub type Clock = std::sync::Arc<dyn Fn() -> f64 + Send + Sync>;

pub fn monotonic() -> f64 {
    static START: OnceLock<Instant> = OnceLock::new();
    // Offset keeps values positive and comparable within one process.
    START.get_or_init(Instant::now).elapsed().as_secs_f64() + 1000.0
}

pub fn wall() -> f64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs_f64()).unwrap_or(0.0)
}

pub fn monotonic_clock() -> Clock {
    std::sync::Arc::new(monotonic)
}

pub fn wall_clock() -> Clock {
    std::sync::Arc::new(wall)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn python_line_and_space_semantics() {
        assert_eq!(splitlines("a\r\nb\rc\nd\x0be\u{2028}f\n"), vec!["a", "b", "c", "d", "e", "f"]);
        assert_eq!(splitlines(""), Vec::<&str>::new());
        assert_eq!(splitlines("\n\n"), vec!["", ""]);
        assert_eq!(strip("\x1c a b\t\n"), "a b");
        assert_eq!(split_ws(" 1  2\t3 "), vec!["1", "2", "3"]);
        assert_eq!(unhex("0aFF"), Some(vec![10, 255]));
        assert!(unhex("0g").is_none());
        for _ in 0..100 {
            assert!(choice(3) < 3);
        }
        assert_eq!(token_hex(32).len(), 64);
    }
}
