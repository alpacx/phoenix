//! Eight-hour confirmed connection history in the private state database
//! (history.py). Same table as the Python service.
use crate::error::{invalid, Result};
use crate::json::{json, Value};
use crate::py::Clock;
use crate::store::ConfigStore;
use rusqlite::{params, Connection};
use std::path::PathBuf;

const WINDOW: i64 = 28800;

pub struct History {
    path: PathBuf,
    clock: Clock,
}

impl History {
    /// `clock` is wall time (Python time.time).
    pub fn new(store: &ConfigStore, clock: Clock) -> Result<History> {
        let history = History { path: store.path.clone(), clock };
        history.connect()?.execute_batch(
            "CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, connected_at INTEGER NOT NULL, country TEXT NOT NULL, server TEXT NOT NULL, server_id INTEGER NOT NULL)",
        )?;
        Ok(history)
    }

    fn connect(&self) -> Result<Connection> {
        let db = Connection::open(&self.path)?;
        db.busy_timeout(std::time::Duration::from_secs(5))?;
        Ok(db)
    }

    fn now(&self) -> i64 {
        (self.clock)() as i64
    }

    fn expire(db: &Connection, now: i64) -> Result<()> {
        db.execute("DELETE FROM history WHERE connected_at<=? OR connected_at>?", params![now - WINDOW, now])?;
        Ok(())
    }

    pub fn add_confirmed(&self, country: &str, server: &str, server_id: i64) -> Result<()> {
        let now = self.now();
        let mut db = self.connect()?;
        let tx = db.transaction()?;
        Self::expire(&tx, now)?;
        tx.execute("INSERT INTO history(connected_at,country,server,server_id) VALUES(?,?,?,?)", params![now, country, server, server_id])?;
        tx.commit()?;
        Ok(())
    }

    pub fn page(&self, before: i64) -> Result<Value> {
        if before < 0 {
            return invalid("invalid_cursor");
        }
        let now = self.now();
        let mut db = self.connect()?;
        let tx = db.transaction()?;
        Self::expire(&tx, now)?;
        let rows: Vec<Value> = {
            let mut statement = tx.prepare("SELECT id,connected_at,country,server,server_id FROM history WHERE (?=0 OR id<?) ORDER BY id DESC LIMIT 51")?;
            let mapped = statement.query_map(params![before, before], |row| {
                Ok(json!({
                    "id": row.get::<_, i64>(0)?,
                    "connected_at": row.get::<_, i64>(1)?,
                    "country": row.get::<_, String>(2)?,
                    "server": row.get::<_, String>(3)?,
                    "server_id": row.get::<_, i64>(4)?,
                }))
            })?;
            mapped.collect::<rusqlite::Result<_>>()?
        };
        tx.commit()?;
        let more = rows.len() > 50;
        let entries: Vec<Value> = rows.into_iter().take(50).collect();
        let next_before = if more { entries.last().map(|e| e["id"].clone()).unwrap_or(json!(0)) } else { json!(0) };
        Ok(json!({"persistent": true, "now": now, "entries": entries, "next_before": next_before}))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fsutil::testdir::TempDir;
    use std::sync::atomic::{AtomicI64, Ordering};
    use std::sync::Arc;

    #[test]
    fn expiry_pagination_and_restart() {
        let dir = TempDir::new();
        let store = ConfigStore::open(&dir.path().join("state")).unwrap();
        let now = Arc::new(AtomicI64::new(100000));
        let clock = {
            let now = now.clone();
            Arc::new(move || now.load(Ordering::SeqCst) as f64) as Clock
        };
        let history = History::new(&store, clock.clone()).unwrap();
        for i in 0..55 {
            history.add_confirmed("IT", "Test", i).unwrap();
        }
        let page = History::new(&store, clock).unwrap().page(0).unwrap();
        assert_eq!(page["entries"].as_array().unwrap().len(), 50);
        assert_eq!(page["entries"][0]["server_id"], 54);
        assert_eq!(page["persistent"], true);
        let next = page["next_before"].as_i64().unwrap();
        let rest = history.page(next).unwrap();
        assert_eq!(rest["entries"].as_array().unwrap().len(), 5);
        assert_eq!(rest["next_before"], 0);
        assert!(history.page(-1).is_err());
        now.fetch_add(28801, Ordering::SeqCst);
        assert_eq!(history.page(0).unwrap()["entries"], json!([]));
    }
}
