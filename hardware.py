# Author: 数萌AI服务器 (winintel) | winintel.com
"""Parse NVIDIA hardware evidence without assuming board count or ECC support."""

import re
import xml.etree.ElementTree as ET


def gpu_details(text):
    """Return identity, supported ECC locations and retirement counters by index."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {}
    result = {}
    for index, node in enumerate(root.findall("gpu")):
        identity = {
            key: node.findtext(key) for key in (
                "product_name", "product_brand", "product_architecture",
                "uuid", "serial", "vbios_version", "board_id",
            )
        }
        name = identity["product_name"] or ""
        form = re.search(r"\b(SXM\d+|PCIE)\b", name, re.I)
        identity["form_factor"] = form[1].upper() if form else "UNKNOWN"
        identity["ecc_mode"] = node.findtext("ecc_mode/current_ecc")
        counters = {}
        for section in ("ecc_errors", "retired_pages", "remapped_rows"):
            subtree = node.find(section)
            if subtree is None:
                continue

            def leaves(parent, path):
                for child in parent:
                    key = f"{path}/{child.tag}"
                    if len(child):
                        leaves(child, key)
                    else:
                        if section != "remapped_rows" or child.tag in (
                            "correctable_error", "uncorrectable_error",
                            "remapping_pending", "remapping_failure",
                        ):
                            counters[key] = child.text

            leaves(subtree, section)
        identity["error_counters"] = counters
        result[str(index)] = identity
    return result


def matrices(text):
    """Parse CUDA sample matrices, preserving direction, units and GPU indices."""
    result = {}
    current = None
    columns = []
    for line in text.splitlines():
        if "Matrix" in line or ("Bandwidth" in line and "P2P=" in line):
            current = line.strip()
            result[current] = {}
            columns = []
        elif current and ("D\\D" in line or line.strip().startswith("GPU")):
            columns = re.findall(r"\d+", line)
        elif current and columns:
            cells = line.split()
            if len(cells) == len(columns) + 1 and cells[0].isdigit():
                try:
                    row = {column: float(value) for column, value in zip(columns, cells[1:])}
                except ValueError:
                    continue
                result[current][cells[0]] = row
    return result


def nvlink_pairs(text):
    """Identify directly NVLink-connected pairs from nvidia-smi topology."""
    columns = []
    pairs = set()
    for line in text.splitlines():
        cells = line.split()
        if not cells:
            continue
        if not columns and cells[0] == "GPU0":
            columns = [cell[3:] for cell in cells if re.fullmatch(r"GPU\d+", cell)]
        elif columns and re.fullmatch(r"GPU\d+", cells[0]):
            source = cells[0][3:]
            for target, link in zip(columns, cells[1:]):
                if source != target and re.fullmatch(r"NV\d+", link):
                    pairs.add(tuple(sorted((source, target), key=int)))
    return sorted(pairs, key=lambda pair: tuple(map(int, pair)))


def counter_changes(before, after):
    """Compare counters by UUID; missing, reset and unsupported remain visible."""
    changes = []
    old = {gpu.get("uuid"): gpu for gpu in before.values() if gpu.get("uuid")}
    for index, gpu in after.items():
        previous = old.get(gpu.get("uuid"), {})
        for key, raw in gpu.get("error_counters", {}).items():
            if not str(raw).isdigit():
                continue
            value = int(raw)
            prior = previous.get("error_counters", {}).get(key)
            delta = value - int(prior) if str(prior).isdigit() else None
            changes.append({
                "gpu": index, "uuid": gpu.get("uuid"), "counter": key,
                "before": prior, "after": value, "delta": delta,
            })
    return changes


def nvlink_counters(text):
    """Decode nvidia-smi NVLink error counters by GPU, link and error type."""
    result = {}
    gpu = "unknown"
    link = "unknown"
    for line in text.splitlines():
        match = re.match(r"\s*GPU\s+(\d+):", line)
        if match:
            gpu = match[1]
        match = re.search(r"Link\s+(\d+)", line)
        if match:
            link = match[1]
        match = re.search(r"((?:CRC|Replay|Recovery|Malformed|Buffer|ECC)[^:]*):\s*(\d+)\s*$", line, re.I)
        if match:
            result[f"{gpu}/{link}/{match[1].strip()}"] = int(match[2])
    return result
