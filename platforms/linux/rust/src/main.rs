//! Multi-call entry point: `phoenix <role> [options]`.
use phoenix_linux::*;

const USAGE: &str = "usage: phoenix <control|frontend|usb-redirect|usb-gadget|update|stop-guard|preflight|package|install> [options]";

fn main() {
    let argv: Vec<String> = std::env::args().skip(1).collect();
    let Some((role, rest)) = argv.split_first() else {
        eprintln!("{USAGE}");
        std::process::exit(2);
    };
    let code = match role.as_str() {
        "control" => control::main(rest),
        "frontend" => frontend::main(rest),
        "usb-redirect" => usb_admin::main(rest),
        "usb-gadget" => usb_gadget::main(rest),
        "update" => updates::main(rest),
        "stop-guard" => stop_guard::main(rest),
        "preflight" => preflight::main(rest),
        "package" => package::main(rest),
        "install" => install::main(rest),
        "--version" => {
            println!("phoenix {}", env!("CARGO_PKG_VERSION"));
            0
        }
        _ => {
            eprintln!("{USAGE}");
            2
        }
    };
    std::process::exit(code);
}
