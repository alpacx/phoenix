//! Transactional desired-state storage; saving does NOT apply network
//! settings (store.py). Same schema and file as the Python service, so
//! existing state opens unchanged. Only validated, non-secret desired
//! configuration belongs here.
use crate::error::{conflict, invalid, Result};
use crate::fsutil;
use crate::json::{self, Value};
use rusqlite::{params, Connection, TransactionBehavior};
use serde::Serialize;
use std::fs::OpenOptions;
use std::io;
use std::os::unix::fs::{DirBuilderExt, MetadataExt, OpenOptionsExt};
use std::path::{Path, PathBuf};
use std::time::Duration;

const INITIAL: &str = r#"{"schema_version": 1, "direct": false}"#;
const PAYLOAD_LIMIT: usize = 65536;

#[derive(Debug, Clone, PartialEq)]
pub struct Stored {
    pub revision: i64,
    pub desired: Value,
}

pub struct ConfigStore {
    pub path: PathBuf,
}

/// serde_json formatter producing Python `json.dumps` defaults: ", " and
/// ": " separators and ASCII-only output (`ensure_ascii=True`). Used so the
/// 64 KiB limit measures the same bytes the Python service stored.
struct PythonFormatter;

impl serde_json::ser::Formatter for PythonFormatter {
    fn begin_array_value<W: ?Sized + io::Write>(&mut self, writer: &mut W, first: bool) -> io::Result<()> {
        if first {
            Ok(())
        } else {
            writer.write_all(b", ")
        }
    }
    fn begin_object_key<W: ?Sized + io::Write>(&mut self, writer: &mut W, first: bool) -> io::Result<()> {
        if first {
            Ok(())
        } else {
            writer.write_all(b", ")
        }
    }
    fn begin_object_value<W: ?Sized + io::Write>(&mut self, writer: &mut W) -> io::Result<()> {
        writer.write_all(b": ")
    }
    fn write_string_fragment<W: ?Sized + io::Write>(&mut self, writer: &mut W, fragment: &str) -> io::Result<()> {
        for c in fragment.chars() {
            if (c as u32) < 0x7f {
                let mut buf = [0u8; 4];
                writer.write_all(c.encode_utf8(&mut buf).as_bytes())?;
            } else {
                let mut units = [0u16; 2];
                for unit in c.encode_utf16(&mut units) {
                    write!(writer, "\\u{unit:04x}")?;
                }
            }
        }
        Ok(())
    }
}

/// Python `json.dumps(value)` byte-for-byte for strings, integers, booleans,
/// null, arrays and objects (float formatting may differ).
pub fn python_dumps(value: &Value) -> String {
    let mut out = Vec::new();
    let mut serializer = serde_json::Serializer::with_formatter(&mut out, PythonFormatter);
    value.serialize(&mut serializer).expect("serializing a Value cannot fail");
    String::from_utf8(out).expect("formatter emits ASCII")
}

impl ConfigStore {
    /// Creates/validates the private directory and `desired.sqlite3`.
    pub fn open(directory: &Path) -> Result<ConfigStore> {
        if !directory.is_dir() {
            std::fs::DirBuilder::new().recursive(true).mode(0o700).create(directory)?;
        }
        let meta = std::fs::symlink_metadata(directory)?;
        if meta.file_type().is_symlink() || meta.uid() != fsutil::getuid() {
            return invalid("state_directory_must_be_owned_and_not_symlink");
        }
        if meta.mode() & 0o077 != 0 {
            return invalid("state_directory_must_be_private");
        }
        let path = directory.join("desired.sqlite3");
        OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .mode(0o600)
            .custom_flags(libc::O_NOFOLLOW)
            .open(&path)?;
        let meta = std::fs::metadata(&path)?;
        if meta.uid() != fsutil::getuid() || meta.mode() & 0o077 != 0 {
            return invalid("state_database_must_be_private");
        }
        let store = ConfigStore { path };
        let db = store.connect()?;
        db.execute_batch("CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, payload TEXT NOT NULL)")?;
        db.execute("INSERT OR IGNORE INTO config VALUES (1, 0, ?)", params![INITIAL])?;
        Ok(store)
    }

    fn connect(&self) -> Result<Connection> {
        let db = Connection::open(&self.path)?;
        db.busy_timeout(Duration::from_secs(5))?;
        Ok(db)
    }

    pub fn load(&self) -> Result<Stored> {
        let db = self.connect()?;
        let (revision, payload): (i64, String) = db.query_row("SELECT revision,payload FROM config WHERE id=1", [], |row| Ok((row.get(0)?, row.get(1)?)))?;
        Ok(Stored { revision, desired: json::parse(payload.as_bytes())? })
    }

