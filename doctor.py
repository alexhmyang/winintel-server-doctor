#!/usr/bin/env python3
# Author: 数萌AI服务器 (winintel) | winintel.com
"""Run established hardware tools and produce evidence-based acceptance reports."""

import argparse
import csv
import datetime as dt
import html
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from hardware import (
    counter_changes,
    gpu_details,
    matrices,
    nvlink_counters,
    nvlink_pairs,
)

ROOT = Path(__file__).resolve().parent
VERSION = "0.2.0"
FIELDS = [
    "index", "name", "pci.bus_id", "memory.total", "power.limit",
    "power.max_limit", "driver_version", "ecc.errors.uncorrected.volatile.total",
]
TARGETS = {
    "gpu_count", "gpu_name_contains", "gpu_memory_mib_min",
    "gpu_power_limit_w_min", "gpu_pcie_width_min", "gpu_pcie_speed_gt_min",
    "gpu_h2d_mb_s_min", "gpu_d2h_mb_s_min", "cpu_logical_min",
    "cpu_events_s_min", "ram_gib_min", "ram_populated_dimms_min",
    "ram_configured_mhz_min", "ram_write_mib_s_min",
    "disk_read_mib_s_min", "disk_write_mib_s_min", "disk_randread_iops_min",
    "ram_channels_min", "ram_channel_locator_regex",
    "gpu_nvlink_gb_s_min", "gpu_vram_coverage_pct_min",
}


def number(value):
    """Return a finite numeric reading or None for unavailable hardware data."""
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def run_command(argv, timeout=30, cwd=None):
    """Capture a command and kill its process group on timeout or interruption."""
    started = time.monotonic()
    result = {"command": [str(x) for x in argv]}
    env = dict(os.environ, LC_ALL="C", LANG="C")
    try:
        with tempfile.TemporaryFile() as output:
            proc = subprocess.Popen(
                result["command"], stdout=output, stderr=subprocess.STDOUT,
                cwd=cwd, env=env, start_new_session=True,
            )
            try:
                result["returncode"] = proc.wait(timeout=timeout)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                result["returncode"] = 124
                result["timed_out"] = True
                if isinstance(sys.exc_info()[1], KeyboardInterrupt):
                    raise
            output.seek(0)
            result["output"] = output.read().decode("utf-8", errors="replace")
    except OSError as exc:
        result.update(returncode=127, output=str(exc))
    result["seconds"] = round(time.monotonic() - started, 3)
    return result


def pcie(bus):
    """Read negotiated and supported PCIe link properties from Linux sysfs."""
    bus = bus.lower()
    # nvidia-smi uses an eight-digit PCI domain; sysfs uses four digits.
    if re.fullmatch(r"[0-9a-f]{8}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]", bus):
        bus = bus[4:]
    if not re.fullmatch(r"[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]", bus):
        return {}
    base = Path("/sys/bus/pci/devices") / bus
    result = {"bus": bus}
    for field in ("current_link_width", "max_link_width", "current_link_speed", "max_link_speed", "numa_node"):
        value = read(base / field)
        result[field] = value
    return result


def dimms(text, include_serials=False):
    """Extract populated DIMM topology without recording serial numbers."""
    rows = []
    for block in text.split("Memory Device\n")[1:]:
        values = {}
        for line in block.splitlines():
            if ":" in line:
                key, value = line.strip().split(":", 1)
                values[key] = value.strip()
        size = values.get("Size", "")
        if not size or size in ("No Module Installed", "Unknown"):
            continue
        rows.append({
            "size": size, "locator": values.get("Locator"),
            "bank": values.get("Bank Locator"),
            "configured_speed": values.get("Configured Memory Speed", values.get("Configured Clock Speed")),
            "rated_speed": values.get("Speed"),
            "manufacturer": values.get("Manufacturer"),
            "part_number": values.get("Part Number"),
            "type": values.get("Type"),
            "data_width": values.get("Data Width"),
            **({"serial": values.get("Serial Number")} if include_serials else {}),
        })
    return rows


