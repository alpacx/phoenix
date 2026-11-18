//! Argv-only command execution (no shell). Mirrors runtime.Runner: 15 s
//! timeout, LC_ALL=C, stderr discarded so private configuration never leaks.
use crate::error::{Error, Result};
use std::io::{Read, Write};
use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Output {
    pub code: i32,
    pub stdout: String,
}

pub trait Runner: Send + Sync {
    /// Run `argv`. A non-zero exit is an error unless `optional`; failing to
    /// start or a timeout is always an error. Errors never include stderr.
    fn exec(&self, argv: &[&str], input: Option<&str>, optional: bool) -> Result<Output>;

    fn run(&self, argv: &[&str]) -> Result<Output> {
        self.exec(argv, None, false)
    }
    fn optional(&self, argv: &[&str]) -> Result<Output> {
        self.exec(argv, None, true)
    }
    fn input(&self, argv: &[&str], data: &str) -> Result<Output> {
        self.exec(argv, Some(data), false)
    }
}

pub type SharedRunner = Arc<dyn Runner>;

fn failed(argv: &[&str]) -> Error {
    Error::Network(format!("command_failed:{}", argv.first().copied().unwrap_or("")))
}

/// Real runner. Construction requires Linux root, as in the Python service.
pub struct SystemRunner {
    pub timeout: Duration,
}

impl SystemRunner {
    pub fn new() -> Result<Self> {
        if !cfg!(target_os = "linux") || unsafe { libc::geteuid() } != 0 {
            return Err(Error::Network("linux_root_required".into()));
        }
        Ok(SystemRunner { timeout: Duration::from_secs(15) })
    }

    /// For read-only callers that may run unprivileged (preflight, tests).
    pub fn unprivileged() -> Self {
        SystemRunner { timeout: Duration::from_secs(15) }
    }
}

/// Run with timeout; returns (exit code, stdout). Kills the child on timeout.
pub fn run_with_timeout(argv: &[&str], input: Option<&str>, timeout: Duration) -> std::io::Result<Option<(i32, Vec<u8>)>> {
    let mut command = Command::new(argv[0]);
    command
        .args(&argv[1..])
        .env("LC_ALL", "C")
        .stdin(if input.is_some() { Stdio::piped() } else { Stdio::null() })
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    let mut child = command.spawn()?;
    let writer = input.map(|data| {
        let mut stdin = child.stdin.take().expect("piped stdin");
        let data = data.to_owned();
        std::thread::spawn(move || {
            let _ = stdin.write_all(data.as_bytes());
        })
    });
    let mut stdout = child.stdout.take().expect("piped stdout");
    let reader = std::thread::spawn(move || {
        let mut out = Vec::new();
        let _ = stdout.read_to_end(&mut out);
        out
    });
    let mut stderr = child.stderr.take().expect("piped stderr");
    let drain = std::thread::spawn(move || {
        let mut sink = Vec::new();
        let _ = stderr.read_to_end(&mut sink);
    });
    let deadline = Instant::now() + timeout;
    let status = loop {
        if let Some(status) = child.try_wait()? {
            break Some(status);
        }
        if Instant::now() >= deadline {
            let _ = child.kill();
            let _ = child.wait();
            break None;
        }
        std::thread::sleep(Duration::from_millis(5));
    };
    if let Some(writer) = writer {
        let _ = writer.join();
    }
    let out = reader.join().unwrap_or_default();
    let _ = drain.join();
    Ok(status.map(|s| (s.code().unwrap_or(-1), out)))
}

impl Runner for SystemRunner {
    fn exec(&self, argv: &[&str], input: Option<&str>, optional: bool) -> Result<Output> {
        if argv.is_empty() {
            return Err(failed(argv));
        }
        match run_with_timeout(argv, input, self.timeout) {
            Ok(Some((code, stdout))) => {
                if code != 0 && !optional {
                    return Err(failed(argv));
                }
                Ok(Output { code, stdout: String::from_utf8_lossy(&stdout).into_owned() })
            }
            _ => Err(failed(argv)),
        }
    }
}

/// Recorded call of a [`FakeRunner`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Call {
    pub argv: Vec<String>,
    pub input: Option<String>,
}

type Responder = dyn Fn(&[String], Option<&str>) -> Option<Output> + Send + Sync;

/// Test double: records every call; a responder decides outputs (default:
/// exit 0 with empty stdout). A responder returning code != 0 behaves like a
/// failing tool, honouring `optional` exactly like the real runner.
pub struct FakeRunner {
    pub calls: Mutex<Vec<Call>>,
    responder: Box<Responder>,
}

impl FakeRunner {
    pub fn new() -> Self {
        FakeRunner { calls: Mutex::new(Vec::new()), responder: Box::new(|_, _| None) }
    }
    pub fn with(responder: impl Fn(&[String], Option<&str>) -> Option<Output> + Send + Sync + 'static) -> Self {
        FakeRunner { calls: Mutex::new(Vec::new()), responder: Box::new(responder) }
    }
    pub fn argvs(&self) -> Vec<Vec<String>> {
        self.calls.lock().unwrap().iter().map(|c| c.argv.clone()).collect()
    }
    pub fn clear(&self) {
        self.calls.lock().unwrap().clear();
    }
}

impl Default for FakeRunner {
    fn default() -> Self {
        Self::new()
    }
}

impl Runner for FakeRunner {
    fn exec(&self, argv: &[&str], input: Option<&str>, optional: bool) -> Result<Output> {
        let argv: Vec<String> = argv.iter().map(|s| s.to_string()).collect();
        self.calls.lock().unwrap().push(Call { argv: argv.clone(), input: input.map(str::to_owned) });
        let output = (self.responder)(&argv, input).unwrap_or_default();
        if output.code != 0 && !optional {
            return Err(Error::Network(format!("command_failed:{}", argv[0])));
        }
        Ok(output)
    }
}

pub fn ok(stdout: &str) -> Option<Output> {
    Some(Output { code: 0, stdout: stdout.to_owned() })
}

pub fn exit(code: i32) -> Option<Output> {
    Some(Output { code, stdout: String::new() })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn system_runner_captures_and_times_out() {
        let runner = SystemRunner { timeout: Duration::from_millis(300) };
        let out = runner.input(&["cat"], "hello").unwrap();
        assert_eq!(out.stdout, "hello");
        assert_eq!(runner.optional(&["sh", "-c", "exit 3"]).unwrap().code, 3);
        assert_eq!(runner.run(&["sh", "-c", "echo secret >&2; exit 3"]).unwrap_err().code(), "command_failed:sh");
        assert!(runner.optional(&["sleep", "5"]).is_err());
        assert!(runner.optional(&["/nonexistent-tool"]).is_err());
    }

    #[test]
    fn fake_runner_records() {
        let fake = FakeRunner::with(|argv, _| if argv[0] == "false" { exit(1) } else { ok("x") });
        assert_eq!(fake.run(&["true"]).unwrap().stdout, "x");
        assert!(fake.run(&["false"]).is_err());
        assert_eq!(fake.optional(&["false"]).unwrap().code, 1);
        assert_eq!(fake.argvs().len(), 3);
    }
}
