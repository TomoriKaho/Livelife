#!/usr/bin/env bash
# Run as group5 in a reviewed checkout. No sudo, Docker, or host-level service.
set -euo pipefail
test "$(id -un)" = group5
task_source="$(cd -- "$(dirname -- "$0")" && pwd)"
task_root=/home/group5/livelife
umask 077
mkdir -p "$task_root/control" "$task_root/releases"
cp -R "$task_source/livelife" "$task_root/control/"
cp "$task_source/course-entry.py" "$task_source/prepare-backend.py" "$task_source/prepare-frontend.py" "$task_root/control/"
cp "$task_source/install-android-tools.py" "$task_source/install-build-tools.py" "$task_root/control/"
python3 -m venv "$task_root/control-venv"
"$task_root/control-venv/bin/python" -m pip install --disable-pip-version-check --index-url https://mirrors.aliyun.com/pypi/simple 'supervisor==4.3.0' || \
  "$task_root/control-venv/bin/python" -m pip install --disable-pip-version-check --index-url https://pypi.tuna.tsinghua.edu.cn/simple 'supervisor==4.3.0'
printf 'Course control installed at %s; configure the dedicated authorized key next.\n' "$task_root"

python3 "$task_root/control/install-build-tools.py" "$task_root"
