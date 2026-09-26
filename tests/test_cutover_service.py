import httpx
import pytest

from devtools_cutover.cutover_service import CutoverService
from devtools_cutover.infrai_dns import InfraiDnsClient
from devtools_cutover.models import CutoverPhase, CutoverRequest


@pytest.mark.asyncio
async def test_release_captures_previous_record_and_rollback_restores_it() -> None:
    writes: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/dns/domain/get":
            return httpx.Response(200, json={"ok": True, "data": {"zone_id": "zone_42"}})
        if request.url.path == "/v1/dns/record/list":
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "data": [
                        {
                            "record_id": "record_7",
                            "record_type": "CNAME",
                            "name": "tools",
                            "content": "old.vercel.app",
                            "ttl": 300,
                        }
                    ],
                },
            )
        payload = __import__("json").loads(request.content)
        writes.append(payload)
        return httpx.Response(200, json={"ok": True, "data": payload})

    dns = InfraiDnsClient(api_key="test-key", transport=httpx.MockTransport(handler))
    service = CutoverService(dns)
    request = CutoverRequest(
        domain="example.com",
        name="tools",
        record_type="CNAME",
        content="new.vercel.app",
        ttl=60,
        build_id="build-204",
    )

    released = await service.release(request)
    rolled_back = await service.rollback("build-204")
    await dns.close()

    assert released.build.status == "ready"
    assert rolled_back.release.phase == CutoverPhase.ROLLED_BACK
    assert writes[0]["content"] == "new.vercel.app"
    assert writes[0]["ttl"] == 60
    assert writes[1]["content"] == "old.vercel.app"
    assert writes[1]["ttl"] == 300
    assert all(write["zone_id"] == "zone_42" for write in writes)
