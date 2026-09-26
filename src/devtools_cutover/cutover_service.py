from typing import Any

from .infrai_dns import InfraiDnsClient
from .models import BuildEvent, CutoverPhase, CutoverRequest, CutoverResult, Diagnostic, ReleaseOperation


def _matching_record(records: list[dict[str, Any]], request: CutoverRequest) -> dict[str, Any] | None:
    return next(
        (
            record
            for record in records
            if record.get("name") == request.name and record.get("record_type") == request.record_type
        ),
        None,
    )


class CutoverService:
    def __init__(self, dns: InfraiDnsClient) -> None:
        self._dns = dns
        self._releases: dict[str, CutoverResult] = {}

    async def release(self, request: CutoverRequest) -> CutoverResult:
        zone = await self._dns.get_zone(request.domain)
        zone_id = str(zone["zone_id"])
        records = await self._dns.list_records(zone_id)
        previous = _matching_record(records, request)
        active = await self._dns.upsert_record(
            zone_id=zone_id,
            record_type=request.record_type,
            name=request.name,
            content=request.content,
            ttl=request.ttl,
            record_id=str(previous["record_id"]) if previous and previous.get("record_id") else None,
            idempotency_key=f"cutover:{request.build_id}:{zone_id}:{request.name}",
        )
        result = CutoverResult(
            build=BuildEvent(build_id=request.build_id),
            release=ReleaseOperation(
                phase=CutoverPhase.RELEASED,
                zone_id=zone_id,
                previous_record=previous,
                active_record=active,
            ),
            diagnostics=[
                Diagnostic(check="zone", status="pass", detail=f"Resolved zone_id {zone_id}"),
                Diagnostic(check="ttl", status="pass", detail=f"Cutover TTL is {request.ttl} seconds"),
                Diagnostic(
                    check="rollback",
                    status="pass" if previous else "attention",
                    detail="Previous record captured" if previous else "No previous record was present",
                ),
            ],
        )
        self._releases[request.build_id] = result
        return result

    async def rollback(self, build_id: str) -> CutoverResult:
        result = self._releases[build_id]
        previous = result.release.previous_record
        if previous is None:
            raise ValueError("This release has no previous record to restore")
        restored = await self._dns.upsert_record(
            zone_id=result.release.zone_id,
            record_type=str(previous["record_type"]),
            name=str(previous["name"]),
            content=str(previous["content"]),
            ttl=int(previous["ttl"]) if previous.get("ttl") is not None else None,
            record_id=str(previous["record_id"]) if previous.get("record_id") else None,
            idempotency_key=f"rollback:{build_id}:{result.release.zone_id}:{previous['name']}",
        )
        result.release.phase = CutoverPhase.ROLLED_BACK
        result.release.active_record = restored
        result.diagnostics.append(
            Diagnostic(check="rollback_applied", status="pass", detail="Previous record restored")
        )
        return result

    def diagnostics(self, build_id: str) -> CutoverResult:
        return self._releases[build_id]
