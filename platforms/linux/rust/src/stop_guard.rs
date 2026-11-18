//! Systemd stop/crash guard for the dedicated Phoenix target (stop_guard.py):
//! forwarding off first, then a drop-all forward table independent of `phoenix`.
use crate::error::Result;
use crate::runner::{Runner, SystemRunner};
use std::path::Path;

const TABLE: &str = "table inet phoenix_stop {\n chain forward {\n  type filter hook forward priority -20; policy drop;\n  counter drop\n }\n}\n";

pub fn block(runner: &dyn Runner, forwarding: &Path) -> Result<()> {
    // Disable forwarding even if nft userspace is unavailable or the table is damaged.
    std::fs::write(forwarding, "0")?;
    let exists = runner.optional(&["nft", "list", "table", "inet", "phoenix_stop"])?.code == 0;
    let script = if exists { format!("delete table inet phoenix_stop\n{TABLE}") } else { TABLE.to_string() };
    runner.input(&["nft", "-f", "-"], &script)?;
    Ok(())
}

/// `phoenix stop-guard`
pub fn main(args: &[String]) -> i32 {
    if !args.is_empty() {
        return crate::args::usage_error("usage: phoenix stop-guard");
    }
    let result = SystemRunner::new().and_then(|runner| block(&runner, Path::new("/proc/sys/net/ipv4/ip_forward")));
    match result {
        Ok(()) => 0,
        Err(e) => {
            eprintln!("phoenix: {e}");
            1
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fsutil::testdir::TempDir;
    use crate::runner::{exit, FakeRunner};

    #[test]
    fn forwarding_disabled_before_nft_failure() {
        let dir = TempDir::new();
        let forwarding = dir.path().join("forwarding");
        std::fs::write(&forwarding, "1").unwrap();
        let seen = forwarding.clone();
        let failing = FakeRunner::with(move |_, _| {
            assert_eq!(std::fs::read_to_string(&seen).unwrap(), "0");
            exit(2)
        });
        assert!(block(&failing, &forwarding).is_err());
        assert_eq!(failing.argvs().len(), 2, "list is optional, load must fail loudly");
    }

    #[test]
    fn replaces_existing_stop_table() {
        let dir = TempDir::new();
        let forwarding = dir.path().join("forwarding");
        let runner = FakeRunner::new();
        block(&runner, &forwarding).unwrap();
        let calls = runner.calls.lock().unwrap();
        assert_eq!(calls[1].argv, vec!["nft", "-f", "-"]);
        assert!(calls[1].input.as_deref().unwrap().starts_with("delete table inet phoenix_stop\ntable inet phoenix_stop {"));
        assert!(calls[1].input.as_deref().unwrap().contains("policy drop;"));
    }

    /// Real nft in an isolated container (tools/rust-kernel-tests.sh): forwarding off,
    /// drop-all table installed, and a second run replaces it.
    #[test]
    #[ignore = "needs an isolated Docker container with NET_ADMIN"]
    fn kernel_stop_guard_in_isolated_container() {
        assert!(Path::new("/.dockerenv").exists(), "never run on a host or target");
        let runner = SystemRunner::new().unwrap();
        let dir = TempDir::new();
        let forwarding = dir.path().join("forwarding");
        std::fs::write(&forwarding, "1").unwrap();
        block(&runner, &forwarding).unwrap();
        block(&runner, &forwarding).unwrap();
        assert_eq!(std::fs::read_to_string(&forwarding).unwrap(), "0");
        let table = runner.run(&["nft", "list", "table", "inet", "phoenix_stop"]).unwrap().stdout;
        assert!(table.contains("hook forward priority") && table.contains("policy drop;"), "{table}");
        runner.run(&["nft", "delete", "table", "inet", "phoenix_stop"]).unwrap();
    }
}
