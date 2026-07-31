#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$ROOT_DIR/data"

mkdir -p "$DATA_DIR"
kaggle datasets download georgymamarin/kaggriculture-episodes \
    --path "$DATA_DIR" \
    --unzip
