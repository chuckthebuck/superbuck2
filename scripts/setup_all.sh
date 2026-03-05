#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

INSTALL_DEPS=1
CREATE_VENV=1

usage() {
  cat <<USAGE
Usage: ./scripts/setup_all.sh [options]

Set up both monorepo projects (bucksaltbot + unbuckbot).

Options:
  --no-install-deps   Create config/env scaffolding only; skip npm/pip installs
  --no-venv           Don't create unbuckbot/.venv (uses system Python)
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
    --no-venv)
      CREATE_VENV=0
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

setup_unbuckbot() {
  local dir="$ROOT_DIR/unbuckbot"
  log "Setting up unbuckbot"

  ensure_file "$dir/.env.example" "$dir/.env"

  if [[ "$INSTALL_DEPS" -eq 1 ]]; then
    if [[ "$CREATE_VENV" -eq 1 ]]; then
      if [[ ! -d "$dir/.venv" ]]; then
        (cd "$dir" && python3 -m venv .venv)
        log "created: unbuckbot/.venv"
      else
        log "exists: unbuckbot/.venv"
      fi
      # shellcheck disable=SC1091
      source "$dir/.venv/bin/activate"
    fi
    (cd "$dir" && python3 -m pip install -r requirements.txt)
  else
    log "Skipping dependency installation for unbuckbot"
  fi
}

setup_bucksaltbot
setup_unbuckbot

log "Done."
log "Next steps:"
log "  - bucksaltbot: start Redis + MariaDB, then run ./bucksaltbot/scripts/run_dev_env.sh"
log "  - unbuckbot: run ./unbuckbot/toolforge/start.sh"
