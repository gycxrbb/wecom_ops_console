#!/usr/bin/env bash
set -Eeuo pipefail
project="$1"
sha="$2"
inbox="$3"
home=$(dirname "$0")
state_dir="${WECOM_STATE_DIR:-/var/lib/wecom-deploy/test}"
mkdir -p "$state_dir"
chmod 700 "$state_dir"
exec 8>"$project/.pipeline-build.lock"
flock -w 300 8 || exit 1
umask 077
log="$state_dir/build-$sha.log"
exec 3>&1 4>&2
exec >>"$log" 2>&1
say() { printf '%s\n' "$*" >&3; }
smoke="wecom-build-smoke-${sha:0:12}"
cleanup() {
  result=$?
  trap - EXIT
  docker rm -f "$smoke" >/dev/null 2>&1 || true
  if [ "$result" != 0 ]; then say "BUILD_FAILED: inspect private server log $log"; fi
  exit "$result"
}
trap cleanup EXIT
trap 'exit 130' HUP INT TERM
cd "$project"
git diff --quiet
git diff --cached --quiet
git bundle verify "$inbox/source.bundle"
git fetch "$inbox/source.bundle" HEAD
test "$(git rev-parse FETCH_HEAD)" = "$sha"
git merge-base --is-ancestor "$(git rev-parse HEAD)" "$sha"
context="$inbox/context"
mkdir "$context"
git archive "$sha" | tar -x -C "$context"
image="wecom-ops-console-release:$sha"
say "BUILD_START $sha"
# Bound this application's build resources; do not change other containers.
DOCKER_BUILDKIT=0 docker build --memory=1536m --memory-swap=1664m --cpu-shares=256 \
  --label "org.opencontainers.image.revision=$sha" -t "$image" "$context"
say IMAGE_BUILT
# A public artifact must contain only clean tracked source, never runtime data or keys.
docker run --rm --entrypoint python "$image" -c 'from pathlib import Path; assert not Path("/app/.env").exists(); assert not list(Path("/app/data").glob(".rsa_key_*.pem"))'
docker rm -f "$smoke" >/dev/null 2>&1 || true
docker run -d --name "$smoke" -e DATABASE_URL=sqlite:////tmp/ci.db \
  -e CRM_PROFILE_ENABLED=true -e AI_COACH_ENABLED=true -e IMAGE_GEN_ENABLED=true \
  -e RAG_ENABLED=false -e AI_BASE_URL=http://127.0.0.1:9 -e AI_API_KEY= \
  --entrypoint uvicorn "$image" app.main:app --host 0.0.0.0 --port 8000 --workers 1
ready=0
for attempt in $(seq 1 "${WECOM_HEALTH_ATTEMPTS:-60}"); do
  if docker exec -i "$smoke" python - < "$home/probe.py"; then ready=1; break; fi
  sleep 3
done
test "$ready" = 1
docker rm -f "$smoke" >/dev/null
say ISOLATED_STARTUP_API_FRONTEND_OK
mkdir "$inbox/release"
python3 "$home/package_release.py" --from-bundle "$sha" "$inbox/source.bundle" "$inbox/release"
# Reuse the very same tested image on test and, only after approval, production.
WECOM_STATE_DIR="$state_dir" bash "$home/deploy.sh" test "$project" "$sha" "$inbox/release" >&3
python3 "$home/publish_release.py" "$project" "$sha" "$inbox/release" >&3
