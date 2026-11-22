#!/usr/bin/env python3
# Author: 数萌AI服务器 (winintel) | winintel.com
"""Persist health snapshots and retry configured anomaly delivery."""

import argparse
import datetime as dt
import fcntl
import json
import os
import socket
import urllib.request
from pathlib import Path

from doctor import read, run_command, storage_health
from hardware import counter_changes, gpu_details, nvlink_counters


def snapshot(previous):
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    boot = read("/proc/sys/kernel/random/boot_id")
    smi = run_command(["nvidia-smi", "-q", "-x"])
    args = ["journalctl", "-k", "-p", "warning", "-o", "json", "--no-pager"]
    if previous.get("cursor") and previous.get("boot_id") == boot:
        args += ["--after-cursor", previous["cursor"]]
    else:
        since = dt.datetime.fromisoformat(previous["time"]).timestamp() if previous.get("time") else dt.datetime.now(dt.timezone.utc).timestamp() - 1800
        args += ["--since", f"@{int(since)}"]
    journal = run_command(args)
    records = []
    for line in journal["output"].splitlines():
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
    edac = {str(path): read(path) for pattern in ("mc*/ce_count", "mc*/ue_count")
            for path in Path("/sys/devices/system/edac/mc").glob(pattern)}
    return {
        "time": now, "host": socket.gethostname(), "boot_id": boot,
        "gpus": gpu_details(smi["output"]), "gpu_query_code": smi["returncode"],
        "kernel_records": records,
        "cursor": records[-1].get("__CURSOR") if records else previous.get("cursor") if previous.get("boot_id") == boot else None,
        "journal_code": journal["returncode"],
        "journal_error": journal["output"] if journal["returncode"] else None,
        "edac": edac,
        "storage": storage_health(),
        "nvlink": run_command(["nvidia-smi", "nvlink", "-e"]),
        "failed_services": run_command(["systemctl", "--failed", "--no-legend", "--plain"]),
    }


def anomalies(previous, current):
    """Identify changed evidence; do not classify a reboot's cause without proof."""
    events = []
    if previous.get("boot_id") and previous["boot_id"] != current["boot_id"]:
        events.append({"kind": "REBOOT_DETECTED", "detail": "Boot ID changed; inspect BMC/previous-boot logs to establish cause"})
    for key in ("gpu_query_code", "journal_code"):
        if current[key]:
            events.append({"kind": "COLLECTION_FAILED", "source": key, "code": current[key]})
    old_uuids = {gpu.get("uuid") for gpu in previous.get("gpus", {}).values()}
    new_uuids = {gpu.get("uuid") for gpu in current["gpus"].values()}
    if previous and old_uuids != new_uuids:
        events.append({"kind": "GPU_SET_CHANGED", "before": sorted(str(x) for x in old_uuids), "after": sorted(str(x) for x in new_uuids)})
    for change in counter_changes(previous.get("gpus", {}), current["gpus"]):
        key, value, delta = change["counter"], change["after"], change["delta"]
        initial_bad = delta is None and value > 0 and (
            "uncorrected" in key or "uncorrectable" in key or "/double_bit/" in key
            or key.startswith(("retired_pages/", "remapped_rows/"))
        )
        if initial_bad or (delta is not None and delta != 0):
            events.append({"kind": "GPU_COUNTER_CHANGED", **change})
    for record in current["kernel_records"]:
        events.append({
            "kind": "KERNEL_WARNING_OR_ERROR", "message": record.get("MESSAGE"),
            "priority": record.get("PRIORITY"), "cursor": record.get("__CURSOR"),
        })
    for path, raw in current["edac"].items():
        prior = previous.get("edac", {}).get(path)
        if str(raw).isdigit() and int(raw) > (int(prior) if str(prior).isdigit() else 0):
            events.append({"kind": "RAM_EDAC_ERROR", "counter": path, "before": prior, "after": raw})
    for device, result in current["storage"].items():
        if result["returncode"] in (124, 127):
            events.append({"kind": "STORAGE_HEALTH_UNAVAILABLE", "device": device, "code": result["returncode"]})
            continue
        try:
            data = json.loads(result["output"])
            status = data.get("smart_status", {}).get("passed")
        except (ValueError, KeyError):
            status = None
        if result["returncode"] & 0b11111000 or status is False:
            events.append({"kind": "STORAGE_SMART_ERROR", "device": device, "code": result["returncode"]})
        elif result["returncode"] or status is None:
            events.append({"kind": "STORAGE_HEALTH_UNAVAILABLE", "device": device, "code": result["returncode"]})
    services = current["failed_services"]
    if services["returncode"] == 0 and services["output"].strip():
        events.append({"kind": "FAILED_SYSTEMD_SERVICES", "detail": services["output"]})
    # NVLink counter output is retained; numeric increases are decoded separately.
    old_link = nvlink_counters(previous.get("nvlink", {}).get("output", ""))
    for key, value in nvlink_counters(current["nvlink"]["output"]).items():
        if value > old_link.get(key, 0):
            events.append({"kind": "NVLINK_ERROR", "counter": key, "before": old_link.get(key), "after": value})
    return events


def atomic_json(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def deliver(url, payload):
    if not url.startswith("https://"):
        raise ValueError("Alert URL must use HTTPS")
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        if not 200 <= response.status < 300:
            raise OSError(f"Webhook HTTP {response.status}")


def main():
    parser = argparse.ArgumentParser(description="winintel AI persistent hardware monitor")
    parser.add_argument("--state-dir", default="/var/lib/winintel-server-doctor")
    parser.add_argument("--config", default="/etc/winintel-server-doctor/monitor.json")
    args = parser.parse_args()
    os.umask(0o077)
    directory = Path(args.state_dir)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "monitor.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state_file = directory / "state.json"
        previous = json.loads(state_file.read_text()) if state_file.exists() else {}
        config_path = Path(args.config)
        config = json.loads(config_path.read_text()) if config_path.exists() else {}
        current = snapshot(previous)
        events = anomalies(previous, current)
        payload = {
            "brand": "winintel AI", "host": current["host"],
            "time": current["time"], "events": events,
            "kind": "anomaly" if events else "heartbeat",
            "boot_id": current["boot_id"], "gpu_count": len(current["gpus"]),
        }
        if events:
            with (directory / "alerts.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        queue_file = directory / "pending.json"
        pending = json.loads(queue_file.read_text()) if queue_file.exists() else []
        if config.get("webhook_url") and (events or config.get("send_heartbeat", True)):
            pending.append(payload)
        atomic_json(queue_file, pending)
        atomic_json(state_file, current)
        delivered = 0
        if config.get("webhook_url"):
            while pending and delivered < 10:
                try:
                    deliver(config["webhook_url"], pending[0])
                except (OSError, ValueError):
                    # Do not print an endpoint that might contain a secret token.
                    print(json.dumps({"delivery": "FAILED", "pending": len(pending)}))
                    break
                pending.pop(0)
                delivered += 1
                atomic_json(queue_file, pending)
        print(json.dumps({
            "events": len(events), "delivered": delivered, "pending": len(pending),
            "external_alerting": bool(config.get("webhook_url")),
            "state": str(state_file), "alerts": str(directory / "alerts.jsonl"),
        }))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
