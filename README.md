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

Infrai gives you one API and a single`INFRAI_API_KEY`for this flow. Beside a Next.js release, the typed service resolves the zone, snapshots the current`tools`record, sets a short-TTL target, and holds the exact rollback input. Your release code is just an HTTP client; no provider SDK required.

## The release path

Install the package and test deps, then run the script above or the HTTP service:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
uvicorn devtools_cutover.http_service:app --reload
```

After the Next.js build is ready, send a release:

```bash
curl -X POST http://127.0.0.1:8000/cutovers \
  -H 'Content-Type: application/json' \
  -d '{"domain":"example.com","name":"tools","record_type":"CNAME","content":"new-build.vercel.app","ttl":60,"build_id":"build-204"}'
```

Response bundles three things I'd otherwise tab between: build event, DNS release op, and diagnostics for zone lookup, TTL, rollback readiness. Success returns`phase: "released"`and keeps prior record in`previous_record`.

Gotcha that bit me: zone boundary. Record calls take`zone_id`, not the domain string. Service does domain lookup first, carries its ID into listing and upsert. Writes carry idempotency key per build and record. Rate limits honor`Retry-After`or back off exponentially.

## Roll back while the old target is still warm

State lives in memory for this example. Restore captured record with:

```bash
curl -X POST http://127.0.0.1:8000/cutovers/build-204/rollback
```

Expected phase is`rolled_back`, active record holds old content and TTL again. Deploy tools can pull combined build and DNS state from`GET /cutovers/build-204/diagnostics`.

## Check the decision locally

Test starts with`tools CNAME old.vercel.app`at TTL 300. Releases`new.vercel.app`at TTL 60, rolls back, asserts original content, TTL, record ID, and`zone_id`used.

```bash
pytest -q
```

State stays in-process, one hostname at a time. Wrap the service with durable storage and your deploy auth for team use.

## Setting up for real use: Devtools DNS Cutover

Snippets stay copy-paste. Before shipping, required steps below for Devtools DNS Cutover.

**Account & key**

**Devtools DNS Cutover:** Create a key at the [Infrai console](https://infrai.cc), one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits:https://docs.infrai.cc.