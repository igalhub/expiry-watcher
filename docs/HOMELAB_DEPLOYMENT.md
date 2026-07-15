# Home Lab Deployment (Proxmox + Ubuntu Server VM)

This guide covers deploying expiry-watcher on a Proxmox home lab
running Ubuntu Server 24.04 in a VM — tested on a Beelink SER mini PC
with Proxmox VE 9.2.3.

## Environment

| Component | Version |
|---|---|
| Hypervisor | Proxmox VE 9.2.3 |
| OS | Ubuntu Server 24.04.3 LTS |
| Docker | 29.6.0 |
| Python | 3.12 |

## Prerequisites

- Ubuntu Server VM with Docker installed
- Static IP configured
- SSH access from your main machine
- A running [vault-secrets-demo](https://github.com/igalhub/vault-secrets-demo)
  instance for Vault checks

## Installation

```bash
git clone git@github.com:igalhub/expiry-watcher.git
cd expiry-watcher

sudo apt install -y python3.12-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configure targets

```bash
cp config/targets.yaml.example config/targets.yaml
```

Edit `config/targets.yaml` — replace example domains with real TLS
endpoints:

```yaml
tls_endpoints:
  - host: "github.com"
    port: 443
  - host: "google.com"
    port: 443
local_certs: []
vault:
  url: "http://localhost:8200"
settings:
  check_interval_hours: 6
  db_path: "results.db"
```

## Configure Vault credentials

Requires a running vault-secrets-demo instance. Get the root token:

```bash
cat ~/vault-secrets-demo/.vault-init.json | grep root_token
```

Then create the expiry-watcher AppRole:

```bash
export VAULT_TOKEN=<root-token>
bash scripts/vault_setup_test_role.sh
```

Copy the printed `role_id` and `secret_id` into `config/vault.yaml`:

```bash
cp config/vault.yaml.example config/vault.yaml
vim config/vault.yaml
```

## Run the checker and start the dashboard

```bash
# Generate results.db
python3 -m checker.check

# Start dashboard container
docker compose up -d
```

## Verify

```bash
curl http://localhost:8080/status
```

## Access from your main machine

`http://<VM_IP>:8080`
`http://<VM_IP>:8080/status`
Replace `<VM_IP>` with your VM's static IP address.

## Notes

- `python3.12-venv` must be installed explicitly on Ubuntu Server —
  it is not included by default
- The example targets in `config/targets.yaml.example` will produce
  DNS resolution errors on a VM without public internet access to those
  domains — replace with real endpoints
- Vault re-seals on every VM reboot — run `bash scripts/unseal.sh`
  in vault-secrets-demo before running the checker

## Running alongside other projects

Tested running simultaneously with:
- **vault-secrets-demo** (ports 8000, 8200)
- **docker-sentinel** (port 8081)
- **kube-sentinel** (Grafana port 30093, Prometheus port 31664)
- **Portainer** (port 9000)

No port conflicts. Dashboard container visible in Portainer at
`http://<VM_IP>:9000`.

**Shared Vault `approle` mount ceiling (confirmed live, EW-014):** expiry-watcher's
`expiry-watcher-test-short-ttl` AppRole and vault-secrets-demo's `demo-app`
AppRole share the same `approle/` auth mount on the Vault instance. That
mount has `max_lease_ttl = 2160h` (90 days) — any `secret_id` `ttl`
requested above 90 days is silently capped to exactly 90 days rather than
honored or rejected (verified: requesting `ttl=120d` returned
`secret_id_ttl: 7776000` seconds, i.e. `90.0` days). This is the same
mechanism — not a separate one — as the mount-level `max_lease_ttl` that
capped login-token leases in vault-secrets-demo's own earlier finding; it
was previously known to affect token lease TTLs and is now confirmed to
affect `secret_id` TTLs too, since both are governed by the same auth
mount's tuning. Keep any future short-TTL AppRole test fixture on this
shared instance under 90 days.
