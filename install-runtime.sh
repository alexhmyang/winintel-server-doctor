#!/usr/bin/env bash
# Author: 数萌AI服务器 (winintel) | winintel.com
set -Eeuo pipefail
PREFIX="${1:-/opt/winintel-server-doctor}"
[[ "$PREFIX" =~ ^/[a-zA-Z0-9_./-]+$ && "$PREFIX" != / ]] || exit 2
install -d -m 755 "$PREFIX"
UV="${WININTEL_UV_BIN:-$(command -v uv || true)}"
if [[ -z "$UV" ]]; then
    [[ -x "$PREFIX/uv" ]] && UV="$PREFIX/uv"
fi
if [[ -z "$UV" ]]; then
    MIRROR="${WININTEL_GITHUB_MIRROR:-https://ghfast.top}"
    [[ "$MIRROR" = https://* && "$MIRROR" != *[[:space:]]* ]] || exit 2
    STAGE="$(mktemp -d)"
    trap 'rm -rf -- "$STAGE"' EXIT
    curl --fail --location --retry 3 --connect-timeout 20 \
        "$MIRROR/https://github.com/astral-sh/uv/releases/download/0.8.13/uv-x86_64-unknown-linux-gnu.tar.gz" \
        -o "$STAGE/uv.tar.gz"
    tar -xzf "$STAGE/uv.tar.gz" -C "$STAGE"
    install -m 755 "$STAGE/uv-x86_64-unknown-linux-gnu/uv" "$PREFIX/uv"
    UV="$PREFIX/uv"
elif [[ "$UV" != "$PREFIX/uv" ]]; then
    install -m 755 "$UV" "$PREFIX/uv"
fi
if [[ ! -x "$PREFIX/.venv/bin/python" ]]; then
    "$PREFIX/uv" venv --offline --python /usr/bin/python3 "$PREFIX/.venv"
fi
