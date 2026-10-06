#!/usr/bin/env bash
# This root-owned script manages only livelife-gateway.service on port 443.
set -euo pipefail
task_root=/opt/livelife
source "$task_root/acme.env"
test "${LIVELIFE_IP:?}" = 192.144.253.40
test -n "${ACME_EMAIL:?}"
task_lego="$task_root/bin/lego"
task_cert="$task_root/acme/certificates/$LIVELIFE_IP.crt"
task_mode="${1:-renew}"
task_was_running=false
if systemctl is-active --quiet livelife-gateway.service; then
  task_was_running=true
  systemctl stop livelife-gateway.service
fi
trap 'if $task_was_running; then systemctl start livelife-gateway.service; fi' EXIT
task_args=(run --path "$task_root/acme" --email "$ACME_EMAIL" --domains "$LIVELIFE_IP"
           --accept-tos --profile shortlived --tls --tls.address :443 --http-timeout 30
           --cert.timeout 60 --no-random-sleep)
if [[ "$task_mode" == staging ]]; then
  task_args=(run --path "$task_root/acme-staging" --email "$ACME_EMAIL" --domains "$LIVELIFE_IP"
             --accept-tos --profile shortlived --tls --tls.address :443 --http-timeout 30
             --cert.timeout 60 --no-random-sleep
             --server https://acme-staging-v02.api.letsencrypt.org/directory)
  "$task_lego" "${task_args[@]}"
  exit 0
elif [[ "$task_mode" == initial ]]; then
  "$task_lego" "${task_args[@]}"
elif [[ "$task_mode" == renew ]]; then
  "$task_lego" "${task_args[@]}" --renew-days 3
else
  exit 2
fi
openssl x509 -in "$task_cert" -checkend 86400 -noout
# Stage both files first; failures preserve the previous certificate.
install -o root -g livelife -m 640 "$task_cert" "$task_root/tls/fullchain.pem.next"
install -o root -g livelife -m 640 "$task_root/acme/certificates/$LIVELIFE_IP.key" "$task_root/tls/key.pem.next"
mv "$task_root/tls/fullchain.pem.next" "$task_root/tls/fullchain.pem"
mv "$task_root/tls/key.pem.next" "$task_root/tls/key.pem"
