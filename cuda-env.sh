#!/usr/bin/env bash
# Author: 数萌AI服务器 (winintel) | winintel.com
# Usage: source /opt/winintel-server-doctor/cuda-env.sh 12.8
winintel_cuda_env() {
    local version="${1:-12.8}"
    case "$version" in 11.6|12.8|13.0) ;; *) echo "Select 11.6, 12.8 or 13.0" >&2; return 1 ;; esac
    [[ -x "/usr/local/cuda-$version/bin/nvcc" ]] || { echo "Toolkit not installed" >&2; return 1; }
    export CUDA_HOME="/usr/local/cuda-$version"
    export PATH="$CUDA_HOME/bin:$PATH"
    export LD_LIBRARY_PATH="$CUDA_HOME/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    if [[ "$version" = 11.6 ]]; then
        export CC=/usr/bin/gcc-10 CXX=/usr/bin/g++-10 CUDAHOSTCXX=/usr/bin/g++-10
    else
        unset CC CXX CUDAHOSTCXX
    fi
    "$CUDA_HOME/bin/nvcc" --version
}
winintel_cuda_env "${1:-12.8}"
