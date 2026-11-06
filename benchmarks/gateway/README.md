# Phoenix gateway integration bench

## Current setup

Waveshare ESP32-P4-NANO: phone on Phoenix-Test (192.168.9.0/24) → C6 Wi-Fi/SDIO
→ production P4 firewall/NAPT → WireGuard → Ethernet → Mac userspace peer.
USB device is disabled. Mac routes, DNS and pf remain unchanged.
Ethernet is 100 Mbit/s; this hardware cannot validate a gigabit target.

Optional `-internet-exit` adds public IPv4 TCP/UDP relay through ordinary Mac
sockets, including DNS. The user confirmed Google browsing from the phone.
The public IP is the Mac network's IP; the Mac and host process must stay on.
No ICMP relay or IPv6. Private/reserved destinations are rejected; 256 concurrent
sessions, TCP sessions limited to 10 minutes, UDP idle timeout 30 seconds.
TLS stays end-to-end. Browsing destinations/query names are not logged.
This is a bench exit, not a remote VPN provider or a production router service.

## Results

All listed speed series completed 3 × 8 MiB in each direction. Values are
aggregate payload bits / total browser transfer time, relative to the phone.

| Series | Download Mbit/s | Upload Mbit/s |
|---|---:|---:|
| Initial VPN | 12.43 | 23.03 |
| VPN after peer outages | 6.38 | 16.84 |
| Direct, firewall/NAPT active | 8.87 | 22.89 |

Direct ranges: download 6.73–11.27, upload 19.92–26.95. Same phone and HTTP
payload, but direct uses macOS TCP while VPN terminates in gVisor. Variability
and different host TCP stacks prevent attributing differences solely to crypto.

Two complete 15-second peer-outage reports verified automatic HTTP recovery.
Latest: requests fail from t=2.202 to 15.419 s; resume at t=17.622 s after peer
restart at t≈17 s, remain successful through t=34.817 s. No P4 reboot needed.
A subsequent six-transfer series completed (second table row).

Targeted egress test, `egress-results.json`: three synthetic AP-client UDP
packets to the Mac, ports 53/443/8081, unique IPv4 IDs 64000–64002. Actual
production input/route/NAPT/egress hooks are exercised, with UART completion
acknowledgment. Capture sees zero plaintext in VPN mode, zero while blocked,
all three in direct mode (positive control), zero after blocking again.
This is NOT a comprehensive leak audit, semantic DNS test, or observation of
all router-facing Ethernet traffic. IPv6 leakage is not empirically certified.
Earlier inconclusive attempts are retained: the generator lacked Ethernet
headroom; corrected using PBUF_LINK before accepting the positive control.

Ten-minute VPN endurance completed: 608.835 seconds, 45 cycles,
90 complete transfers × 8 MiB = 720 MiB. Download 12.25 Mbit/s
(range 6.55–14.61), upload 22.33
(range 16.65–24.92). No transfer errors, panic or
reboot during this series. Sampled heap 330444–397036 bytes in the run
window, ending at 393452; no obvious downward trend, not proof of no memory leaks.
Final state: VPN enabled, direct disabled, Internet exit running.
Summary: results/gatewaybench/endurance-summary.json.

## Fixes and scope

Production AP subnet moved from 192.168.8.0/24 to 192.168.9.0/24 to avoid the
actual router subnet. USB client subnet stays 192.168.7.0/24.
Production forwarding now records ingress in p->if_idx in the input hook and
uses netif_get_by_index: IDF lwIP sets current_input_netif only for local delivery,
after its forwarding branch. That previously prevented real client forwarding.
Shared WireGuard fixes and PPP client-data separation are documented in the
WireGuard benchmark README.

C6 firmware is unchanged and still reports a hosted-version mismatch warning.
The measured AP data path works, but compatibility is not exhaustively tested.
No eFuse modifications. Private test keys/AP password are local under
results/gatewaybench (gitignored, 0600). Never publish firmware with test keys.

## Build and operation

`CONFIG_PHOENIX_GATEWAY_BENCH` defaults off. It enables bench AP/VPN startup,
UART-only mode controls and synthetic probe; production admin/pairing is not
started in this bench. Direct mode expires after 300 seconds and restores VPN.
This UART-installed bench does not enable software-signed OTA.

```sh
IDF_TARGET=esp32p4 ./tools/build.sh -B build-gatewaybench \
 -D SDKCONFIG="$PWD/build-gatewaybench/sdkconfig" \
 -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;benchmarks/gateway/sdkconfig.bench'
```

Phoenix OTA layout: app at 0x20000. Use build-local @flash_args, never the earlier
standalone benchmark offset 0x10000. Endpoint/clock/private header generated
locally for this setup. Reboot may reset the clock epoch; restart the test peer
with the firmware, or provision a fresh epoch for a new deployment.

Only one UART monitor: opening another can reset the board. Use
benchmarks/gateway/monitor_control.py with port, --commands and --seconds.
Write commands atomically to results/gatewaybench/uart-command.txt, formatted
`UNIQUE_NONCE bench vpn` (or blocked/direct/probe). Commands are bench-only.

Host binary .tools/wgbench/host-internet:

```sh
.tools/wgbench/host-internet -gateway-server -internet-exit \
 -direct-listen 192.168.8.103:8080 -dir results/gatewaybench
```

Tunnel page http://10.77.0.1:8080. Direct comparison page
http://192.168.8.103:8080 is restricted to P4 source and only works in direct mode.
Phone: mobile data off, join Phoenix-Test, keep Safari foreground and screen on.
Use Misura for six transfers, peer-outage button for recovery, endurance button
for ten minutes of local bidirectional transfers. Internet browsing remains
available in VPN mode through the Mac.

Current logs: uart-probe-fixed.log, server-final-exit.jsonl, host-final-exit.log,
egress-results.json, egress-wide.pcap under results/gatewaybench. Older attempt
logs retained. summarize.py reads progress without exposing credentials.

Validation: firmware build/flash, existing firewall/parser/USB host checks,
Go destination-policy tests and opt-in DNS+HTTPS integration test passed.
The latter uses linked userspace TUNs and verifies a real HTTPS certificate;
it complements, rather than replaces, the phone browsing confirmation.
