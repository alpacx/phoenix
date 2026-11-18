//! Phoenix Linux gateway services. One static binary, several roles:
//! privileged control worker, unprivileged HTTPS frontend, signed updater,
//! USB gadget/redirect helpers, stop guard and read-only preflight.
//!
//! Ported from the original Python service (same module names, API and state
//! files); that code was removed on 2026-11-18 and lives in git history.
pub mod error;
pub mod json;
pub mod py;
pub mod ipv4;
pub mod runner;
pub mod fsutil;
pub mod args;
pub mod signals;
pub mod web;

pub mod vault;
pub mod store;
pub mod history;
pub mod policy;
pub mod firewall;
pub mod wireguard;
pub mod rotation;
pub mod access_point;

pub mod auth;
pub mod rpc;
pub mod http;
pub mod frontend;
pub mod usb_admin;

pub mod httpc;
pub mod uplink_http;
pub mod nord;
pub mod runtime;
pub mod lan;
pub mod station;
pub mod speedcheck;
pub mod uploadcheck;

pub mod package;
pub mod updates;
pub mod install;
pub mod usb_gadget;
pub mod usb_bench;
pub mod stop_guard;
pub mod preflight;

pub mod controller;
pub mod local_api;
pub mod control;
