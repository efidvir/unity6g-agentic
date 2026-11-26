"""The HTTP interface of the mock controller.

- /tfs-api/... is modeled on the northbound tfs-api of TeraFlowSDN: devices and links, read and configured.
- /mock/v1/controller/version reports the interface version, which the transport adapter compares with the
  range its binding pins.
- /mock/v1/telemetry/... serves the counters of the radio links, polled or streamed, for the sources of the
  Monitoring System.
- /mock/v1/behaviors and /mock/v1/clock steer the mock; behaviors leave them unaffected.

The behaviors in force decide how the controller's interface and its telemetry answer: see config.py."""

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import TypeAdapter, ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from u6g_mockctl.config import BehaviorSpec, MockConfig, parse_duration
from u6g_mockctl.sim import ConfigurationError, Simulation, Unavailable, iso

BEHAVIOR = TypeAdapter(BehaviorSpec)


def create_app(config: MockConfig) -> FastAPI:
    sim = Simulation(config)
    app = FastAPI(title="u6g-mockctl", description=__doc__)
    app.state.sim = sim

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, err: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=err.status_code, content={"message": err.detail})

    @app.exception_handler(Unavailable)
    async def unavailable(_request: Request, err: Unavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content={"message": str(err)})

    def known_device(uuid: str) -> None:
        if uuid not in sim.devices:
            raise HTTPException(status_code=404, detail=f"device {uuid} not found")

    def known_links(links: list[str]) -> None:
        unknown = [link for link in links if link not in sim.links]
        if unknown:
            raise HTTPException(status_code=404, detail=f"links not found: {', '.join(unknown)}")

    # The controller's interface, modeled on the tfs-api of TeraFlowSDN

    @app.get("/tfs-api/device_ids")
    async def device_ids() -> dict[str, Any]:
        await sim.maybe_silent(telemetry=False)
        return {"device_ids": [{"device_uuid": {"uuid": d}} for d in sim.devices]}

    @app.get("/tfs-api/devices")
    async def devices() -> dict[str, Any]:
        await sim.maybe_silent(telemetry=False)
        return {"devices": [sim.device_json(d) for d in sim.devices]}

    @app.get("/tfs-api/device/{uuid}")
    async def device(uuid: str) -> dict[str, Any]:
        await sim.maybe_silent(telemetry=False)
        known_device(uuid)
        return sim.device_json(uuid)

    @app.put("/tfs-api/device/{uuid}")
    async def configure(uuid: str, body: dict[str, Any] = Body(...)) -> JSONResponse:  # noqa: B008
        await sim.maybe_silent(telemetry=False)
        known_device(uuid)
        try:
            status, content = await sim.configure(uuid, body)
        except ConfigurationError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err
        return JSONResponse(status_code=status, content=content)

    @app.get("/tfs-api/link_ids")
    async def link_ids() -> dict[str, Any]:
        await sim.maybe_silent(telemetry=False)
        return {"link_ids": [{"link_uuid": {"uuid": link}} for link in sim.links]}

    @app.get("/tfs-api/links")
    async def links() -> dict[str, Any]:
        await sim.maybe_silent(telemetry=False)
        return {"links": [sim.link_json(link) for link in sim.links]}

    @app.get("/tfs-api/link/{uuid}")
    async def link(uuid: str) -> dict[str, Any]:
        await sim.maybe_silent(telemetry=False)
        known_links([uuid])
        return sim.link_json(uuid)

    @app.get("/mock/v1/controller/version")
    async def version() -> dict[str, str]:
        await sim.maybe_silent(telemetry=False)
        return sim.version()

    # Telemetry for the sources of the Monitoring System

    def selected(links: str | None) -> list[str]:
        names = list(sim.links) if links is None else [x for x in links.split(",") if x]
        known_links(names)
        return names

    @app.get("/mock/v1/telemetry/counters")
    async def counters(links: str | None = Query(default=None)) -> dict[str, Any]:
        await sim.maybe_silent(telemetry=True)
        return sim.counters(selected(links))

    @app.get("/mock/v1/telemetry/stream")
    async def stream(
        interval: str = Query(...),
        count: int | None = Query(default=None, ge=1),
        links: str | None = Query(default=None),
    ) -> StreamingResponse:
        try:
            period = parse_duration(interval).total_seconds()
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err
        if period <= 0:
            raise HTTPException(status_code=400, detail="the interval is positive")
        names = selected(links)
        await sim.maybe_silent(telemetry=True)

        async def samples() -> AsyncIterator[str]:
            sent, due = 0, sim.clock.seconds()
            while count is None or sent < count:
                await sim.wait_until(due)
                yield f"event: sample\ndata: {json.dumps(sim.counters(names))}\n\n"
                sent, due = sent + 1, due + period

        return StreamingResponse(samples(), media_type="text/event-stream")

    # Steering the mock

    @app.get("/mock/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "time": iso(sim.clock.now())}

    @app.get("/mock/v1/clock")
    async def clock() -> dict[str, Any]:
        spec = sim.clock.spec
        return {"time": iso(sim.clock.now()), "mode": spec.mode, "scale": spec.scale}

    @app.post("/mock/v1/clock/step")
    async def step(body: dict[str, Any] = Body(...)) -> dict[str, Any]:  # noqa: B008
        try:
            sim.step(parse_duration(str(body.get("by"))).total_seconds())
        except ValueError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        return {"time": iso(sim.clock.now())}

    @app.get("/mock/v1/behaviors")
    async def behaviors() -> dict[str, Any]:
        return {"behaviors": [b.as_json() for b in sim.behaviors]}

    @app.post("/mock/v1/behaviors", status_code=201)
    async def add_behavior(body: dict[str, Any] = Body(...)) -> dict[str, str]:  # noqa: B008
        try:
            spec = BEHAVIOR.validate_python(body)
        except ValidationError as err:
            raise HTTPException(status_code=422, detail=err.errors(include_url=False)) from err
        return {"id": sim.add_behavior(spec)}

    @app.delete("/mock/v1/behaviors/{behavior_id}", status_code=204)
    async def remove_behavior(behavior_id: str) -> Response:
        if not sim.remove_behavior(behavior_id):
            raise HTTPException(status_code=404, detail=f"behavior {behavior_id} not found")
        return Response(status_code=204)

    @app.delete("/mock/v1/behaviors", status_code=204)
    async def clear_behaviors() -> Response:
        sim.clear_behaviors()
        return Response(status_code=204)

    return app
