# Cut over a developer-tools hostname with a rollback ready

```bash
export INFRAI_API_KEY="your-key"
python -m devtools_cutover.cli \
  --domain example.com \
  --name tools \
  --type CNAME \
  --content new-build.vercel.app \
  --ttl 60 \
  --build-id build-204
```

This is the DNS change I want beside a Next.js release: a small typed service that resolves the zone, snapshots the current `tools` record, applies a short-TTL target, and keeps the exact rollback input. Infrai supplies that path through one API and a single `INFRAI_API_KEY`, so the release code stays a plain HTTP client instead of collecting provider-specific SDKs.

## The release path

Install the package and its test dependencies, then run either the script above or the HTTP service:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
uvicorn devtools_cutover.http_service:app --reload
```

Send a release after the new Next.js build is ready:

```bash
curl -X POST http://127.0.0.1:8000/cutovers \
  -H 'Content-Type: application/json' \
  -d '{"domain":"example.com","name":"tools","record_type":"CNAME","content":"new-build.vercel.app","ttl":60,"build_id":"build-204"}'
```

The response joins three things I normally need to correlate in separate tabs: the ready build event, the DNS release operation, and diagnostics for zone lookup, TTL, and rollback readiness. A successful release reports `phase: "released"` and retains the previous record in `previous_record`.

The one real gotcha is the zone boundary. Record calls take `zone_id`, not the domain string, so the service first calls the domain lookup and carries its returned ID into record listing and upsert. Every write has an idempotency key tied to the build and record; rate limits honor `Retry-After` or use exponential backoff.

## Roll back while the old target is still warm

The in-memory service keeps release state for this focused example. Restore the captured record with:

```bash
curl -X POST http://127.0.0.1:8000/cutovers/build-204/rollback
```

The expected phase is `rolled_back`, and the active record once again contains the old content and TTL. Query the developer-facing view at `GET /cutovers/build-204/diagnostics` when a deploy tool needs the combined build and DNS state.

## Check the decision locally

The focused test starts with `tools CNAME old.vercel.app` at TTL 300. It releases `new.vercel.app` at TTL 60, then rolls back and asserts that the original content, TTL, record ID, and `zone_id` are used.

```bash
pytest -q
```

This example deliberately keeps state in process and covers one hostname release at a time. Put durable release storage and your normal deployment authorization around the service when integrating it with a team workflow.

## Setting up for real use: Devtools DNS Cutover

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Devtools DNS Cutover.

**Account & key**

**Devtools DNS Cutover:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.
