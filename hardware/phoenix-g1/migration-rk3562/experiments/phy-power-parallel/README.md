# PHY joint SW geometry — isolated, electrically unqualified

This experiment freezes compact-corridor source `21c11942a68f62c506769caed42e84f3358d85e159f8b7bc2ba2f87e9014b30f`. No main board, main checkpoint or original compact study was modified.

`checkpoint.json` selects joint-002 for **geometry study only**. Its SW trunk and output branch remain 1.55 mm, clearance rules remain unchanged, input corridor remains 1.05 mm. RXCLK resistor return is relocated to the already-tested main-route corridor ending at (66.15,30.125), maintaining 0.20 mm track and 0.45/0.20 mm via. The output branch termination is offset 0.15 mm within L501 pad 2; this removes the 0.10 mm inter-branch clearance failure without narrowing either branch.

Joint-001 exposed a further clearance to U5 NC pad31 (0.0735 mm). Joint-002 moves the broad SW trunk outward/upward and extends the existing exploratory pin fanout. This removes all new DRC errors, but the 0.20 mm QFN neck is 0.707 mm long and **does not satisfy the historical >60 mil whole-path guidance**. No permission/derogation to that guidance is inferred. Do not promote this route as qualified power layout.

Verification: zero new DRC violations; 2,006 pad instances and 5,810 unreplaced tracks/vias preserved; 71 original connected pad groups preserved; no new mechanical reservation conflicts. U5.30→L501.1, L501.2→C511.1, R522.2→C515.2 and C515.1→C517.1 connectivity passes. Six subprocess tests exercise nominal routes, intentional width reductions, SW/output disconnections and mandatory qualification hold.

Rebuild with KiCad Python:

```
python3 hardware/phoenix-g1/tools/parallel_phy_sw_joint.py --case joint-rebuild
python3 hardware/phoenix-g1/tools/parallel_phy_test_joint.py
```

Use KiCad bundled Python, not generic system Python. Test script checks frozen joint-002 hash; rebuild receives new UUIDs and has its own report. Each report compares actual geometry with the frozen baseline. Existing baseline DRC items remain; “zero new” does not mean production-ready.

Remaining electrical holds: applicable Realtek fanout guidance, compact inductor saturation/DCR/ripple, effective C515 capacitance at 3.3 V (component review indicates strong DC bias reduction), and remaining input/load feeds. No simulation or physical test has been performed. No BOM adoption, purchase or manufacturing release.

## Follow-up component and feed probes

`variant-16v.json` records a second geometry-passing, six-test-passing candidate using CL10A475KO8NNNC (C19666) for C515, with unchanged 0603 footprint. Component-review Samsung numeric curves indicate 3.2694 µF typical at 3.3 V; this is an improvement over approximately 2.10 µF for C1705, **not** a guaranteed effective minimum or validation of regulator stability. Rebuild using `--bulk-16v --case joint-16v-rebuild`. Test via `PHOENIX_PHY_TEST_VARIANT=joint-16v`.

The 0805 candidate CL21A475KAQNNNE (C1779) was physically substituted in `runs/joint-0805` and rejected: GND copper at y=23.3 and courtyards R509/R1002/R516 interfere. Do not treat it as a drop-in. `bulk-0805-review.json` lists the required surrounding layout changes.

Two explicitly drawn full-width F.Cu feed candidates are retained as rejected evidence: `feed-front` (R530 to C515,1.05 mm,19 new violations) and `load-front` (C511 to C512,1.55 mm,84 new violations). These specific paths intersect existing oscillator, buck feedback, bypass and strap copper. They do not prove that all possible F.Cu paths are impossible. Do not repeat them or adopt them. `parallel_phy_feed_probe.py` reproduces both without modifying the baseline or reducing widths.

## Post-inductor distribution geometry

`load-checkpoint.json` records C511.1→C512.1 continuity via a full 1.55 mm In3.Cu corridor and two 0.60/0.30 mm through vias at each end. The north2 path avoids the CPU via at (56.5,28.5) found by the north1 probe; the southern path remains rejected due to oscillator/ground vias. No new traces are placed on In1/In4 ground planes. Zero new DRC violations, all 5,822 incoming copper items and 72 connected pad groups preserved, no new mechanical conflicts. Six tests include width reduction, cutting either via array, ground-plane role and mandatory qualification holds.

This is **post-inductor distribution**, not a relaxation of the unresolved REG_OUT/DVDD33 local no-via/width guidance. Via current capacity, power integrity, return paths, thermal performance and pad-overlap/filled-via assembly requirements remain unqualified. No fabrication release. `parallel_phy_feed_probe.py load-in3-north2` rebuilds this geometry; `parallel_phy_test_load.py` checks it.

### Additional bypasses

`load-c514-checkpoint.json`: extends the In3 1.55 mm distribution to C514/U5.21, with two 0.60/0.30 mm load vias. Six tests pass; zero new DRC, all incoming copper preserved. The earlier y=29.0/29.1 paths fail against the RXCLK GND via; final trunk y=28.9 gives 0.225 mm nominal clearance.

