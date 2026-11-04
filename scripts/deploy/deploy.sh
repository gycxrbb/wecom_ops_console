#!/usr/bin/env bash
set -Eeuo pipefail

environment="$1"
project="$2"
sha="$3"
inbox="$4"
service=wecom-ops-console
state_dir="${WECOM_STATE_DIR:-/var/lib/wecom-deploy/$environment}"
mkdir -p "$state_dir"
chmod 700 "$state_dir"
exec 9>"$project/.pipeline-deploy.lock"
flock -w 300 9 || { echo DEPLOY_LOCK_TIMEOUT; exit 1; }
log="$state_dir/deploy-$sha.log"
umask 077
exec 3>&1 4>&2
exec >>"$log" 2>&1
say() { printf '%s\n' "$*" >&3; }
cd "$project"
git diff --quiet
git diff --cached --quiet
old_sha=$(git rev-parse HEAD)
old_image=$(docker inspect --format '{{.Image}}' "$service")
image_name=$(docker inspect --format '{{.Config.Image}}' "$service")
image_tag="wecom-ops-console-release:$sha"
expected_image=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["image_id"])' "$inbox/manifest.json")
changed=0
success=0
rollback() {
  say ROLLBACK_START
  docker tag "$old_image" "$image_name"
  git reset --keep "$old_sha"
  docker compose -f docker-compose.prod.yml up -d --no-deps --no-build "$service"
  say "ROLLBACK_RESTORED $old_sha; verify host health before retry"
}
finish() {
  result=$?
  trap - EXIT
  if [ "$result" != 0 ]; then
    if [ "$changed" = 1 ] && [ "$success" = 0 ]; then
      rollback || say "ROLLBACK_FAILED: inspect private server log $log"
    fi
    say "DEPLOY_FAILED: inspect private server log $log"
  fi
  exit "$result"
}
trap finish EXIT
trap 'exit 130' INT TERM HUP
say "RELEASE_RECEIVED $sha"
git bundle verify "$inbox/source.bundle"
git fetch "$inbox/source.bundle" HEAD
test "$(git rev-parse FETCH_HEAD)" = "$sha"
git merge-base --is-ancestor "$old_sha" "$sha"
say IMAGE_LOADING
identity="$(dirname "$0")/image_identity.py"
local_image=$(python3 "$identity" "$image_tag" "$expected_image" "$sha" 2>/dev/null || true)
if [ -z "$local_image" ]; then
  gzip -dc "$inbox/image.tar.gz" | docker load
  local_image=$(python3 "$identity" "$image_tag" "$expected_image" "$sha")
fi
say "IMAGE_IDENTITY_VERIFIED config=$expected_image local=$local_image"
test "$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$image_tag")" = "$sha"
test "$(docker image inspect --format '{{.Architecture}}' "$image_tag")" = amd64
if [ "$old_sha" = "$sha" ] && [ "$old_image" = "$local_image" ]; then
  test "$(docker inspect --format '{{.State.Health.Status}}' "$service")" = healthy
  docker exec -i "$service" python - < "$(dirname "$0")/probe.py"
  say "DEPLOY_ALREADY_CURRENT $sha"
  exit 0
fi
docker tag "$old_image" wecom-ops-console-rollback:previous
changed=1
git merge --ff-only "$sha"
docker tag "$local_image" "$image_name"
docker compose -f docker-compose.prod.yml up -d --no-deps --no-build "$service"
say SERVICE_STARTED
healthy=0
for attempt in $(seq 1 "${WECOM_HEALTH_ATTEMPTS:-60}"); do
  status=$(docker inspect --format '{{.State.Status}}' "$service")
  health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$service")
  if [ "$status" = running ] && [ "$health" = healthy ]; then healthy=1; break; fi
  if [ "$status" = exited ] || [ "$health" = unhealthy ]; then break; fi
  sleep 3
done
test "$healthy" = 1
test "$(docker inspect --format '{{.Image}}' "$service")" = "$local_image"
docker exec -i "$service" python - < "$(dirname "$0")/probe.py"
python3 - "$state_dir" "$sha" "$local_image" "$old_sha" "$old_image" "$expected_image" <<'PY'
import json, os, sys, time
from pathlib import Path
root, sha, image, old_sha, old_image, config_id = sys.argv[1:]
path = Path(root) / 'current.json'
tmp = path.with_suffix('.tmp')
tmp.write_text(json.dumps({'commit':sha, 'image_id':image, 'previous_commit':old_sha,
                           'previous_image_id':old_image, 'image_config_id':config_id, 'deployed_at':int(time.time())}))
os.replace(str(tmp), str(path))
PY
success=1
say "DEPLOY_OK $sha $local_image config=$expected_image"
# Only application release tags are candidates; never prune unrelated images.
while IFS= read -r tag; do
  case "$tag" in
    "$image_tag"|"wecom-ops-console-release:$old_sha") continue ;;
    wecom-ops-console-release:*) docker image rm "$tag" || true ;;
  esac
done < <(docker image ls --format '{{.Repository}}:{{.Tag}}' wecom-ops-console-release)
