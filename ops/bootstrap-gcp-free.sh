#!/usr/bin/env bash
# Run on a Debian 12 Google Compute Engine VM from the checked-out repository.
set -Eeuo pipefail
umask 077

if [[ $(id -u) -ne 0 ]]; then
    echo 'Run this script with sudo.' >&2
    exit 1
fi

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_dir"
if [[ ! -f ops/compose.yaml || ! -f ops/compose.gcp-free.yaml ]]; then
    echo 'Run from a Tripothon checkout containing the online server files.' >&2
    exit 1
fi

. /etc/os-release
if [[ ${ID:-} != debian || ${VERSION_ID:-} != 12 ]]; then
    echo 'This bootstrap script supports Debian 12 only.' >&2
    exit 1
fi

# A single e2-micro has 1 GiB RAM. Swap keeps the first image build from
# exhausting memory; it lives on the existing boot disk, not a second disk.
if [[ ! -e /swapfile ]]; then
    fallocate -l 1G /swapfile
    chmod 0600 /swapfile
    mkswap /swapfile >/dev/null
fi
if ! swapon --show=NAME --noheadings | grep -Fxq /swapfile; then
    swapon /swapfile
fi
if ! grep -Eq '^/swapfile[[:space:]]' /etc/fstab; then
    printf '/swapfile none swap sw 0 0\n' >> /etc/fstab
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl git
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: ${VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

external_ip=$(curl -fsS --max-time 5 -H 'Metadata-Flavor: Google' \
    'http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip')
python3 - "$external_ip" <<'PY'
import ipaddress
import sys
ipaddress.IPv4Address(sys.argv[1])
PY
domain=${external_ip//./-}.sslip.io

if [[ ! -e ops/production.env ]]; then
    sed "s/^TRIPOTHON_DOMAIN=.*/TRIPOTHON_DOMAIN=${domain}/" \
        ops/production.env.example > ops/production.env
fi
chmod 0600 ops/production.env
configured_domain=$(sed -n 's/^TRIPOTHON_DOMAIN=//p' ops/production.env)
if [[ ! $configured_domain =~ ^[A-Za-z0-9.-]+$ ]]; then
    echo 'Set one plain TRIPOTHON_DOMAIN value in ops/production.env.' >&2
    exit 1
fi

install -m 0700 -d ops/secrets
if [[ ! -e ops/secrets/registration-code ]]; then
    python3 -c 'import secrets; print(secrets.token_urlsafe(32))' \
        > ops/secrets/registration-code
fi
# Docker Compose mounts a file-backed secret with its host ownership. The API
# runs as uid/gid 10001, so grant only that group read access.
chown root:10001 ops/secrets/registration-code
chmod 0640 ops/secrets/registration-code

compose=(docker compose --env-file ops/production.env \
    -f ops/compose.yaml -f ops/compose.gcp-free.yaml)
"${compose[@]}" config --quiet
"${compose[@]}" up -d --build

printf 'Demo URL: https://%s/health\n' "$configured_domain"
echo 'AI payment remains disabled; no Tripo or OpenAI keys were installed.'
echo 'The private invitation code is in ops/secrets/registration-code on this VM.'