`load-c513-checkpoint.json`: moves previously disconnected C513 from its remote position to (65.4,34.5), beside U5.8, preserving pad identities and nets. Replaces only its two explicitly identified disconnected ground-stub segments. Adds the 1.55 mm In3 branch and two 0.60/0.30 mm vias, a 0.20 mm F.Cu pin fanout, and a 0.20 mm local GND return with a 0.45/0.20 mm via. Both C513 terminals are verified connected, including U5.8→C513.1 and C513.2→existing GND. Zero new DRC and six tests pass; mandatory fanout/current/PI/via-overlap holds remain. Courtyard placement is tight between U5 and U22; manufacturability remains to be reviewed. The rejected vertical and first horizontal placements are retained in c513/c513b reports.

No main/BOM adoption has occurred. The latest geometry candidate is an isolated study, not a replacement for the main checkpoint. C522/U5.38 and upstream input feed remain incomplete.

## Rebuild and C522 blockers

`rebuild-verification.json` confirms a fresh C513d rebuild matches all footprint identities/placements, pad UUIDs/nets/sizes and track/via geometry (generated copper UUIDs and zone serialization excluded). Fresh DRC/preservation/connectivity also pass. Rebuild does not overwrite the selected study: set `PHOENIX_PHY_OUTPUT_CASE=rebuild-c513d` when calling its builder.

C522 studies `c522-clock` and `c522-clock2` remain rejected. The first relocates the capacitor behind the board and replaces XOUT, but collides with Y501 pad, the existing +5V_MAIN trunk on In2, and clock copper. The second also replaces the B.Cu XIN branch at its original 0.20 mm width; single-via escape and broad power still collide with the local ground/clock corridor. Neither candidate is selected. Clock loading/loop geometry and any changed via strategy would require qualification even after geometric success. Moving C511 local return or the upstream 5V corridor would be a broader joint change; no such change was made here.

## Sequential continuation — 18 November, 16V bulk carried forward

`load-c513-16v-checkpoint.json` is the latest isolated geometry variant. It carries the previously studied C515 CL10A475KO8NNNC into the C513 bypass/distribution candidate. No copper geometry or footprint placement changes were made in this variant. DRC introduces no violations; preservation and nine required connectivity checks pass. Six load tests pass, including deliberate route narrowing and disconnections. Current public C19666 lookup: $0.015, presale 2503304 / overseas 3310825; not assembly allocation. Typical 3.2694uF at 3.3V is not a guaranteed minimum or stability qualification. No main-board/BOM adoption.

New `input-in2-001` upstream feed probe was rejected: full 1.05mm inner route collides with +3V3_IO and WIFI_BUCK_OUT; entry/exit also collide with the oscillator ground and CPU_BUCK_EN. Do not run the untried `input-in2-002` as a proposed fix: moving the middle path does not solve endpoint conflicts. The input needs a joint redesign of the existing R530 entry and C2007/Y2001 ground corridor and a different C515 via escape. R530 input pad is already connected, so moving it without restoring its incoming branch is not acceptable. No reduced widths or clearance rules.

## Upstream PHY supply and pin 38, 19 November

The isolated board in `phy-upstream-verified.json` supplies C515 from R530 with 1.05 mm copper. The new In2.Cu route totals 27.44 mm including the array connections. The oscillator supply and ground branches were rerouted. The audit compares the saved board with input-ground-local-002, checks pad groups and explicit copper replacements, and finds no new DRC items or mount conflicts. Removing either single via at either end retains connectivity. Removing both vias at either end interrupts the feed. Review DC drop, transient response, oscillator return, and capacitor land/via manufacturability before adoption. The compact inductor and effective capacitance remain subject to electrical qualification.

Reproduce the upstream path with `phy_offset_link.py --reroute --array --ground reuse`, `phy_bulk_corridor.py --detour --east`, then `phy_verify_bulk.py`. Use the KiCad Python interpreter for these scripts and a Python 3 interpreter with Shapely on PATH for the grid search.

The downstream experiment reroutes the oscillator input/output at their inherited widths. The pin-38 via connects to a rear C522 bypass in `c522-local-bypass.json`. Its return reaches an existing ground via. That stage still requires a supply branch from C511. Clock loading, bypass-loop inductance, and clearances under assembly tolerances remain to be qualified.

The subsequent integrated candidate in `c522-verified.json` also connects C511 to C522 and PHY pin 38. C522 is on the rear at (61.3,32.1). Its ground terminal connects to an existing return via. The new rear 1.55 mm branch reaches the existing C513 via pair. Cutting either individual via preserves the C522 supply and cutting both opens it in the CAD connectivity graph. The 0.20 mm local pin escape, changed crystal routing and return length require electrical review. Pin continuity and geometric checks do not qualify regulator stability.

The reproducible chain after the upstream route is `phy_pin38_escape.py`, `phy_c522_rear.py --local --new-return --wide`, `phy_c522_joint_sites.py`, `phy_c522_return.py --joint`, then `phy_verify_c522.py`.
