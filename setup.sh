#!/usr/bin/env bash
set -euo pipefail
base="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
command -v python3 >/dev/null || { printf '%s\n' '需要 Python 3：Ubuntu / Debian 请运行 sudo apt-get install python3'; exit 1; }
exec python3 "$base/manage.py" "$@"
