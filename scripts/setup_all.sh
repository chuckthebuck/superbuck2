#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

INSTALL_DEPS=1

usage() {
  cat <<USAGE
Usage: ./scripts/setup_all.sh [options]

Set up the monorepo rollback project (bucksaltbot) and userscript scaffolding.

Options:
  --no-install-deps   Create config/env scaffolding only; skip npm/pip installs
  -h, --help          Show this help
USAGE
}

log() {
  printf '[setup_all] %s\n' "$*"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-install-deps)
      INSTALL_DEPS=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

ensure_file() {
  local src="$1"
  local dst="$2"
  if [[ -f "$dst" ]]; then
    log "exists: ${dst#$ROOT_DIR/}"
  else
    cp "$src" "$dst"
    log "created: ${dst#$ROOT_DIR/}"
  fi
}

setup_bucksaltbot() {
  local dir="$ROOT_DIR/bucksaltbot"
  log "Setting up bucksaltbot"

  ensure_file "$dir/.env.tmpl" "$dir/.env"
  ensure_file "$dir/replica.my.cnf.tmpl" "$dir/replica.my.cnf"

  if [[ "$INSTALL_DEPS" -eq 1 ]]; then
    (cd "$dir" && npm ci)
    (cd "$dir" && python3 -m pip install -r requirements.txt)
  else
    log "Skipping dependency installation for bucksaltbot"
  fi
}

setup_userscript() {
  local dir="$ROOT_DIR/unbuckbot"
  log "Preparing userscript directory"
  ensure_file "$dir/.env.example" "$dir/.env"
}

setup_bucksaltbot
setup_userscript

log "Done."
log "Next steps:"
log "  - bucksaltbot: start Redis + MariaDB, then run ./bucksaltbot/scripts/run_dev_env.sh"
log "  - userscript: set TOOL_ENDPOINT in ./unbuckbot/userscript/mass-rollback.user.js and install it in your browser"
