//! Allowlisted application bundle, format 2 (Rust): STORED zip with
//!   manifest.json  {"format": 2, "signed": false, "files": {name: sha256}}
//!   bin/phoenix    the static binary (mode 0755 once installed)
//!   deploy/<name>  for every name in DEPLOY (and OPTIONAL when present)
//! SHA-256 detects corruption, not authenticity (that is updates.rs).
//!
//! The zip reader/writer is local and STORED-only: the zip crate's reader
//! silently merges duplicate names, which would hide a smuggled entry.
use crate::args::{usage_error, Args};
use crate::error::{invalid, Error, Result};
use crate::json::{self, Map, Value};
use crate::py;
use std::collections::HashSet;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::os::unix::fs::{OpenOptionsExt, PermissionsExt};
use std::path::Path;

pub const BINARY: &str = "bin/phoenix";
pub const DEPLOY: [&str; 6] = [
    "phoenix-usb-gadget.service",
    "phoenix.service",
    "phoenix-control.service",
    "phoenix-update.service",
    "phoenix-update-recover.service",
    "target.example.json",
];
/// Opt-in USB administration units (USB_ADMIN.md): bundled and allowlisted,
/// installed only by hand or when replacing an installation that has them.
pub const OPTIONAL: [&str; 5] = [
    "phoenix-usb-http.service",
    "phoenix-usb-http.socket",
    "phoenix-usb-https.service",
    "phoenix-usb-https.socket",
    "phoenix-update-usb.conf",
];
pub const MAX_ENTRIES: usize = 128;
pub const MAX_SIZE: u64 = 16 * 1024 * 1024;
const MANIFEST: &str = "manifest.json";
const REQUIRED: [&str; 3] = [BINARY, "deploy/phoenix.service", "deploy/phoenix-control.service"];

pub fn permitted(name: &str) -> bool {
    name == BINARY || name.strip_prefix("deploy/").map(|n| DEPLOY.contains(&n) || OPTIONAL.contains(&n)).unwrap_or(false)
}

pub fn sha256_hex(data: &[u8]) -> String {
    py::hex(ring::digest::digest(&ring::digest::SHA256, data).as_ref())
}

const fn crc_table() -> [u32; 256] {
    let mut table = [0u32; 256];
    let mut i = 0;
    while i < 256 {
        let mut c = i as u32;
        let mut k = 0;
        while k < 8 {
            c = if c & 1 != 0 { 0xEDB8_8320 ^ (c >> 1) } else { c >> 1 };
            k += 1;
        }
        table[i] = c;
        i += 1;
    }
    table
}

static CRC_TABLE: [u32; 256] = crc_table();

pub fn crc32(data: &[u8]) -> u32 {
    !data.iter().fold(!0u32, |c, &b| CRC_TABLE[((c ^ b as u32) & 0xff) as usize] ^ (c >> 8))
}

/// One STORED zip member; `mode` is the full unix st_mode from the central directory.
pub struct Entry<'a> {
    pub name: String,
    pub mode: u32,
    pub data: &'a [u8],
}

impl Entry<'_> {
    pub fn is_symlink(&self) -> bool {
        self.mode & 0o170000 == 0o120000
    }
    pub fn is_dir(&self) -> bool {
        self.name.ends_with('/') || self.mode & 0o170000 == 0o040000
    }
}

