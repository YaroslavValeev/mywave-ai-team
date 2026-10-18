#!/usr/bin/env bash
# Owner-operated maintenance window; this performs an app-only production rollout.
set -Eeuo pipefail
umask 077
cd /opt/mywave/ai-team

OPS_SHA="${1:?Exact reviewed operations commit is required}"
OWNER_SHA="${2:?Exact owner-approved application commit is required}"
[[ "$OPS_SHA" =~ ^[0-9a-f]{40}$ ]]
[[ "$OWNER_SHA" == '20476d9fd5a8df89dd9ae33c1c61957569c39307' ]]
test "$(git rev-parse "${OPS_SHA}^{commit}")" = "$OPS_SHA"

OPS_DIR="/opt/mywave/ai-team-runtime/ops-${OPS_SHA}"
test ! -L "$OPS_DIR"
install -d -m 0700 "$OPS_DIR"
git archive --format=tar "$OPS_SHA" scripts/server | tar -x -C "$OPS_DIR"

python3 "$OPS_DIR/scripts/server/qualify_crewai_owner_runtime_20261018.py"
python3 "$OPS_DIR/scripts/server/recover_task35_20261018.py"
python3 "$OPS_DIR/scripts/server/recover_task35_20261018.py" --execute --owner-approved-task 35
python3 "$OPS_DIR/scripts/server/release_owner_runtime_20261018.py"
python3 "$OPS_DIR/scripts/server/release_owner_runtime_20261018.py" --execute --owner-approved-sha "$OWNER_SHA"
