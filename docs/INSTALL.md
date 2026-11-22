# Installation guide

Author: 数萌AI服务器 (winintel) | winintel.com

## Supported systems

Native Ubuntu 22.04 or 24.04, x86_64, sudo/root access, sufficient disk space, and an internet connection to the configured HTTPS mirrors. WSL is refused: it uses a Windows host driver. Virtual machines must expose a correctly passed-through GPU.

Allow approximately 15–30 GiB free for downloads, installed toolkits and staging when choosing multiple CUDA versions. A single CUDA 12.8 installer is about 5.4 GB. Cached downloads resume and an already-present matching toolkit is skipped.

## Default installation

```bash
sudo bash install.sh --dry-run
sudo bash install.sh
```

The script uses an isolated APT source list in `/var/cache/winintel-server-doctor`; it does not replace the administrator's global sources. Ubuntu APT signatures remain enabled. The proprietary `nvidia-driver-580-server` package installs the newest available compatible patch, including DKMS/kernel dependencies.

CUDA uses fixed patch-version NVIDIA China `.run` archives with **only `--toolkit` selected**. Bundled older drivers are not installed. The archive's embedded integrity check runs before installation. These checks plus HTTPS are not an independently pinned SHA-256 supply-chain attestation; mirror overrides must be trusted. Release-bundle checksums cover this project's files, not the separately downloaded CUDA archives.

The installed CLI is `/usr/local/bin/winintel-doctor`; its files live under `/opt/winintel-server-doctor`. GPU tools are built locally for SM70 using CUDA 12.8. Their source is vendored with licenses.

The CLI uses an isolated uv-managed Python 3.10+ environment with standard-library code and no pip dependencies. An existing uv binary can be reused with `WININTEL_UV_BIN`; otherwise a pinned standalone uv archive is downloaded through `WININTEL_GITHUB_MIRROR` (default `https://ghfast.top`). No foreign-download fallback is used. Benchmark sources are already vendored.

`sudo bash install.sh --monitor` adds the persistent half-hour monitor. Existing-driver servers can run `sudo bash install-monitor.sh` alone. See [MONITORING.md](MONITORING.md) to configure an authorized alert receiver.

## Select CUDA

```bash
sudo bash install.sh --cuda 12.8,11.6
sudo bash install.sh --cuda 13.0 --skip-driver --skip-tools --allow-unsupported-cuda13
source /opt/winintel-server-doctor/cuda-env.sh 11.6
```

CUDA 11.6 installation is supported here only on Ubuntu 22.04, with GCC 10 installed for its legacy compiler. For 24.04, use a separately managed compatible container. Never add `--override` to force past an unsupported compiler.

On a V100 host, a CUDA 13 request requires both 12.8 and explicit `--allow-unsupported-cuda13`. The standalone 13.0 command above is intended for newer compatible GPUs. CUDA 13 support is detected conservatively; unknown device names require explicit acknowledgement. The default environment and V100 benchmark builds remain on 12.8 when it is selected.

The project does not replace `/usr/local/cuda` or global shell environments. Source `cuda-env.sh` to choose a version for the current terminal. The GCC 10 environment for 11.6 is cleared when switching back to 12.8/13.0.

## Existing drivers and Secure Boot

The installer refuses unattended driver changes while GPU compute processes are present. Stop workloads through their existing service manager during maintenance. A possible NVIDIA `.run` driver installation is refused; migrate to APT using the administrator-reviewed NVIDIA uninstaller procedure first. The script does not purge packages.

For Secure Boot, Ubuntu modules may require a trusted signing key and MOK enrollment at boot. Check:

```bash
mokutil --sb-state
ubuntu-drivers devices
```

Follow Ubuntu's [Secure Boot / DKMS instructions](https://wiki.ubuntu.com/UEFI/SecureBoot/DKMS). Install/enroll the signed driver through the administrator's established procedure; then run `install.sh --skip-driver`. Do not silently disable firmware Secure Boot for a customer.

R580 is Volta's final compatible branch. If it is missing from the configured mirror, installation stops instead of selecting R595/R620. Refresh the mirror or supply a trusted maintained domestic Ubuntu mirror:

```bash
sudo WININTEL_UBUNTU_MIRROR=https://mirrors.aliyun.com/ubuntu \
  bash install.sh
```

`WININTEL_CUDA_MIRROR` can point to a trusted domestic mirror with the same `VERSION/local_installers/FILENAME` layout. No automatic foreign-download fallback is used.

## After installation

The script never reboots automatically. Reboot during maintenance, then run `nvidia-smi` and inspect `dkms status` if the module does not load. With kernel headers unavailable for a custom kernel, use the server vendor's supported Ubuntu kernel/header pair.

```bash
winintel-doctor inventory
sudo winintel-doctor test --profile customer.json --disk-path /mnt/nvme
```

Installation logs are in `/var/cache/winintel-server-doctor/install-*.log`. Test reports are in the caller's `reports/` directory or the explicitly specified new `--output` directory. Existing output directories are refused to preserve previous results.
