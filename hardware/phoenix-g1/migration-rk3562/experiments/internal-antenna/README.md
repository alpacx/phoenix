# Internal antenna — candidate, not integrated

User approved internal dual-band antenna on 2026-11-18. RK3562 and AP6256 remain unchanged. No purchase/order/commit/push.

## Selection and cost

Pulse W3006, JLC C5123155. Public lookup: USD 0.9074 at 1+, presale 623, overseas 625. These fields do not guarantee allocated PCBA stock. Snapshot: ../../../../sourcing/public/C5123155.json. Johanson C17489534 rejected for current selection because both public stock fields were zero despite search-index stock claims.

Antenna body 10 x 3.2 x 1.5 mm; this is not the required RF area. Manufacturer issue2137 layout1 covers 2.4/5GHz. Page6 has layer-specific openings, with a conservative envelope 14.15 x 7.4 mm. The footprint contains land pads only: it MUST NOT be placed without separately implementing the RF clearance polygons. No ground on support pad2. No RF performance has been measured on Phoenix.

## Circuit

Standalone kicad/internal-antenna.kicad_sch replaces the existing RF selection concept, not an extra sheet to attach unchanged. R2001 represents the EXISTING external selector, not a second component with that reference. Default R2005 fitted, R2001 DNP. External assembly variant reverses these. Never fit both. R2006 is series tuning; C2010 is optional shunt DNP; L2002 1.5nH is only the manufacturer's initial matching value. RF-qualified MPN and final values remain open. Selection must sit at the physical branch, avoiding an open RF stub. Existing R2001 placement is not accepted as final RF placement.

## Verification

KiCad netlist export succeeded. check_internal_antenna.py verifies five named nets, floating support pad and DNP choices. ERC has one unsuppressed isolated-label warning on the external output, expected in this standalone fragment. No full-system ERC claim.

screen_internal_antenna.py checked 204 edge windows against component bounds on both faces and routed copper. All need relocation; minimum-conflict windows overlap J2 Ethernet and are unsuitable. Screen is conservative, 1mm pitch, does not prove every possible arrangement impossible. Ground zones and case/heatsink must also be reviewed. No existing copper, hole or component was moved.

## Remaining integration

Resolve a real edge RF window without violating power/DDR/USB constraints. Integrate the circuit into the active schematic and deterministic rebuild chain, update assembly alternatives and BOM, route controlled-impedance feed, implement layer-specific clearance, and review enclosure/thermal metal. Then check netlist/PCB agreement, ERC/DRC deltas and mechanical clearances. RF matching and radiated tests in the final enclosure remain physical validation requirements.

Current active board remains pmic-ldo-inputs/pcb/parallel-local-copper.kicad_pcb (sha256 recorded in review/edge-placement-screen.json). Do not promote this candidate as an assembled or working antenna.

## Reproduce

Run build_internal_antenna.py with a sexpdata-capable Python (temporary environment /tmp/phoenix-antenna-venv was used); export KiCad XML netlist to review/netlist.xml; run check_internal_antenna.py. Run screen_internal_antenna.py with KiCad Python. Generator never rewrites the active board. Source: https://productfinder.pulseeng.com/doc_type/WEB301/doc_num/W3006/doc_part/W3006.pdf
