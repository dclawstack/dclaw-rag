# Installation

## Via DPanel

1. Open DPanel at `https://panel.yourdomain.com`
2. Find **DClaw RAG** in the app grid
3. Click **Install**
4. The DClaw Operator will provision:
   - Namespace: `dclaw-rag`
   - Frontend deployment (Next.js)
   - Backend deployment (FastAPI)
   - PostgreSQL database (CloudNativePG)
   - Ingress with TLS

## Via kubectl

```bash
# Apply the DClawApp CRD
kubectl apply -f - <<EOF
apiVersion: platform.dclaw.io/v1
kind: DClawApp
metadata:
  name: rag
spec:
  appId: rag
  appName: DClaw RAG
  version: 0.1.0
  category: platform
  enabled: true
  frontend:
    image: ghcr.io/dclawstack/dclaw-rag:latest
    replicas: 2
  backend:
    image: ghcr.io/dclawstack/dclaw-rag-backend:latest
    replicas: 2
  database:
    enabled: true
    storage: 10Gi
  ingress:
    enabled: true
    host: rag.yourdomain.com
    tls: true
EOF
```

## Verify

```bash
kubectl get pods -n dclaw-rag
kubectl get ingress -n dclaw-rag
```
