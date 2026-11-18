//! Private-file helpers: O_NOFOLLOW opens, owner/mode checks, atomic replace.
use crate::error::{invalid, Result};
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::os::unix::fs::{DirBuilderExt, MetadataExt, OpenOptionsExt};
use std::path::Path;

pub fn getuid() -> u32 {
    unsafe { libc::getuid() }
}

pub fn geteuid() -> u32 {
    unsafe { libc::geteuid() }
}

pub fn is_symlink(path: &Path) -> bool {
    fs::symlink_metadata(path).map(|m| m.file_type().is_symlink()).unwrap_or(false)
}

/// Python `Path.exists()`: follows symlinks; dangling links do not exist.
pub fn exists(path: &Path) -> bool {
    fs::metadata(path).is_ok()
}

fn open_nofollow(path: &Path) -> std::io::Result<File> {
    OpenOptions::new().read(true).custom_flags(libc::O_NOFOLLOW).open(path)
}

/// Read a file that must be owned by this UID and private (mode & 0o077 == 0).
pub fn read_private(path: &Path, code: &str) -> Result<Vec<u8>> {
    let mut file = open_nofollow(path)?;
    let meta = file.metadata()?;
    if meta.uid() != getuid() || meta.mode() & 0o077 != 0 {
        return invalid(code);
    }
    let mut data = Vec::new();
    file.read_to_end(&mut data)?;
    Ok(data)
}

/// Read at most `limit` bytes of a private file.
pub fn read_private_limited(path: &Path, limit: u64, code: &str) -> Result<Vec<u8>> {
    let file = open_nofollow(path)?;
    let meta = file.metadata()?;
    if meta.uid() != getuid() || meta.mode() & 0o077 != 0 {
        return invalid(code);
    }
    let mut data = Vec::new();
    file.take(limit).read_to_end(&mut data)?;
    Ok(data)
}

pub fn fsync_dir(path: &Path) -> Result<()> {
    File::open(path)?.sync_all()?;
    Ok(())
}

/// mkstemp + write + fsync + rename + fsync(dir). Temporary file is 0600.
pub fn atomic_write(path: &Path, data: &[u8], prefix: &str) -> Result<()> {
    let parent = path.parent().unwrap_or_else(|| Path::new("."));
    let temporary = loop {
        let candidate = parent.join(format!("{prefix}{}", crate::py::token_hex(6)));
        match OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .custom_flags(libc::O_NOFOLLOW)
            .open(&candidate)
        {
            Ok(file) => break (candidate, file),
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(e) => return Err(e.into()),
        }
    };
    let (name, mut file) = temporary;
    let result = (|| -> Result<()> {
        file.write_all(data)?;
        file.flush()?;
        file.sync_all()?;
        drop(file);
        fs::rename(&name, path)?;
        fsync_dir(parent)
    })();
    if result.is_err() {
        let _ = fs::remove_file(&name);
    }
    result
}

/// Create (O_CREAT|O_TRUNC|O_NOFOLLOW, 0600) and write a private file.
pub fn write_private(path: &Path, data: &[u8]) -> Result<()> {
    let mut file = OpenOptions::new()
        .write(true)
        .create(true)
        .truncate(true)
        .mode(0o600)
        .custom_flags(libc::O_NOFOLLOW)
        .open(path)?;
    file.write_all(data)?;
    Ok(())
}

/// `mkdir(parents=True, exist_ok=True, mode)` then refuse symlinks, foreign
/// owners and any permission bit in `forbidden` (Python's st_mode checks).
pub fn ensure_dir(path: &Path, mode: u32, forbidden: u32, code: &str) -> Result<()> {
    if !path.is_dir() {
        fs::DirBuilder::new().recursive(true).mode(mode).create(path)?;
    }
    let meta = fs::symlink_metadata(path)?;
    if meta.file_type().is_symlink() || meta.uid() != getuid() || meta.mode() & forbidden != 0 {
        return invalid(code);
    }
    Ok(())
}

#[cfg(test)]
pub mod testdir {
    use std::path::{Path, PathBuf};

    /// Private temporary directory removed on drop (tests only).
    pub struct TempDir(pub PathBuf);

    impl TempDir {
        pub fn new() -> Self {
            use std::os::unix::fs::DirBuilderExt;
            let path = std::env::temp_dir().join(format!("phoenix-test-{}", crate::py::token_hex(8)));
            std::fs::DirBuilder::new().mode(0o700).create(&path).unwrap();
            TempDir(path)
        }
        pub fn path(&self) -> &Path {
            &self.0
        }
    }

    impl Default for TempDir {
        fn default() -> Self {
            Self::new()
        }
    }

    impl Drop for TempDir {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::PermissionsExt;

    #[test]
    fn private_files() {
        let dir = testdir::TempDir::new();
        let path = dir.path().join("secret.json");
        atomic_write(&path, b"{}", ".t-").unwrap();
        assert_eq!(fs::metadata(&path).unwrap().mode() & 0o777, 0o600);
        assert_eq!(read_private(&path, "bad").unwrap(), b"{}");
        fs::set_permissions(&path, fs::Permissions::from_mode(0o640)).unwrap();
        assert_eq!(read_private(&path, "bad").unwrap_err().code(), "bad");
        let link = dir.path().join("link");
        std::os::unix::fs::symlink(&path, &link).unwrap();
        assert!(read_private(&link, "bad").is_err());
        assert_eq!(fs::read_dir(dir.path()).unwrap().count(), 2);
        ensure_dir(&dir.path().join("a/b"), 0o700, 0o077, "dir").unwrap();
        fs::set_permissions(dir.path().join("a/b"), fs::Permissions::from_mode(0o755)).unwrap();
        assert_eq!(ensure_dir(&dir.path().join("a/b"), 0o700, 0o077, "dir").unwrap_err().code(), "dir");
    }
}
