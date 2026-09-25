import os
from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

MODEL_NAME = os.environ.get("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
MODEL_REVISION = os.environ.get("EMBEDDING_MODEL_REVISION", "1110a243fdf4706b3f48f1d95db1a4f5529b4d41")
MODEL_PATH = os.environ.get("EMBEDDING_MODEL_PATH", "/opt/model")
EXPECTED_DIMENSIONS = int(os.environ.get("EMBEDDING_DIMENSIONS", "384"))
MAX_BATCH_SIZE = int(os.environ.get("EMBEDDING_MAX_BATCH_SIZE", "32"))

app = FastAPI(title="AI Nexus Embedding Service", version="1.0.0")
model = SentenceTransformer(MODEL_PATH)

class EmbedRequest(BaseModel):
    texts: List[str] = Field(min_length=1, max_length=MAX_BATCH_SIZE)

@app.get("/health")
def health():
    dimensions = model.get_sentence_embedding_dimension()
    return {
        "status": "ok" if dimensions == EXPECTED_DIMENSIONS else "dimension_mismatch",
        "model": MODEL_NAME,
        "revision": MODEL_REVISION,
        "dimensions": dimensions,
        "max_batch_size": MAX_BATCH_SIZE,
    }

@app.post("/embed")
def embed(request: EmbedRequest):
    cleaned = [text.strip() for text in request.texts]
    if any(not text for text in cleaned):
        raise HTTPException(status_code=400, detail="texts must not be empty")

    vectors = model.encode(
        cleaned,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    if vectors.shape[1] != EXPECTED_DIMENSIONS:
        raise HTTPException(status_code=500, detail="unexpected embedding dimensions")

    return {
        "model": MODEL_NAME,
        "revision": MODEL_REVISION,
        "dimensions": EXPECTED_DIMENSIONS,
        "embeddings": vectors.tolist(),
    }