/// Deterministic STORED zip: 1980-01-01 timestamps, unix regular files.
pub fn zip_write(entries: &[(&str, &[u8], u32)]) -> Result<Vec<u8>> {
    if entries.len() >= 0xffff {
        return invalid("zip_too_many_entries");
    }
    let mut out = Vec::new();
    let mut central = Vec::new();
    for (name, data, mode) in entries {
        let size = u32::try_from(data.len()).map_err(|_| Error::Invalid("zip_entry_too_large".into()))?;
        let name_len = u16::try_from(name.len()).map_err(|_| Error::Invalid("zip_name_too_long".into()))?;
        let offset = u32::try_from(out.len()).map_err(|_| Error::Invalid("zip_too_large".into()))?;
        let crc = crc32(data);
        let flags: u16 = if name.is_ascii() { 0 } else { 0x800 };
        let common = |buf: &mut Vec<u8>| {
            buf.extend_from_slice(&20u16.to_le_bytes());
            buf.extend_from_slice(&flags.to_le_bytes());
            buf.extend_from_slice(&0u16.to_le_bytes()); // stored
            buf.extend_from_slice(&0u16.to_le_bytes()); // 00:00:00
            buf.extend_from_slice(&0x21u16.to_le_bytes()); // 1980-01-01
            buf.extend_from_slice(&crc.to_le_bytes());
            buf.extend_from_slice(&size.to_le_bytes());
            buf.extend_from_slice(&size.to_le_bytes());
            buf.extend_from_slice(&name_len.to_le_bytes());
            buf.extend_from_slice(&0u16.to_le_bytes()); // extra
        };
        out.extend_from_slice(&0x0403_4b50u32.to_le_bytes());
        common(&mut out);
        out.extend_from_slice(name.as_bytes());
        out.extend_from_slice(data);
        central.extend_from_slice(&0x0201_4b50u32.to_le_bytes());
        central.extend_from_slice(&((3u16 << 8) | 20).to_le_bytes()); // made by unix
        common(&mut central);
        central.extend_from_slice(&0u16.to_le_bytes()); // comment
        central.extend_from_slice(&0u16.to_le_bytes()); // disk
        central.extend_from_slice(&0u16.to_le_bytes()); // internal attributes
        central.extend_from_slice(&((0o100000 | (mode & 0o7777)) << 16).to_le_bytes());
        central.extend_from_slice(&offset.to_le_bytes());
        central.extend_from_slice(name.as_bytes());
    }
    let cd_offset = u32::try_from(out.len()).map_err(|_| Error::Invalid("zip_too_large".into()))?;
    let cd_size = central.len() as u32;
    out.extend_from_slice(&central);
    let count = entries.len() as u16;
    out.extend_from_slice(&0x0605_4b50u32.to_le_bytes());
    out.extend_from_slice(&[0, 0, 0, 0]);
    out.extend_from_slice(&count.to_le_bytes());
    out.extend_from_slice(&count.to_le_bytes());
    out.extend_from_slice(&cd_size.to_le_bytes());
    out.extend_from_slice(&cd_offset.to_le_bytes());
    out.extend_from_slice(&0u16.to_le_bytes());
    Ok(out)
}

fn bad_zip() -> Error {
    Error::Invalid("invalid_zip".into())
}

fn u16_at(data: &[u8], at: usize) -> Result<u16> {
    let bytes = data.get(at..at.checked_add(2).ok_or_else(bad_zip)?).ok_or_else(bad_zip)?;
    Ok(u16::from_le_bytes([bytes[0], bytes[1]]))
}

fn u32_at(data: &[u8], at: usize) -> Result<u32> {
    let bytes = data.get(at..at.checked_add(4).ok_or_else(bad_zip)?).ok_or_else(bad_zip)?;
    Ok(u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]))
}

