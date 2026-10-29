#!/usr/bin/env bash
# Weekly restore check (pipeline P14): restore the latest backup into a scratch database and run sanity queries.
# Fill in once the backup tool (pgBackRest or WAL-G) is chosen. See docs 06_repo_deployment.md section 6.
set -euo pipefail
echo "TODO: restore latest backup into lozhka_restore_check and compare row counts"
exit 1
