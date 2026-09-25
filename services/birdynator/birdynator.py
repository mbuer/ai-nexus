#!/usr/bin/env python3
import argparse
import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen

import psycopg


DB_HOST = os.getenv("BIRDYNATOR_DB_HOST", "ai-nexus-postgres")
DB_NAME = os.getenv("BIRDYNATOR_DB_NAME", "birdynator")
DB_USER = os.getenv("BIRDYNATOR_DB_USER", "birdynator")
DB_PASSWORD_FILE = os.getenv("BIRDYNATOR_DB_PASSWORD_FILE", "/run/secrets/db-password")
EMBEDDING_URL = os.getenv("BIRDYNATOR_EMBEDDING_URL", "http://ai-nexus-embedding:8000")
EMBEDDING_MODEL_SLUG = os.getenv("BIRDYNATOR_EMBEDDING_MODEL_SLUG", "all-minilm-l6-v2-1110a24")


def db_password():
    return Path(DB_PASSWORD_FILE).read_text().strip()


def connect():
    return psycopg.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=db_password(),
        connect_timeout=5,
    )


def embed(text):
    payload = json.dumps({"texts": [text]}).encode()
    req = Request(
        f"{EMBEDDING_URL}/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=15) as response:
        data = json.loads(response.read())
    vector = data["embeddings"][0]
    if len(vector) != 384:
        raise RuntimeError(f"unexpected embedding dimensions: {len(vector)}")
    return vector


def vector_literal(vector):
    return "[" + ",".join(str(float(value)) for value in vector) + "]"


def health():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user, current_database()")
            db_user, db_name = cur.fetchone()

    with urlopen(f"{EMBEDDING_URL}/health", timeout=5) as response:
        embedding = json.loads(response.read())

    print(json.dumps({
        "status": "ok",
        "database": db_name,
        "database_user": db_user,
        "embedding_status": embedding.get("status"),
        "embedding_dimensions": embedding.get("dimensions"),
    }, sort_keys=True))


def remember(args):
    vector = embed(args.content)
    metadata = json.loads(args.metadata)

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory
                    (memory_type, content, metadata, source_type, source_ref, confidence)
                VALUES (%s, %s, %s::jsonb, %s, %s, %s)
                RETURNING id
                """,
                (
                    args.type,
                    args.content,
                    json.dumps(metadata),
                    args.source_type,
                    args.source_ref,
                    args.confidence,
                ),
            )
            memory_id = cur.fetchone()[0]

            cur.execute(
                "SELECT id FROM embedding_models WHERE slug = %s AND active = TRUE",
                (EMBEDDING_MODEL_SLUG,),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError(f"active embedding model not found: {EMBEDDING_MODEL_SLUG}")
            model_id = row[0]

            cur.execute(
                """
                INSERT INTO memory_embeddings (memory_id, model_id, embedding)
                VALUES (%s, %s, %s::vector)
                ON CONFLICT (memory_id, model_id)
                DO UPDATE SET embedding = EXCLUDED.embedding, updated_at = NOW()
                """,
                (memory_id, model_id, vector_literal(vector)),
            )
        conn.commit()

    print(json.dumps({"status": "remembered", "memory_id": memory_id}))


def recall(args):
    vector = vector_literal(embed(args.query))

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.id, m.memory_type, m.content, m.source_type, m.source_ref,
                       m.confidence, (me.embedding <=> %s::vector) AS distance
                FROM memory_embeddings me
                JOIN memory m ON m.id = me.memory_id
                JOIN embedding_models em ON em.id = me.model_id
                WHERE em.slug = %s
                  AND em.active = TRUE
                  AND m.status = 'active'
                ORDER BY me.embedding <=> %s::vector
                LIMIT %s
                """,
                (vector, EMBEDDING_MODEL_SLUG, vector, args.limit),
            )
            rows = cur.fetchall()

    output = [
        {
            "id": row[0],
            "memory_type": row[1],
            "content": row[2],
            "source_type": row[3],
            "source_ref": row[4],
            "confidence": float(row[5]) if row[5] is not None else None,
            "distance": float(row[6]),
        }
        for row in rows
    ]
    print(json.dumps(output, indent=2))


def serve():
    health()
    while True:
        time.sleep(3600)


def main():
    parser = argparse.ArgumentParser(prog="birdynator")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health")
    sub.add_parser("serve")

    remember_parser = sub.add_parser("remember")
    remember_parser.add_argument("content")
    remember_parser.add_argument("--type", default="observation")
    remember_parser.add_argument("--metadata", default="{}")
    remember_parser.add_argument("--source-type", default="manual")
    remember_parser.add_argument("--source-ref")
    remember_parser.add_argument("--confidence", type=float)

    recall_parser = sub.add_parser("recall")
    recall_parser.add_argument("query")
    recall_parser.add_argument("--limit", type=int, default=5)

    args = parser.parse_args()

    if args.command == "health":
        health()
    elif args.command == "serve":
        serve()
    elif args.command == "remember":
        remember(args)
    elif args.command == "recall":
        recall(args)


if __name__ == "__main__":
    main()
