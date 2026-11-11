

## Verified Wi-Fi relocation — current working PCB

Use **`wifi-relocation/io.kicad_pcb`**, identified by `working-board.json`, for the next layout work. This supersedes the failed `cpu-board-integration/` diagnostic. The original DDR3 board and the pre-relocation LPDDR4 baseline remain unchanged.

AP6256 U25 is now centred at **61.5, 20 mm**, clear of the CPU/RAM through-via escape area. The 90 × 40 mm outline remains unchanged; the smaller enclosure target is not achieved. Local bypass components were repositioned and prioritized for routing, including the buck output capacitor and the 100 nF IO bypass. Displaced SoC bypass positions still need power-integrity review.

The rebuild restores and independently audits converter continuity, converter-to-ferrite and module VBAT feeds, buck output, ground returns, IO bypass, PMIC IO supply, the 32.768 kHz signal, and oscillator power/bypass. All corresponding connectivity flags pass. This does **not** establish operational Wi-Fi: SDIO/RF/crystal completion, firmware and physical testing remain open.

The switch node stays on B.Cu without vias. One output connection uses two 0.60/0.30 mm vias and In3.Cu, approximately 5.23 mm total. Its power integrity is unqualified. The pre-existing PMIC escape geometry is reproduced with one 0.127 mm wide, 0.94 mm long neck; a dedicated net-width exception is accompanied by an audit requiring that every sub-0.20 mm IO track is exactly this segment.

The independent preservation audit verifies every source pad assignment, all retained source copper, and the explicit removal list. The final DRC has no short, copper-clearance, hole-clearance, crossing, width or courtyard-overlap findings. It still reports **125 intentionally unfinished DDR vias and 14 silkscreen findings**; the unconnected-item report reaches its 499-item cap. This remains an incomplete board, not a manufacturing release.

Reproduce from the existing LPDDR4 baseline with:

```sh
python3 hardware/phoenix-g1/tools/rebuild_wifi_relocation.py
```

The full `rebuild_lpddr4_candidate.py` also runs this stage. It stops on generation or verification failure and writes the verified checkpoint only after all checks pass. Evidence: `wifi-relocation/io-audit.json`, `wifi-relocation/io-drc.json`, `wifi-relocation/preservation-audit.json`, and `wifi-relocation/verified-checkpoint.json`.

Next layout constraint: retain the separated CPU/Wi-Fi areas while completing the five remaining CPU escapes and end-to-end DDR routing. Land/paste, stackup/impedance, timing, power sequencing, thermal and prototype qualifications remain mandatory open work. **Assembly readiness is false.**

## Simultaneous CPU escape and board interference update

The new `cpu-simultaneous-coupon/` experiment verifies **60 of 65** CPU signal escapes together using 0.0762 mm tracks/clearance and 0.45/0.20 mm through-vias. KiCad reports only 60 deliberately dangling vias. An independent copper-graph audit confirms each escaped CPU pad actually reaches its assigned via. The remaining balls are B8, A3, B4, A25 and C26. No end-to-end DDR routing is implied.

Earlier search scores as high as 64 were **rejected**, because the first search omitted hole-to-track spacing when adding a track beside an existing via. The solver now checks that distance in both insertion directions; historical search counts are not validation results.

The separate `cpu-board-integration/` board is a **failing interference diagnostic, not an improved candidate**. Transferring the verified CPU escapes to the existing placement exposes interference with the routed AP6256 Wi-Fi module on the reverse side (U1 centre 43,20 mm; U25 centre 45,20 mm), including its power copper. The RAM placement candidate and original DDR3 board remain untouched. A conservative 0.5 mm CPU relocation search protecting routed copper, crystals, RAM and connectors found no acceptable centre. This bounded search is not proof that relocation is impossible: coordinated component/island placement needs redesign rather than a single-component move.

Rebuild with `python3 hardware/phoenix-g1/tools/rebuild_lpddr4_candidate.py`. The rebuild distinguishes passing isolated geometry from deliberately failing full-board interference checks. See `cpu-simultaneous-coupon/audit.json`, `cpu-board-integration/drc.json` and `cpu-board-integration/placement-search.json`. Manufacturing readiness remains false.

## Earlier baseline checkpoint (before Wi-Fi relocation) — LPDDR4 integrated candidate

This section supersedes the chronological findings below. Current whole-system schematic: `system/kicad/integrated/phoenix-g1.kicad_sch`. Current PCB candidate: `system/kicad/pcb/phoenix-lpddr4-placement.kicad_pcb`. Neither is a manufacturing release.

