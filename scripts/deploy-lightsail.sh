#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf 'Deployment stopped: %s\n' "$1" >&2
  exit 1
}

target_commit="${1:-}"
[[ "$target_commit" =~ ^[0-9a-f]{40}$ ]] || fail 'A full tested commit SHA is required.'

# The override is useful for local verification; production uses the fixed path.
repo_dir="${LIGHTSAIL_APP_DIR:-/home/ubuntu/vachanamrut_app}"
cd -- "$repo_dir"
export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND='ssh -o BatchMode=yes'

[[ "$(git branch --show-current)" == master ]] || fail 'The server checkout must be on master.'
[[ -f .env ]] || fail 'The existing server .env file is missing.'
# Support both Docker Compose command formats.
if ! docker compose version >/dev/null 2>&1; then
  docker() {
    if [[ "${1:-}" == "compose" ]]; then
      shift
      command docker-compose "$@"
    else
      command docker "$@"
    fi
  }
fi

docker compose version > /dev/null

# Chroma changes its tracked runtime files. Preserve them; Git still refuses
# an update if an incoming database change would overwrite local data.
git diff --quiet -- . ':(exclude)backend/Data/vachanamrut_db/**' || fail 'Commit or review server source edits first.'
git diff --cached --quiet || fail 'The server has staged changes; review them first.'
git fetch --no-tags origin master:refs/remotes/origin/master
git cat-file -e "${target_commit}^{commit}"
git merge-base --is-ancestor "$target_commit" refs/remotes/origin/master || fail 'The tested commit is not on origin/master.'
current_commit="$(git rev-parse HEAD)"
git merge-base --is-ancestor "$current_commit" refs/remotes/origin/master || fail 'The server has local commits outside origin/master.'

if [[ "$current_commit" != "$target_commit" ]] && git merge-base --is-ancestor "$target_commit" "$current_commit"; then
  printf 'Skipping superseded commit %s; the server already has a newer commit.\n' "$target_commit"
  exit 0
fi

git merge --ff-only "$target_commit"
[[ "$(git rev-parse HEAD)" == "$target_commit" ]] || fail 'The server checkout does not match the tested commit.'
docker compose config --quiet
docker compose build backend frontend

wait_for_url() {
  local label="$1" url="$2"
  local attempt
  printf 'Waiting for %s...\n' "$label"
  for ((attempt = 1; attempt <= 60; attempt++)); do
    if curl --fail --silent --max-time 5 "$url" > /dev/null 2>&1; then
      return 0
    fi
    sleep 3
  done
  docker compose ps
  fail "$label did not become ready."
}

# Start the API first because topic cards depend on its resolved references.
docker compose up -d --no-build --no-deps --force-recreate backend
wait_for_url backend http://127.0.0.1:10000/health

# Only the frontend's anonymous node_modules volume is renewed. Scripture
# and Chroma data use the existing backend bind mount and are preserved.
docker compose up -d --no-build --no-deps --force-recreate --renew-anon-volumes frontend
wait_for_url frontend http://127.0.0.1:3000/

# Exercise browsing only; this does not make an inference-provider request.
docker compose exec -T backend python - <<'PY'
import json
from urllib.request import urlopen

def get(path):
    with urlopen("http://127.0.0.1:10000" + path, timeout=10) as response:
        return json.load(response)

health = get("/health")
assert health.get("status") == "ok", "Backend health check failed"
references = [vat for topic in get("/api/topics") for vat in topic.get("linked_vats", [])]
reference = next((vat for vat in references if str(vat.get("id")) == "539"), None)
assert reference is not None, "Topic reference 539 is missing"
assert (reference["prakran_no"], reference["vat_no"]) == (3, 4), "Topic reference 539 resolves incorrectly"
assert get("/api/swaminivato?prakran_no=3&vat_no=4")["id"] == 539, "Reader destination is incorrect"
print("Backend, frontend, and topic-link checks passed.")
PY

printf 'Deployed tested commit %s successfully.\n' "$target_commit"
