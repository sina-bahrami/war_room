# Deployment Guide

This document now covers the Docker Compose workflow for local development and simple fallback deployments.

For the recommended self-hosted production path, use [DEPLOYMENT_K8S.md](./DEPLOYMENT_K8S.md).

## Recommended Topology

For Docker Compose, the cleanest deployment is a single Linux VM:

- Ubuntu 22.04 or 24.04
- 4 vCPU minimum
- 8 GB RAM minimum
- 60 GB SSD recommended
- Ports `80/443` open to the internet

This is the most natural fit because the backend follows a Sovereign_Watch-style self-hosted service layout while the frontend remains a lightweight worldmonitor-style static dashboard.

## Services

- `frontend`: nginx serving the built React dashboard and proxying `/api`
- `backend`: FastAPI application
- `ingestor`: long-running connector worker
- `postgres`: primary persistence
- `redis`: summary cache

## First-Time Setup

1. Copy `.env.example` to `.env`.
2. Set:
   - `POSTGRES_PASSWORD`
   - `ALLOWED_ORIGINS`
   - `ENABLE_SAMPLE_DATA`
3. Recommended: set the unified snapshot source:
   - `WARROOM_JSON_SOURCE_URL=/project-root/warroom_dashboard_data.json`
4. Optionally set legacy live source URLs if you are not using unified mode:
   - `AUSTENDER_SOURCE_URL`
   - `NSW_ETENDERING_SOURCE_URL`
   - `VIC_TENDERS_SOURCE_URL`
   - `QLD_PROCUREMENT_SOURCE_URL`
   - `PROMPCORP_PIPELINE_SOURCE_URL`
   These may be remote URLs or local filesystem paths.
5. Start the stack:

```bash
docker compose up -d --build
```

6. Open:
   - `http://localhost:8080`
   - `http://localhost:8080/health`

## Production Notes

Before public deployment, do these:

1. Put the frontend behind TLS using your reverse proxy or cloud load balancer.
2. Restrict access to `/api/tenders/admin/run-ingestion` if you do not want manual public sync triggers.
3. Configure backups for PostgreSQL and Redis volumes.
4. Replace sample sources with live procurement feeds and internal data exports.
5. Add authentication if this will expose internal pipeline data outside trusted users.

## Deployment Modes

### Local evaluation

- Keep `ENABLE_SAMPLE_DATA=true`
- Leave source URLs empty
- Use sample tenders and pipeline data bundled in the repo

### Controlled internal deployment

- Prefer `WARROOM_JSON_SOURCE_URL` with a curated unified snapshot
- Or keep public procurement sources live in legacy mode
- Point `PROMPCORP_PIPELINE_SOURCE_URL` to internal CSV or JSON exports if needed
- Restrict access with VPN or reverse-proxy authentication

### Full production

- Run on a hardened VM or private Kubernetes namespace
- Add SSO or gateway auth
- Add monitoring for:
  - connector failures
  - DB size growth
  - ingestion freshness
  - dashboard API latency

## Suggested Validation Checklist

1. `GET /health` returns `ok`
2. `GET /api/dashboard/summary` returns counts and source health
3. Dashboard loads the `Active Bids` view successfully
4. Main filters update tender results
5. `Recently Closed` and `Sources` views render expected data
6. Manual ingestion trigger refreshes connector run timestamps
