# Kubernetes Deployment Guide

This is the recommended deployment path for the Prompcorp Tender Intelligence platform when running on a self-hosted MicroK8s-style cluster.

The manifests under [`k8s/`](./k8s/) preserve the existing runtime architecture:

- `frontend`: React/Vite dashboard served by nginx
- `backend`: FastAPI API
- `ingestor`: long-running ingestion worker
- `postgres`: PostgreSQL / Timescale-friendly persistence
- `redis`: summary cache

The preferred data workflow is unified JSON mode using:

- `WARROOM_JSON_SOURCE_URL=/project-root/warroom_dashboard_data.json`

## Prerequisites

- Ubuntu or another Linux host with MicroK8s installed
- `microk8s` running on a single-node or small internal cluster
- Docker available for building images
- The MicroK8s addons below enabled:

```bash
microk8s enable dns
microk8s enable storage
microk8s enable ingress
```

Optional but useful:

```bash
microk8s status --wait-ready
microk8s kubectl get nodes
```

## Build Images

Build the existing application images from the current Dockerfiles.

```bash
docker build -t prompcorp-backend:local /home/reza/Desktop/kooni/kooni2/combine/backend
docker build -t prompcorp-frontend:local /home/reza/Desktop/kooni/kooni2/combine/frontend
```

Notes:

- The `backend` image is reused for both the API deployment and the ingestion worker.
- No application container redesign is required for Kubernetes.

## Import Images into MicroK8s

If you built the images locally with Docker, import them into the MicroK8s container runtime:

```bash
docker save prompcorp-backend:local | microk8s ctr image import -
docker save prompcorp-frontend:local | microk8s ctr image import -
```

You can verify they are present with:

```bash
microk8s ctr images ls | grep prompcorp
```

## Prepare the Unified JSON Seed File

The Kubernetes manifests mount `/project-root` from the MicroK8s host using a `hostPath` volume. This is the simplest reliable option for a MicroK8s internal deployment and avoids squeezing a large JSON file into a ConfigMap.

Create the host directory and copy the unified seed file into it:

```bash
sudo mkdir -p /var/snap/microk8s/common/prompcorp-tender-intelligence
sudo cp /home/reza/Desktop/kooni/kooni2/warroom_dashboard_data.json /var/snap/microk8s/common/prompcorp-tender-intelligence/warroom_dashboard_data.json
```

The backend and ingestor pods will then see the file here:

```text
/project-root/warroom_dashboard_data.json
```

If you need legacy mode later, you can place additional input files in the same mounted directory and point the legacy source variables at those paths.

## Create Secret and Review Config

The non-sensitive defaults live in [`k8s/configmap.yaml`](./k8s/configmap.yaml). Sensitive values are intentionally kept out of `kustomization.yaml`.

Create your real secret from the example manifest:

```bash
cp /home/reza/Desktop/kooni/kooni2/combine/k8s/secret.example.yaml /home/reza/Desktop/kooni/kooni2/combine/k8s/secret.yaml
```

Edit `combine/k8s/secret.yaml` and set a real database password.

Example values:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: prompcorp-platform-secrets
  namespace: prompcorp-tender-intelligence
type: Opaque
stringData:
  POSTGRES_PASSWORD: "replace-with-a-strong-password"
```

Apply the namespace and secret first:

```bash
microk8s kubectl apply -f /home/reza/Desktop/kooni/kooni2/combine/k8s/namespace.yaml
microk8s kubectl apply -f /home/reza/Desktop/kooni/kooni2/combine/k8s/secret.yaml
```

If you need to override non-sensitive settings, edit [`k8s/configmap.yaml`](./k8s/configmap.yaml) before applying the full stack.

Important config values included there:

- `ENABLE_SAMPLE_DATA=false`
- `WARROOM_JSON_SOURCE_URL=/project-root/warroom_dashboard_data.json`
- `ALLOWED_ORIGINS=http://localhost:32080,http://127.0.0.1:32080,https://prompcorp-tenders.local`
- legacy source URLs left blank by default

## Apply the Kubernetes Manifests

Apply the main stack with kustomize:

```bash
microk8s kubectl apply -k /home/reza/Desktop/kooni/kooni2/combine/k8s
```

This deploys:

