#!/usr/bin/env bash

set -euo pipefail

# Configure these for the backup host, or override them with environment variables.
REMOTE_HOST="${REMOTE_HOST:-example.com}"
REMOTE_USER="${REMOTE_USER:-deploy}"
SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/gigplanner.pem}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-/opt/gigplanner/app}"
REMOTE_DB_PATH="${REMOTE_DB_PATH:-$REMOTE_APP_DIR/gigplanner.db}"
LOCAL_BACKUP_DIR="${LOCAL_BACKUP_DIR:-$(cd "$(dirname "$0")" && pwd)}"
BACKUP_PREFIX="${BACKUP_PREFIX:-gigplanner-db}"

if [[ "$REMOTE_HOST" == "example.com" ]]; then
  echo "Set REMOTE_HOST before running this script." >&2
  exit 1
fi

if [[ ! -f "$SSH_KEY_PATH" ]]; then
  echo "SSH key not found: $SSH_KEY_PATH" >&2
  exit 1
fi

mkdir -p "$LOCAL_BACKUP_DIR"

backup_stamp="$(date '+%A-%Y-%m-%d')"
local_backup_path="$LOCAL_BACKUP_DIR/${BACKUP_PREFIX}-${backup_stamp}.db"
remote_temp_path="/tmp/${BACKUP_PREFIX}-$(date '+%Y%m%d-%H%M%S').db"

ssh_opts=(
  -i "$SSH_KEY_PATH"
  -o BatchMode=yes
  -o IdentitiesOnly=yes
  -o StrictHostKeyChecking=accept-new
)

remote_command=$(cat <<EOF
set -euo pipefail
cleanup() {
  sudo rm -f '$remote_temp_path'
}
trap cleanup EXIT

if command -v sqlite3 >/dev/null 2>&1; then
  sudo sqlite3 '$REMOTE_DB_PATH' ".backup '$remote_temp_path'"
else
  sudo cp '$REMOTE_DB_PATH' '$remote_temp_path'
fi

sudo cat '$remote_temp_path'
EOF
)

ssh "${ssh_opts[@]}" "$REMOTE_USER@$REMOTE_HOST" "$remote_command" > "$local_backup_path"

if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$local_backup_path" "PRAGMA integrity_check;" >/dev/null
fi

echo "Backup written to $local_backup_path"
