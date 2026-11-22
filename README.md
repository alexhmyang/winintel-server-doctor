# ⚡ winintel AI Server Doctor

### Ubuntu setup. Tesla V100 stress tests. Evidence you can share.

[![License: MIT](https://img.shields.io/badge/our_code-MIT-75d9ff.svg)](LICENSE)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04%20%7C%2024.04-E95420.svg)](docs/INSTALL.md)

🌐 **[winintel.com](https://winintel.com)** · 📺 **[Bilibili](https://space.bilibili.com/429959998)** · 🎬 **[YouTube](https://www.youtube.com/@winintelcom)** · 🇨🇳 **[中文教程](README.zh-CN.md)**

Give customers and their AI Agents one consistent workflow to install a V100-compatible NVIDIA driver, choose CUDA, check hardware, and generate a readable acceptance report.

**🚀 Install · 🔥 Stress · 🔎 Measure · 📊 Report**

| What you get | How it works |
|---|---|
| 🟢 V100 driver setup | Latest proprietary **R580-server patch available in Ubuntu APT**, with signed Ubuntu packages |
| 🧰 CUDA selection | **12.8.1**, **11.6.2**, and **13.0.2** toolkit-only installers; side-by-side environments |
| 🔥 GPU burn-in | Vendored **gpu-burn**, compiled for **SM70**, computed-result checks per GPU, ECC checks, power/utilization CSV |
| ⚙️ CPU & RAM | **stress-ng** verification and **sysbench** repeatable measurements |
| 💾 Storage | **fio** CRC32C verification, sequential read/write and 4K random-read IOPS on a unique scratch file |
| 🔌 PCIe & interconnect | Negotiated lane count/speed, pinned-memory H2D/D2H transfers, CUDA P2P bandwidth/latency matrices |
| 📊 Reports | Standalone **HTML + JSON + Markdown**, with per-check PASS / FAIL / UNKNOWN and evidence logs |
| 🤖 Agent workflow | Dry-run plans, explicit arguments, configurable thresholds, stable exit codes, [AGENTS.md](AGENTS.md) |
| 🇨🇳 China-first downloads | Tsinghua Ubuntu mirror + NVIDIA China toolkit downloads; vendored GPU sources require no build-time GitHub fetch |

## Start here

Download and extract the [v0.1.0 release bundle](https://github.com/alexhmyang/winintel-server-doctor/releases/tag/v0.1.0), or clone this repository. For China networks, distribute the same checksum-verified bundle through your company's domestic download service.

```bash
cd winintel-server-doctor
sudo bash install.sh
```

Restart during your maintenance window, then:

```bash
nvidia-smi
winintel-doctor inventory
sudo winintel-doctor test \
  --profile /opt/winintel-server-doctor/profiles/v100-sxm2-8gpu.json \
  --disk-path /var/tmp --seconds 60
```

Open the generated `reports/<timestamp>/report.html`. Give `report.json` to your AI Agent. Reports stay on your machine; nothing is uploaded automatically.

**Default installation: R580-server + CUDA 12.8 + all test tools.** Download size is several GB; allow roughly 10–30 minutes for setup depending on bandwidth, kernel compilation, and cached files. A 60-second acceptance run typically takes 8–15 minutes. Run during maintenance: tests consume GPU, CPU, RAM and storage resources.

## V100 compatibility comes first

| Choice | V100 compute | Supported Ubuntu in this project |
|---|---|---|
| Proprietary R580-server | ✅ Last NVIDIA driver branch supporting Volta | 22.04 / 24.04 |
| CUDA 12.8.1 | ✅ Recommended default | 22.04 / 24.04 |
| CUDA 11.6.2 | ✅ Legacy toolchain, GCC 10 environment | 22.04; use a container on 24.04 |
| CUDA 13.0.2 | ❌ Volta compilation and library support removed | 22.04 / 24.04, compatible newer GPUs only |

`nvidia-smi` showing “CUDA Version: 13.x” describes a **driver API capability**, not V100 support in the CUDA 13 toolkit. Never compile V100 programs using CUDA 13.

```bash
# V100: install both supported toolkits
sudo bash install.sh --cuda 12.8,11.6

# Ubuntu 22.04: install all requested toolkits, including a toolkit-only CUDA 13
# for newer GPUs/cross-development. V100 tools/default remain on CUDA 12.8.
sudo bash install.sh --cuda all --allow-unsupported-cuda13

# Select a toolkit in this shell
source /opt/winintel-server-doctor/cuda-env.sh 12.8
```

“Latest” means the newest compatible R580-server patch published by Ubuntu's package maintainers and synchronized to the selected mirror. It does not mean installing an incompatible R595/R620 driver or claiming the Ubuntu package is always identical to NVIDIA's newest upstream patch.

## Make “pass” mean something

The bundled 8×V100 SXM2 profile checks GPU count, model, VRAM, 300 W power limit, PCIe Gen3 ×16, and 10,000 MB/s H2D/D2H transfer floors. It is a **starting profile**, not a universal hardware warranty. PCIe V100 boards often have a 250 W limit: edit the profile for the actual board.

Set CPU, RAM and disk thresholds from the purchased configuration and a same-settings baseline:

```json
{
  "name": "Customer order acceptance",
  "gpu_count": 8,
  "gpu_name_contains": "V100",
  "cpu_logical_min": 64,
  "ram_gib_min": 500,
  "ram_populated_dimms_min": 16,
  "ram_configured_mhz_min": 2666,
  "disk_read_mib_s_min": 1500,
  "disk_write_mib_s_min": 1000,
  "disk_randread_iops_min": 100000
}
```

These numbers are **example targets**, not measured results. Fields absent or `null` remain UNKNOWN. A complete acceptance profile must cover the checks you want accepted. Memory channels require vendor-confirmed DIMM locator mapping; the tool never equates DIMM count with channel count. See [testing methodology](docs/TESTING.md).

## Automation

```bash
sudo bash install.sh --dry-run
winintel-doctor test --profile customer.json --dry-run

sudo winintel-doctor test --profile customer.json --seconds 300 \
  --disk-path /mnt/customer-nvme --output /var/tmp/customer-acceptance
```

| Exit code | Meaning |
|---|---|
| `0` | All emitted acceptance checks pass; dry-run also returns 0 |
| `2` | One or more checks fail; also argparse usage errors, which emit no report |
| `3` | Incomplete: missing tool/data/threshold, skipped test, timeout or interruption |
| Other nonzero | Installer/system error; inspect stderr and installation log |

The final stdout line contains report paths and status as JSON; progress goes to stderr. Report directories are private by default and may contain process IDs, device topology and filesystem paths. Share the rendered report deliberately.

## Transparent foundations

This project integrates established tools; it does not claim to invent a GPU benchmark or NVIDIA driver. Original licenses and source headers remain in `vendor/`. [THIRD_PARTY.md](THIRD_PARTY.md) records pinned upstream versions.

**Release validation:** see [VALIDATION.md](docs/VALIDATION.md) for the actual checks performed and their limits. Full driver installation and V100 hardware burn-in must be validated on native Ubuntu before treating a specific server as accepted.

⭐ If this saves a customer setup call, **star the repository** and share your hardware profile. Follow **winintel AI** for practical AI server deployment guides.

Maintained by **数萌AI服务器 (winintel)** · [winintel.com](https://winintel.com) · service@winintel.com. AI assistance was used for orchestration and documentation.

## Official references

- [NVIDIA GPU architecture / driver / CUDA matrix](https://docs.nvidia.com/datacenter/tesla/drivers/cuda-toolkit-driver-and-architecture-matrix.html)
- [NVIDIA driver lifecycle and support](https://docs.nvidia.com/datacenter/tesla/drivers/supported-drivers-and-cuda-toolkit-versions.html)
- [CUDA 12.8 Linux installation guide](https://docs.nvidia.com/cuda/archive/12.8.1/cuda-installation-guide-linux/index.html)
- [CUDA 13.0 release notes](https://docs.nvidia.com/cuda/archive/13.0.0/cuda-toolkit-release-notes/index.html)