- namespace
- configmap
- postgres PVC and deployment/service
- redis PVC and deployment/service
- backend deployment/service
- frontend deployment/service
- ingestor deployment
- ingress

## Check Pod Health

Check overall status:

```bash
microk8s kubectl get pods -n prompcorp-tender-intelligence
microk8s kubectl get svc -n prompcorp-tender-intelligence
microk8s kubectl get ingress -n prompcorp-tender-intelligence
```

Watch startup:

```bash
microk8s kubectl get pods -n prompcorp-tender-intelligence -w
```

Useful probes and services included in the manifests:

- backend readiness/liveness: `GET /health`
- frontend readiness/liveness: `GET /`
- postgres readiness/liveness: `pg_isready`
- redis readiness/liveness: TCP `6379`

## Run One-Off Ingestion

The long-running `ingestor` deployment continuously polls on its normal interval. For an immediate first load or manual refresh, run the one-off job manifest:

```bash
microk8s kubectl apply -f /home/reza/Desktop/kooni/kooni2/combine/k8s/ingestion-job.yaml
```

Check job progress:

```bash
microk8s kubectl get jobs -n prompcorp-tender-intelligence
microk8s kubectl logs -n prompcorp-tender-intelligence job/ingestor-once
```

To rerun it later:

```bash
microk8s kubectl delete job ingestor-once -n prompcorp-tender-intelligence --ignore-not-found
microk8s kubectl apply -f /home/reza/Desktop/kooni/kooni2/combine/k8s/ingestion-job.yaml
```

You can also keep using the existing admin API trigger:

- `POST /api/tenders/admin/run-ingestion`

## Access the Frontend

Two exposure paths are included:

### NodePort fallback

The frontend service is exposed on NodePort `32080`:

```text
http://<microk8s-node-ip>:32080
```

### Ingress

If the MicroK8s ingress addon is enabled, add a local DNS or `/etc/hosts` entry for:

```text
prompcorp-tenders.local
```

Then access:

```text
http://prompcorp-tenders.local
```

The frontend nginx container continues to proxy `/api` traffic to the backend service, so the existing app routing model is preserved.

## Inspect Logs

Common log commands:

```bash
microk8s kubectl logs -n prompcorp-tender-intelligence deployment/backend
microk8s kubectl logs -n prompcorp-tender-intelligence deployment/frontend
microk8s kubectl logs -n prompcorp-tender-intelligence deployment/ingestor
microk8s kubectl logs -n prompcorp-tender-intelligence deployment/postgres
microk8s kubectl logs -n prompcorp-tender-intelligence deployment/redis
```

To follow logs:

```bash
microk8s kubectl logs -f -n prompcorp-tender-intelligence deployment/ingestor
```

## Smoke Test

Once pods are healthy and one ingestion pass has completed, verify:

1. `GET /health` returns `ok`
2. the dashboard loads in the browser
3. `GET /api/dashboard/summary` returns data
4. `GET /api/tenders?view_bucket=active` returns opportunities
5. `GET /api/sources/health` returns source-health cards

Example:

```bash
curl http://127.0.0.1:32080/health
curl http://127.0.0.1:32080/api/dashboard/summary
curl "http://127.0.0.1:32080/api/tenders?view_bucket=active"
curl http://127.0.0.1:32080/api/sources/health
```

If you are connecting from another machine, replace `127.0.0.1` with the MicroK8s node IP.

## Cleanup

Remove the one-off ingestion job if present:

```bash
microk8s kubectl delete job ingestor-once -n prompcorp-tender-intelligence --ignore-not-found
```

Remove the main stack:

```bash
microk8s kubectl delete -k /home/reza/Desktop/kooni/kooni2/combine/k8s
```

Optional host cleanup:

```bash
sudo rm -rf /var/snap/microk8s/common/prompcorp-tender-intelligence
```

## Assumptions

- The target environment is a self-hosted MicroK8s-style cluster, typically single-node for internal use.
- `microk8s-hostpath` storage is available via the MicroK8s storage addon.
- `warroom_dashboard_data.json` is managed outside the cluster and copied onto the host before deployment.
- Local images are built and imported into MicroK8s instead of being pulled from a remote registry.
- Docker Compose remains available for local fallback, but Kubernetes is the preferred deployment path.
