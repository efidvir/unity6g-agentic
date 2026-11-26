"""Work item 0.7, the transport part: the mock controller answers as a controller does; rejection,
timeout, silence, a change of interface version and acknowledgement without effect are each reproducible
by configuration."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml
from pydantic import ValidationError
from u6g_mockctl.app import create_app
from u6g_mockctl.config import MockConfig, load_config

TOPOLOGY = (
    Path(__file__).resolve().parents[1] / "services/mockctl/u6g_mockctl/topologies/transport-small.yaml"
)


def config(
    behaviors: list[dict[str, Any]] | None = None, mode: str = "manual", scale: float = 1.0
) -> MockConfig:
    data = yaml.safe_load(TOPOLOGY.read_text())
    data["clock"]["mode"] = mode
    data["clock"]["scale"] = scale
    data["behaviors"] = behaviors or []
    return MockConfig.model_validate(data)


Scenario = Callable[[httpx.AsyncClient], Awaitable[None]]


def run(scenario: Scenario, cfg: MockConfig | None = None) -> None:
    async def main() -> None:
        transport = httpx.ASGITransport(app=create_app(cfg or config()))
        async with httpx.AsyncClient(transport=transport, base_url="http://mockctl") as client:
            await scenario(client)

    asyncio.run(main())


def modulation_rule(link: str, profile: str) -> dict[str, Any]:
    return {
        "action": "CONFIGACTION_SET",
        "custom": {
            "resource_key": f"/radio-link[{link}]/modulation-profile",
            "resource_value": json.dumps({"profile": profile}),
        },
    }


def device_body(device: str, *rules: dict[str, Any]) -> dict[str, Any]:
    return {"device_id": {"device_uuid": {"uuid": device}}, "device_config": {"config_rules": list(rules)}}


async def put_modulation(client: httpx.AsyncClient, device: str, link: str, profile: str) -> httpx.Response:
    return await client.put(
        f"/tfs-api/device/{device}", json=device_body(device, modulation_rule(link, profile))
    )


async def requested(client: httpx.AsyncClient, device: str, link: str) -> str:
    body = (await client.get(f"/tfs-api/device/{device}")).json()
    for rule in body["device_config"]["config_rules"]:
        if rule["custom"]["resource_key"] == f"/radio-link[{link}]/modulation-profile":
            profile: str = json.loads(rule["custom"]["resource_value"])["profile"]
            return profile
    raise AssertionError(f"no modulation rule for {link} on {device}")


async def counters(client: httpx.AsyncClient, link: str) -> dict[str, Any]:
    body = (await client.get("/mock/v1/telemetry/counters", params={"links": link})).json()
    sample: dict[str, Any] = body["links"][0]
    return sample


async def step(client: httpx.AsyncClient, by: str) -> None:
    assert (await client.post("/mock/v1/clock/step", json={"by": by})).status_code == 200


# The controller's interface


def test_devices_and_links_read_as_the_tfs_api_writes_them() -> None:
    async def scenario(client: httpx.AsyncClient) -> None:
        devices = (await client.get("/tfs-api/devices")).json()["devices"]
        assert [d["device_id"]["device_uuid"]["uuid"] for d in devices] == [
            "mw-north-1",
            "mw-north-2",
            "mw-north-3",
            "mw-south-1",
        ]
        assert {d["device_type"] for d in devices} == {"microwave-radio-system"}
        assert await requested(client, "mw-north-1", "link-0041") == "256QAM"
        links = (await client.get("/tfs-api/links")).json()["links"]
        assert [link["link_id"]["link_uuid"]["uuid"] for link in links] == [
            "link-0041",
            "link-0042",
            "link-0057",
        ]
        ends = links[0]["link_endpoint_ids"]
        assert [e["device_id"]["device_uuid"]["uuid"] for e in ends] == ["mw-north-1", "mw-north-2"]
        missing = await client.get("/tfs-api/device/mw-west-9")
        assert missing.status_code == 404
        assert "not found" in missing.json()["message"]
        version = (await client.get("/mock/v1/controller/version")).json()
        assert version == {"interface": "tfs-nbi", "version": "7.0"}

    run(scenario)


def test_a_configuration_reaches_the_controller_view_and_the_radios() -> None:
    async def scenario(client: httpx.AsyncClient) -> None:
        reply = await put_modulation(client, "mw-north-2", "link-0041", "64QAM")
        assert reply.status_code == 200
        assert reply.json() == {"device_uuid": {"uuid": "mw-north-2"}}
        assert await requested(client, "mw-north-1", "link-0041") == "64QAM"
        sample = await counters(client, "link-0041")
        assert (sample["modulation"], sample["capacity"], sample["link-state"]) == ("64QAM", 510.0, "up")

    run(scenario)


@pytest.mark.parametrize(
    ("device", "rule", "message"),
    [
        ("mw-north-1", modulation_rule("link-0041", "8QAM"), "profile"),
        ("mw-north-1", modulation_rule("link-0057", "64QAM"), "not an end"),
        (
            "mw-north-1",
            {"action": "CONFIGACTION_DELETE", "custom": modulation_rule("link-0041", "QPSK")["custom"]},
            "only",
        ),
        (
            "mw-north-1",
            {"action": "CONFIGACTION_SET", "custom": {"resource_key": "/fan/speed", "resource_value": "{}"}},
            "unknown",
        ),
        (
            "mw-north-1",
            {
                "action": "CONFIGACTION_SET",
                "custom": {
                    "resource_key": "/radio-link[link-0041]/tx-power",
                    "resource_value": '{"powerDbm": 40}',
                },
            },
            "transmit power",
        ),
    ],
)
def test_a_malformed_configuration_is_refused_and_changes_nothing(
    device: str, rule: dict[str, Any], message: str
) -> None:
    async def scenario(client: httpx.AsyncClient) -> None:
        reply = await client.put(f"/tfs-api/device/{device}", json=device_body(device, rule))
        assert reply.status_code == 400
        assert message in reply.json()["message"]
        assert await requested(client, "mw-north-1", "link-0041") == "256QAM"
        assert (await counters(client, "link-0041"))["modulation"] == "256QAM"

    run(scenario)


def test_the_body_names_the_device_of_the_path() -> None:
    async def scenario(client: httpx.AsyncClient) -> None:
        body = device_body("mw-north-2", modulation_rule("link-0041", "64QAM"))
        reply = await client.put("/tfs-api/device/mw-north-1", json=body)
        assert reply.status_code == 400

    run(scenario)


# The simulated channel


def test_a_downshift_before_the_fade_keeps_the_link_up() -> None:
    """The story of the link-assurance agent: 256QAM goes down at the peak of the fade, 64QAM stays up."""

    async def held(client: httpx.AsyncClient) -> None:
        await step(client, "PT3M")
        assert (await put_modulation(client, "mw-north-1", "link-0041", "64QAM")).status_code == 200
        await step(client, "PT7M")
        sample = await counters(client, "link-0041")
        assert (sample["link-state"], sample["capacity"]) == ("up", 510.0)
        assert sample["rsl"] < -60

    async def left(client: httpx.AsyncClient) -> None:
        await step(client, "PT10M")
        sample = await counters(client, "link-0041")
        assert (sample["link-state"], sample["capacity"]) == ("down", 0.0)
        assert sample["errored-seconds"] > 60

    run(held)
    run(left)


def test_the_channel_is_reproduced_from_the_seed() -> None:
    samples: list[dict[str, Any]] = []

    async def scenario(client: httpx.AsyncClient) -> None:
        await step(client, "PT9M")
        samples.append(await counters(client, "link-0041"))

    run(scenario)
    run(scenario)
    assert samples[0] == samples[1]


# The behaviors


def test_rejection_by_configuration() -> None:
    reject = {"kind": "reject", "match": {}, "count": 1, "status": 503, "message": "driver unavailable"}

    async def scenario(client: httpx.AsyncClient) -> None:
        refused = await put_modulation(client, "mw-north-1", "link-0041", "64QAM")
        assert (refused.status_code, refused.json()) == (503, {"message": "driver unavailable"})
        assert await requested(client, "mw-north-1", "link-0041") == "256QAM"
        assert (await put_modulation(client, "mw-north-1", "link-0041", "64QAM")).status_code == 200

    run(scenario, config([reject]))


def test_a_behavior_matches_only_the_requests_it_names() -> None:
    reject = {
        "kind": "reject",
        "match": {"devices": ["mw-north-3"]},
        "count": "unlimited",
        "status": 409,
        "message": "locked",
    }

    async def scenario(client: httpx.AsyncClient) -> None:
        assert (await put_modulation(client, "mw-north-1", "link-0041", "64QAM")).status_code == 200
        assert (await put_modulation(client, "mw-north-3", "link-0042", "64QAM")).status_code == 409

    run(scenario, config([reject]))


def test_timeout_with_the_change_carried_out() -> None:
    timeout = {"kind": "timeout", "match": {}, "count": 1, "delay": "PT0.3S", "applies": True}

    async def scenario(client: httpx.AsyncClient) -> None:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(put_modulation(client, "mw-north-1", "link-0041", "64QAM"), 0.1)
        assert await requested(client, "mw-north-1", "link-0041") == "64QAM", "read-back finds the change"
        assert (await counters(client, "link-0041"))["modulation"] == "64QAM"

    run(scenario, config([timeout]))


def test_timeout_without_the_change() -> None:
    timeout = {"kind": "timeout", "match": {}, "count": 1, "delay": "PT0.2S", "applies": False}

    async def scenario(client: httpx.AsyncClient) -> None:
        late = await put_modulation(client, "mw-north-1", "link-0041", "64QAM")
        assert late.status_code == 504
        assert await requested(client, "mw-north-1", "link-0041") == "256QAM"

    run(scenario, config([timeout]))


def test_silence_until_removed() -> None:
    async def scenario(client: httpx.AsyncClient) -> None:
        added = await client.post(
            "/mock/v1/behaviors", json={"kind": "silence", "count": "unlimited", "scope": "api"}
        )
        assert added.status_code == 201
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(client.get("/tfs-api/devices"), 0.1)
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(client.get("/mock/v1/controller/version"), 0.1)
        assert (await client.get("/mock/v1/health")).status_code == 200, "the mock itself stays steerable"
        assert (await client.get("/mock/v1/telemetry/counters")).status_code == 200, (
            "scope api spares telemetry"
        )
        pending = asyncio.ensure_future(client.get("/tfs-api/device/mw-north-1"))
        await asyncio.sleep(0.05)
        assert not pending.done()
        assert (await client.delete(f"/mock/v1/behaviors/{added.json()['id']}")).status_code == 204
        assert (await pending).status_code == 503, "a request held through the silence gets no useful answer"
        assert (await client.get("/tfs-api/devices")).status_code == 200

    run(scenario)


def test_silence_of_the_telemetry_too() -> None:
    async def scenario(client: httpx.AsyncClient) -> None:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(client.get("/mock/v1/telemetry/counters"), 0.1)

    run(scenario, config([{"kind": "silence", "count": "unlimited", "scope": "all"}]))


def test_change_of_interface_version() -> None:
    async def scenario(client: httpx.AsyncClient) -> None:
        assert (await client.get("/mock/v1/controller/version")).json()["version"] == "8.0"
        listed = (await client.get("/mock/v1/behaviors")).json()["behaviors"]
        assert [b["spec"]["kind"] for b in listed] == ["versionChange"]
        assert (await client.delete("/mock/v1/behaviors")).status_code == 204
        assert (await client.get("/mock/v1/controller/version")).json()["version"] == "7.0"

    run(scenario, config([{"kind": "versionChange", "count": "unlimited", "version": "8.0"}]))


def test_acknowledgement_without_effect() -> None:
    async def scenario(client: httpx.AsyncClient) -> None:
        assert (await put_modulation(client, "mw-north-1", "link-0041", "64QAM")).status_code == 200
        assert await requested(client, "mw-north-1", "link-0041") == "64QAM", "the controller's view changed"
        sample = await counters(client, "link-0041")
        assert (sample["modulation"], sample["capacity"]) == ("256QAM", 680.0), "the radios did not"

    run(scenario, config([{"kind": "ackWithoutEffect", "match": {}, "count": 1}]))


# Telemetry, clock and configuration


def test_the_stream_sends_samples_at_the_interval() -> None:
    async def scenario(client: httpx.AsyncClient) -> None:
        reply = await client.get(
            "/mock/v1/telemetry/stream", params={"interval": "PT5S", "count": 3, "links": "link-0041"}
        )
        assert reply.headers["content-type"].startswith("text/event-stream")
        events = [
            json.loads(line[len("data: ") :]) for line in reply.text.splitlines() if line.startswith("data: ")
        ]
        assert len(events) == 3
        assert all(e["links"][0]["link"] == "link-0041" for e in events)
        times = [e["time"] for e in events]
        assert times == sorted(times)

    run(scenario, config(mode="realTime", scale=500.0))


def test_a_realtime_clock_is_not_stepped() -> None:
    async def scenario(client: httpx.AsyncClient) -> None:
        assert (await client.post("/mock/v1/clock/step", json={"by": "PT1M"})).status_code == 409

    run(scenario, config(mode="realTime"))


def test_a_behavior_without_its_count_is_refused() -> None:
    async def scenario(client: httpx.AsyncClient) -> None:
        reply = await client.post("/mock/v1/behaviors", json={"kind": "versionChange", "version": "8.0"})
        assert reply.status_code == 422

    run(scenario)


def test_the_configuration_is_checked_on_load() -> None:
    assert load_config(TOPOLOGY).controller.version == "7.0"
    data = yaml.safe_load(TOPOLOGY.read_text())
    data["links"][0]["a"]["endpoint"] = "rf9"
    with pytest.raises(ValidationError, match="no endpoint rf9"):
        MockConfig.model_validate(data)
    data = yaml.safe_load(TOPOLOGY.read_text())
    data["seedling"] = 1
    with pytest.raises(ValidationError):
        MockConfig.model_validate(data)
