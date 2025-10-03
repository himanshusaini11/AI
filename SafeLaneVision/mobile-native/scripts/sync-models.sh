#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")/../../models/export" && pwd)"
DEST_DIR="$(cd "$(dirname "$0")/.." && pwd)/assets/models"
mkdir -p "$DEST_DIR"

for f in owlvit_int8.onnx deeplab_mnv3_int8.onnx midas_small_int8.onnx; do
  if [ -f "$SRC_DIR/$f" ]; then
    cp "$SRC_DIR/$f" "$DEST_DIR/$f"
    echo "Copied $f"
  else
    echo "Warning: $f not found in $SRC_DIR" >&2
  fi
 done

cat <<MSG
Models copied into $DEST_DIR. On first launch, copy them to device writable storage and update MODEL_PATHS in src/config.ts accordingly.
MSG
