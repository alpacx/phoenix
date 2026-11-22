# Display attachment review — 2026-11-18

No CAD or BOM is changed. The13 missing DS1 pads cannot honestly be closed by selecting a generic FPC connector.

New checks exclude Hirose FH12-8S-0.5SH(55) and XUNPU FPC-05F-8PH20 as direct mates for the previously investigated C08 panel: their required exposed-contact and stiffener lengths exceed the panel dimensions. HS096T01H13 retains the same problematic13-contact flex architecture. XUNPUH15 is on hold because its publicPDF is invalid; XYECONN is on hold because a mating drawing was not retrieved. Previous exclusions were read, not retried.

A complete Waveshare0.96inchLCDModule(SKU15868) avoids custom bonding by purchasing the already assembled display board. Official documentation gives32.5×26mm, ST7735S160×80,3.3V/5V supply with matching logic, andPH2.0 8-pin interface. The manufacturer schematic is archived. This preserves the color non-touch display and separate command, but requires mechanical and power-interface changes; direct listedprice isUSD6.99 and JLC availability for this exactmodule was not established. It is a documented fallback, not a selectedBOMpart.

The production path remains blocked on documented mating/bonding for the exact rawpanel or a qualified alternativemodule. Samples and mounting verification remain necessary even after documents match. No party contacted and no order placed.

`review.json` contains exact candidate reasons, source pages, decision limits and hashes. `sources/*.json` contains fresh publicJLC observations, not reservedPCBAstock.

Schematic visual check: J1 and J2 use reversed pin numbering. BL is a logic input through1kΩ to an S8050 base, with10kΩ pull-up toVCC: floatingBL can turn the backlight on. Preserve reset-off via active low control or switched modulepower; do not assume existing rawpanel driver maps directly.
