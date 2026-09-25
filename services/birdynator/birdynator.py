#!/usr/bin/env python3
import argparse
import json
import os
import time
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener, urlopen

import psycopg


DB_HOST = os.getenv("BIRDYNATOR_DB_HOST", "ai-nexus-postgres")
DB_NAME = os.getenv("BIRDYNATOR_DB_NAME", "birdynator")
DB_USER = os.getenv("BIRDYNATOR_DB_USER", "birdynator")
DB_PASSWORD_FILE = os.getenv("BIRDYNATOR_DB_PASSWORD_FILE", "/run/secrets/db-password")
EMBEDDING_URL = os.getenv("BIRDYNATOR_EMBEDDING_URL", "http://ai-nexus-embedding:8000")
EMBEDDING_MODEL_SLUG = os.getenv("BIRDYNATOR_EMBEDDING_MODEL_SLUG", "all-minilm-l6-v2-1110a24")
OPENAI_API_KEY_FILE = os.getenv("OPENAI_API_KEY_FILE", "/run/secrets/openai-api-key")
OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/responses")
OPENAI_PROXY = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
MODEL_FAST = os.getenv("BIRDYNATOR_MODEL_FAST", "gpt-5.6-luna")
MODEL_DEFAULT = os.getenv("BIRDYNATOR_MODEL_DEFAULT", "gpt-5.6-terra")
MODEL_DEEP = os.getenv("BIRDYNATOR_MODEL_DEEP", "gpt-5.6-sol")


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
    rows = recall_rows(args.query, args.limit)

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



def openai_key():
    return Path(OPENAI_API_KEY_FILE).read_text().strip()


def openai_opener():
    if not OPENAI_PROXY:
        raise RuntimeError("HTTPS_PROXY is required for controlled OpenAI egress")
    return build_opener(ProxyHandler({"https": OPENAI_PROXY}))


def openai_text(data):
    parts = []
    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(content["text"])
    if not parts:
        raise RuntimeError("OpenAI response contained no output_text")
    return "\n".join(parts)


def model_for_tier(tier):
    return {
        "fast": MODEL_FAST,
        "default": MODEL_DEFAULT,
        "deep": MODEL_DEEP,
    }[tier]


def recall_rows(query, limit=5):
    vector = vector_literal(embed(query))
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
                (vector, EMBEDDING_MODEL_SLUG, vector, limit),
            )
            return cur.fetchall()


def ask(args):
    rows = recall_rows(args.question, args.limit)
    memories = []
    for row in rows:
        memories.append({
            "id": row[0],
            "memory_type": row[1],
            "content": row[2],
            "source_type": row[3],
            "source_ref": row[4],
            "confidence": float(row[5]) if row[5] is not None else None,
            "distance": float(row[6]),
        })

    context = "\n".join(
        f"- [memory {m['id']}; type={m['memory_type']}; source={m['source_type']}] {m['content']}"
        for m in memories
    ) or "(no relevant stored memories)"

    payload = json.dumps({
        "model": model_for_tier(args.tier),
        "store": False,
        "instructions": (
            "You are Birdynator, a careful personal bird-analysis agent. "
            "Use the supplied memories as context, not as unquestionable truth. "
            "Distinguish observations, user notes, conclusions, and hypotheses. "
            "Do not invent observations or provenance. If context is insufficient, say so."
        ),
        "input": f"Question:\n{args.question}\n\nRelevant memories:\n{context}",
    }).encode()

    req = Request(
        OPENAI_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {openai_key()}",
            "Content-Type": "application/json",
        },
    )

    with openai_opener().open(req, timeout=60) as response:
        data = json.loads(response.read())

    print(openai_text(data))


def api_health():
    req = Request(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {openai_key()}"},
    )
    with openai_opener().open(req, timeout=30) as response:
        data = json.loads(response.read())
    ids = {item.get("id") for item in data.get("data", [])}
    needed = {MODEL_FAST, MODEL_DEFAULT, MODEL_DEEP}
    missing = sorted(needed - ids)
    if missing:
        raise RuntimeError(f"configured OpenAI models unavailable: {missing}")
    print(json.dumps({"status": "ok", "models": sorted(needed)}))

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

    ask_parser = sub.add_parser("ask")
    ask_parser.add_argument("question")
    ask_parser.add_argument("--tier", choices=("fast", "default", "deep"), default="default")
    ask_parser.add_argument("--limit", type=int, default=5)

    sub.add_parser("api-health")

    args = parser.parse_args()

    if args.command == "health":
        health()
    elif args.command == "serve":
        serve()
    elif args.command == "remember":
        remember(args)
    elif args.command == "recall":
        recall(args)
    elif args.command == "ask":
        ask(args)
    elif args.command == "api-health":
        api_health()


if __name__ == "__main__":
    main()
