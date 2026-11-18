//! Error categories mirroring the Python exception classes of the original
//! service. The category, not the message, decides HTTP/RPC status codes.
//! Messages are short machine codes; never put secrets or tool output in them.
use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Error {
    /// Python ValueError/KeyError/TypeError: rejected input or failed validation.
    Invalid(String),
    /// Python RevisionConflict: concurrent command or stale revision.
    Conflict(String),
    /// Python Unavailable: capability not configured on this target.
    Unavailable(String),
    /// Python NetworkError: a system tool failed or networking is not usable.
    Network(String),
    /// Python OSError: filesystem, socket or database failure.
    Io(String),
}

pub type Result<T> = std::result::Result<T, Error>;

impl Error {
    pub fn code(&self) -> &str {
        match self {
            Error::Invalid(c) | Error::Conflict(c) | Error::Unavailable(c) | Error::Network(c) | Error::Io(c) => c,
        }
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.code())
    }
}

impl std::error::Error for Error {}

pub fn invalid<T>(code: &str) -> Result<T> {
    Err(Error::Invalid(code.to_string()))
}

pub fn conflict<T>(code: &str) -> Result<T> {
    Err(Error::Conflict(code.to_string()))
}

pub fn unavailable<T>(code: &str) -> Result<T> {
    Err(Error::Unavailable(code.to_string()))
}

pub fn network<T>(code: &str) -> Result<T> {
    Err(Error::Network(code.to_string()))
}

impl From<std::io::Error> for Error {
    fn from(error: std::io::Error) -> Self {
        // The kind only: paths and OS strings stay out of API-visible errors.
        Error::Io(format!("io_{:?}", error.kind()).to_lowercase())
    }
}

impl From<rusqlite::Error> for Error {
    fn from(_: rusqlite::Error) -> Self {
        Error::Io("database_error".to_string())
    }
}

impl From<serde_json::Error> for Error {
    fn from(_: serde_json::Error) -> Self {
        Error::Invalid("invalid_json".to_string())
    }
}