/// Strict reader: single disk, no zip64, STORED only, no encryption or data
/// descriptors, CRC and local headers checked. Duplicate names are returned.
/// Entries must be in file order without overlap, so CRC work never exceeds
/// the input size (this runs before any signature check).
pub fn zip_read(data: &[u8]) -> Result<Vec<Entry<'_>>> {
    if data.len() < 22 {
        return Err(bad_zip());
    }
    let lowest = data.len().saturating_sub(22 + 0xffff);
    let mut eocd = None;
    for at in (lowest..=data.len() - 22).rev() {
        if u32_at(data, at)? == 0x0605_4b50 && at + 22 + u16_at(data, at + 20)? as usize == data.len() {
            eocd = Some(at);
            break;
        }
    }
    let eocd = eocd.ok_or_else(bad_zip)?;
    let (disk, cd_disk) = (u16_at(data, eocd + 4)?, u16_at(data, eocd + 6)?);
    let (on_disk, count) = (u16_at(data, eocd + 8)?, u16_at(data, eocd + 10)?);
    let (cd_size, cd_offset) = (u32_at(data, eocd + 12)? as usize, u32_at(data, eocd + 16)? as usize);
    if disk != 0 || cd_disk != 0 || on_disk != count || count as usize > MAX_ENTRIES || cd_offset.checked_add(cd_size) != Some(eocd) {
        return Err(bad_zip());
    }
    let mut entries = Vec::with_capacity(count as usize);
    let mut p = cd_offset;
    let mut previous_end = 0usize;
    for _ in 0..count {
        if u32_at(data, p)? != 0x0201_4b50 {
            return Err(bad_zip());
        }
        let flags = u16_at(data, p + 8)?;
        let method = u16_at(data, p + 10)?;
        let crc = u32_at(data, p + 16)?;
        let (compressed, size) = (u32_at(data, p + 20)? as usize, u32_at(data, p + 24)? as usize);
        let (name_len, extra_len, comment_len) = (u16_at(data, p + 28)? as usize, u16_at(data, p + 30)? as usize, u16_at(data, p + 32)? as usize);
        let disk_start = u16_at(data, p + 34)?;
        let external = u32_at(data, p + 38)?;
        let offset = u32_at(data, p + 42)? as usize;
        if method != 0 || flags & !0x800 != 0 || compressed != size || disk_start != 0 || offset >= cd_offset || offset < previous_end {
            return Err(bad_zip());
        }
        let raw_name = data.get(p + 46..p + 46 + name_len).ok_or_else(bad_zip)?;
        let name = std::str::from_utf8(raw_name).map_err(|_| bad_zip())?.to_string();
        if u32_at(data, offset)? != 0x0403_4b50 || u16_at(data, offset + 6)? != flags || u16_at(data, offset + 8)? != method || u32_at(data, offset + 14)? != crc {
            return Err(bad_zip());
        }
        let local_name_len = u16_at(data, offset + 26)? as usize;
        let local_extra_len = u16_at(data, offset + 28)? as usize;
        if data.get(offset + 30..offset + 30 + local_name_len) != Some(raw_name) {
            return Err(bad_zip());
        }
        let start = offset + 30 + local_name_len + local_extra_len;
        let end = start.checked_add(size).ok_or_else(bad_zip)?;
        if end > cd_offset {
            return Err(bad_zip());
        }
        previous_end = end;
        let content = &data[start..end];
        if crc32(content) != crc {
            return Err(bad_zip());
        }
        entries.push(Entry { name, mode: external >> 16, data: content });
        p += 46 + name_len + extra_len + comment_len;
        if p > eocd {
            return Err(bad_zip());
        }
    }
    if p != eocd {
        return Err(bad_zip());
    }
    Ok(entries)
}

fn read_source(path: &Path) -> Result<Vec<u8>> {
    let meta = fs::symlink_metadata(path)?;
    if !meta.file_type().is_file() {
        return invalid("unexpected_package_source");
    }
    Ok(fs::read(path)?)
}

/// Build `output` (must not exist) from `binary` and `deploy_dir`.
pub fn build(output: &Path, binary: &Path, deploy_dir: &Path) -> Result<Value> {
    let mut files: Vec<(String, Vec<u8>, u32)> = vec![(BINARY.to_string(), read_source(binary)?, 0o755)];
    for name in DEPLOY {
        files.push((format!("deploy/{name}"), read_source(&deploy_dir.join(name))?, 0o644));
    }
    for name in OPTIONAL {
        let path = deploy_dir.join(name);
        if fs::symlink_metadata(&path).is_ok() {
            files.push((format!("deploy/{name}"), read_source(&path)?, 0o644));
        }
    }
    files.sort_by(|a, b| a.0.cmp(&b.0));
    let mut digests = Map::new();
    for (name, data, _) in &files {
        digests.insert(name.clone(), Value::String(sha256_hex(data)));
    }
    let mut manifest = Map::new();
    manifest.insert("files".into(), Value::Object(digests));
    manifest.insert("format".into(), Value::from(2));
    manifest.insert("signed".into(), Value::Bool(false));
    let manifest = serde_json::to_string_pretty(&Value::Object(manifest)).map_err(Error::from)?;
    let mut entries: Vec<(&str, &[u8], u32)> = files.iter().map(|(n, d, m)| (n.as_str(), d.as_slice(), *m)).collect();
    entries.push((MANIFEST, manifest.as_bytes(), 0o644));
    let archive = zip_write(&entries)?;
    let mut file = OpenOptions::new().write(true).create_new(true).mode(0o644).open(output)?;
    file.write_all(&archive)?;
    file.sync_all()?;
    verify(output)
}

