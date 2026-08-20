#!/usr/bin/env bash
set -euo pipefail

ENV_DIR="${ALPHA_OPENBB_ENV:-$HOME/.alpha/openbb-env}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 is required." >&2
  exit 1
fi

"$PYTHON_BIN" -m venv "$ENV_DIR"
# shellcheck disable=SC1091
source "$ENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "$(cd "$(dirname "$0")" && pwd)/requirements-openbb.txt"

if command -v openbb-build >/dev/null 2>&1; then
  openbb-build
fi

python - <<'PY'
from openbb import obb
print("OpenBB import OK")
print("ALPHA finance adapter is installed in read-only mode.")
PY

echo "Activate with: source $ENV_DIR/bin/activate"
