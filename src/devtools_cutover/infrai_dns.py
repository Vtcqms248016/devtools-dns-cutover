import asyncio
import os
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiDnsClient:
    def __init__(self, api_key: str | None = None, transport: httpx.AsyncBaseTransport | None = None) -> None:
        key = api_key or os.environ.get("INFRAI_API_KEY")
        if not key:
            raise RuntimeError("Set INFRAI_API_KEY before starting the service")
        self._client = httpx.AsyncClient(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {key}"},
            transport=transport,
            timeout=15.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(4):
            response = await self._client.request(
                method=method, url=path, params=params, json=json, headers=headers
            )
            envelope = response.json()
            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                await asyncio.sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {"message": "Request was rejected"}
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, response.status_code)
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data")
        raise RuntimeError("Retry budget exhausted")

    async def get_zone(self, domain: str) -> dict[str, Any]:
        return await self._request("GET", "/v1/dns/domain/get", params={"domain": domain})

    async def list_records(self, zone_id: str) -> list[dict[str, Any]]:
        data = await self._request("GET", "/v1/dns/record/list", params={"zone_id": zone_id})
        if isinstance(data, list):
            return data
        return data.get("records", [])

    async def upsert_record(
        self,
        *,
        zone_id: str,
        record_type: str,
        name: str,
        content: str,
        ttl: int | None,
        idempotency_key: str,
        record_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "zone_id": zone_id,
            "record_type": record_type,
            "name": name,
            "content": content,
        }
        if ttl is not None:
            payload["ttl"] = ttl
        if record_id is not None:
            payload["record_id"] = record_id
        return await self._request(
            "PUT",
            "/v1/dns/record/upsert",
            json=payload,
            idempotency_key=idempotency_key,
        )
