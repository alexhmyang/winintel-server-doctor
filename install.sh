#!/usr/bin/env bash
# Author: 数萌AI服务器 (winintel) | winintel.com
set -Eeuo pipefail
umask 022
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CUDA_VERSIONS=12.8
DRIVER=1
TOOLS=1
ALLOW13=0
DRY_RUN=0
PREFIX=/opt/winintel-server-doctor
CACHE=/var/cache/winintel-server-doctor
UBUNTU_MIRROR="${WININTEL_UBUNTU_MIRROR:-https://mirrors.tuna.tsinghua.edu.cn/ubuntu}"
CUDA_MIRROR="${WININTEL_CUDA_MIRROR:-https://developer.download.nvidia.cn/compute/cuda}"
usage() {
    cat <<'EOF'
winintel AI Server Doctor installer (Ubuntu 22.04/24.04 x86_64)
  sudo bash install.sh [options]
  --cuda 12.8|11.6|13.0|all|none   Comma-separated versions; default 12.8
  --skip-driver                    Keep the installed driver
  --skip-tools                     Do not build benchmark programs
  --allow-unsupported-cuda13        Install toolkit only on V100; keep 12.8 default
  --prefix /absolute/path          Default /opt/winintel-server-doctor
  --dry-run                        Print plan without downloading/changing anything
  --help
Driver: newest Ubuntu-packaged proprietary R580-server patch (V100 compatible).
CUDA 13 does NOT support V100 compute. CUDA 11.6 requires Ubuntu 22.04 here.
No automatic reboot, power-limit change, or benchmark execution.
EOF
}
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
run() {
    printf '+ '; printf '%q ' "$@"; printf '\n'
    if (( ! DRY_RUN )); then "$@"; fi
}
while (( $# )); do
    case "$1" in
        --cuda) [[ $# -ge 2 ]] || die "Missing CUDA version"; CUDA_VERSIONS=$2; shift 2 ;;
        --skip-driver) DRIVER=0; shift ;;
        --skip-tools) TOOLS=0; shift ;;
        --allow-unsupported-cuda13) ALLOW13=1; shift ;;
        --prefix) [[ $# -ge 2 ]] || die "Missing prefix"; PREFIX=$2; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        --help|-h) usage; exit 0 ;;
        *) die "Unknown option: $1" ;;
    esac
done
[[ "$PREFIX" = /* && "$PREFIX" != / && "$PREFIX" != *$'\n'* ]] || die "Invalid prefix"
[[ -f /etc/os-release ]] || die "Ubuntu required"
# shellcheck disable=SC1091
source /etc/os-release
[[ "$ID" = ubuntu && "$VERSION_ID" =~ ^(22.04|24.04)$ ]] || die "Ubuntu 22.04/24.04 required"
[[ "$(uname -m)" = x86_64 ]] || die "Only x86_64 is supported"
if grep -qi microsoft /proc/sys/kernel/osrelease; then
    die "WSL uses the Windows host driver. Use this installer on native Ubuntu."
fi
(( DRY_RUN || EUID == 0 )) || die "Run with sudo"
[[ "$CUDA_VERSIONS" != all ]] || CUDA_VERSIONS=12.8,11.6,13.0
IFS=, read -r -a VERSIONS <<< "$CUDA_VERSIONS"
[[ ${#VERSIONS[@]} -gt 0 ]] || die "Empty CUDA selection"
HAS12=0
HAS13=0
for version in "${VERSIONS[@]}"; do
    case "$version" in
        12.8) HAS12=1 ;;
        13.0) HAS13=1 ;;
        11.6) [[ "$VERSION_ID" = 22.04 ]] || die "11.6 supported only on Ubuntu 22.04; use a container on 24.04" ;;
        none) [[ ${#VERSIONS[@]} = 1 ]] || die "none cannot be combined" ;;
        *) die "Unsupported CUDA version: $version" ;;
    esac
done
GPU_INFO="$(lspci -nn 2>/dev/null || true)"
if (( HAS13 )) && grep -Eqi 'V100|GV100|GP10[02467]|GM[12][0-9][0-9]' <<< "$GPU_INFO"; then
    (( ALLOW13 && HAS12 )) || die "CUDA 13 cannot run on Volta/Pascal/Maxwell. Use 12.8, or explicitly install both with --allow-unsupported-cuda13."
fi
# Unknown hardware requires an explicit acknowledgement too.
if (( HAS13 && ! ALLOW13 )) && ! grep -Eqi 'TU10[246]|GA10[02467]|GH100|AD10[2467]|GB[12][0-9][0-9]' <<< "$GPU_INFO"; then
    die "CUDA 13 GPU compatibility unknown; inspect lspci first or use --allow-unsupported-cuda13"
fi
if (( DRIVER )); then
    for sb_file in /sys/firmware/efi/efivars/SecureBoot-*; do
        [[ -f "$sb_file" ]] || continue
        sb_state="$(od -An -t u1 -j4 -N1 "$sb_file" 2>/dev/null || true)"
        [[ "${sb_state// /}" != 1 ]] || die "Secure Boot enabled; follow docs/INSTALL.md before unattended driver installation"
    done
    if command -v mokutil >/dev/null && mokutil --sb-state 2>/dev/null | grep -qi enabled; then
        die "Secure Boot enabled: follow docs/INSTALL.md for signed modules/MOK before unattended installation"
    fi
    if [[ -f /var/log/nvidia-installer.log ]] && ! dpkg-query -W nvidia-driver-580-server >/dev/null 2>&1; then
        die "Possible .run driver installation detected. Follow docs/INSTALL.md before switching to APT."
    fi
    if command -v nvidia-smi >/dev/null; then
        ACTIVE="$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null || true)"
        [[ ! "$ACTIVE" =~ [0-9] ]] || die "GPU processes are running; schedule a maintenance window"
    fi
fi
for url in "$UBUNTU_MIRROR" "$CUDA_MIRROR"; do
    [[ "$url" = https://* && "$url" != *[[:space:]]* ]] || die "Mirrors must use HTTPS without whitespace"
done
printf 'Ubuntu %s; CUDA %s; driver R580-server; destination %s\n' "$VERSION_ID" "$CUDA_VERSIONS" "$PREFIX"
if (( DRY_RUN )); then
    printf 'Plan: Ubuntu packages from %s; toolkit-only installers from %s\n' "$UBUNTU_MIRROR" "$CUDA_MIRROR"
    printf 'Plan: latest signed R580-server APT patch; CUDA defaults to 12.8 when selected.\n'
    exit 0
fi
install -d -m 755 "$PREFIX" "$CACHE"
exec 9>"$CACHE/install.lock"
flock -n 9 || die "Another installation is running"
LOG="$CACHE/install-$(date -u +%Y%m%dT%H%M%SZ).log"
exec > >(tee -a "$LOG") 2>&1
trap 'printf "Installation failed at line %s. Log: %s\n" "$LINENO" "$LOG" >&2' ERR
APT_SOURCE="$CACHE/ubuntu.sources.list"
printf 'deb %s %s main restricted universe multiverse\n' "$UBUNTU_MIRROR" "$VERSION_CODENAME" > "$APT_SOURCE"
printf 'deb %s %s-updates main restricted universe multiverse\n' "$UBUNTU_MIRROR" "$VERSION_CODENAME" >> "$APT_SOURCE"
printf 'deb %s %s-security main restricted universe multiverse\n' "$UBUNTU_MIRROR" "$VERSION_CODENAME" >> "$APT_SOURCE"
APT=(apt-get -o "Dir::Etc::sourcelist=$APT_SOURCE" -o "Dir::Etc::sourceparts=-"
    -o Acquire::Retries=3 -o APT::Update::Error-Mode=any)
run "${APT[@]}" update
PACKAGES=(ca-certificates curl build-essential pciutils dmidecode smartmontools
    nvme-cli stress-ng sysbench fio numactl mokutil python3 python3-venv)
if (( DRIVER )); then PACKAGES+=("linux-headers-$(uname -r)" nvidia-driver-580-server); fi
if [[ ",$CUDA_VERSIONS," = *,11.6,* ]]; then PACKAGES+=(gcc-10 g++-10); fi
if (( DRIVER )); then
    CANDIDATE="$(apt-cache -o "Dir::Etc::sourcelist=$APT_SOURCE" -o "Dir::Etc::sourceparts=-" policy nvidia-driver-580-server | awk '/Candidate:/ {print $2}')"
    [[ "$CANDIDATE" =~ ^580[.] ]] || die "R580-server unavailable from the selected Ubuntu mirror; no unsupported branch will be installed"
fi
export DEBIAN_FRONTEND=noninteractive
run "${APT[@]}" install -y --no-install-recommends "${PACKAGES[@]}"
for version in "${VERSIONS[@]}"; do
    [[ "$version" != none ]] || continue
    case "$version" in
        12.8) release=12.8.1; file=cuda_12.8.1_570.124.06_linux.run ;;
        13.0) release=13.0.2; file=cuda_13.0.2_580.95.05_linux.run ;;
        11.6) release=11.6.2; file=cuda_11.6.2_510.47.03_linux.run ;;
    esac
    DEST="/usr/local/cuda-$version"
    if [[ -x "$DEST/bin/nvcc" ]] && "$DEST/bin/nvcc" --version | grep -q "release $version,"; then
        printf 'Already installed: %s\n' "$DEST"
        continue
    fi
    DOWNLOAD="$CACHE/$file"
    run curl --fail --location --retry 3 --connect-timeout 20 --continue-at - \
        --output "$DOWNLOAD" "$CUDA_MIRROR/$release/local_installers/$file"
    # The self-extracting NVIDIA archive checks its embedded integrity data.
    run sh "$DOWNLOAD" --check
    # Preserve the administrator's existing global CUDA symlink.
    link_state=directory
    saved_link=
    if [[ -L /usr/local/cuda ]]; then
        link_state=symlink
        saved_link="$(readlink /usr/local/cuda)"
    elif [[ ! -e /usr/local/cuda ]]; then
        link_state=absent
    fi
    installer_status=0
    run sh "$DOWNLOAD" --silent --toolkit --toolkitpath="$DEST" || installer_status=$?
    if [[ "$link_state" = symlink ]]; then
        ln -sfn "$saved_link" /usr/local/cuda
    elif [[ "$link_state" = absent && -L /usr/local/cuda ]]; then
        # Remove only the default symlink newly created by this toolkit installer.
        if [[ "$(readlink -f /usr/local/cuda)" = "$DEST" ]]; then
            rm -- /usr/local/cuda
        fi
    fi
    (( installer_status == 0 )) || die "CUDA $version installer exited $installer_status"
    "$DEST/bin/nvcc" --version
done
# Keep toolkit selection local to this product rather than replacing /usr/local/cuda.
DEFAULT=12.8
if (( ! HAS12 )); then DEFAULT="${VERSIONS[0]}"; fi
if [[ "$DEFAULT" != none ]]; then
    printf '%s\n' "$DEFAULT" > "$PREFIX/default-cuda"
fi
run cp -a "$ROOT/doctor.py" "$ROOT/profiles" "$ROOT/vendor" "$ROOT/cuda-env.sh" "$ROOT/winintel-doctor" "$PREFIX/"
run chmod 755 "$PREFIX/winintel-doctor"
if (( TOOLS )); then
    [[ -x /usr/local/cuda-12.8/bin/nvcc ]] || die "Tool builds require CUDA 12.8; install it or use --skip-tools"
    run make -C "$PREFIX/vendor/gpu-burn" -j"$(nproc)" COMPUTE=70 CUDAPATH=/usr/local/cuda-12.8
    install -d "$PREFIX/bin"
    for tool in deviceQuery bandwidthTest p2pBandwidthLatencyTest; do
        source_file="$PREFIX/vendor/cuda-samples/$tool/$tool.cu"
        if [[ "$tool" = deviceQuery ]]; then
            source_file="$PREFIX/vendor/cuda-samples/$tool/$tool.cpp"
        fi
        run /usr/local/cuda-12.8/bin/nvcc -O3 -std=c++17 -arch=sm_70 \
            -I "$PREFIX/vendor/cuda-samples/Common" \
            "$source_file" -o "$PREFIX/bin/$tool"
    done
fi
ln -sfn "$PREFIX/winintel-doctor" /usr/local/bin/winintel-doctor
printf 'Installation complete. Log: %s\n' "$LOG"
printf 'Next: reboot in your maintenance window, then run nvidia-smi and winintel-doctor inventory.\n'
printf 'Benchmarks: sudo winintel-doctor test --profile %s/profiles/v100-sxm2-8gpu.json\n' "$PREFIX"
