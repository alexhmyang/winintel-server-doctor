# v0.1.0 validation

Author: 数萌AI服务器 (winintel) | winintel.com

Validation date: **2026-11-22**.

## Checks performed

- **13 behavioral tests passed**, including unavailable readings, missing thresholds, faulty GPU output with zero process exit, timeout, customer-file preservation, HTML escaping, and vendor-mapped memory channels.
- **Bash syntax checks and ShellCheck passed** for the installer, environment selector and CLI launcher.
- **Ruff checks passed** for the Python CLI and tests using Python 3.10-compatible rules.
- **Native Ubuntu 22.04 V100 inventory and dry-run passed** on an 8×Tesla V100-SXM2-32GB system using R580.178.04, 300 W limits. The inventory report contained 42 passing checks and 6 UNKNOWN checks, correctly remaining INCOMPLETE because performance/unspecified checks were not accepted.
- **Actual CPU/RAM/storage CLI smoke run passed its tool executions** on Ubuntu 24.04 under WSL: stress-ng CPU/VM verification, sysbench CPU/memory, fio 1GiB CRC32C preparation/verification, sequential read/write and random reads. Each timed tool used 10 seconds. All 9 invoked commands returned zero. The overall report remained INCOMPLETE, as expected, because GPU stress was skipped and acceptance thresholds were not supplied.
- **WSL driver installation was correctly refused.**
- NVIDIA China URLs for CUDA **12.8.1**, **13.0.2**, and **11.6.2** returned HTTP 200 in availability checks. Full CUDA archives were not downloaded during this validation.
- Public sources retain the pinned gpu-burn and CUDA Samples licenses and original headers.

## Practical limits

This release has **not** completed an end-to-end clean NVIDIA-driver/CUDA installation, a local build of all GPU tools, or a new V100 burn-in run. The native V100 host had active GPU workloads, so validation there was limited to read-only inventory and installation planning.

The WSL smoke run verifies the orchestration and safe scratch-file path; its speed results are not a V100 server baseline and are not advertised as customer acceptance scores.

Before accepting a customer server, complete native Ubuntu installation, scheduled reboot, GPU tool builds, and the full run with order-specific thresholds. A 60-second default test is a short acceptance check, not a long-term reliability certification.
