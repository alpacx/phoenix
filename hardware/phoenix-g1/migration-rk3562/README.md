## Active memory direction — 2026-11-10

User approved migration toward **1 GB LPDDR4 in one package**, compact layout, non-touch display and board-mounted five-way control. Qualification work is in `experiments/lpddr4-1gb/`. Active CAD remains DDR3 until the new memory electrical map, power and boot requirements are qualified. This supersedes the DDR3 direction as a target, not as a claim of completed CAD migration.


### Joint Wi-Fi power candidate — 2026-11-09

`experiments/wifi-vddio/joint-placement/final.kicad_pcb` is a separate candidate, not the accepted PCB or the transactional rebuild output. It passes geometric DRC and the independent Wi-Fi continuity audit including local VDDIO bypass, module grounds, internal buck and LPO. A negative test removes the 12 VDDIO back tracks and detects the intended disconnection without losing other module checks.

This resolves the previous bounded-routing failures by repositioning the buck/capacitor group, using an internal-layer buck output bridge and allowing a 7.3024 mm U25.20 ground path. The output bridge is approximately 11.516 mm; both paths require electrical layout review before adoption. Upstream PMIC and oscillator power are still incomplete. Displaced SoC decoupling also remains unqualified. No simulation or physical verification was performed; no fabrication release. The main PCB and its accepted reports are unchanged. See the candidate `result.json` for hashes and evidence.

### Oscillator supply candidate — 2026-11-09

`experiments/wifi-vddio/oscillator/candidate.kicad_pcb` extends the joint candidate with C2007 on the front at (52,28), local oscillator bypass and a connection to the module IO rail. DRC reports zero geometric violations; independent continuity and a deliberately disconnected feed test pass. Front copper was visually inspected. PMIC power remains absent, so this is not an operational clock/Wi-Fi result.

U4.55 escape is incompatible with the current generic 0.20 mm track/0.20 mm clearance recipe: adjacent 0.15 mm pads on 0.35 mm pitch leave 0.175 mm clearance around a centered 0.20 mm trace. A qualified fine-pitch power escape is needed, not a global relaxation of DRC. Source reservoir placement, current capacity and sequencing remain open. Main PCB and accepted reports remain unchanged.
