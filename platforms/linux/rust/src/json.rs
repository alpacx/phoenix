//! Strict JSON shared by HTTP and the privileged local protocol, plus the
//! type checks the Python service performed with `type(x) is int/bool`.
use crate::error::{invalid, Error, Result};
use serde::de::{self, Deserialize, Deserializer, MapAccess, SeqAccess, Visitor};
pub use serde_json::{json, Map, Value};
use std::fmt;

struct Strict(Value);

impl<'de> Deserialize<'de> for Strict {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> std::result::Result<Self, D::Error> {
        deserializer.deserialize_any(StrictVisitor).map(Strict)
    }
}

struct StrictVisitor;

impl<'de> Visitor<'de> for StrictVisitor {
    type Value = Value;

    fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("JSON value")
    }
    fn visit_bool<E>(self, v: bool) -> std::result::Result<Value, E> {
        Ok(Value::Bool(v))
    }
    fn visit_i64<E>(self, v: i64) -> std::result::Result<Value, E> {
        Ok(Value::Number(v.into()))
    }
    fn visit_u64<E>(self, v: u64) -> std::result::Result<Value, E> {
        Ok(Value::Number(v.into()))
    }
    fn visit_f64<E: de::Error>(self, v: f64) -> std::result::Result<Value, E> {
        serde_json::Number::from_f64(v).map(Value::Number).ok_or_else(|| E::custom("invalid_json_number"))
    }
    fn visit_str<E>(self, v: &str) -> std::result::Result<Value, E> {
        Ok(Value::String(v.to_owned()))
    }
    fn visit_string<E>(self, v: String) -> std::result::Result<Value, E> {
        Ok(Value::String(v))
    }
    fn visit_unit<E>(self) -> std::result::Result<Value, E> {
        Ok(Value::Null)
    }
    fn visit_none<E>(self) -> std::result::Result<Value, E> {
        Ok(Value::Null)
    }
    fn visit_seq<A: SeqAccess<'de>>(self, mut seq: A) -> std::result::Result<Value, A::Error> {
        let mut out = Vec::new();
        while let Some(Strict(value)) = seq.next_element()? {
            out.push(value);
        }
        Ok(Value::Array(out))
    }
    fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> std::result::Result<Value, A::Error> {
        let mut out = Map::new();
        while let Some(key) = map.next_key::<String>()? {
            if out.contains_key(&key) {
                return Err(de::Error::custom("duplicate_json_key"));
            }
            let Strict(value) = map.next_value()?;
            out.insert(key, value);
        }
        Ok(Value::Object(out))
    }
}

/// Strict parse: duplicate keys, NaN/Infinity and trailing data are rejected.
pub fn loads(data: &[u8]) -> Result<Value> {
    let mut deserializer = serde_json::Deserializer::from_slice(data);
    let Strict(value) = Strict::deserialize(&mut deserializer).map_err(|_| Error::Invalid("invalid_json".into()))?;
    deserializer.end().map_err(|_| Error::Invalid("invalid_json".into()))?;
    Ok(value)
}

/// Lenient parse for trusted local files and tool output (Python `json.loads`).
pub fn parse(data: &[u8]) -> Result<Value> {
    serde_json::from_slice(data).map_err(|_| Error::Invalid("invalid_json".into()))
}

pub fn dumps(value: &Value) -> String {
    serde_json::to_string(value).expect("serializing a Value cannot fail")
}

/// Python `type(v) is int`: JSON integers only, never booleans or floats.
pub fn is_int(value: &Value) -> bool {
    matches!(value, Value::Number(n) if n.is_i64() || n.is_u64())
}

/// policy.integer: an integer within [low, high].
pub fn integer(value: &Value, low: i64, high: i64) -> Result<i64> {
    match value.as_i64() {
        Some(n) if is_int(value) && low <= n && n <= high => Ok(n),
        _ => invalid("invalid_integer"),
    }
}

/// policy.boolean: `type(v) is bool`.
pub fn boolean(value: &Value) -> Result<bool> {
    value.as_bool().ok_or_else(|| Error::Invalid("invalid_boolean".into()))
}

pub fn object(value: &Value) -> Result<&Map<String, Value>> {
    value.as_object().ok_or_else(|| Error::Invalid("object_required".into()))
}

/// Python `d[key]`: a missing key is a KeyError, reported as invalid input.
pub fn field<'a>(map: &'a Map<String, Value>, key: &str) -> Result<&'a Value> {
    map.get(key).ok_or_else(|| Error::Invalid("missing_field".into()))
}

/// `d.get(key, default)` for strings; a present non-string is invalid.
pub fn str_or<'a>(map: &'a Map<String, Value>, key: &str, default: &'a str) -> Result<&'a str> {
    match map.get(key) {
        None => Ok(default),
        Some(Value::String(s)) => Ok(s),
        Some(_) => invalid("invalid_field_type"),
    }
}

/// Truthiness of a JSON value as Python `bool(value)` would evaluate it.
pub fn truthy(value: Option<&Value>) -> bool {
    match value {
        None | Some(Value::Null) => false,
        Some(Value::Bool(b)) => *b,
        Some(Value::Number(n)) => n.as_f64().map(|f| f != 0.0).unwrap_or(true),
        Some(Value::String(s)) => !s.is_empty(),
        Some(Value::Array(a)) => !a.is_empty(),
        Some(Value::Object(o)) => !o.is_empty(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn strict_rejects_duplicates_and_constants() {
        assert!(loads(br#"{"a":1,"a":2}"#).is_err());
        assert!(loads(br#"{"a":{"b":1,"b":1}}"#).is_err());
        assert!(loads(b"NaN").is_err());
        assert!(loads(b"[Infinity]").is_err());
        assert!(loads(b"{} x").is_err());
        assert_eq!(loads(br#" {"a":[1,2.5,"x",null,true]} "#).unwrap(), json!({"a":[1,2.5,"x",null,true]}));
    }

    #[test]
    fn integer_excludes_booleans_and_floats() {
        assert!(integer(&json!(true), 0, 1).is_err());
        assert!(integer(&json!(1.0), 0, 1).is_err());
        assert_eq!(integer(&json!(1), 0, 1).unwrap(), 1);
        assert!(integer(&json!(2), 0, 1).is_err());
        assert!(integer(&json!(u64::MAX), 0, i64::MAX).is_err());
        assert!(boolean(&json!(0)).is_err());
    }
}
