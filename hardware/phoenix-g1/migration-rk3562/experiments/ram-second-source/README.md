# DDR3 second-source investigation — 2026-11-10

Status: documentary candidate only; no BOM, schematic or PCB substitution.

## Procurement snapshot

Prices USD per chip, first quantity tier, excluding assembly, freight and taxes. Stock is a point-in-time observation, not a reservation or longevity commitment.

| Candidate | JLC code | Orderable chips | Unit USD | Two-chip 512 MB total USD |
|---|---|---:|---:|---:|
| Existing Hynix H5TQ2G63GFR-TEC | C2909894 | 35 | 7.5856 | 15.1712 |
| Winbond W632GU6RB-11 | C39979278 | 1363 | 13.3565 | 26.7130 |
| ISSI IS43TR16128DL-107MBL | C17204641 | 0 | 10.4195 indicative | unavailable |

Winbond costs USD 11.5418 more per board at the first tier. This is essentially the same RAM component cost as the separately researched 1 GB Hynix LPDDR4 (USD 26.5722), but changing memory technology requires a separate electrical/layout/boot qualification. No technology change is implied here.

## Documentary compatibility

Compared Winbond W632GU6RB datasheet A01, 2024-02-26, ball configuration section 5, against the x16 96-ball package map in the existing Hynix datasheet. The 16 populated rows A–T (excluding I/O/Q/S), columns 1,2,3,7,8,9, have matching signal assignments. PDF text extraction loses the Hynix overbars: differential polarities must also be visually checked before final sign-off.

Both parts are 2 Gbit x16 (256 MB each); two preserve 512 MB and a 32-bit aggregate interface. Winbond explicitly supports 1.5 V ±0.075 V as well as 1.35 V. Keep the existing 1.5 V design for this candidate; DDR3L marking is not an instruction to change the rail.

Winbond package: 96-ball VFBGA, 7.5 × 13 mm, 0.8 mm pitch. Footprint land dimensions, tolerances and paste still need manufacturing comparison against the actual project footprint. The -11 speed grade supports up to 1866 MT/s; this alone does not qualify the planned 1066 MT/s operating point, controller timings, training or boot firmware.

## Lifecycle evidence and limits

Winbond's 2026 product selection guide lists the exact W632GU6RB-11 commercial part as mass production. It does not guarantee future availability or a fixed supply period for this SKU. General DDR3 longevity statements must not be treated as a commitment for this exact part. Distributor lifecycle indications differ for related suffixes, including the industrial W632GU6RB11I; do not substitute suffixes silently.

ISSI is not an assembly-ready fallback today because the checked JLC part has zero orderable stock. The W632GU6RB-11 TR lookup failed exact-MPN validation and supplies no usable stock conclusion.

## Decision

Retain the existing BOM while listing W632GU6RB-11 as a candidate alternate. It improves current sourcing options without requiring an immediate memory-technology redesign, but is more expensive and is not yet a qualified drop-in replacement. Before adopting: verify graphical ball polarities and footprint geometry, confirm exact-part lifecycle with manufacturer documentation, qualify DDR initialization/timing and test hardware stability over operating conditions. No simulation or physical RAM test was performed.

## Evidence

- Stock: winbond-stock.json and C17204641-stock.json in this directory; existing Hynix snapshot under ../../sourcing/ddr3-stock-2026-11-10.json.
- Winbond datasheet (local W632GU6RB_A01.pdf): https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/6970/W632GU6RB_A01.pdf
- Winbond official 2026 guide: https://www.winbond.com/export/sites/winbond/product-selection-guide/file/2026-Winbond-Customized-Memory-Solution.pdf?__locale=en
- JLC candidate: https://jlcpcb.com/partdetail/C39979278
- Hynix datasheet: ../../../reference/H5TQ2G63GFR-C2909894.pdf