def inventory(include_serials=False):
    cpu = run_command(["lscpu", "-J"])
    try:
        cpu_data = json.loads(cpu["output"])
    except (ValueError, KeyError):
        cpu_data = {"error": cpu["output"]}
    smi = run_command([
        "nvidia-smi", "--query-gpu=" + ",".join(FIELDS),
        "--format=csv,noheader,nounits",
    ])
    gpus = []
    if smi["returncode"] == 0:
        for row in csv.reader(smi["output"].splitlines(), skipinitialspace=True):
            if len(row) == len(FIELDS):
                gpu = dict(zip(FIELDS, row))
                gpu["pcie"] = pcie(gpu["pci.bus_id"])
                gpus.append(gpu)
    mem = read("/proc/meminfo") or ""
    total = re.search(r"MemTotal:\s+(\d+)", mem)
    available = re.search(r"MemAvailable:\s+(\d+)", mem)
    dmi = run_command(["dmidecode", "-t", "17"])
    details_query = run_command(["nvidia-smi", "-q", "-x"])
    details = gpu_details(details_query["output"])
    for gpu in gpus:
        extra = details.get(gpu["index"], {})
        if not include_serials:
            extra.pop("serial", None)
        gpu["details"] = extra
    topo = run_command(["nvidia-smi", "topo", "-m"])
    disk_fields = "NAME,TYPE,SIZE,MODEL,VENDOR,REV,ROTA,TRAN,MOUNTPOINTS"
    if include_serials:
        disk_fields += ",SERIAL,WWN"
    disks = run_command(["lsblk", "-J", "-o", disk_fields])
    try:
        block_devices = json.loads(disks["output"])
    except ValueError:
        block_devices = {"error": disks["output"]}
    result = {
        "cpu": cpu_data, "cpu_logical": os.cpu_count(),
        "ram_gib": round(int(total[1]) / 1024**2, 2) if total else None,
        "available_ram_gib": round(int(available[1]) / 1024**2, 2) if available else None,
        "dimms": dimms(dmi["output"], include_serials),
        "dimms_available": dmi["returncode"] == 0,
        "gpus": gpus, "gpu_query": smi, "gpu_topology": topo,
        "disks": block_devices,
        "gpu_details_query": details_query,
        "nvlink_status": run_command(["nvidia-smi", "nvlink", "-s"]),
        "nvlink_error_counters": run_command(["nvidia-smi", "nvlink", "-e"]),
        "pcie_all_devices": run_command(["lspci", "-Dnnvv"]),
        "network": run_command(["ip", "-j", "-details", "link"]),
        "usb": run_command(["lsusb"]),
        "system_board_bios_cpu_psu": run_command([
            "dmidecode", "-t", "0,1,2,3,4,9,16,39",
        ]),
        "storage_health": storage_health(),
        "bmc_sensors": run_command(["ipmitool", "sdr", "elist"]),
        "bmc_event_log": run_command(["ipmitool", "sel", "elist"]),
        "edac": {str(path): read(path) for pattern in ("mc*/ce_count", "mc*/ue_count")
                 for path in Path("/sys/devices/system/edac/mc").glob(pattern)},
        "memory_channels": "UNKNOWN: use vendor channel mapping for DIMM locators; DIMM count is not channel count.",
        "platform": run_command(["uname", "-srmo"])["output"].strip(),
    }
    if not include_serials:
        def redact(value):
            if isinstance(value, dict):
                return {key: redact(item) for key, item in value.items()
                        if key.lower() not in ("serial", "serial_number", "wwn")}
            if isinstance(value, list):
                return [redact(item) for item in value]
            if isinstance(value, str):
                value = re.sub(r"(?im)^.*Serial Number\s*:.*$", "Serial Number: omitted", value)
                value = re.sub(r"<serial>.*?</serial>", "<serial>omitted</serial>", value)
                value = re.sub(r'("serial_number"\s*:\s*)"[^"]*"', r'\1"omitted"', value)
            return value
        result = redact(result)
    return result


def storage_health():
    listing = run_command(["lsblk", "-J", "-d", "-o", "PATH,TYPE"])
    try:
        devices = json.loads(listing["output"])["blockdevices"]
    except (ValueError, KeyError):
        return {"discovery": listing}
    return {
        device["path"]: run_command(["smartctl", "-a", "-j", device["path"]])
        for device in devices if device.get("type") == "disk"
    }


def component_tables(inv):
    def table(title, columns, rows):
        heading = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
        body = "".join("<tr>" + "".join(
            f"<td>{html.escape('—' if value is None else str(value))}</td>"
            for value in row
        ) + "</tr>" for row in rows)
        return f"<h2>{title}</h2><div class='table'><table><tr>{heading}</tr>{body}</table></div>"

    result = table("GPU components", ["GPU", "Model", "VRAM MiB", "Board", "Serial", "PCI bus"], [
        [gpu.get("index"), gpu.get("name"), gpu.get("memory.total"),
         gpu.get("details", {}).get("form_factor"), gpu.get("details", {}).get("serial"),
         gpu.get("pci.bus_id")] for gpu in inv.get("gpus", [])
    ])
    result += table("Memory modules", ["Slot", "Bank", "Size", "Manufacturer", "Part", "Speed", "Serial"], [
        [dimm.get(key) for key in ("locator", "bank", "size", "manufacturer",
                                  "part_number", "configured_speed", "serial")]
        for dimm in inv.get("dimms", [])
    ])
    result += table("Storage components", ["Device", "Model", "Size", "Transport", "Serial"], [
        [device.get(key) for key in ("name", "model", "size", "tran", "serial")]
        for device in inv.get("disks", {}).get("blockdevices", [])
        if device.get("type") == "disk"
    ])
    return result


