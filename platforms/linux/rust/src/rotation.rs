//! Provider-independent selection and monotonic rotation deadline (rotation.py).
use crate::error::{invalid, Result};
use crate::py::Clock;

pub const RESTRICTED: [&str; 16] = ["CN", "RU", "BY", "TR", "IQ", "AE", "OM", "IN", "IR", "EG", "TM", "KP", "UG", "MM", "SA", "VE"];

/// `choice(n)` returns an index in [0, n); production passes `py::choice`.
pub fn choose_country(countries: &[String], fixed: &str, previous: &str, exclude: bool, choice: &mut dyn FnMut(usize) -> usize) -> Result<String> {
    let mut eligible: Vec<&str> = countries.iter().map(String::as_str).filter(|c| !(exclude && RESTRICTED.contains(c))).collect();
    eligible.sort_unstable();
    eligible.dedup();
    if !fixed.is_empty() {
        if !eligible.contains(&fixed) {
            return invalid("country_unavailable_or_excluded");
        }
        return Ok(fixed.to_string());
    }
    if eligible.len() > 1 {
        eligible.retain(|c| *c != previous);
    }
    if eligible.is_empty() {
        return invalid("no_eligible_countries");
    }
    Ok(eligible[choice(eligible.len())].to_string())
}

pub struct Rotation {
    clock: Clock,
    deadline: Option<f64>,
}

impl Rotation {
    pub fn new(clock: Clock) -> Self {
        Rotation { clock, deadline: None }
    }
    pub fn connected(&mut self, enabled: bool, interval: i64) -> Result<()> {
        if !(30..=86400).contains(&interval) {
            return invalid("invalid_rotation");
        }
        self.deadline = enabled.then(|| (self.clock)() + interval as f64);
        Ok(())
    }
    pub fn disconnected(&mut self) {
        self.deadline = None;
    }
    /// Whole seconds left (ceil), 0 when no deadline.
    pub fn remaining(&self) -> i64 {
        match self.deadline {
            None => 0,
            Some(deadline) => ((deadline - (self.clock)()).ceil() as i64).max(0),
        }
    }
    pub fn due(&self) -> bool {
        self.deadline.map(|d| (self.clock)() >= d).unwrap_or(false)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::sync::Arc;

    #[test]
    fn choose() {
        let codes: Vec<String> = ["IT", "RU", "DE"].iter().map(|s| s.to_string()).collect();
        let mut first = |_: usize| 0;
        assert_eq!(choose_country(&codes, "", "", false, &mut first).unwrap(), "DE");
        assert_eq!(choose_country(&codes, "", "DE", false, &mut first).unwrap(), "IT");
        assert_eq!(choose_country(&codes, "RU", "", false, &mut first).unwrap(), "RU");
        assert!(choose_country(&codes, "RU", "", true, &mut first).is_err());
        assert!(choose_country(&codes, "XX", "", false, &mut first).is_err());
        let one = vec!["IT".to_string()];
        assert_eq!(choose_country(&one, "", "IT", false, &mut first).unwrap(), "IT");
        assert!(choose_country(&["RU".to_string()], "", "", true, &mut first).is_err());
    }

    #[test]
    fn deadline() {
        let now = Arc::new(AtomicU64::new(100));
        let source = now.clone();
        let mut rotation = Rotation::new(Arc::new(move || source.load(Ordering::SeqCst) as f64));
        assert!(rotation.connected(true, 29).is_err());
        rotation.connected(true, 60).unwrap();
        assert_eq!(rotation.remaining(), 60);
        now.store(159, Ordering::SeqCst);
        assert!(!rotation.due());
        now.store(160, Ordering::SeqCst);
        assert!(rotation.due());
        now.store(200, Ordering::SeqCst);
        assert_eq!(rotation.remaining(), 0);
        rotation.connected(false, 60).unwrap();
        assert!(!rotation.due());
    }
}
