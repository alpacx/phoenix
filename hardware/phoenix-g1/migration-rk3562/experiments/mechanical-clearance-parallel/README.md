# Mounting clearance study — 18 November 2026

Source is the frozen main board bdeb44f58dea3d0261469c1d3f7eeb5a9e6df03e95648710393c9e09c83f6aeb.

Five previously unrouted resistors were relocated without modifying any original copper or net: R2014 front (23,6.125), R521 back (67,28.5), R525 back (69,28), R526 back (71,29), R527 back (73,29.5), coordinates in mm. These positions clear the H8103/H8105 body reservations. Signal fanout and RGMII timing are not thereby qualified.

`parallel_mechanical_clearance.py` rebuilds and verifies placement. `parallel_mechanical_hole.py` adds H8105, an M2 2.2 mm NPTH at (70,34), only after both-side pad/courtyard clearance. Existing 5.4 mm screwhead/body reserve is unchanged. The final hole candidate has no additional DRC violations, preserves all 2006 original pads and 5774 original copper objects, and preserves 70 connected pad groups.

`parallel_mechanical_test.py` has five positive/fault-injection cases: valid geometry, component obstruction, wrong drill, shifted hole and tracks permitted in the reservation. All pass. Main integration also receives an independent DRC and regression suite.

The mounting screen now excludes each hole footprint from its own reservation; the three historic self-matches were not physical obstructions. No other matches are suppressed. H8104 remains blocked by actual components. Screw length, spacer tolerance, case, assembly sequence and thermal solution are unqualified; no production readiness is claimed.

Rejected preliminary placement: R521 B(67,26), R526 B(71,28), R527 B(73,28) collided with U25 courtyard/pads and GND tracks/vias; not adopted. Current accepted positions preserve R525 B(69,28). No copper width or clearance was reduced.