class Report:
    def __init__(self, profile, output):
        self.output = output
        self.data = {
            "schema_version": 1, "tool_version": VERSION,
            "brand": "winintel AI", "website": "https://winintel.com",
            "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "profile": profile, "checks": [], "tools": {}, "inventory": {},
            "limitations": [
                "An observed speed is not a universal specification.",
                "Unspecified acceptance thresholds remain UNKNOWN.",
                "DIMM population is not measured memory channel count.",
                "PCIe link speed is sampled after transfer; idle power management may lower it.",
                "GPU FP32/FP64 workload metrics are not tensor/AI throughput.",
                "ECC locations depend on hardware. Compute correctness is tested separately.",
                "VRAM tests cover allocated memory; driver-reserved memory is inaccessible.",
                "Optional sensors or hidden components remain unavailable, not inferred.",
            ],
        }

    def check(self, name, status, actual=None, expected=None, detail=""):
        self.data["checks"].append({
            "name": name, "status": status, "actual": actual,
            "expected": expected, "detail": detail,
        })

    def minimum(self, name, actual, key, detail=""):
        expected = self.data["profile"].get(key)
        measured = number(actual)
        if expected is None or measured is None:
            status = "UNKNOWN"
        else:
            status = "PASS" if measured >= expected else "FAIL"
        self.check(name, status, actual, expected, detail)

    def command(self, name, argv, timeout=30, cwd=None):
        print(f"[RUN] {name}", file=sys.stderr, flush=True)
        result = run_command(argv, timeout, cwd)
        log = self.output / "logs" / f"{name}.log"
        log.write_text(result["output"], encoding="utf-8")
        self.data["tools"][name] = {
            key: value for key, value in result.items() if key != "output"
        }
        self.data["tools"][name]["log"] = f"logs/{name}.log"
        return result

    def tool_check(self, name, result, valid=None):
        if result["returncode"] in (124, 127):
            status = "UNKNOWN"
        elif result["returncode"] != 0 or valid is False:
            status = "FAIL"
        else:
            status = "PASS"
        self.check(name, status, result["returncode"], 0, f"See logs/{name}.log")

    def save(self):
        statuses = [item["status"] for item in self.data["checks"]]
        overall = "FAIL" if "FAIL" in statuses else "INCOMPLETE" if not statuses or "UNKNOWN" in statuses else "PASS"
        self.data["overall"] = overall
        self.data["counts"] = {key: statuses.count(key) for key in ("PASS", "FAIL", "UNKNOWN")}
        (self.output / "report.json").write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        rows = []
        md = [
            "# winintel AI — Server Acceptance Report", "",
            f"**Result: {overall}** · {self.data['created_utc']}", "",
            "| Check | Result | Measured | Target |", "|---|---|---|---|",
        ]
        for check in self.data["checks"]:
            cells = [check[key] for key in ("name", "status", "actual", "expected")]
            strings = ["—" if x is None else str(x) for x in cells]
            rows.append(
                "<tr>" + "".join(
                    f"<td>{html.escape(x)}</td>" for x in strings
                ) + f"<td>{html.escape(check['detail'])}</td></tr>"
            )
            md.append("| " + " | ".join(x.replace("|", "\\|") for x in strings) + " |")
        limits = "".join(f"<li>{html.escape(x)}</li>" for x in self.data["limitations"])
        tools = "".join(
            f'<li><a href="{html.escape(tool["log"])}">{html.escape(name)}</a>'
            f' — exit {tool["returncode"]}, {tool["seconds"]}s</li>'
            for name, tool in self.data["tools"].items()
        )
        document = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>winintel AI | Server Acceptance</title>
