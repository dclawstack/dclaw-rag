# Troubleshooting

Common issues and solutions for DClaw RAG.

## Quick Diagnostics

```bash
# Check app pods
kubectl get pods -n dclaw-rag

# Check logs
kubectl logs -n dclaw-rag deployment/dclaw-rag-backend

# Check database
kubectl get clusters -n dclaw-rag
```

## Sections

- [Common Issues](./common-issues)
- [FAQ](./faq)