    /// Conflict("revision_conflict_reload") when the revision changed.
    pub fn save(&self, expected_revision: i64, desired: &Value, validate: &dyn Fn(&Value) -> Result<()>) -> Result<Stored> {
        if expected_revision < 0 {
            return invalid("invalid_revision");
        }
        let payload = python_dumps(desired);
        if payload.len() > PAYLOAD_LIMIT {
            return invalid("configuration_too_large");
        }
        let normalized = json::parse(payload.as_bytes())?;
        validate(&normalized)?;
        let mut db = self.connect()?;
        let tx = db.transaction_with_behavior(TransactionBehavior::Immediate)?;
        let revision: i64 = tx.query_row("SELECT revision FROM config WHERE id=1", [], |row| row.get(0))?;
        if revision != expected_revision {
            return conflict("revision_conflict_reload");
        }
        tx.execute("UPDATE config SET revision=?,payload=? WHERE id=1", params![revision + 1, payload])?;
        tx.commit()?;
        Ok(Stored { revision: revision + 1, desired: normalized })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::error::Error;
    use crate::fsutil::testdir::TempDir;
    use crate::json::json;
    use std::os::unix::fs::PermissionsExt;

    #[test]
    fn python_compatible_serialization() {
        let value = json!({"a": [1, "\u{e9}\u{7f}\u{2028}\u{1f600}", null, true], "b": {"c": "x"}});
        let expected = concat!("{\"a\": [1, \"", "\\u00e9\\u007f\\u2028\\ud83d\\ude00", "\", null, true], \"b\": {\"c\": \"x\"}}");
        assert_eq!(python_dumps(&value), expected);
        assert_eq!(python_dumps(&json!({"schema_version": 1, "direct": false})), INITIAL);
    }

    #[test]
    fn transactional_revisions() {
        let dir = TempDir::new();
        let state = dir.path().join("state");
        let store = ConfigStore::open(&state).unwrap();
        assert_eq!(std::fs::metadata(&state).unwrap().mode() & 0o777, 0o700);
        assert_eq!(std::fs::metadata(&store.path).unwrap().mode() & 0o777, 0o600);
        assert_eq!(store.load().unwrap(), Stored { revision: 0, desired: json!({"schema_version": 1, "direct": false}) });
        let saved = store.save(0, &json!({"policy": {"x": 1}}), &|_| Ok(())).unwrap();
        assert_eq!(saved.revision, 1);
        assert_eq!(store.save(0, &json!({}), &|_| Ok(())).unwrap_err(), Error::Conflict("revision_conflict_reload".into()));
        assert!(store.save(1, &json!({}), &|_| invalid("rejected")).is_err());
        assert_eq!(store.load().unwrap().revision, 1);
        assert!(store.save(-1, &json!({}), &|_| Ok(())).is_err());
        assert!(store.save(1, &json!({"x": "a".repeat(70000)}), &|_| Ok(())).is_err());
        // Reopening keeps state and never resets the revision.
        let again = ConfigStore::open(&state).unwrap();
        assert_eq!(again.load().unwrap().desired, json!({"policy": {"x": 1}}));
    }

    #[test]
    fn refuses_shared_directory_or_database() {
        let dir = TempDir::new();
        let state = dir.path().join("state");
        std::fs::create_dir(&state).unwrap();
        std::fs::set_permissions(&state, std::fs::Permissions::from_mode(0o755)).unwrap();
        assert_eq!(ConfigStore::open(&state).err().unwrap().code(), "state_directory_must_be_private");
        std::fs::set_permissions(&state, std::fs::Permissions::from_mode(0o700)).unwrap();
        let store = ConfigStore::open(&state).unwrap();
        std::fs::set_permissions(&store.path, std::fs::Permissions::from_mode(0o644)).unwrap();
        assert_eq!(ConfigStore::open(&state).err().unwrap().code(), "state_database_must_be_private");
        let link = dir.path().join("link");
        std::os::unix::fs::symlink(&state, &link).unwrap();
        assert_eq!(ConfigStore::open(&link).err().unwrap().code(), "state_directory_must_be_owned_and_not_symlink");
    }

    #[test]
    fn opens_python_created_database() {
        let dir = TempDir::new();
        let state = dir.path().join("state");
        std::fs::create_dir(&state).unwrap();
        std::fs::set_permissions(&state, std::fs::Permissions::from_mode(0o700)).unwrap();
        let path = state.join("desired.sqlite3");
        {
            let db = Connection::open(&path).unwrap();
            db.execute_batch("CREATE TABLE config (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, payload TEXT NOT NULL)").unwrap();
            db.execute("INSERT INTO config VALUES (1, 7, ?)", params![r#"{"schema_version": 1, "direct": false, "policy": {"default_allow": true}}"#]).unwrap();
        }
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o600)).unwrap();
        let store = ConfigStore::open(&state).unwrap();
        let loaded = store.load().unwrap();
        assert_eq!(loaded.revision, 7);
        assert_eq!(loaded.desired["policy"]["default_allow"], true);
    }
}