<style>
body{{font:16px system-ui;background:#0c1427;color:#e8edf7;margin:0;padding:36px}}
main{{max-width:1200px;margin:auto}}h1{{font-size:40px}}a{{color:#75d9ff}}
.score{{font-size:56px;font-weight:800;color:{"#ff8a8a" if overall == "FAIL" else "#79d9ff"}}}
.cards{{display:flex;gap:24px;flex-wrap:wrap}}.card{{padding:24px;background:#17243e;border-radius:16px}}
.card strong{{font-size:38px}}table{{width:100%;border-collapse:collapse;font-size:14px}}
td,th{{padding:12px;text-align:left;border-bottom:1px solid #354462}}.table{{overflow-x:auto}}
footer{{margin-top:32px;color:#aab9d3}}code{{color:#75d9ff}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere}}
</style><main><p>winintel AI · Ubuntu Hardware Acceptance</p><h1>Your server. Measured.</h1>
<p class="score">{overall}</p>
<p>{html.escape(self.data['profile'].get('name', 'Custom profile'))}</p>
<p>{html.escape(self.data['created_utc'])}</p>
<div class="cards">{''.join(f'<div class="card"><strong>{count}</strong><p>{key}</p></div>' for key, count in self.data['counts'].items())}</div>
{component_tables(self.data['inventory'])}
<h2>Acceptance checks</h2><div class="table"><table><tr><th>Check</th><th>Result</th><th>Measured</th><th>Target</th><th>Evidence</th></tr>
{''.join(rows)}</table></div><h2>Measurements &amp; topology</h2>
<details open><summary>Hardware components and topology</summary><pre>{html.escape(json.dumps(self.data['inventory'], indent=2, ensure_ascii=False))}</pre></details>
<h2>Evidence logs</h2><ul>{tools}</ul><h2>How to read this report</h2><ul>{limits}</ul>
<p><a href="report.json">Download JSON for your AI Agent</a> · <a href="report.md">Markdown report</a></p>
<footer>数萌AI服务器 (winintel) · <a href="https://winintel.com">winintel.com</a></footer></main></html>"""
        (self.output / "report.html").write_text(document, encoding="utf-8")
        md.extend(["", "## Hardware components and topology", "", "```json",
                   json.dumps(self.data["inventory"], indent=2, ensure_ascii=False), "```"])
        (self.output / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        return {"PASS": 0, "FAIL": 2, "INCOMPLETE": 3}[overall]


def check_inventory(report, inv):
    profile = report.data["profile"]
    gpus = inv["gpus"]
    expected = profile.get("gpu_count")
    report.check(
        "GPU count", "UNKNOWN" if expected is None else
        "PASS" if len(gpus) == expected else "FAIL", len(gpus), expected,
    )
    report.minimum("CPU logical threads", inv["cpu_logical"], "cpu_logical_min")
    report.minimum("RAM capacity (GiB)", inv["ram_gib"], "ram_gib_min")
    report.minimum(
        "Populated DIMMs", len(inv["dimms"]) if inv["dimms_available"] else None,
        "ram_populated_dimms_min",
    )
    mapping = profile.get("ram_channel_locator_regex")
    channels = None
    if mapping and inv["dimms_available"] and inv["dimms"]:
        matches = [re.search(mapping, f"{d['bank']} {d['locator']}") for d in inv["dimms"]]
        if all(match is not None for match in matches):
            channels = len({match.groups() for match in matches})
    report.minimum(
        "Populated memory channels", channels, "ram_channels_min",
        "Requires a vendor-confirmed locator regex capturing CPU and channel; no automatic inference.",
    )
    speeds = [
        number((d["configured_speed"] or "").split(" ")[0]) for d in inv["dimms"]
    ]
    report.minimum(
        "Lowest configured DIMM speed (MT/s)", min(speeds) if speeds and all(x is not None for x in speeds) else None,
        "ram_configured_mhz_min",
    )
    query_code = inv["gpu_query"]["returncode"]
    report.check(
        "GPU driver query",
        "UNKNOWN" if query_code in (124, 127) else "PASS" if query_code == 0 else "FAIL",
        query_code, 0, "Evidence: JSON inventory.gpu_query",
    )
    for category in ("pcie_all_devices", "network", "usb", "system_board_bios_cpu_psu",
                     "bmc_sensors", "bmc_event_log"):
        if category in inv:
            result = inv[category]
            report.check(f"Inventory {category}", "PASS" if result["returncode"] == 0 else "UNKNOWN",
                         result["returncode"], 0, "Collection result; unavailable/hidden components need vendor or BMC access")
    for device, result in inv.get("storage_health", {}).items():
        if device == "discovery":
            report.check("Storage health discovery", "UNKNOWN", detail=result["output"])
            continue
        status = "UNKNOWN"
        if result["returncode"] not in (124, 127):
            if result["returncode"] & 0b11111000:
                status = "FAIL"
            else:
                try:
                    passed = json.loads(result["output"]).get("smart_status", {}).get("passed")
                    status = "PASS" if passed is True and result["returncode"] == 0 else "FAIL" if passed is False else "UNKNOWN"
                except ValueError:
                    pass
        report.check(f"Disk {device} SMART health", status, result["returncode"], 0,
                     "Health snapshot; a storage speed test does not prove remaining lifetime")
    for gpu in gpus:
        name = f"GPU {gpu['index']}"
        target = profile.get("gpu_name_contains")
        report.check(
            name + " model", "UNKNOWN" if target is None else
            "PASS" if target.lower() in gpu["name"].lower() else "FAIL",
            gpu["name"], target,
        )
        report.minimum(name + " VRAM (MiB)", gpu["memory.total"], "gpu_memory_mib_min")
        report.minimum(name + " power limit (W)", gpu["power.limit"], "gpu_power_limit_w_min")
        max_power = number(gpu["power.max_limit"])
        limit = number(gpu["power.limit"])
        report.check(
            name + " maximum supported power configured",
            "UNKNOWN" if max_power is None or limit is None else
            "PASS" if limit >= max_power else "FAIL", limit, max_power,
            "Read-only check; this tool never changes GPU power limits.",
        )
        ecc = number(gpu["ecc.errors.uncorrected.volatile.total"])
        report.check(name + " uncorrectable volatile ECC", "UNKNOWN" if ecc is None else "PASS" if ecc == 0 else "FAIL", ecc, 0)
        for key, raw in gpu.get("details", {}).get("error_counters", {}).items():
            value = number(raw)
            if value is not None:
                report.check(name + " initial " + key, "PASS" if value == 0 else "FAIL", value, 0)
            elif raw in ("Yes", "Pending", "Failure"):
                report.check(name + " " + key, "FAIL", raw, "No")


def bandwidth_value(text, label):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if label in line:
            for candidate in lines[i + 1:i + 10]:
                match = re.match(r"\s*\d+\s+([0-9.]+)\s*$", candidate)
                if match:
                    return number(match[1])
    return None


def gpu_tests(report, args):
    gpus = report.data["inventory"]["gpus"]
    if not gpus:
        report.check("GPU stress", "UNKNOWN", detail="No working NVIDIA GPU query")
        return
    active = report.command("gpu-processes", ["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"])
    if active["returncode"] != 0 or re.search(r"\d", active["output"]):
        report.check("GPU stress", "UNKNOWN", detail="GPU processes active or process query unavailable; run during maintenance")
        return
    query = report.command("device-query", [ROOT / "bin/deviceQuery"])
    report.tool_check("device-query", query, "Result = PASS" in query["output"])
    for gpu in gpus:
        index = gpu["index"]
        result = report.command(
            f"gpu-{index}-bandwidth",
            [ROOT / "bin/bandwidthTest", f"--device={index}", "--memory=pinned", "--mode=quick"],
            timeout=120,
        )
        report.tool_check(f"gpu-{index}-bandwidth", result, "Result = PASS" in result["output"])
        report.minimum(f"GPU {index} H2D (MB/s)", bandwidth_value(result["output"], "Host to Device"), "gpu_h2d_mb_s_min")
        report.minimum(f"GPU {index} D2H (MB/s)", bandwidth_value(result["output"], "Device to Host"), "gpu_d2h_mb_s_min")
        link = pcie(gpu["pci.bus_id"])
        gpu["pcie_after_transfer"] = link
        report.minimum(f"GPU {index} negotiated PCIe lanes", link.get("current_link_width"), "gpu_pcie_width_min")
        speed = (link.get("current_link_speed") or "").split(" ")[0]
        report.minimum(f"GPU {index} PCIe speed (GT/s)", speed, "gpu_pcie_speed_gt_min", "Idle downshift possible; confirm under sustained traffic if this fails.")
    if len(gpus) > 1:
        peer = report.command("gpu-p2p", [ROOT / "bin/p2pBandwidthLatencyTest"], timeout=180)
        parsed = matrices(peer["output"])
        bandwidth = parsed.get("Unidirectional P2P=Enabled Bandwidth (P2P Writes) Matrix (GB/s)", {})
        connectivity = parsed.get("P2P Connectivity Matrix", {})
        report.tool_check("gpu-p2p", peer, bool(bandwidth) and bool(connectivity))
        report.data["p2p_matrices"] = parsed
        pairs = nvlink_pairs(report.data["inventory"].get("gpu_topology", {}).get("output", ""))
        report.data["nvlink_pairs"] = pairs
        for left, right in pairs:
            for source, target in ((left, right), (right, left)):
                connected = connectivity.get(source, {}).get(target) == 1
                value = bandwidth.get(source, {}).get(target) if connected else None
                report.minimum(f"NVLink GPU {source} to {target} (GB/s)", value, "gpu_nvlink_gb_s_min",
                               "CUDA P2P writes on an NVLink-connected pair; achieved bandwidth, not physical per-link rate")
        if not pairs:
            if report.data["inventory"].get("gpu_topology", {}).get("returncode") == 0:
                report.data["nvlink_test"] = "NOT_APPLICABLE: no NVLink-connected GPU pairs"
            else:
                report.check("NVLink bandwidth", "UNKNOWN", detail="Topology unavailable; cannot decide whether NVLink exists")
    else:
        report.data["nvlink_pairs"] = []
        report.data["nvlink_test"] = "NOT_APPLICABLE: one GPU; no GPU-to-GPU pair"
    before = report.command("gpu-ecc-before", ["nvidia-smi", "-q", "-x"])
    before_details = gpu_details(before["output"])
    nvlink_before = report.command("nvlink-errors-before", ["nvidia-smi", "nvlink", "-e"])
    telemetry_path = report.output / "logs/gpu-telemetry.csv"
    with telemetry_path.open("w", encoding="utf-8") as handle:
        monitor = subprocess.Popen([
            "nvidia-smi",
            "--query-gpu=index,power.draw,power.limit,utilization.gpu,clocks.current.sm",
            "--format=csv,nounits", "--loop=1",
        ], stdout=handle, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            for precision, options in (("fp32", []), ("fp64", ["-d"])):
                burn = report.command(
                    f"gpu-burn-{precision}",
                    [ROOT / "vendor/gpu-burn/gpu_burn", *options, str(args.seconds)],
                    timeout=args.seconds + 90, cwd=ROOT / "vendor/gpu-burn",
                )
                burn_checks(report, gpus, burn, args.seconds, precision)
            for gpu in gpus:
                index = gpu["index"]
                memory = report.command(
                    f"gpu-{index}-vram",
                    [ROOT / "bin/cuda_memtest", "--device", index, "--num_passes",
                     str(getattr(args, "vram_passes", 1)), "--num_iterations", "100",
                     "--exit_on_error", "--enable_test", "9"]
                    if getattr(args, "bit_fade", False) else
                    [ROOT / "bin/cuda_memtest", "--device", index, "--num_passes",
                     str(getattr(args, "vram_passes", 1)), "--num_iterations", "100",
                     "--exit_on_error"],
                    timeout=getattr(args, "vram_timeout", 1800),
                )
                required = list(range(11)) if getattr(args, "bit_fade", False) else [*range(9), 10]
                finished = all(len(re.findall(rf"\bTest{test} finished\b", memory["output"])) >= getattr(args, "vram_passes", 1) for test in required)
                report.tool_check(f"gpu-{index}-vram", memory, finished and "Program exits" in memory["output"])
                allocated = re.search(r"Allocated (\d+) MB", memory["output"])
                capacity = number(gpu.get("memory.total"))
                coverage = round(int(allocated[1]) / capacity * 100, 2) if allocated and capacity else None
                gpu["vram_test_allocated_mib"] = int(allocated[1]) if allocated else None
                report.minimum(f"GPU {index} VRAM tested coverage (%)", coverage, "gpu_vram_coverage_pct_min")
                reference = report.command(
                    f"gpu-{index}-matrix-reference",
                    [ROOT / "bin/matrixMul", f"--device={index}"], timeout=120,
                )
                report.tool_check(f"gpu-{index}-matrix-reference", reference, "Result = PASS" in reference["output"])
                lu = report.command(
                    f"gpu-{index}-fp64-lu-reference",
                    [ROOT / "bin/simpleCUBLAS_LU", f"--device={index}"], timeout=120,
                )
                report.tool_check(f"gpu-{index}-fp64-lu-reference", lu,
                                  "TEST SUCCESSFUL" in lu["output"] and "ERROR:" not in lu["output"])
        finally:
            monitor.terminate()
            try:
                monitor.wait(timeout=5)
            except subprocess.TimeoutExpired:
                monitor.kill()
                monitor.wait()
    report.data["gpu_telemetry_log"] = "logs/gpu-telemetry.csv"
    after = report.command("gpu-ecc-after", ["nvidia-smi", "-q", "-x"])
    after_details = gpu_details(after["output"])
    report.data["ecc_changes"] = counter_changes(before_details, after_details)
    for gpu in gpus:
        details = after_details.get(gpu["index"], {})
        enabled = details.get("ecc_mode")
        report.check(f"GPU {gpu['index']} ECC enabled", "PASS" if enabled == "Enabled" else "UNKNOWN",
                     enabled, "Enabled", "Unsupported ECC is not an ECC pass")
        changes = [item for item in report.data["ecc_changes"] if item["gpu"] == gpu["index"]]
        if not changes:
            report.check(f"GPU {gpu['index']} ECC counters", "UNKNOWN", detail="No numeric ECC/retirement counters available")
        for change in changes:
            key, value, delta = change["counter"], change["after"], change["delta"]
            absolute_bad = value > 0 and (
                "uncorrected" in key or "uncorrectable" in key
                or "/double_bit/" in key or key.startswith("retired_pages/")
                or key.startswith("remapped_rows/")
            )
            status = "FAIL" if absolute_bad or (delta is not None and delta > 0) else "UNKNOWN" if delta is None or delta < 0 else "PASS"
            report.check(f"GPU {gpu['index']} {key}", status, value, change["before"],
                         f"Delta={delta}; positive corrected or uncorrected increments fail acceptance; resets are UNKNOWN")
    for kind in ("-s", "-e"):
        result = report.command(f"nvlink-after{kind}", ["nvidia-smi", "nvlink", kind])
        report.data[f"nvlink_after{kind}"] = result["output"]
        if kind == "-e" and report.data.get("nvlink_pairs"):
            earlier = nvlink_counters(nvlink_before["output"])
            later = nvlink_counters(result["output"])
            if not later:
                report.check("NVLink error counters", "UNKNOWN", detail="No readable link-error counters")
            for key, value in later.items():
                old = earlier.get(key)
                delta = value - old if old is not None else None
                status = "FAIL" if value > 0 else "UNKNOWN" if delta is None or delta < 0 else "PASS"
                report.check(f"NVLink {key}", status, value, old, f"Delta={delta}")


def burn_checks(report, gpus, burn, seconds, precision):
    """A zero tool exit alone does not prove every GPU computed correctly."""
    for gpu in gpus:
        index = gpu["index"]
        ok = re.search(rf"GPU\s+{re.escape(index)}:\s+OK\b", burn["output"]) is not None
        bad = re.search(rf"GPU\s+{re.escape(index)}:\s+(?:FAULTY|FAILED|FAIL)\b", burn["output"]) is not None
        completed = burn["seconds"] >= seconds * 0.8
        status = "FAIL" if bad else "UNKNOWN" if burn["returncode"] in (124, 127) else "FAIL" if burn["returncode"] else "PASS" if ok and completed else "UNKNOWN"
        report.check(f"GPU {index} {precision.upper()} stress correctness", status,
                     detail=f"Computed-result comparisons; logs/gpu-burn-{precision}.log")


def cpu_ram_tests(report, args):
    threads = os.cpu_count() or 1
    cpu = report.command("cpu-stress", [
        "stress-ng", "--cpu", str(threads), "--cpu-method", "all",
        "--verify", "--timeout", f"{args.seconds}s", "--metrics-brief",
    ], timeout=args.seconds + 45)
    report.tool_check("cpu-stress", cpu)
    score = report.command("cpu-score", [
        "sysbench", "cpu", f"--threads={threads}", "--cpu-max-prime=20000",
        f"--time={args.seconds}", "run",
    ], timeout=args.seconds + 30)
    report.tool_check("cpu-score", score)
    match = re.search(r"events per second:\s+([0-9.]+)", score["output"])
    report.minimum("CPU events/s", match[1] if match else None, "cpu_events_s_min", "sysbench prime=20000; compare only identical settings")
    memory = report.command("ram-stress", [
        "stress-ng", "--vm", "1", "--vm-bytes", "25%", "--vm-method", "all",
        "--verify", "--timeout", f"{args.seconds}s", "--metrics-brief",
    ], timeout=args.seconds + 45)
    report.tool_check("ram-stress", memory)
    speed = report.command("ram-write", [
        "sysbench", "memory", "--threads=1", "--memory-block-size=64M",
        "--memory-total-size=1024T", "--memory-oper=write", "--memory-access-mode=seq",
        f"--time={args.seconds}", "run",
    ], timeout=args.seconds + 30)
    report.tool_check("ram-write", speed)
    match = re.search(r"\(([0-9.]+)\s+MiB/sec\)", speed["output"])
    report.minimum("RAM write (MiB/s)", match[1] if match else None, "ram_write_mib_s_min", "sysbench 64MiB working set, one thread; cache effects possible; not full socket/channel bandwidth")


def disk_tests(report, args):
    target = Path(args.disk_path).resolve()
    if not target.is_dir():
        report.check("Disk benchmark", "UNKNOWN", detail="--disk-path must be an existing directory")
        return
    report.data["disk_target"] = str(target)
    if shutil.disk_usage(target).free < (args.disk_size_gib + 2) * 1024**3:
        report.check("Disk benchmark", "UNKNOWN", detail="Insufficient scratch space")
        return
    mount = report.command("disk-mount", ["findmnt", "-J", "-T", str(target), "-o", "SOURCE,TARGET,FSTYPE"])
    report.data["disk_mount"] = mount["output"]
    # Only a unique scratch directory/file is written. No raw-device path is accepted.
    with tempfile.TemporaryDirectory(prefix=".winintel-fio-", dir=target) as scratch:
        filename = Path(scratch) / "test.bin"
        warmup = report.command("disk-prepare", [
            "fio", "--name=prepare", f"--filename={filename}", "--rw=write",
            "--bs=1M", f"--size={args.disk_size_gib}G", "--direct=1",
            "--ioengine=libaio", "--iodepth=16", "--end_fsync=1",
            "--verify=crc32c", "--do_verify=1", "--output-format=json",
        ], timeout=600)
        report.tool_check("disk-prepare", warmup)
        if warmup["returncode"] != 0:
            return
        for mode, block, key, direction, metric in [
            ("read", "1M", "disk_read_mib_s_min", "read", "bw_bytes"),
            ("write", "1M", "disk_write_mib_s_min", "write", "bw_bytes"),
            ("randread", "4k", "disk_randread_iops_min", "read", "iops"),
        ]:
            result = report.command(f"disk-{mode}", [
                "fio", f"--name={mode}", f"--filename={filename}", f"--rw={mode}",
                f"--bs={block}", f"--size={args.disk_size_gib}G", "--direct=1",
                "--ioengine=libaio", "--iodepth=32", "--numjobs=1", "--time_based",
                f"--runtime={args.seconds}", "--ramp_time=3", "--output-format=json",
            ], timeout=args.seconds + 60)
            measurement = None
            valid = None
            try:
                jobs = json.loads(result["output"])["jobs"]
                valid = bool(jobs) and all(job["error"] == 0 for job in jobs)
                measurement = sum(job[direction][metric] for job in jobs)
                if metric == "bw_bytes":
                    measurement /= 1024**2
                measurement = round(measurement, 2)
            except (ValueError, KeyError, TypeError):
                valid = False if result["returncode"] == 0 else None
            report.tool_check(f"disk-{mode}", result, valid)
            report.minimum(f"Disk {mode} ({'IOPS' if metric == 'iops' else 'MiB/s'})", measurement, key, "fio direct I/O, QD32, one job, unique scratch file")


def load_profile(path):
    with Path(path).open(encoding="utf-8") as handle:
        profile = json.load(handle)
    if not isinstance(profile, dict):
        raise ValueError("Profile must be a JSON object")
    if profile.get("name") is not None and not isinstance(profile["name"], str):
        raise ValueError("Profile name must be a string")
    unknown = set(profile) - TARGETS - {"name"}
    if unknown:
        raise ValueError(f"Unknown profile keys: {sorted(unknown)}")
    for key in TARGETS - {"gpu_name_contains", "ram_channel_locator_regex"}:
        if profile.get(key) is not None:
            value = profile[key]
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{key} must be null or a non-negative finite number")
    if profile.get("gpu_name_contains") is not None and not isinstance(profile["gpu_name_contains"], str):
        raise ValueError("gpu_name_contains must be null or a string")
    mapping = profile.get("ram_channel_locator_regex")
    if mapping is not None and (
        not isinstance(mapping, str) or re.compile(mapping).groups < 1
    ):
        raise ValueError("ram_channel_locator_regex must contain capture groups")
    return profile


def main():
    parser = argparse.ArgumentParser(description="winintel AI Ubuntu hardware acceptance")
    parser.add_argument("action", choices=("inventory", "test"))
    parser.add_argument("--profile", default=str(ROOT / "profiles/inventory-only.json"))
    parser.add_argument("--output", help="New report directory; existing directories are refused")
    parser.add_argument("--seconds", type=int, default=60, help="Per benchmark, 10..86400")
    parser.add_argument("--disk-path", default="/var/tmp", help="Existing filesystem directory; never a raw device")
    parser.add_argument("--disk-size-gib", type=int, default=4)
    parser.add_argument("--skip-gpu", action="store_true")
    parser.add_argument("--skip-cpu-ram", action="store_true")
    parser.add_argument("--skip-disk", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--include-serials", action="store_true", help="Include private component serial numbers")
    parser.add_argument("--vram-passes", type=int, default=1, help="VRAM pattern passes; use 32 for complete test6 pattern rotation")
    parser.add_argument("--vram-timeout", type=int, default=1800, help="Per GPU memory test timeout")
    parser.add_argument("--bit-fade", action="store_true", help="Add 3-hour VRAM retention test per pass; increase timeout")
    args = parser.parse_args()
    if args.action == "test" and not args.skip_gpu and os.environ.get("CUDA_VISIBLE_DEVICES"):
        parser.error("Unset CUDA_VISIBLE_DEVICES so GPU indices match nvidia-smi")
    if not 10 <= args.seconds <= 86400 or not 1 <= args.disk_size_gib <= 1024:
        parser.error("seconds must be 10..86400; disk size 1..1024 GiB")
    if not 1 <= args.vram_passes <= 1000 or not 60 <= args.vram_timeout <= 604800:
        parser.error("vram passes must be 1..1000; timeout 60..604800")
    if args.bit_fade and args.vram_timeout < 10800 * args.vram_passes + 1800:
        parser.error("Bit fade needs --vram-timeout >= 10800 * passes + 1800 seconds")
    try:
        profile = load_profile(args.profile)
    except (OSError, ValueError, re.error) as exc:
        parser.error(str(exc))
    if args.dry_run:
        print(json.dumps({
            "action": args.action, "profile": profile, "seconds_per_test": args.seconds,
            "disk_path": args.disk_path, "disk_size_gib": args.disk_size_gib,
            "skip_gpu": args.skip_gpu, "skip_cpu_ram": args.skip_cpu_ram,
            "skip_disk": args.skip_disk,
            "estimated_seconds_excluding_install_and_vram": args.seconds * 9 + 600,
            "vram_budget": "Detected GPU count × per-GPU VRAM timeout; actual duration varies with capacity and passes",
            "writes": "Unique fio scratch file only; cleaned up afterward",
            "gpu_workloads": ["FP32 burn", "FP64 burn", "VRAM patterns", "matrix reference", "PCIe", "NVLink/P2P"],
            "vram_passes": args.vram_passes, "bit_fade": args.bit_fade,
            "vram_timeout_per_gpu": args.vram_timeout,
        }, indent=2))
        return 0
    output = Path(args.output) if args.output else Path.cwd() / "reports" / dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    os.umask(0o077)
    output.mkdir(parents=True, exist_ok=False)
    (output / "logs").mkdir()
    report = Report(profile, output)
    try:
        inv = inventory(args.include_serials)
        report.data["inventory"] = inv
        check_inventory(report, inv)
        if args.action == "test":
            if args.skip_gpu:
                report.check("GPU stress", "UNKNOWN", detail="Skipped by operator")
            else:
                gpu_tests(report, args)
            if args.skip_cpu_ram:
                report.check("CPU and RAM tests", "UNKNOWN", detail="Skipped by operator")
            else:
                cpu_ram_tests(report, args)
            if args.skip_disk:
                report.check("Disk tests", "UNKNOWN", detail="Skipped by operator")
            else:
                disk_tests(report, args)
        else:
            report.check("Performance tests", "UNKNOWN", detail="Inventory action does not stress hardware")
    except KeyboardInterrupt:
        report.check("Run interrupted", "UNKNOWN", detail="Stopped by operator")
    except Exception as exc:
        report.check("Runner exception", "UNKNOWN", detail=f"{type(exc).__name__}: {exc}")
    code = report.save()
    print(json.dumps({
        "overall": report.data["overall"], "exit_code": code,
        "report_json": str(output / "report.json"),
        "report_html": str(output / "report.html"),
    }))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
