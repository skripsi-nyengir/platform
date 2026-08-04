#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "install-vps.sh must run as root" >&2
  exit 77
fi

for command in docker jq curl pg_restore flock sudo visudo sshd; do
  command -v "$command" >/dev/null || {
    echo "required command is missing: $command" >&2
    exit 69
  }
done

repository_root=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
install -d -m 0700 -o root -g root \
  /opt/anomaly-platform/{backups,logs,manifests,tmp,shared,shared/models}
install -m 0600 -o root -g root "$repository_root/compose.cpu.yaml" \
  /opt/anomaly-platform/compose.cpu.yaml
install -m 0600 -o root -g root "$repository_root/compose.production.cpu.yaml" \
  /opt/anomaly-platform/compose.production.cpu.yaml
install -m 0755 -o root -g root "$repository_root/scripts/deploy/anomaly-platform-deploy" \
  /usr/local/sbin/anomaly-platform-deploy
install -m 0755 -o root -g root "$repository_root/scripts/deploy/anomaly-deploy-force-command" \
  /usr/local/sbin/anomaly-deploy-force-command

if ! id anomaly-deploy >/dev/null 2>&1; then
  useradd --create-home --shell /bin/sh anomaly-deploy
fi
gpasswd --delete anomaly-deploy docker >/dev/null 2>&1 || true
passwd --lock anomaly-deploy >/dev/null

cat >/etc/sudoers.d/anomaly-platform-deploy <<'EOF'
anomaly-deploy ALL=(root) NOPASSWD: /usr/local/sbin/anomaly-platform-deploy preflight
anomaly-deploy ALL=(root) NOPASSWD: /usr/local/sbin/anomaly-platform-deploy deploy
anomaly-deploy ALL=(root) NOPASSWD: /usr/local/sbin/anomaly-platform-deploy rollback-last
EOF
chmod 0440 /etc/sudoers.d/anomaly-platform-deploy
visudo -cf /etc/sudoers.d/anomaly-platform-deploy

cat >/etc/ssh/sshd_config.d/90-anomaly-deploy.conf <<'EOF'
Match User anomaly-deploy
    AuthenticationMethods publickey
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    PermitTTY no
    AllowTcpForwarding no
    AllowAgentForwarding no
    X11Forwarding no
    PermitTunnel no
    GatewayPorts no
    ForceCommand /usr/local/sbin/anomaly-deploy-force-command
EOF
sshd -t

echo "Bootstrap installed. Provision authorized_keys, .env, MQTT CA, model artifacts, and GHCR login before reloading sshd."
