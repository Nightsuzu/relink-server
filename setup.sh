#!/usr/bin/env bash
set -euo pipefail
base="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
for runtime in python3 python3.13 python3.12 python3.11 python3.10 python3.9; do
  if command -v "$runtime" >/dev/null && "$runtime" -c 'import sys; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
    exec "$runtime" "$base/manage.py" "$@"
  fi
done
printf '%s\n' '需要 Python 3.9 或更新版本。请先通过系统软件源安装；旧系统可安装 python3.9，再运行本命令。未修改系统。' >&2
exit 1