/// Verify an in-memory bundle; returns the manifest.
pub fn verify_bytes(data: &[u8]) -> Result<Value> {
    let entries = zip_read(data)?;
    let names: HashSet<&str> = entries.iter().map(|e| e.name.as_str()).collect();
    let total: u64 = entries.iter().map(|e| e.data.len() as u64).sum();
    if names.len() != entries.len() || entries.len() > MAX_ENTRIES || total > MAX_SIZE {
        return invalid("invalid_archive_size_or_duplicates");
    }
    for entry in &entries {
        if entry.name != MANIFEST && !permitted(&entry.name) {
            return invalid("unexpected_archive_path");
        }
        if entry.is_symlink() || entry.is_dir() {
            return invalid("archive_links_not_allowed");
        }
    }
    let manifest_data = entries.iter().find(|e| e.name == MANIFEST).ok_or_else(|| Error::Invalid("manifest_missing".into()))?.data;
    let manifest = json::loads(manifest_data)?;
    let object = json::object(&manifest)?;
    if object.get("format") != Some(&Value::from(2)) || object.get("signed") != Some(&Value::Bool(false)) {
        return invalid("unsupported_bundle_format");
    }
    let files = json::field(object, "files")?.as_object().ok_or_else(|| Error::Invalid("manifest_mismatch".into()))?;
    let mut expected: HashSet<&str> = files.keys().map(String::as_str).collect();
    expected.insert(MANIFEST);
    if expected != names {
        return invalid("manifest_mismatch");
    }
    if !REQUIRED.iter().all(|r| files.contains_key(*r)) {
        return invalid("incomplete_bundle");
    }
    for (name, digest) in files {
        let entry = entries.iter().find(|e| &e.name == name).ok_or_else(|| Error::Invalid("manifest_mismatch".into()))?;
        if digest.as_str() != Some(sha256_hex(entry.data).as_str()) {
            return invalid("bundle_checksum_mismatch");
        }
    }
    Ok(manifest)
}

pub fn verify(bundle: &Path) -> Result<Value> {
    verify_bytes(&std::fs::read(bundle)?)
}

/// Write the members of a verified bundle under `destination` (created by the
/// caller): files 0644, bin/phoenix 0755, directories 0755, everything fsynced.
pub fn extract(data: &[u8], destination: &Path) -> Result<()> {
    for entry in zip_read(data)? {
        if entry.name != MANIFEST && !permitted(&entry.name) {
            return invalid("unexpected_archive_path");
        }
        let path = destination.join(&entry.name);
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        let mode = if entry.name == BINARY { 0o755 } else { 0o644 };
        let mut file = OpenOptions::new().write(true).create_new(true).mode(0o600).custom_flags(libc::O_NOFOLLOW).open(&path)?;
        file.write_all(entry.data)?;
        file.sync_all()?;
        fs::set_permissions(&path, fs::Permissions::from_mode(mode))?;
    }
    let mut directories = vec![destination.to_path_buf()];
    let mut index = 0;
    while index < directories.len() {
        for item in fs::read_dir(&directories[index])? {
            let item = item?;
            if item.file_type()?.is_dir() {
                directories.push(item.path());
            }
        }
        index += 1;
    }
    // Deepest first, as in Python, so a parent is synced after its children.
    for directory in directories.iter().rev() {
        fs::set_permissions(directory, fs::Permissions::from_mode(0o755))?;
        crate::fsutil::fsync_dir(directory)?;
    }
    Ok(())
}

/// `phoenix package build <bundle> --binary F --deploy-dir D` | `phoenix package verify <bundle>`
pub fn main(args: &[String]) -> i32 {
    let parsed = match Args::parse(args, &["binary", "deploy-dir"], &[]) {
        Ok(p) => p,
        Err(e) => return usage_error(&e),
    };
    let [action, bundle] = parsed.positionals.as_slice() else {
        return usage_error("usage: phoenix package build|verify BUNDLE [--binary F --deploy-dir D]");
    };
    let result = match action.as_str() {
        "build" => {
            let Some(deploy) = parsed.get("deploy-dir") else {
                return usage_error("--deploy-dir is required");
            };
            let binary = match parsed.get("binary") {
                Some(b) => b.into(),
                None => match std::env::current_exe() {
                    Ok(path) => path,
                    Err(_) => return usage_error("--binary is required"),
                },
            };
            build(Path::new(bundle), &binary, Path::new(deploy))
        }
        "verify" => verify(Path::new(bundle)),
        _ => return usage_error("action must be build or verify"),
    };
    match result {
        Ok(manifest) => {
            let count = manifest.get("files").and_then(Value::as_object).map(|f| f.len()).unwrap_or(0);
            println!("{}", json::dumps(&json::json!({"files": count, "verified": true, "signed": false})));
            0
        }
        Err(e) => {
            eprintln!("phoenix: {e}");
            1
        }
    }
}

