"""Screen the base-board input budget on a saved RK3562 PCB (KiCad Python)."""
import hashlib
import json
import re
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "migration-rk3562/experiments/phy-power-parallel"
CHECKPOINT = LAB / "layout-pmic-image-c468.json"
OUTPUT = ROOT / "migration-rk3562/review/usb-1a5-screen.json"


def main():
    checkpoint = json.loads(CHECKPOINT.read_text())
    path = LAB / checkpoint["board"]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == checkpoint["sha256"]
    board = pcbnew.LoadBoard(str(path))
    board.BuildConnectivity()
    def pad(label):
        ref, pin = label.split(".")
        return board.FindFootprintByReference(ref).FindPadByNumber(pin)

    groups = {}
    for first, second in checkpoint["verified_pairs"]:
        if first not in groups:
            groups[first] = {item.m_Uuid.AsString() for item in
                             board.GetConnectivity().GetConnectedItems(pad(first))}
        assert pad(second).m_Uuid.AsString() in groups[first], (first, second)

    expected = {"U6.25": "CC_OUT1_N", "U6.26": "CC_OUT2_N",
                "U14.1": "CC_OUT1_N", "U14.2": "CC_OUT2_N",
                "U14.4": "USB_CURRENT_OK", "U15.2": "USB_MAIN_ENABLE",
                "U15.7": "USB_ILIM", "R1201.1": "USB_ILIM",
                "C1202.1": "USB_DVDT"}
    assert all(pad(pin).GetNetname() == net for pin, net in expected.items())
    assert board.FindFootprintByReference("R1201").GetValue() == "806R 1%"
    assert board.FindFootprintByReference("C1202").GetValue().startswith("22n")
    caps = {}
    for fp in board.GetFootprints():
        if not re.fullmatch(r"C[0-9]+", fp.GetReference()):
            continue
        if {p.GetNetname() for p in fp.Pads()} != {"+5V_MAIN", "GND"}:
            continue
        value = re.match(r"([\d.]+)([nu])", fp.GetValue())
        assert value, fp.GetReference()
        caps[fp.GetReference()] = float(value[1]) * (0.001 if value[2] == "n" else 1)
    total = sum(caps.values())
    prior = json.loads((ROOT / "review/usb-power-budget.json").read_text())
    slew = prior["startup_typical"]["slew_v_per_ms"]
    scenarios = []
    for vin in (5.0, 4.75):
        for efficiency in (0.85, 0.90):
            wifi_input = 3.584 / efficiency
            scenarios.append({"assumed_board_input_v": vin, "assumed_wifi_efficiency": efficiency,
                              "wifi_input_a_at_assumed_1a_radio_peak": round(wifi_input/vin, 3),
                              "remaining_input_w_for_all_other_loads_and_losses":
                                  round(vin*1.5 - wifi_input, 3)})
    # Compare discrete RILM values with the same first-order tolerance model
    # as check_usb_power_budget.py. AON bypasses the main switch.
    limits = []
    for resistance in (806, 1620, 1690, 1740):
        low = (2000/(resistance*1.01) + 0.04) * 0.925
        high = (2000/(resistance*0.99) + 0.04) * 1.075
        limits.append({"rilm_ohm": resistance,
                       "main_limit_low_a": round(low, 3),
                       "main_limit_high_a": round(high, 3),
                       "input_current_left_for_aon_at_high_limit_ma": round(1000*(1.5-high), 1)})
    # Pin the models to the populated parts, not the earlier RK3568/DDR3 BOM.
    selected = {ref: board.FindFootprintByReference(ref).GetValue()
                for ref in ("U1", "U2", "U5", "U25", "U8001")}
    assert selected == {"U1": "RK3562", "U2": "H9HCNNN8KUMLHR-NME",
                        "U5": "RTL8211F-CG", "U25": "AP6256",
                        "U8001": "KLM8G1GETF_B041_DRAFT"}
    # SK hynix rev 1.1 p.198: IDD4R1/2/Q, burst read only.
    # Samsung Table 32: max RMS over 100 ms, x8 HS400; not instant peaks.
    storage_w = 3.3 * 0.050 + 1.8 * 0.180
    read_cases = {"3200": (0.016, 0.300, 0.340),
                  "3733": (0.018, 0.345, 0.368)}
    combined = []
    for speed, (idd1, idd2, iddq) in read_cases.items():
        ram_w = 1.8 * idd1 + 1.1 * (idd2 + iddq)
        for vin in (5.0, 4.75):
            for eta in (0.85, 0.90):
                # Effective end-to-end conversion assumption for each modeled
                # rail. Board-input residual still includes unmodeled losses.
                occupied = (3.584 + ram_w + storage_w) / eta + vin * 0.010
                combined.append({"dram_read_test_mt_s": speed, "assumed_vin_v": vin,
                                 "assumed_conversion_efficiency": eta,
                                 "dram_rail_power_w": round(ram_w, 4),
                                 "modeled_input_power_w": round(occupied, 4),
                                 "unallocated_input_w": round(vin*1.5 - occupied, 4)})
    # Compare the main-branch load with U15, independently of the port budget.
    # Taking VMAIN = board input voltage is optimistic: series drops reduce
    # the voltage at the downstream converters and increase their input current.
    branch_cases = []
    for case in combined:
        vin = case["assumed_vin_v"]
        modeled_a = case["modeled_input_power_w"] / vin
        branch_cases.append({
            "dram_mt_s": case["dram_read_test_mt_s"], "assumed_vmain_v": vin,
            "efficiency": case["assumed_conversion_efficiency"],
            "modeled_main_a": round(modeled_a, 4),
            "remaining_main_w_at_low_limit": {
                str(row["rilm_ohm"]): round(vin * (row["main_limit_low_a"] - modeled_a), 3)
                for row in limits if row["rilm_ohm"] != 806},
            "remaining_main_w_at_ti_1780_ohm_low_limit": round(vin * (1.09 - modeled_a), 3)})
    # The upstream guard includes both main and always-on output current.
    # Small loads tied directly to VBUS_RAW and U24 bias bypass that reading.
    assert board.FindFootprintByReference("R1905").GetValue() == "33.2k 1%"
    for label, net in {"U24.9": "VBUS_RAW", "U24.4": "VBUS_PROTECTED",
                       "U24.17": "VBUS_GUARD_ILIM", "R1905.1": "VBUS_GUARD_ILIM",
                       "R1905.2": "GND"}.items():
        assert pad(label).GetNetname() == net
    monitor_pad = pad("U24.19")
    monitor_copper = [item for item in board.GetConnectivity().GetConnectedItems(monitor_pad)
                      if isinstance(item, pcbnew.PCB_TRACK)]
    assert not monitor_copper
    guard_screen = {
        "reference": "reference/tps25940-official.pdf sections 7.5, 9.3.6 and equation 4",
        "fitted_rilim_kohm": 33.2, "typical_limit_a": round(89 / 33.2, 3),
        "ideal_rilim_for_1a5_nominal_kohm": round(89 / 1.5, 3),
        "qualification": "Nominal 1.5 A is not a worst-case ceiling. TI lists 42.2 and 88.7 kohm test points surrounding this resistance; neither establishes a guaranteed trip range for an intermediate value.",
        "two_stage_drop_case": {
            "assumed_guard_a": 1.5, "assumed_main_a": 1.2,
            "assumed_board_input_v": 4.75,
            "guard_drop_v_at_64_mohm": 1.5 * 0.064,
            "main_drop_v_at_53_mohm": 1.2 * 0.053,
            "vmain_before_trace_losses_v": round(4.75 - 1.5 * 0.064 - 1.2 * 0.053, 4),
            "basis": "High RON at up to 125 C, imposed currents. Excludes board interconnect, transient and converter dropout."},
        "monitor_on_current_board": "U24.19 IMON has no routed track; use an external VBUS current measurement for first-board characterization.",
        "optional_monitor_study": {
            "assumed_rimon_ohm": 8200, "assumed_current_a": 1.5,
            "typical_signal_v": round(52.3e-6 * 1.5 * 8200, 3),
            "scope": "Candidate lab probe only; gain-only nominal voltage, offset and resistor tolerance excluded. No ADC, pad or component committed to PCB."}}
    report = {"checkpoint": str(path.relative_to(ROOT)), "sha256": digest,
              "verified_pairs_rechecked": len(checkpoint["verified_pairs"]),
              "scope": "Static screen based on pad net assignments, not completed routing or measurements",
              "typec_gpio_source": "reference/hd3ss3220.pdf, pin functions SDA/OUT1 and SCL/OUT2 (UFP GPIO mode)",
              "present_enable": "U14 NOR(OUT1, OUT2) accepts high-current advertisement only",
              "candidate_current_qualifier": "Invert OUT1 to accept 1.5 A and 3 A; retain downstream attach/readiness checks; do not enable on default current",
              "main_switch_current_limit_nominal_a": round(2000/806 + 0.04, 3),
              "limit_scope": "U15 excludes always-on loads; changing the CC decoder alone does not enforce the 1.5 A input target",
              "main_nominal_caps_uf": dict(sorted(caps.items())), "total_nominal_uf": round(total, 2),
              "typical_cap_charge_ma": round(total*slew, 2),
              "ramp_scope": "Capacitance directly assigned to +5V_MAIN on this PCB; excludes regulator startup and tolerance",
              "wifi_scenarios": scenarios,
              "parts_on_checkpoint": selected,
              "combined_load_scenarios": combined,
              "scenario_sources": {
                  "dram": "experiments/lpddr4-1gb/H9HCNNN8KUMLHR.pdf p.198, IDD4R read pattern, two speed bins evaluated separately. Not measured gateway traffic or boot current.",
                  "emmc": "reference/samsung-klm8g1getf-b041.pdf section 9.1 table 32, 8 GB: VCC 50 mA, VCCQ 180 mA. At board nominal rails: 0.489 W; HS400 x8, 100 ms RMS ratings do not establish instantaneous peak.",
                  "lcd": "Nominal 10 mA backlight branch only, logic and driver excluded.",
                  "usb": "reference/hd3ss3220.pdf active CC and SS mux 0.7 mA typical, 0.9 mA maximum under specified test conditions. Count in remaining AON/system budget, not as entire AON load.",
                  "phy": "RTL8211F datasheet section 7 ALDPS: link-down power values are unsuitable for active Gigabit.",
                  "remaining": "Shared input allowance for SoC, PHY, PMIC overhead not already modeled, Wi-Fi I/O, display logic, AON and all other unmodeled loads. Base board, no expansion. Coincident literature scenarios; no time-domain or thermal validation."
              },
              "upstream_guard": guard_screen,
              "main_branch_cases": branch_cases,
              "main_branch_basis": "Main branch only; remaining watts cover RK3562, PHY, all other downstream loads and unmodeled losses. Positive residual does not qualify the design. Negative residual is a conflict within the modeled simultaneous-load scenario. Upstream AON and total port current must be checked independently.",
              "ti_1780_ohm_reference": {"source": "reference/tps2595.pdf section 7.5, ILIMIT table",
                                       "test_vin_v": 5, "low_a": 1.09, "typ_a": 1.17, "high_a": 1.24,
                                       "scope": "Published test condition; no external resistor tolerance added. Applying low limit at 4.75 V is a sensitivity case, not a guaranteed spec there."},
              "rilm_candidates_screen_only": limits,
              "rilm_limits": "Typical U15 equation with assumed +/-7.5 percent and 1 percent resistor tolerance; negative headroom means the limit is above the entire source budget. Lower limit must still support startup. No candidate selected.",
              "wifi_basis": "review/wifi-power-check.json: 1 A peak is specified at 3.3 V; applying it at 3.584 V is a scenario only",
              "release_gate": "Quantify simultaneous SoC, RAM, PHY, eMMC, LCD and AON input loads, conversion/cable losses and startup transients before enabling 1.5 A in production."}
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
