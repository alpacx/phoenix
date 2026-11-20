# Parallel independent layout — 2026-11-18

Frozen source: `baseline/source.kicad_pcb`, SHA `bdeb44f58dea3d0261469c1d3f7eeb5a9e6df03e95648710393c9e09c83f6aeb`.
Do not replace the main checkpoint with this file: other parallel branches require integration.

## Accepted CAD-only additions

Latest candidate: `ground-returns-three.kicad_pcb`, SHA
`ef81c2ed49ea43fe43fdad822bc91c5d76b4d84bcb3552ce7afd79023e2dc8d8`.
Three successive stages add **38 GND segments, all 0.3 mm**, no new vias,
no changed existing copper/footprints/pad nets/design rules. Nineteen existing
capacitor ground pads are now continuous with reference C435.2:

- Stage 1: C466, C468, C469, C465, C467, C463, C464.
- Stage 2: C1663, C1665, C1668, C1669, C1676, C1502, C1503.
- Stage 3: C1649, C1654, C1671, C1678, C1646.

Every stage has zero introduced DRC violations and preservation checks.
18 CAD tests (three suites) cover accepted candidate, baseline rejection,
reduced trace width, deleted added trace, changed original copper and changed
footprint placement. `apply-test.json` additionally checks full-delta application
and rejection of repeated application.

## Integration

`delta.json` describes only added tracks and nineteen connection checks.
Import `parallel_control_apply_delta.apply(board)` from `hardware/phoenix-g1/tools`.
It preserves delta UUIDs and rejects duplicate/partial application; caller must
run fill, final integrated differential DRC and whole-board preservation tests.
No main checkpoint or other-agent file was edited.

## Limits

These are CAD continuity/clearance checks, not power-integrity qualification.
Decoupling return-loop inductance and final stackup remain unqualified. No
simulation, physical test or production readiness is implied. Existing return
vias/planes are reused; schematic connections are unchanged.

VDC/+1V8 joint escape was inspected but not changed. C425 pad gap and existing
+3V3_SYS via constrain a simple reroute; do not repeat historical rejected VDC
pin route. Geometry snapshot is `geometry.json`; other work was selected to
produce independently integrable progress.

## Additional frozen stages

- `lcd-dc.kicad_pcb`, SHA `8829c427754d9d59c53edf8f783c2fc70d3900f7a5c6f4cb8e1f191b66a34f04`: closes U1.N1 → U21.4/R1813.1, 33 tracks 0.2mm and 2 through vias 0.45/0.2mm. No design-rule change. Seven CAD tests plus apply/duplicate rejection. `lcd-delta.json`, `parallel_control_apply_lcd_delta.apply(board)` are integration inputs.
- `ground-vias.kicad_pcb`, SHA `0aa53e68dc55c31e844bfd5de4acaaa899b4d79c0116bdd42ba860e42fd7adf4`: five short ground returns C1670/C1659/C1653/C1648/C1660, five 0.3mm tracks and five 0.6/0.3mm vias. Seven CAD tests plus apply/duplicate rejection. No introduced DRC, no via-in-pad. `ground-vias-delta.json`, `parallel_control_apply_ground_vias_delta.apply(board)` are integration inputs.

Ground-via stage deliberately excludes C1661/C1674/C2301, reserved by root for
H8104 relocation. Both stages preserve every existing copper object and pad net.
The root integrates these deltas with concurrent mechanical/PHY work; don't
replace the integrated main board by the independent candidate.

MDIO exploration produced no accepted candidate. At existing 0.2mm width the
U1.AC2 surface escape search remains enclosed (49 cells, zero valid through-via
sites). U5.14 is on the **east** edge; its outward corridor is constrained by
the existing +3V3 route to R515/C516. No widths or clearances were weakened.
`parallel_control_mdio_soc.py` / `parallel_control_mdio_phy.py` are rejected
exploration scripts, not production stages. Revisit with coordinated PHY
power placement, not repeated identical escape searches.

- `ram-ground-vias.kicad_pcb`, SHA `55e20dbd6d145a94482c055849b55b8de0a2b332f55f4ac3445a49ac6569a38d`: 7 ground returns C1666/C1657/C1658/C1667/C1672/C1650/C1664. Seven 0.3mm tracks, seven 0.6/0.3mm through vias outside component pads. Delta/apply pair: `ram-ground-vias-delta.json`, `parallel_control_apply_ram_ground_vias_delta.apply(board)`.
- `middle-ground-vias.kicad_pcb`, SHA `75e1b85c569a2619f37e2c418d7868b897cee2f1b490602a80f9bb47f2281545`: 13 ground returns C1633/C1673/C1624/C1656/C1651/C1619/C1652/C1620/C1675/C1655/C1662/C1623/C1647. Thirteen 0.3mm tracks, thirteen 0.6/0.3mm through vias outside component pads. Delta/apply pair: `middle-ground-vias-delta.json`, `parallel_control_apply_middle_ground_vias_delta.apply(board)`.

Both final stages have zero introduced DRC, complete original copper/pad-group
preservation, seven CAD tests each plus successful delta application and
repeated-application rejection. Original rules and placements remain unchanged.
Total independent branch progress: **44 GND returns plus one LCD_DC connection
merging two old net groups (two endpoint pairs checked)**. All stage data is
frozen for root integration. Do not re-run generation tools over accepted files
while root integrates: new copper UUIDs would invalidate exported deltas.
