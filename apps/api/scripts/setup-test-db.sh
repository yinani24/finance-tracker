#!/usr/bin/env bash
#
# Bring up a local PostgreSQL instance for running the API test suite in an
# ephemeral sandbox (e.g. Claude Code on the web, CI without a service DB).
#
# The conftest fixtures connect to `settings.test_database_url`, which defaults
# to `postgresql://localhost:5432/finance_tracker_test` — i.e. localhost:5432,
# no user (libpq then falls back to the current OS user). This script starts a
# throwaway cluster there and provisions a login role for the current user plus
# the test database, so `pytest` works with zero extra configuration.
#
# Idempotent: safe to re-run. Data lives under $PGDATA (default /tmp/ft-pgdata)
# and is disposable.
#
# Usage:
#   apps/api/scripts/setup-test-db.sh            # start + provision
#   PGDATA=/custom/path apps/api/scripts/setup-test-db.sh
#
# Prereqs: a PostgreSQL server package (initdb/pg_ctl) must be installed.
# PostgreSQL refuses to run as root, so if invoked as root this script drops to
# the `postgres` system user for cluster operations.

set -euo pipefail

PGPORT="${PGPORT:-5432}"
PGDATA="${PGDATA:-/tmp/ft-pgdata}"
PGHOST="${PGHOST:-localhost}"
TEST_DB="${TEST_DB:-finance_tracker_test}"
DEV_DB="${DEV_DB:-finance_tracker}"

# Locate the PostgreSQL bin dir (Debian/Ubuntu layout, else rely on PATH).
PGBIN="$(dirname "$(command -v initdb 2>/dev/null || true)")"
if [[ -z "$PGBIN" || ! -x "$PGBIN/initdb" ]]; then
  PGBIN="$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1 || true)"
fi
if [[ -z "$PGBIN" || ! -x "$PGBIN/initdb" ]]; then
  echo "ERROR: could not find initdb/pg_ctl. Install PostgreSQL first." >&2
  exit 1
fi

# postgres can't run as root; pick an unprivileged owner if we are root.
RUN_AS=""
if [[ "$(id -u)" -eq 0 ]]; then
  RUN_AS="postgres"
  mkdir -p "$PGDATA"
  chown "$RUN_AS" "$PGDATA" /tmp
fi
run() { if [[ -n "$RUN_AS" ]]; then su "$RUN_AS" -c "$1"; else bash -c "$1"; fi; }

# The role name the default config connects as = the OS user running pytest.
APP_ROLE="${APP_ROLE:-$(id -un)}"

if [[ ! -f "$PGDATA/PG_VERSION" ]]; then
  echo "==> initdb ($PGDATA)"
  run "$PGBIN/initdb -D '$PGDATA' -U postgres --auth=trust" >/dev/null
fi

if ! run "$PGBIN/pg_ctl -D '$PGDATA' status" >/dev/null 2>&1; then
  echo "==> starting postgres on $PGHOST:$PGPORT"
  run "$PGBIN/pg_ctl -D '$PGDATA' -o '-p $PGPORT -k /tmp' -l '$PGDATA/server.log' start" >/dev/null
  sleep 2
fi

psql_su() { run "$PGBIN/psql -h '$PGHOST' -p '$PGPORT' -U postgres -tc \"$1\""; }

# Provision the login role the app connects as (superuser keeps it simple for
# create/drop-all in the fixtures). Skip if it already exists.
if [[ "$(psql_su "SELECT 1 FROM pg_roles WHERE rolname='$APP_ROLE'" | tr -d '[:space:]')" != "1" ]]; then
  echo "==> creating role '$APP_ROLE'"
  psql_su "CREATE ROLE \"$APP_ROLE\" WITH LOGIN SUPERUSER" >/dev/null
fi

for db in "$TEST_DB" "$DEV_DB"; do
  if [[ "$(psql_su "SELECT 1 FROM pg_database WHERE datname='$db'" | tr -d '[:space:]')" != "1" ]]; then
    echo "==> creating database '$db' (owner $APP_ROLE)"
    run "$PGBIN/createdb -h '$PGHOST' -p '$PGPORT' -U postgres -O '$APP_ROLE' '$db'"
  fi
done

echo "==> ready: postgresql://$APP_ROLE@$PGHOST:$PGPORT/$TEST_DB"