- One H9HCNNN8KUMLHR-NME, 1 GB. 65 active CPU/RAM signal connections. ODT G2/T2 tied to VDD2 following the RK3562 reference and Hynix MR22 behavior; CPU ODT outputs and unused rank controls explicitly NC.
- RAM and SoC calibration pull-ups checked separately. Both CPU DDR voltage domains are 1.1 V. VDD1 is 1.8 V. Divider selected: RT0603BRD0745K3L / C861415 and RT0603BRD07121KL / C861095; live orderable stock 25,611 and 4,900, unit prices $0.0432 and $0.0478. No purchase.
- PCB RAM at (30,9) mm. Four unrouted front components and four unrouted backside capacitors relocated. CPU, crystals and all 1,708 prior copper items preserved. Added 65 short RAM escapes plus 65 through-vias. New eight-capacitor VDD1 bank placed on reverse side.
- 1,776 PCB pad dispositions match the integrated contract. The 13 display pads remain missing. Original DDR3 PCB is untouched.
- Current PCB DRC: 65 dangling RAM vias, one existing PMIC neck width issue, and silkscreen findings. No shorts, copper-clearance or courtyard-overlap findings. Whole-board unconnected reporting reaches the 499 display cap; this is not a routed board.
- Wi-Fi converter, module supply, grounds, local buck, VDDIO and LPO continuity checks still pass after plane refill. They do not prove power integrity or RF performance.
- Isolated RAM coupon: 65 signal dogbones at 0.10 mm line/space and 0.45/0.20 mm vias. CPU corner coupon: five constrained signals at 0.0762 mm line/space, with vias staggered to preserve hole clearance. Its only five DRC findings are intentionally dangling vias. Neither coupon proves full simultaneous CPU-to-RAM routing.
- Scoped PCB rules permit 0.10 mm RAM escape geometry, while retaining 0.20 mm width checking elsewhere. The existing 0.127 mm PMIC neck must still be reported; the audit explicitly checks this. No DRC exclusions added. CPU 3 mil geometry has NOT been applied to the integrated PCB rules.
- Selected-component subtotal: $79.7063 from mixed-date catalog snapshots; only newly selected RAM/bypass/divider refreshed in this work. This is not an assembled-board quote and excludes fabrication, assembly, procurement minima, shipping and taxes. The EUR50 budget is not achieved or asserted.

Rebuild with `python3 hardware/phoenix-g1/tools/rebuild_lpddr4_candidate.py` from the repository root. Uses the installed KiCad and existing `/tmp/phoenix-eda-venv`; it does not install dependencies or order anything. The rebuild removes the prior checkpoint manifest first and writes a new one only after checks pass.

Remaining critical work: final land/paste/process qualification, simultaneous CPU and complete DDR routing, power/ground escape and reference-plane review, impedance and package-aware timing constraints, PMIC dynamic/load/sequencing qualification, display footprint and full-board completion, loader training and physical tests. The public RK3562 datasheet/reference establish connectivity but no RK3562-specific routing/timing guide was obtained in the latest search; rules from other processors must not be treated as validated RK3562 limits.

---

# Phoenix RK3562 — LPDDR4 1 GB migration

User-approved design direction, 2026-11-10: one LPDDR4 package targeting 1 GB, compact placement, non-touch color display and board-mounted five-way control. Retain passive cooling and USB-C device operation. Exterior 85 × 35 mm remains a mechanical target, not a validated enclosure dimension.

Candidate: H9HCNNN8KUMLHR-NME / JLC C2912103. Exact part is not yet qualified. Latest saved stock snapshot: ../../sourcing/ddr4-lpddr4-stock-2026-11-10.json. Do not interpret technology choice as a manufacturer longevity guarantee.

The candidate datasheet specifies 8 Gbit total, two x16 channels, one chip select per channel, 200 balls, 10 × 15 mm body, pitch 0.8 × 0.65 mm. Supplies: VDD1 1.8 V; VDD2 and VDDQ 1.1 V. Do not copy LPDDR4X 0.6 V supplies.

`signal-map.csv` maps 67 signals from the actual RK3562 manufacturer pin CSV to the candidate ball table. Generated by ../../../tools/build_rk3562_lpddr4_candidate.py (resolve from repository tools directory if moving this file). Assertions check unique RAM balls and presence of every mapped SoC function. Six second-rank controller functions remain intentionally unmapped for this single-rank candidate. This is a documentary draft, not a completed schematic. The full 200-ball map and isolated memory schematic are now generated; supply sources and decoupling remain incomplete.

