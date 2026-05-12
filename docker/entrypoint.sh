#!/usr/bin/env bash

set -euo pipefail

# SM_CODE_DIR is set by SageMaker for Training Jobs.
# For Processing Jobs, code is typically at /opt/ml/processing/input/code.
if [ -n "${SM_MODULE:-}" ]; then
    # Training Job context
    CODE_DIR="${HOME}/.local/lib/python3.13/site-packages" # Generic fallback if SM_MODULE is set but not installed
    # In SageMaker Training, the sourcedir.tar.gz is extracted to /opt/ml/code
    CODE_DIR="/opt/ml/code"
else
    # Processing Job context
    CODE_DIR="${SM_CODE_DIR:-/opt/ml/processing/input/code}"
fi

log() { echo "[entrypoint.sh] $*" >&2; }

# If 'CODE_DIR' contains '*.tar.gz' or '*.tgz' (tarball), extraer in-place.
if [ -d "$CODE_DIR" ]; then
    cd "$CODE_DIR"

    shopt -s nullglob
    tarballs=( *.tar.gz *.tgz )
    shopt -u nullglob

    for tarball in "${tarballs[@]}"; do
        log "Extracting '${tarball}'"
        tar -xzf "$tarball"
    done
else
    log "'${CODE_DIR}' does not exist"
fi

# Determinar script a ejecutar
if [ "$#" -gt 0 ]; then
    raw_script="$1"
    shift
    case "$raw_script" in
        "$CODE_DIR"/*) script="${raw_script#"$CODE_DIR"/}" ;;
        "train") script="main.py" ;; # SageMaker Training sends 'train'
        *) script="$raw_script" ;;
    esac
else
    script="main.py"
fi

if [ -d "$CODE_DIR" ] && [ ! -f "$script" ]; then
    cd "$CODE_DIR"
fi

log "Workdir: '$(pwd)'"
log "Script: '${script}'"
log "Args: $*"

# Si hay 'pyproject.toml' usar UV
if [ -f "pyproject.toml" ]; then
    log "'pyproject.toml' found, using 'uv'"

    if [ -f "uv.lock" ]; then
        log "'uv.lock' found, running 'uv sync --frozen'"
        uv sync --frozen
    else
        log "'uv.lock' not found, running 'uv sync'"
        uv sync
    fi

    py_version=$(uv run python -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
    if [ ! -f ".python-version" ]; then
        log "'.python-version' not found, pinning 'python ${py_version}' from resolved interpreter"
        echo "$py_version" > .python-version
    fi

    exec uv run --no-sync python "$script" "$@"
else
    log "'pyproject.toml' not found, using system 'python $(python3 --version 2>&1)'"
    exec python3 "$script" "$@"
fi
