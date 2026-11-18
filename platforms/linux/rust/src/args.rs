//! Minimal argparse: `--name value`, `--flag`, positionals. Unknown options
//! are rejected so a typo in a systemd unit fails loudly.
use std::collections::HashMap;

#[derive(Debug, Default)]
pub struct Args {
    pub options: HashMap<String, String>,
    pub flags: Vec<String>,
    pub positionals: Vec<String>,
}

impl Args {
    /// `valued`: options taking a value; `flags`: boolean options (no value).
    pub fn parse(argv: &[String], valued: &[&str], flags: &[&str]) -> Result<Args, String> {
        let mut out = Args::default();
        let mut iter = argv.iter();
        while let Some(arg) = iter.next() {
            if let Some(name) = arg.strip_prefix("--") {
                let (name, inline) = match name.split_once('=') {
                    Some((n, v)) => (n, Some(v.to_string())),
                    None => (name, None),
                };
                if valued.contains(&name) {
                    let value = match inline {
                        Some(v) => v,
                        None => iter.next().cloned().ok_or_else(|| format!("--{name} requires a value"))?,
                    };
                    if out.options.insert(name.to_string(), value).is_some() {
                        return Err(format!("--{name} given twice"));
                    }
                } else if flags.contains(&name) && inline.is_none() {
                    out.flags.push(name.to_string());
                } else {
                    return Err(format!("unknown option --{name}"));
                }
            } else {
                out.positionals.push(arg.clone());
            }
        }
        Ok(out)
    }

    pub fn get(&self, name: &str) -> Option<&str> {
        self.options.get(name).map(String::as_str)
    }

    pub fn require(&self, name: &str) -> Result<&str, String> {
        self.get(name).ok_or_else(|| format!("--{name} is required"))
    }

    pub fn flag(&self, name: &str) -> bool {
        self.flags.iter().any(|f| f == name)
    }
}

/// Print an argument error like argparse and return its exit status.
pub fn usage_error(message: &str) -> i32 {
    eprintln!("phoenix: {message}");
    2
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_options() {
        let argv: Vec<String> = ["start", "--config", "/x", "--restart", "--port=9"].iter().map(|s| s.to_string()).collect();
        let args = Args::parse(&argv, &["config", "port"], &["restart"]).unwrap();
        assert_eq!(args.get("config"), Some("/x"));
        assert_eq!(args.get("port"), Some("9"));
        assert!(args.flag("restart"));
        assert_eq!(args.positionals, vec!["start"]);
        assert!(Args::parse(&["--bad".to_string()], &[], &[]).is_err());
        assert!(Args::parse(&["--config".to_string()], &["config"], &[]).is_err());
    }
}
