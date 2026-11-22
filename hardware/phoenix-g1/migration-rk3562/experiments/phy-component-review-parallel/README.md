# Independent PHY component review — 2026-11-18

This dossier changes no CAD or BOM. It is a documentary review, not electrical qualification.

## Concrete findings

Samsung CL10A475KP8NNNC (C1705) has a part-specific manufacturer characteristic sheet, archived under `sources`. Its graph shows roughly 4.0–4.2 µF at 1 V and 1.9–2.35 µF at 3.3 V from a nominal 4.7 µF. These are approximate readings of typical 1 kHz / 1 Vrms curves, not guaranteed minima. Tolerance, temperature, aging and actual ripple remain outside this estimate. Thus C515 must not be described as 4.7 µF effective. A higher voltage rating alone is not proof of improved effective capacitance.

Realtek rev1.9 section9.1 still delegates detailed layout to the separate RTL8211F Series Layout Guide; it supplies no explicit short-neck exception to the older >60 mil REG_OUT rule. It also restricts the regulator to the PHY core supply and calls for low-ESR X5R/X7R output capacitance. The newer mirrored document is manufacturer-authored but carries a customer watermark; it is corroboration, not an independently obtained current design approval.

Fresh public JLCPCB results: C1705 presale443652 / overseas578220, initialPrice USD0.0127; C22459322 presale5863 / overseas5870, initialPrice USD0.0392. Both return assemblyComponentFlag=false. These figures do not establish immediately allocatable PCBA stock or a delivered assembly quotation.

## Decisions for the CAD work

- Keep candidate compact L501 and C511/C515 experimental; no BOM promotion based on these checks.
- Continue broad, short, same-layer power corridors and minimal pad escape, but preserve explicit unresolved qualification for the escape width.
- Do not supply other devices from REG_OUT-derived1V.
- Do not increase bulk capacitance or change inductor value simply to mask the missing regulator stability window.
- Obtain exact applicable layout guidance / acceptable pad escape and effective capacitance window before production signoff. Prototype ripple, startup and thermal tests remain necessary.

Machine-readable details and source hashes: `review.json`. Source files are retained for reproducibility.

## Current manufacturer numeric curves (supersede rough PDF readings)

The Samsung public product HTML embeds the actual typical curve samples. Those pages and extracted DC-bias JSON are archived. At25°C,1kHz,1Vrms:

| Part/JLC | Package | At1V | At3.3V | Public initial USD |
|---|---|---:|---:|---:|
| CL10A475KP8NNNC/C1705 |0603|4.206µF|2.100µF|0.0127|
| CL10A475KO8NNNC/C19666 |0603|4.512µF|3.269µF|0.0150|
| CL21A475KAQNNNE/C1779 |0805|4.696µF|approximately3.95µF|0.0343|

0805 value uses interpolation of adjacent manufacturer samples; exact result inreview.json. All are typical, not guaranteed. C19666 is the useful no-footprint-change candidate; its nominal value remains4.7µF and the PHY minimum effective requirement remains unresolved. No automatic BOM substitution. C1779 is not a geometric drop-in.

Compact-inductor screening did not establish a superior qualified drop-in: MurataDFE252012P-2R2M=P2 has84mΩ maximumDCR versus65mΩ compactMagnetsyc and costsUSD0.117; PRODTechPSTMAA3020-2R2MB is3×3mm and catalog45mΩ but lacks retrieved manufacturer qualification (USD0.134). Both publicrecords remain distinct fromPCBA allocation.
