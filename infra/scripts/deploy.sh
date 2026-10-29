#!/usr/bin/env bash
# Run on the server from the repository root:  ./infra/scripts/deploy.sh <git-tag>
# Steps marked "Phase" are enabled as those parts of the system come into existence.
set -euo pipefail

TAG="${1:?usage: deploy.sh <git-tag>}"

git fetch --tags
git checkout "$TAG"

uv sync --frozen --all-packages
make db-migrate
# Phase 1: Django migrations, then triggers and grants
# make api-migrate db-attach-cdc db-grants db-constraints
# Phase 2: web build
# pnpm install --frozen-lockfile && pnpm --filter web build

pm2 reload ecosystem.config.js --update-env
# Phase 2: smoke test
# curl -fsS http://127.0.0.1:8010/api/v1/health
echo "deployed $TAG"
