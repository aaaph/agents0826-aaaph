#!/usr/bin/env bash
# Deploy / update the team Neo4j on the host, then apply the idempotent schema.
# Reads deploy/.env for NEO4J_PASSWORD + DEPLOY_HOST. Safe to re-run.
#
# Usage: cd deploy && ./deploy.sh
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] || { echo "ERROR: deploy/.env missing. Copy .env.example -> .env and fill it."; exit 1; }
set -a; source .env; set +a
: "${NEO4J_PASSWORD:?set NEO4J_PASSWORD in .env}"
: "${DEPLOY_HOST:?set DEPLOY_HOST in .env}"

REMOTE_DIR="~/claude-platform-deploy"
SCHEMA="../memory-hooks/schema_v2.cypher"

echo "==> 1/4 copy compose + schema to ${DEPLOY_HOST}"
ssh -o StrictHostKeyChecking=accept-new "$DEPLOY_HOST" "mkdir -p $REMOTE_DIR"
scp docker-compose.neo4j.yml "$DEPLOY_HOST:$REMOTE_DIR/"
scp "$SCHEMA" "$DEPLOY_HOST:$REMOTE_DIR/schema_v2.cypher"

echo "==> 2/4 start container (docker group; no sudo needed after re-login)"
ssh "$DEPLOY_HOST" "cd $REMOTE_DIR && NEO4J_PASSWORD='$NEO4J_PASSWORD' docker compose -f docker-compose.neo4j.yml up -d"

echo "==> 3/4 wait for Bolt"
ssh "$DEPLOY_HOST" "
  for i in \$(seq 1 30); do
    if docker exec neo4j-team cypher-shell -u neo4j -p '$NEO4J_PASSWORD' 'RETURN 1;' >/dev/null 2>&1; then
      echo 'bolt ready'; exit 0
    fi
    sleep 3
  done
  echo 'TIMEOUT waiting for Bolt'; exit 1
"

echo "==> 4/4 apply idempotent schema"
ssh "$DEPLOY_HOST" "cat $REMOTE_DIR/schema_v2.cypher | docker exec -i neo4j-team cypher-shell -u neo4j -p '$NEO4J_PASSWORD'"

echo "==> done. Verify schema:"
ssh "$DEPLOY_HOST" "docker exec neo4j-team cypher-shell -u neo4j -p '$NEO4J_PASSWORD' 'SHOW INDEXES YIELD name, state WHERE name STARTS WITH \"memory\" RETURN name, state;'"
echo "Team points HOOKS_NEO4J_URI=bolt://\${DEPLOY_HOST##*@}:7687"
