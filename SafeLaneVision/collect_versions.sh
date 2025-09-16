#!/usr/bin/env bash
set -euo pipefail
OUT="VERSIONS.md"
TS="$(date -u +"%Y-%m-%d %H:%M:%SZ")"
have(){ command -v "$1" >/dev/null 2>&1; }

{
  echo "## Captured: $TS (UTC)"
  echo
  echo "### System"
  have sw_vers && sw_vers || echo "sw_vers: N/A"
  have brew && brew --version || echo "brew: N/A"
  echo
  echo "### Containers"
  have docker && docker --version || echo "docker: N/A"
  have docker && docker compose version || echo "docker compose: N/A"
  echo
  echo "### Database stack"
  have psql && psql --version || echo "psql: N/A"
  if have docker && docker compose ps db >/dev/null 2>&1; then
    echo "- Server:" 
    docker compose exec -T db psql -U postgres -d safelane -c "SELECT version();" || true
    echo "- PostGIS:"
    docker compose exec -T db psql -U postgres -d safelane -c "SELECT postgis_full_version();" || true
    echo "- pgvector:"
    docker compose exec -T db psql -U postgres -d safelane -c "SELECT extversion FROM pg_extension WHERE extname='vector';" || true
  else
    echo "db container: N/A"
  fi
  echo
  echo "### Python (project libs)"
  have python3 && python3 --version || echo "python3: N/A"
  have python3 && python3 -m pip show fastapi uvicorn SQLAlchemy psycopg httpx onnx onnxruntime 2>/dev/null | egrep 'Name: |Version:' || echo "python packages: N/A"
} >> "$OUT"
echo "Appended capture to $OUT"
