# Hardware acceptance methodology

Author: 数萌AI服务器 (winintel) | winintel.com

## What is measured

| Area | Tool / measurement | What a pass proves |
|---|---|---|
| GPU inventory | nvidia-smi | Driver query works; count/model/VRAM meet the supplied order |
| GPU correctness | gpu-burn | Each GPU reports OK after the requested workload duration |
| GPU memory errors | ECC before and after burn | No reported uncorrectable volatile ECC |
| GPU operating state | nvidia-smi CSV every second | Power/utilization/SM-clock evidence; power limits are never changed |
| PCIe | sysfs + bandwidthTest | Negotiated lane count/rate and achieved pinned host transfer speed |
| Multi-GPU | topo -m + p2pBandwidthLatencyTest | Peer transfer matrices produced successfully; not an NVLink universal score |
| CPU | stress-ng --verify + sysbench prime=20000 | Verification workload completed and configured events/s target met |
| RAM correctness | stress-ng VM --verify, 25% available memory | Verification workload passed for the tested allocation/time |
| RAM write | sysbench, 64MiB, one thread | Repeatable workload metric; not full memory-channel bandwidth |
| Storage correctness | fio CRC32C write/read verification | Scratch-file data verified successfully |
| Storage throughput | fio QD32, direct, sequential 1MiB / random 4KiB reads | Filesystem/device path meets the supplied same-settings targets |

CUDA Samples describe their results as illustrative and variable with GPU Boost. We use them as transparent diagnostic baselines, not certified hardware benchmark rankings.

Default burn-in is 60 seconds per tool. Increase to `--seconds 300` or longer for sustained acceptance. A short pass does not establish long-term hardware reliability. No model is downloaded or inference benchmark implied.

## Profiles

All threshold keys accept a finite, non-negative number or `null`; count equality is used for `gpu_count`, while the other numeric thresholds are minimums. `gpu_name_contains` is a case-insensitive substring. Unknown keys are rejected so a typo cannot silently disable a check.

CPU events/s, RAM MiB/s and disk speeds depend on exact settings and hardware. Create a reference result on a known-good equivalent server, then set the order-specific acceptance floors. `ram_configured_mhz_min` is a legacy field name: its reading is the numeric DMI configured transfer-rate field, usually MT/s, not an inferred DDR clock.

An idle PCIe link may read Gen1 even after a short transfer. A link-rate failure requires checking sustained-transfer behavior, BIOS settings, slot wiring, risers and negotiated width. A reported ×16 slot does not prove downstream switches have unlimited aggregate bandwidth.

## Memory channels

Inventory records populated DIMM sizes, bank/slot locators and configured speed. It omits DIMM serial numbers. DMI does not provide a universal reliable channel map, so the report defaults to UNKNOWN.

If the manufacturer's documentation confirms locators such as `CPU1_CH0_DIMM0`, a profile can supply:

```json
{
  "name": "Vendor-confirmed example ONLY; adapt to the real locators",
  "ram_channel_locator_regex": "CPU([0-9]+)_CH([0-9]+)_DIMM[0-9]+",
  "ram_channels_min": 12
}
```

The capture groups identify the CPU and channel. Two DIMMs in the same CPU/channel tuple count once. Every populated DIMM must match; otherwise the channel count remains UNKNOWN. Validate the regex against the mainboard manual first. This checks populated channels, not electrically measured channel bandwidth or firmware interleaving.

## Storage scope

`--disk-path` must name an existing directory with scratch space. `findmnt` records the filesystem path; `lsblk` records device inventory. A unique `.winintel-fio-*` temporary directory is created and cleaned up. No existing customer file or raw disk is opened as an fio target. Scratch writes still consume SSD endurance and storage bandwidth.

The default scratch size is 4 GiB. Preparation writes and verifies the entire file; three timed measurements reuse it. Preparation is capped at 600 seconds. Unsupported direct I/O, missing tools and timeouts are reported. Increase `--disk-size-gib` for larger working sets; results may still reflect a controller cache.

This first release does not certify SMART lifetime health, CPU PPIN, disk/GPU serial tracking, full RAM capacity, all PCIe peripherals, IB fabric throughput or AI model performance. These require separate checks and baselines.

## Report states

PASS means an emitted check passed. FAIL takes precedence over UNKNOWN. Otherwise UNKNOWN makes the report INCOMPLETE. An inventory-only report is intentionally incomplete for performance acceptance.

Missing thresholds, missing tools, skipped categories, a duration that ends too early, timeout and interruption never become a pass. GPU burn output is checked per GPU because a zero gpu-burn process exit code alone does not prove correctness.

JSON contains the profile, inventory, checks, command arguments, timings and relative log paths. HTML needs no server or external assets. JSON/HTML/Markdown and logs are private by default (`umask 077`); they can include topology, process IDs and filesystem paths. Inspect before publishing.
