"""The read-only REST interface of the catalog service u6g-catalog, over a built index (guide Section 11.4).

- GET /v1/entries?kind=&area=        the references of the entries, filtered
- GET /v1/entries/{id}@{version}     one entry, with its kind, owner, deprecation and digest
- GET /v1/resolve?ref=               a reference of a descriptor or an envelope, resolved to its digest
- GET /v1/latest/{id}                the latest version of an entry
- GET /v1/reason-codes/{code}        the entry of a reason code
- GET /v1/health                     readiness, with the digest of the index served"""

from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from u6g_catalog.build import parse_ref
from u6g_catalog.snapshot import sha256


def create_app(index: dict[str, Any], index_digest: str | None = None) -> FastAPI:
    app = FastAPI(title="u6g-catalog", description=__doc__)
    entries: dict[str, dict[str, Any]] = index["entries"]
    served = index_digest or sha256(repr(sorted(entries)).encode())

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, err: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=err.status_code, content={"message": err.detail})

    def summary(ref: str) -> dict[str, Any]:
        e = entries[ref]
        return {"ref": ref, "kind": e["kind"], "deprecated": e["deprecated"], "digest": e["digest"]}

    @app.get("/v1/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "entries": len(entries), "index": served}

    @app.get("/v1/entries")
    async def list_entries(
        kind: str | None = Query(default=None),
        area: str | None = Query(default=None),
    ) -> dict[str, Any]:
        refs = [
            ref
            for ref, e in entries.items()
            if (kind is None or e["kind"] == kind) and (area is None or e["id"].split("/")[0] == area)
        ]
        return {"entries": [summary(ref) for ref in refs]}

    @app.get("/v1/entries/{ref:path}")
    async def get_entry(ref: str) -> dict[str, Any]:
        if ref not in entries:
            raise HTTPException(status_code=404, detail=f"no entry {ref}")
        return entries[ref]

    @app.get("/v1/resolve")
    async def resolve(ref: str = Query(...)) -> dict[str, Any]:
        parsed = parse_ref(ref)
        if parsed is None:
            raise HTTPException(status_code=400, detail=f"{ref!r} is not a catalog reference with a version")
        key = f"{parsed[0]}@{parsed[1]}"
        if key not in entries:
            raise HTTPException(status_code=404, detail=f"{ref} does not resolve")
        return summary(key)

    @app.get("/v1/latest/{entry_id:path}")
    async def latest(entry_id: str) -> dict[str, Any]:
        version = index["latest"].get(entry_id)
        if version is None:
            raise HTTPException(status_code=404, detail=f"no entry {entry_id}")
        return summary(f"{entry_id}@{version}")

    @app.get("/v1/reason-codes/{code}")
    async def reason_code(code: str) -> dict[str, Any]:
        ref = index["reasonCodes"].get(code)
        if ref is None:
            raise HTTPException(status_code=404, detail=f"no reason code {code}")
        return entries[ref]

    return app