#[cfg(test)]
pub mod tests {
    use super::*;
    use crate::fsutil::testdir::TempDir;
    use std::path::PathBuf;

    /// Fake binary + every DEPLOY/OPTIONAL file in `dir`; returns (binary, deploy_dir).
    pub fn sources(dir: &Path) -> (PathBuf, PathBuf) {
        let deploy = dir.join("deploy");
        fs::create_dir_all(&deploy).unwrap();
        for name in DEPLOY.iter().chain(OPTIONAL.iter()) {
            fs::write(deploy.join(name), format!("# {name}\nExecStart=/opt/phoenix/bin/phoenix\n")).unwrap();
        }
        let binary = dir.join("phoenix");
        fs::write(&binary, b"\x7fELF fake phoenix binary").unwrap();
        (binary, deploy)
    }

    pub fn bundle(dir: &Path, name: &str) -> PathBuf {
        let (binary, deploy) = sources(dir);
        let output = dir.join(name);
        build(&output, &binary, &deploy).unwrap();
        output
    }

    fn rebuild(data: &[u8], change: impl Fn(&str, &[u8]) -> Option<Vec<u8>>, extra: &[(&str, &[u8], u32)]) -> Vec<u8> {
        let entries = zip_read(data).unwrap();
        let changed: Vec<(String, Vec<u8>, u32)> =
            entries.iter().map(|e| (e.name.clone(), change(&e.name, e.data).unwrap_or_else(|| e.data.to_vec()), e.mode & 0o7777)).collect();
        let mut all: Vec<(&str, &[u8], u32)> = changed.iter().map(|(n, d, m)| (n.as_str(), d.as_slice(), *m)).collect();
        all.extend_from_slice(extra);
        zip_write(&all).unwrap()
    }

    #[test]
    fn bundle_is_deterministic_and_verified() {
        let dir = TempDir::new();
        let a = bundle(dir.path(), "a.zip");
        let (binary, deploy) = sources(dir.path());
        let b = dir.path().join("b.zip");
        let manifest = build(&b, &binary, &deploy).unwrap();
        assert_eq!(fs::read(&a).unwrap(), fs::read(&b).unwrap());
        assert_eq!(manifest["signed"], false);
        assert_eq!(manifest["format"], 2);
        assert_eq!(manifest["files"].as_object().unwrap().len(), 1 + DEPLOY.len() + OPTIONAL.len());
        assert_eq!(verify(&a).unwrap(), manifest);
        assert!(build(&b, &binary, &deploy).is_err(), "existing output must not be replaced");
        let entries = zip_read(&fs::read(&a).unwrap()).unwrap().into_iter().map(|e| (e.name, e.mode)).collect::<Vec<_>>();
        assert!(entries.contains(&(BINARY.to_string(), 0o100755)));
        assert!(entries.contains(&("deploy/phoenix.service".to_string(), 0o100644)));
    }

    #[test]
    fn extra_paths_corruption_duplicates_and_links_rejected() {
        let dir = TempDir::new();
        let data = fs::read(bundle(dir.path(), "a.zip")).unwrap();
        let cases = vec![
            rebuild(&data, |_, _| None, &[("../outside", b"bad", 0o644)]),
            rebuild(&data, |_, _| None, &[("deploy/other.service", b"bad", 0o644)]),
            rebuild(&data, |n, _| (n == "deploy/phoenix.service").then(|| b"corrupted".to_vec()), &[]),
            rebuild(&data, |_, _| None, &[(BINARY, b"second", 0o755)]),
            rebuild(&data, |n, d| (n == MANIFEST).then(|| String::from_utf8_lossy(d).replace("\"format\": 2", "\"format\": 1").into_bytes()), &[]),
        ];
        for (i, case) in cases.iter().enumerate() {
            assert!(verify_bytes(case).is_err(), "case {i} accepted");
        }
        let mut link = rebuild(&data, |_, _| None, &[]);
        let entries = zip_read(&link).unwrap();
        assert!(entries.iter().all(|e| !e.is_symlink()));
        // Flip the central-directory mode of the first entry to a symlink.
        let cd = u32_at(&link, link.len() - 22 + 16).unwrap() as usize;
        link[cd + 40..cd + 42].copy_from_slice(&0o120777u16.to_le_bytes());
        assert_eq!(verify_bytes(&link).unwrap_err().code(), "archive_links_not_allowed");
        let mut flipped = data.clone();
        flipped[40] ^= 1;
        assert!(verify_bytes(&flipped).is_err(), "CRC must catch corruption");
        assert!(verify_bytes(&data[..data.len() - 1]).is_err());
        let mut trailing = data.clone();
        trailing.push(0);
        assert!(verify_bytes(&trailing).is_err());
    }

