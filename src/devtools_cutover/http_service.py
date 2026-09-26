from functools import cache

from fastapi import Depends, FastAPI, HTTPException

from .cutover_service import CutoverService
from .infrai_dns import InfraiDnsClient, InfraiError
from .models import CutoverRequest, CutoverResult

app = FastAPI(title="Developer tools DNS cutover")


@cache
def get_service() -> CutoverService:
    return CutoverService(InfraiDnsClient())


@app.post("/cutovers", response_model=CutoverResult)
async def create_cutover(
    request: CutoverRequest, service: CutoverService = Depends(get_service)
) -> CutoverResult:
    try:
        return await service.release(request)
    except InfraiError as error:
        status = error.status_code if 400 <= error.status_code < 500 else 502
        raise HTTPException(status_code=status, detail=error.detail) from error


@app.post("/cutovers/{build_id}/rollback", response_model=CutoverResult)
async def rollback_cutover(
    build_id: str, service: CutoverService = Depends(get_service)
) -> CutoverResult:
    try:
        return await service.rollback(build_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Build release not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except InfraiError as error:
        status = error.status_code if 400 <= error.status_code < 500 else 502
        raise HTTPException(status_code=status, detail=error.detail) from error


@app.get("/cutovers/{build_id}/diagnostics", response_model=CutoverResult)
async def get_diagnostics(
    build_id: str, service: CutoverService = Depends(get_service)
) -> CutoverResult:
    try:
        return service.diagnostics(build_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Build release not found") from error
