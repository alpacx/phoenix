//! Private local JSON file for credentials; never returned by the API.
//! Same on-disk format as the Python service (state survives the port).
use crate::error::{invalid, Result};
use crate::fsutil;
use crate::json::{self, Map, Value};
use std::path::{Path, PathBuf};

#[derive(Debug, Clone)]
pub struct Vault {
    pub path: PathBuf,
}

impl Vault {
    /// `vpn-private.json` in `directory` (Python default name).
    pub fn new(directory: &Path) -> Self {
        Vault { path: directory.join("vpn-private.json") }
    }

    pub fn named(directory: &Path, name: &str) -> Self {
        Vault { path: directory.join(name) }
    }

    /// Missing file: `{}`. Wrong owner/mode or a symlink: error.
    pub fn load(&self) -> Result<Value> {
        if !fsutil::exists(&self.path) {
            return Ok(Value::Object(Map::new()));
        }
        let data = fsutil::read_private(&self.path, "private_file_permissions")?;
        json::parse(&data)
    }

    pub fn load_object(&self) -> Result<Map<String, Value>> {
        match self.load()? {
            Value::Object(map) => Ok(map),
            _ => invalid("invalid_private_file"),
        }
    }

    pub fn save(&self, value: &Value) -> Result<()> {
        let prefix = if self.path.file_name().map(|n| n == "vpn-private.json").unwrap_or(false) { ".vpn-" } else { ".vault-" };
        fsutil::atomic_write(&self.path, json::dumps(value).as_bytes(), prefix)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fsutil::testdir::TempDir;
    use crate::json::json;

    #[test]
    fn roundtrip_and_missing() {
        let dir = TempDir::new();
        let vault = Vault::new(dir.path());
        assert_eq!(vault.load().unwrap(), json!({}));
        vault.save(&json!({"provider": "wireguard", "profile": "x"})).unwrap();
        assert_eq!(vault.load_object().unwrap()["provider"], "wireguard");
        assert_eq!(Vault::named(dir.path(), "hotspot-private.json").load().unwrap(), json!({}));
    }
}