    #[test]
    fn missing_required_rejected_and_extract_modes() {
        use std::os::unix::fs::MetadataExt;
        let dir = TempDir::new();
        let (binary, deploy) = sources(dir.path());
        fs::remove_file(deploy.join("phoenix-control.service")).unwrap();
        assert!(build(&dir.path().join("x.zip"), &binary, &deploy).is_err());
        let data = fs::read(bundle(dir.path(), "a.zip")).unwrap();
        let target = dir.path().join("release");
        fs::create_dir(&target).unwrap();
        extract(&data, &target).unwrap();
        assert_eq!(fs::metadata(target.join(BINARY)).unwrap().mode() & 0o777, 0o755);
        assert_eq!(fs::metadata(target.join("deploy/phoenix.service")).unwrap().mode() & 0o777, 0o644);
        assert_eq!(fs::metadata(target.join("bin")).unwrap().mode() & 0o777, 0o755);
        assert!(target.join(MANIFEST).exists());
        assert_eq!(crc32(b"123456789"), 0xCBF4_3926);
    }
}

#[cfg(test)]
mod amplification_tests {
    use super::*;

    fn local(blob: &[u8], crc: u32) -> Vec<u8> {
        let mut data = 0x0403_4b50u32.to_le_bytes().to_vec();
        data.extend_from_slice(&[20, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
        data.extend_from_slice(&crc.to_le_bytes());
        data.extend_from_slice(&(blob.len() as u32).to_le_bytes());
        data.extend_from_slice(&(blob.len() as u32).to_le_bytes());
        data.extend_from_slice(&[1, 0, 0, 0, b'a']);
        data.extend_from_slice(blob);
        data
    }

    fn central(blob: &[u8], crc: u32) -> Vec<u8> {
        let mut data = 0x0201_4b50u32.to_le_bytes().to_vec();
        data.extend_from_slice(&[20, 3, 20, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
        data.extend_from_slice(&crc.to_le_bytes());
        data.extend_from_slice(&(blob.len() as u32).to_le_bytes());
        data.extend_from_slice(&(blob.len() as u32).to_le_bytes());
        data.extend_from_slice(&[1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
        data.extend_from_slice(&0u32.to_le_bytes());
        data.push(b'a');
        data
    }

    fn archive(entries: u16) -> Vec<u8> {
        let blob = vec![7u8; 1024];
        let crc = crc32(&blob);
        let mut data = local(&blob, crc);
        let cd_offset = data.len();
        for _ in 0..entries {
            data.extend_from_slice(&central(&blob, crc));
        }
        let cd_size = data.len() - cd_offset;
        data.extend_from_slice(&0x0605_4b50u32.to_le_bytes());
        data.extend_from_slice(&[0, 0, 0, 0]);
        data.extend_from_slice(&entries.to_le_bytes());
        data.extend_from_slice(&entries.to_le_bytes());
        data.extend_from_slice(&(cd_size as u32).to_le_bytes());
        data.extend_from_slice(&(cd_offset as u32).to_le_bytes());
        data.extend_from_slice(&[0, 0]);
        data
    }

    /// Many central entries pointing at one stored blob are refused before
    /// repeated CRC work (security review: amplification before signature).
    #[test]
    fn overlapping_entries_are_rejected() {
        assert_eq!(zip_read(&archive(1)).unwrap().len(), 1);
        assert!(zip_read(&archive(2)).is_err());
        assert!(zip_read(&archive(200)).is_err());
    }
}