The previous project-wide LPDDR4 study is RK3568-specific and must not be used for RK3562 ball numbers. Existing DDR3 CAD remains recoverable and unchanged by this study.

Compactness: the new body occupies 150 mm². Board area savings cannot be inferred from body area alone: bypass capacitors, BGA escape, power and routing determine the final envelope. Concentrate RAM near CPU, preserve byte-lane groups and keep enclosure/display/control constraints explicit.

Rockchip documents LPDDR4 support in RK3562 DDR tooling, but this does not establish successful training for the exact Hynix component on this PCB. No physical tests or electrical simulation performed.

Sources:
- https://github.com/rockchip-linux/rkbin/blob/master/doc/release/RK3562_EN.md
- https://github.com/rockchip-linux/rkbin/blob/master/tools/ddrbin_tool_user_guide.txt
- https://datasheet.lcsc.com/datasheet/pdf/8c6bc79fc4ddd7e4f398b954dcc5c828.pdf?productCode=C2912103
- Local reference/rk3562-datasheet-v2.1.pdf

## Implemented candidate artifacts

- `ball-disposition.csv`: 200 balls, including 12 DNU and 10 NC.
- `Phoenix_LPDDR4_Draft.pretty/`: draft 200-pad footprint; 0.30 mm land diameter remains provisional.
- `kicad/lpddr4-memory-candidate.kicad_sch`: isolated four-unit RAM sheet plus ZQ resistor.
- `review/netlist-audit.json`: exported KiCad netlist checked against 202 pin dispositions; independent ZQ-to-VDDQ assertion.
- `power-migration.json`: proposed BUCK5/BUCK3 sources and divider static tolerance screen; no sourcing or transient qualification.

Rendered schematic inspected. The initial generated ZQ-to-ground connection inherited from DDR3 was corrected before this candidate checkpoint: Hynix section 4.32.2.1 explicitly requires ZQ to VDDQ. The independent audit now enforces this distinction.

ERC after cleanup: 93 unresolved findings (67 isolated signal labels, 23 undriven inputs, 3 undriven supply nets). These reflect an isolated RAM sheet, not a finished circuit. No suppressions or power flags added. Off-grid and library/footprint link findings have been resolved. KiCad parses the 200-pad footprint with the expected missing rows L/M and columns 6/7.

## Integrated system candidate checkpoint

`system/kicad/integrated/phoenix-g1.kicad_sch` is a separate 42-sheet whole-system candidate, generated by `tools/integrate_rk3562_lpddr4_candidate.py`. It replaces the two-device DDR3 sheet with the single LPDDR4, remaps 67 CPU signals, changes the DDR rail to 1.1 V, changes the BUCK3 divider candidate to 45.3k/121k and feeds memory VDD1 from +1V8_SYS. Divider parts remain unselected; old MPN annotations are removed. The original PCB and DDR3 hierarchy are not overwritten.

The manufacturer RK3562 reference (local rk3562-oomwoo-reference.pdf, visually inspected sheet5) confirms VDDQ and VDDQL at 1.1 V in LPDDR4 mode and PHY RZQ 120 ohm pulled up to VCC_DDR. R1503 is now pulled to +1V1_LPDDR4 and the previously pending CPU ball 1D4 is connected. This differs from DDR3; RAM ZQ is separately 240 ohm to VDDQ.

Added VDD1 bypass candidate: C2301–C2308, 2 x 10u and 6 x 100n based on reference sheet13. Existing 0805/0402 MPNs are reused to avoid inventing a qualified small package; their area and DC-bias behavior remain to be reviewed. Live stock refresh confirmed C1525: 24,289,531 at $0.0031; C15850: 6,737,472 at $0.0315; RAM C2912103: 155 at $26.5722. Costs exclude assembly and procurement minimums. Eight added capacitors total $0.0816 at these unit prices.

Independent exported-netlist audit passes all 1,596 connected pin contracts, all 67 CPU/RAM signal pairs and both calibration networks. 1,789 pin dispositions including NC. No legacy U3 or DDR3 signal/1.5 V nets remain in this candidate. This is connectivity verification, not physical/electrical qualification.

Remaining memory decisions: six unused CPU memory signals are explicitly PENDING, ODT strap versus controller drive must be finalized against loader behavior, existing 1.1 V bypass bank requires requalification, PMIC startup/shutdown and load budget remain unverified. No board routing migration has occurred yet.

Integrated ERC still has 24 findings: {'isolated_pin_label': 8, 'footprint_link_issues': 1, 'power_pin_not_driven': 15}. No waivers added; ERC is not clean and no fabrication release is implied.
