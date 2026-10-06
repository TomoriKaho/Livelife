#!/usr/bin/env bash
# Run as root on the public host; pinned official release + checksum verification.
set -euo pipefail
test "$(id -u)" = 0
task_version=5.5.2
task_archive="lego_v${task_version}_linux_amd64.tar.gz"
task_url="https://github.com/go-acme/lego/releases/download/v${task_version}"
task_tmp="$(mktemp -d)"
trap 'rm -rf -- "$task_tmp"' EXIT
curl --fail --silent --show-error --location --connect-timeout 15 --max-time 120 --proto '=https' --tlsv1.2 "$task_url/$task_archive" -o "$task_tmp/$task_archive"
curl --fail --silent --show-error --location --connect-timeout 15 --max-time 120 --proto '=https' --tlsv1.2 "$task_url/lego_${task_version}_checksums.txt" -o "$task_tmp/checksums.txt"
awk -v file="$task_archive" '$2 == file {print}' "$task_tmp/checksums.txt" > "$task_tmp/selected.sha256"
test -s "$task_tmp/selected.sha256"
(cd "$task_tmp" && sha256sum -c selected.sha256)
tar -xzf "$task_tmp/$task_archive" -C "$task_tmp" lego
install -d -m 755 /opt/livelife/bin
install -o root -g root -m 755 "$task_tmp/lego" /opt/livelife/bin/lego
