# Embedding Service

The embedding service converts text into normalized vectors for semantic retrieval. It is separate from PostgreSQL and receives no database credentials.

## Initial model

- `sentence-transformers/all-MiniLM-L6-v2`
- revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`
- 384 dimensions

## Reproducibility

- Python dependencies are pinned.
- The model revision is pinned.
- The Python base-image tag is resolved to a content digest during each explicit build.
- The model is downloaded during image build and stored inside the image.
- Runtime uses offline Hugging Face/Transformers mode.

A fully hashed transitive Python dependency lock remains a later hardening step.

## Security

- rootless Podman
- internal network only
- no host port
- no database credential
- read-only root filesystem
- limited writable `/tmp`
- CPU, RAM, and PID limits
- one Uvicorn worker

## Deploy

```bash
make embedding-deploy
```

Verify:

```bash
make embedding-verify
```
