# Third-party sources

Author: 数萌AI服务器 (winintel) | winintel.com

Original benchmark code is redistributed without changing source headers. winintel AI provides the installer, CLI orchestration, profiles and reports.

| Component | Pinned version | License / location |
|---|---|---|
| [gpu-burn](https://github.com/wilicc/gpu-burn) | `0d19c94dcb2e9b6858b7586a4c327674cd67113b` | BSD-2-Clause, `vendor/gpu-burn/LICENSE` |
| [NVIDIA CUDA Samples](https://github.com/NVIDIA/cuda-samples) | `v12.8`, `db3eea23946bca2e90a75eca2b5b3e07158a9e11` | NVIDIA sample license, `vendor/cuda-samples/LICENSE` and file headers |
| [cuda_memtest](https://github.com/ComputationalRadiationPhysics/cuda_memtest) | `e94e1ee54e0689c9f154a8a08202554452552ec6` | Illinois/NCSA, `vendor/cuda_memtest/README.md` and source headers; CMake helper MIT |
| [uv](https://github.com/astral-sh/uv) | `0.8.13` standalone bootstrap, downloaded separately | MIT/Apache-2.0 upstream; not included in the source bundle |
| stress-ng | Ubuntu distribution package | Upstream package copyright |
| sysbench | Ubuntu distribution package | Upstream package copyright |
| fio | Ubuntu distribution package | Upstream package copyright |
| NVIDIA driver / CUDA Toolkit | Downloaded separately during installation | NVIDIA terms; not included in the project release bundle |

CUDA sample subset: deviceQuery, bandwidthTest, p2pBandwidthLatencyTest, matrixMul, simpleCUBLAS_LU and required Common headers. GPU kernels are upstream code; this project does not introduce a new GPU stress kernel. cuda_memtest is built with internal NVML monitoring disabled; NVIDIA XML snapshots and telemetry are collected by the separate orchestrator.

Ubuntu APT package versions and command timings are captured during installation/test execution. CUDA toolkits are fixed to 11.6.2, 12.8.1 and 13.0.2. No third-party inference engine or model weights are required.
