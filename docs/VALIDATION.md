# Release validation

Author: 数萌AI服务器 (winintel) | winintel.com

Validation date: **2026-11-22**.

## v0.2.0 expanded checks

- **17 behavioral tests passed** under Linux/uv, including GPU UUID reordering, actual NVLink-pair selection, reboot/ECC/unknown-kernel detection and preserving failed webhook deliveries for retry.
- **Ruff, Bash syntax and ShellCheck passed** for the expanded source and installers.
- **All seven GPU executables built successfully** on native Ubuntu 22.04 with SM70 and CUDA 12.8.93: gpu-burn, deviceQuery, bandwidthTest, p2pBandwidthLatencyTest, matrixMul, double-precision simpleCUBLAS_LU and cuda_memtest. A compact NVIDIA China redistribution toolkit and the host's existing cuBLAS libraries were used for this build validation; this was not a clean full-toolkit installation.
- **Persistent systemd monitoring installed and executed** on the native 8×V100 server. Timer activation and service `Result=success`, `ExecMainStatus=0` were verified; the half-hour scheduled invocation also occurred. No real reboot was forced. Reboot detection and delivery retry were validated with simulated state transitions, without sending a production external alert.
- **Native detailed inventory captured** with component serials for private support reporting. Available GPU memory/register/L1/L2 volatile/aggregate ECC counters were zero at the observed snapshots. Unsupported counters remain recorded as N/A. A zero snapshot is not a burn-in result.

GPU burn-in, VRAM patterns, arithmetic reference execution and NVLink bandwidth **have not run on this busy V100 host**. Its existing eight GPU workloads were preserved. Tool build success and parser tests must not be represented as measured hardware acceptance. New NVIDIA family coverage and clean driver/CUDA installation remain unvalidated.

## v0.1.0 checks performed

- **13 behavioral tests passed**, including unavailable readings, missing thresholds, faulty GPU output with zero process exit, timeout, customer-file preservation, HTML escaping, and vendor-mapped memory channels.
- **Bash syntax checks and ShellCheck passed** for the installer, environment selector and CLI launcher.
- **Ruff checks passed** for the Python CLI and tests using Python 3.10-compatible rules.
- **Native Ubuntu 22.04 V100 inventory and dry-run passed** on an 8×Tesla V100-SXM2-32GB system using R580.178.04, 300 W limits. The inventory report contained 42 passing checks and 6 UNKNOWN checks, correctly remaining INCOMPLETE because performance/unspecified checks were not accepted.
- **Actual CPU/RAM/storage CLI smoke run passed its tool executions** on Ubuntu 24.04 under WSL: stress-ng CPU/VM verification, sysbench CPU/memory, fio 1GiB CRC32C preparation/verification, sequential read/write and random reads. Each timed tool used 10 seconds. All 9 invoked commands returned zero. The overall report remained INCOMPLETE, as expected, because GPU stress was skipped and acceptance thresholds were not supplied.
- **WSL driver installation was correctly refused.**
- NVIDIA China URLs for CUDA **12.8.1**, **13.0.2**, and **11.6.2** returned HTTP 200 in availability checks. Full CUDA archives were not downloaded during this validation.
- Public sources retain the pinned gpu-burn and CUDA Samples licenses and original headers.

## Practical limits

The original v0.1.0 validation did **not** include GPU tool builds. v0.2.0 adds successful native SM70 builds, but still has **not** completed an end-to-end clean NVIDIA-driver/CUDA installation or a new V100 burn-in run. The native V100 host had active GPU workloads.

The WSL smoke run verifies the orchestration and safe scratch-file path; its speed results are not a V100 server baseline and are not advertised as customer acceptance scores.

Before accepting a customer server, complete native Ubuntu installation, scheduled reboot, GPU tool builds, and the full run with order-specific thresholds. A 60-second default test is a short acceptance check, not a long-term reliability certification.
