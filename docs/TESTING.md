# Hardware acceptance methodology

Author: 数萌AI服务器 (winintel) | winintel.com

## What is measured

| Area | Tool / measurement | What a pass proves |
|---|---|---|
| GPU inventory | nvidia-smi | Driver query works; count/model/VRAM meet the supplied order |
| GPU correctness | gpu-burn FP32 and FP64, matrixMul, simpleCUBLAS_LU | Completed per-GPU arithmetic comparisons and independent reference validation |
| GPU VRAM | cuda_memtest 0–8, 10; optional 9 | Completed requested pattern passes on the reported allocation |
| GPU ECC | NVIDIA XML before and after all GPU tests | Supported volatile/aggregate memory/register/cache counters and retirement state checked |
| GPU operating state | nvidia-smi CSV every second | Power/utilization/SM-clock evidence; power limits are never changed |
| PCIe | sysfs + bandwidthTest | Negotiated lane count/rate and achieved pinned host transfer speed |
| Multi-GPU | topo -m + parsed CUDA P2P matrices | Measured NVLink-connected pairs in both directions; non-P2P fallback is not accepted as NVLink speed |
| CPU | stress-ng --verify + sysbench prime=20000 | Verification workload completed and configured events/s target met |
| RAM correctness | stress-ng VM --verify, 25% available memory | Verification workload passed for the tested allocation/time |
| RAM write | sysbench, 64MiB, one thread | Repeatable workload metric; not full memory-channel bandwidth |
| Storage correctness | fio CRC32C write/read verification | Scratch-file data verified successfully |
| Storage throughput | fio QD32, direct, sequential 1MiB / random 4KiB reads | Filesystem/device path meets the supplied same-settings targets |

CUDA Samples describe their results as illustrative and variable with GPU Boost. We use them as transparent diagnostic baselines, not certified hardware benchmark rankings.

Default burn-in is 60 seconds per arithmetic stress tool. Increase to `--seconds 300` or longer for sustained acceptance. VRAM pattern suites have their own `--vram-passes` and `--vram-timeout`, defaulting to one pass and 1800 seconds per GPU. `--seconds` does not truncate the VRAM patterns. A short pass does not establish long-term hardware reliability. No model is downloaded or inference benchmark implied.

Use `--vram-passes 32` for the upstream test6 pattern rotation. `--bit-fade` adds test9, which sleeps and verifies two patterns over approximately three hours per pass and GPU. The CLI requires `--vram-timeout` at least `10800 * passes + 1800`. All required per-test completion markers and the normal exit marker are checked. Allocation coverage uses allocated MiB / reported driver-visible capacity; compare it to `gpu_vram_coverage_pct_min` (for example, 90). Driver-reserved memory cannot be tested.

ECC counters are matched by UUID across snapshots. Positive corrected/uncorrected changes fail acceptance; missing baselines and counter resets are UNKNOWN. Existing uncorrectable/retired/remapped evidence also fails. Unsupported locations are retained in inventory without pretending they are error-free. Arithmetic correctness and ECC are complementary tests.

## Profiles

All threshold keys accept a finite, non-negative number or `null`; count equality is used for `gpu_count`, while the other numeric thresholds are minimums. `gpu_name_contains` is a case-insensitive substring. Unknown keys are rejected so a typo cannot silently disable a check.

CPU events/s, RAM MiB/s and disk speeds depend on exact settings and hardware. Create a reference result on a known-good equivalent server, then set the order-specific acceptance floors. `ram_configured_mhz_min` is a legacy field name: its reading is the numeric DMI configured transfer-rate field, usually MT/s, not an inferred DDR clock.

An idle PCIe link may read Gen1 even after a short transfer. A link-rate failure requires checking sustained-transfer behavior, BIOS settings, slot wiring, risers and negotiated width. A reported ×16 slot does not prove downstream switches have unlimited aggregate bandwidth.

## Memory channels

Inventory records populated DIMM sizes, manufacturers, part numbers, bank/slot locators and configured speed. `--include-serials` includes private component serials for customer support. DMI does not provide a universal reliable channel map, so the report defaults to UNKNOWN.

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

SMART, PCIe peripherals, USB, network and optional BMC evidence are collected; unsupported controllers and missing permissions remain UNKNOWN. Inventory is not a full electrical test of every peripheral, SSD remaining-life certification, CPU PPIN capture, full RAM allocation test, IB throughput test or AI model evaluation.

## Report states

PASS means an emitted check passed. FAIL takes precedence over UNKNOWN. Otherwise UNKNOWN makes the report INCOMPLETE. An inventory-only report is intentionally incomplete for performance acceptance.

Missing thresholds, missing tools, skipped categories, a duration that ends too early, timeout and interruption never become a pass. GPU burn output is checked per GPU because a zero gpu-burn process exit code alone does not prove correctness.

JSON contains the profile, inventory, checks, command arguments, timings and relative log paths. HTML displays GPU/DIMM/disk tables and full collected inventory; Markdown retains inventory too. HTML needs no server or external assets. JSON/HTML/Markdown and logs are private by default (`umask 077`); raw diagnostic logs may contain identifiers even without `--include-serials`. Inspect before publishing.
