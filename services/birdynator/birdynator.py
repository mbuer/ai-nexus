#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import sys
from urllib.error import HTTPError
import time
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener, urlopen

import psycopg
from enrichment import enable_search, cited_report
from journal import report_from_analysis, export as export_journal
from evidence import VERSION, PROMPT_VERSION, build_evidence, analysis_payload, timestamp


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
BIRDNET_DB_HOST = os.getenv("BIRDNET_DB_HOST", "ai-nexus-birdnet-proxy")
BIRDNET_DB_PORT = int(os.getenv("BIRDNET_DB_PORT", "5432"))
BIRDNET_DB_NAME = os.getenv("BIRDNET_DB_NAME", "birdnet")
BIRDNET_DB_USER = os.getenv("BIRDNET_DB_USER", "birdynator_reader")
BIRDNET_DB_PASSWORD_FILE = os.getenv("BIRDNET_DB_PASSWORD_FILE", "/run/secrets/birdnet-db-password")


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


def birdnet_password():
    return Path(BIRDNET_DB_PASSWORD_FILE).read_text().strip()


def connect_birdnet():
    return psycopg.connect(
        host=BIRDNET_DB_HOST,
        port=BIRDNET_DB_PORT,
        dbname=BIRDNET_DB_NAME,
        user=BIRDNET_DB_USER,
        password=birdnet_password(),
        connect_timeout=5,
        options="-c default_transaction_read_only=on",
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


def birdnet_health():
    with connect_birdnet() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user, current_database(), current_setting('transaction_read_only')")
            user, database, read_only = cur.fetchone()
            cur.execute("SELECT COUNT(*) FROM detections")
            detections = cur.fetchone()[0]
    print(json.dumps({
        "status": "ok",
        "database": database,
        "database_user": user,
        "read_only": read_only,
        "detections": detections,
    }, sort_keys=True))


def rows_as_dicts(cur):
    columns = [desc.name for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]


def birdnet_comparison(recent_hours=24, baseline_days=30, top_species=25, through=None):
    # top_species is retained for CLI compatibility; evidence must include rare species.
    if not 1 <= recent_hours <= 168 or not 1 <= baseline_days <= 366:
        raise ValueError("hours must be 1..168 and baseline_days 1..366")
    with connect_birdnet() as conn:
        with conn.cursor() as cur:
            # Both existing views share a stable, read-only snapshot and cutoff.
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            if through is None:
                cur.execute("SELECT MAX(hour_local) FROM bird_activity_hourly")
                latest_hour = cur.fetchone()[0]
            else:
                latest_hour = timestamp(through)
            if latest_hour is None:
                raise RuntimeError("bird_activity_hourly contains no data")
            if latest_hour.tzinfo is not None or latest_hour.minute or latest_hour.second or latest_hour.microsecond:
                raise ValueError("through must be a naive local timestamp aligned to an hour")
            params = (latest_hour, baseline_days, recent_hours, latest_hour)
            cur.execute(
                """
                SELECT * FROM bird_activity_hourly
                WHERE hour_local > %s - (%s * interval '1 day') - (%s * interval '1 hour')
                  AND hour_local <= %s
                ORDER BY hour_local
                """, params)
            activity = rows_as_dicts(cur)
            cur.execute(
                """
                SELECT * FROM bird_species_hourly
                WHERE hour_local > %s - (%s * interval '1 day') - (%s * interval '1 hour')
                  AND hour_local <= %s AND present = 1
                ORDER BY hour_local, species
                """, params)
            species = rows_as_dicts(cur)
    return build_evidence(activity, species, latest_hour, recent_hours, baseline_days)


def save_analysis(dataset, args, model, result_text, source_digest):
    window = dataset["window"]
    source_ref = (
        f"birdnet:bird_activity_hourly+bird_species_hourly:"
        f"through={window['latest_hour']}:"
        f"recent={window['recent_hours']}h:baseline={window['baseline_days']}d"
    )
    parameters = {
        "recent_hours": args.hours,
        "baseline_days": args.baseline_days,
        "top_species": args.top_species,
        "tier": args.tier,
        "evidence_version": VERSION,
        "prompt_version": PROMPT_VERSION,
        "web_enrichment": getattr(args, "web_enrichment", False),
        "external_context": getattr(args, "external_context", {"status": "disabled"}),
        "through": getattr(args, "through", None),
    }
    parameters['journal_report'] = report_from_analysis({
        'id': 'pending', 'source_latest_hour': window['latest_hour'],
        'source_digest': source_digest, 'model': model,
        'parameters': parameters, 'result_text': result_text,
    }, dataset)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO analysis_runs
                    (analysis_type, model, source_type, source_ref, source_latest_hour,
                     recent_hours, baseline_days, source_digest, parameters, result_text)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                RETURNING id
                """,
                (
                    "birdnet_recent_vs_baseline",
                    model,
                    "birdnet_postgres",
                    source_ref,
                    window["latest_hour"],
                    args.hours,
                    args.baseline_days,
                    source_digest,
                    json.dumps(parameters),
                    result_text,
                ),
            )
            analysis_id = cur.fetchone()[0]
        conn.commit()
    return analysis_id


def analysis_history(args):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, analysis_type, model, source_ref, recent_hours, baseline_days, created_at
                FROM analysis_runs
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (args.limit,),
            )
            rows = rows_as_dicts(cur)
    print(json.dumps(rows, default=str, indent=2))


def analyze_birdnet(args):
    dataset = birdnet_comparison(args.hours, args.baseline_days, args.top_species, args.through)
    model = model_for_tier(args.tier)
    request_payload, context = analysis_payload(dataset, model)
    source_digest = hashlib.sha256(context.encode()).hexdigest()
    if args.evidence_only:
        print(json.dumps(dataset, indent=2, sort_keys=True))
        return
    print(f"Journal prompt: {PROMPT_VERSION}; evidence through {dataset['window']['latest_hour']}", file=sys.stderr)
    use_web = getattr(args, "web_enrichment", False)
    args.external_context = {"status": "disabled"}

    def request_report(body):
        req = Request(
            OPENAI_API_URL, data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {openai_key()}",
                     "Content-Type": "application/json"})
        with openai_opener().open(req, timeout=180 if use_web else 90) as response:
            result = json.loads(response.read())
        if result.get("status") in ("failed", "incomplete", "cancelled"):
            raise RuntimeError("OpenAI analysis did not complete; no result saved")
        return result

    if use_web:
        try:
            data = request_report(enable_search(request_payload))
        except HTTPError as error:
            # A rejected tool request is safe to retry without tools. Do not retry
            # ambiguous timeouts, rate limits or server failures automatically.
            if error.code not in (400, 422):
                raise
            args.external_context = {"status": "fallback_request_rejected",
                                     "http_status": error.code}
            print("Optional search request rejected; generating a local-evidence report.", file=sys.stderr)
            data = request_report(request_payload)
            result_text = openai_text(data)
        else:
            try:
                result_text, args.external_context = cited_report(data)
                if (not args.external_context['search_calls']
                        or not args.external_context['cited_sources']):
                    raise ValueError("Required search missing or without citable context")
            except ValueError:
                args.external_context = {"status": "fallback_unusable_sources",
                                         "response_id": data.get("id")}
                print("Optional search had no usable citations; generating a local-evidence report.", file=sys.stderr)
                result_text = openai_text(request_report(request_payload))
    else:
        result_text = openai_text(request_report(request_payload))
    analysis_id = save_analysis(dataset, args, model, result_text, source_digest)
    if getattr(args, 'journal_output', None):
        report = report_from_analysis({
            'id': analysis_id, 'source_latest_hour': dataset['window']['latest_hour'],
            'source_digest': source_digest, 'model': model, 'result_text': result_text,
            'parameters': {'prompt_version': PROMPT_VERSION, 'external_context': args.external_context},
        }, dataset)
        print(f"[journal exported: {export_journal(report, args.journal_output)}]")
    print(result_text)
    print(f"\n[analysis saved: id={analysis_id}; source_digest={source_digest[:12]}]")

def journal_saved(args):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, model, source_latest_hour, source_digest, parameters, result_text "
                        "FROM analysis_runs WHERE id = %s", (args.analysis_id,))
            rows = rows_as_dicts(cur)
    if not rows:
        raise ValueError("Analysis ID not found")
    record = rows[0]
    saved = record['parameters'].get('journal_report')
    evidence = saved.get('evidence') if saved else None
    report = report_from_analysis(record, evidence, args.headline or (saved['headline'] if saved else None))
    print(export_journal(report, args.output))


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
    sub.add_parser("birdnet-health")

    analyze_parser = sub.add_parser("analyze-birdnet")
    analyze_parser.add_argument("--hours", type=int, default=24)
    analyze_parser.add_argument("--baseline-days", type=int, default=30)
    analyze_parser.add_argument("--top-species", type=int, default=25,
                                help="compatibility option; v2 uses all species")
    analyze_parser.add_argument("--through", help="historical local hour, e.g. 2026-09-24T23:00:00")
    analyze_parser.add_argument("--journal-output", help="write standalone HTML, Markdown, JSON and archive index")
    analyze_parser.add_argument("--web-enrichment", action="store_true",
                                help="optional domain-restricted provider-hosted species search")
    analyze_parser.add_argument("--evidence-only", action="store_true",
                                help="print deterministic evidence without OpenAI or persistence")
    analyze_parser.add_argument("--tier", choices=("fast", "default", "deep"), default="default")

    history_parser = sub.add_parser("analysis-history")
    history_parser.add_argument("--limit", type=int, default=10)

    journal_parser = sub.add_parser("export-journal")
    journal_parser.add_argument("analysis_id", type=int)
    journal_parser.add_argument("--output", required=True)
    journal_parser.add_argument("--headline")

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
    elif args.command == "birdnet-health":
        birdnet_health()
    elif args.command == "analyze-birdnet":
        analyze_birdnet(args)
    elif args.command == "export-journal":
        journal_saved(args)
    elif args.command == "analysis-history":
        analysis_history(args)


if __name__ == "__main__":
    main()
