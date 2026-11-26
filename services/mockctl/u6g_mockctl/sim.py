"""The state of the mock controller: the simulated clock, the radio links, the devices and the behaviors."""

import asyncio
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from u6g_mockctl.config import (
    AckWithoutEffectSpec,
    BehaviorSpec,
    ClockSpec,
    Match,
    MockConfig,
    RejectSpec,
    SilenceSpec,
    TimeoutSpec,
    VersionChangeSpec,
    parse_duration,
)
from u6g_mockctl.radio import Fade, RadioLink, capacity_mbps, check_profile, check_tx_power

RESOURCE_KEY = re.compile(r"^/radio-link\[(?P<link>[^\]]+)\]/(?P<param>modulation-profile|tx-power)$")
"""The configuration rules of a radio link, set through either of its devices. A convention of the mock until
the binding of the transport domain settles the keys of the real driver (STATE.md, questions)."""

DEVICE_TYPE = "microwave-radio-system"
PARAMS = {"modulation": "modulation-profile", "tx_power_dbm": "tx-power"}


def iso(instant: datetime) -> str:
    return instant.isoformat().replace("+00:00", "Z")


class SimClock:
    """Simulated time: the epoch plus the seconds elapsed, at a scale of real time or stepped by hand."""

    def __init__(self, spec: ClockSpec) -> None:
        self.spec = spec
        self._offset = 0.0
        self._started = time.monotonic()

    def seconds(self) -> float:
        if self.spec.mode == "manual":
            return self._offset
        return (time.monotonic() - self._started) * self.spec.scale

    def now(self) -> datetime:
        return self.spec.epoch + timedelta(seconds=self.seconds())

    def step(self, seconds: float) -> None:
        if self.spec.mode != "manual":
            raise ValueError("the clock runs in realTime mode; only a manual clock is stepped")
        self._offset += seconds


@dataclass
class Active:
    id: str
    spec: BehaviorSpec
    remaining: int | None
    released: asyncio.Event = field(default_factory=asyncio.Event)

    def as_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "spec": self.spec.model_dump(mode="json", by_alias=True, exclude_none=True),
            "remaining": "unlimited" if self.remaining is None else self.remaining,
        }


def matches(match: Match, device: str, keys: list[str]) -> bool:
    if match.devices is not None and device not in match.devices:
        return False
    return match.resource_keys is None or any(key in match.resource_keys for key in keys)


class ConfigurationError(ValueError):
    """A configuration request the mock refuses, as a controller refuses a malformed request."""


@dataclass
class Change:
    link: str
    param: str
    value: Any


class Simulation:
    def __init__(self, config: MockConfig) -> None:
        self.config = config
        self.clock = SimClock(config.clock)
        self.devices = {d.id: d for d in config.devices}
        self.links: dict[str, RadioLink] = {}
        for spec in config.links:
            fades = [Fade.from_spec(f) for f in config.fades if f.link == spec.id]
            self.links[spec.id] = RadioLink(spec=spec, seed=config.seed, fades=fades)
        self.behaviors: list[Active] = []
        self.ticked = asyncio.Event()
        self._next = 0
        for behavior in config.behaviors:
            self.add_behavior(behavior)

    # Behaviors

    def add_behavior(self, spec: BehaviorSpec) -> str:
        self._next += 1
        remaining = None if spec.count == "unlimited" else spec.count
        active = Active(id=f"b{self._next}", spec=spec, remaining=remaining)
        self.behaviors.append(active)
        return active.id

    def remove_behavior(self, behavior_id: str) -> bool:
        for active in list(self.behaviors):
            if active.id == behavior_id:
                self.behaviors.remove(active)
                active.released.set()
                return True
        return False

    def clear_behaviors(self) -> None:
        for active in list(self.behaviors):
            self.remove_behavior(active.id)

    def take[S](self, kind: type[S], accept: Callable[[S], bool]) -> tuple[Active, S] | None:
        """The first behavior of the kind that accepts the request and has requests left, consuming one."""
        for active in self.behaviors:
            spec = active.spec
            if isinstance(spec, kind) and active.remaining != 0 and accept(spec):
                if active.remaining is not None:
                    active.remaining -= 1
                return active, spec
        return None

    async def maybe_silent(self, telemetry: bool) -> None:
        """Hold a request while a silence captures it; a removed silence answers it as unavailable."""
        found = self.take(SilenceSpec, lambda s: s.scope == "all" or not telemetry)
        if found is not None:
            await found[0].released.wait()
            raise Unavailable("the controller was silent")

    def step(self, seconds: float) -> None:
        self.clock.step(seconds)
        self.ticked.set()

    async def wait_until(self, due: float) -> None:
        """Until the simulated clock reaches due, while no silence of the telemetry is in force."""
        while True:
            silent = self.silent_now()
            if silent is not None:
                await silent.released.wait()
                continue
            remaining = due - self.clock.seconds()
            if remaining <= 0:
                return
            if self.clock.spec.mode == "realTime":
                await asyncio.sleep(remaining / self.clock.spec.scale)
            else:
                self.ticked.clear()
                await self.ticked.wait()

    def silent_now(self) -> Active | None:
        for active in self.behaviors:
            if isinstance(active.spec, SilenceSpec) and active.spec.scope == "all" and active.remaining != 0:
                return active
        return None

    # The controller's interface

    def version(self) -> dict[str, str]:
        changed = self.take(VersionChangeSpec, lambda _s: True)
        version = changed[1].version if changed is not None else self.config.controller.version
        return {"interface": self.config.controller.interface, "version": version}

    def links_of(self, device: str) -> list[RadioLink]:
        return [link for link in self.links.values() if device in (link.spec.a.device, link.spec.b.device)]

    def device_json(self, device: str) -> dict[str, Any]:
        spec = self.devices[device]
        device_id = {"device_uuid": {"uuid": spec.id}}
        rules = []
        for link in self.links_of(device):
            values = {
                "modulation-profile": {"profile": link.requested.modulation},
                "tx-power": {"powerDbm": link.requested.tx_power_dbm},
            }
            for param, value in values.items():
                rules.append(
                    {
                        "action": "CONFIGACTION_SET",
                        "custom": {
                            "resource_key": f"/radio-link[{link.spec.id}]/{param}",
                            "resource_value": json.dumps(value),
                        },
                    }
                )
        return {
            "device_id": device_id,
            "name": spec.id,
            "device_type": DEVICE_TYPE,
            "device_config": {"config_rules": rules},
            "device_operational_status": "DEVICEOPERATIONALSTATUS_ENABLED",
            "device_drivers": ["DEVICEDRIVER_UNDEFINED"],
            "device_endpoints": [
                {
                    "endpoint_id": {"device_id": device_id, "endpoint_uuid": {"uuid": endpoint}},
                    "endpoint_type": "radio",
                    "kpi_sample_types": [],
                }
                for endpoint in spec.endpoints
            ],
            "components": [],
        }

    def link_json(self, link_id: str) -> dict[str, Any]:
        link = self.links[link_id]
        ends = [
            {"device_id": {"device_uuid": {"uuid": end.device}}, "endpoint_uuid": {"uuid": end.endpoint}}
            for end in (link.spec.a, link.spec.b)
        ]
        nominal = capacity_mbps(link.applied.modulation, link.spec.bandwidth_mhz)
        return {
            "link_id": {"link_uuid": {"uuid": link_id}},
            "name": link_id,
            "link_endpoint_ids": ends,
            "attributes": {"total_capacity_gbps": round(nominal / 1000.0, 4), "used_capacity_gbps": 0.0},
        }

    def parse_changes(self, device: str, body: dict[str, Any]) -> list[Change]:
        uuid = body.get("device_id", {}).get("device_uuid", {}).get("uuid")
        if uuid != device:
            raise ConfigurationError(f"the device_id of the body ({uuid!r}) is not the device of the path")
        rules = body.get("device_config", {}).get("config_rules")
        if not isinstance(rules, list) or not rules:
            raise ConfigurationError("the request carries no config_rules")
        own = {link.spec.id for link in self.links_of(device)}
        changes = []
        for i, rule in enumerate(rules):
            if rule.get("action") != "CONFIGACTION_SET":
                raise ConfigurationError(f"config_rules[{i}]: only CONFIGACTION_SET is supported by the mock")
            custom = rule.get("custom") or {}
            key, raw = custom.get("resource_key"), custom.get("resource_value")
            found = RESOURCE_KEY.match(key) if isinstance(key, str) else None
            if found is None:
                raise ConfigurationError(f"config_rules[{i}]: unknown resource_key {key!r}")
            if found["link"] not in own:
                raise ConfigurationError(
                    f"config_rules[{i}]: the device {device} is not an end of {found['link']}"
                )
            try:
                value = json.loads(raw) if isinstance(raw, str) else None
            except json.JSONDecodeError as err:
                raise ConfigurationError(f"config_rules[{i}]: resource_value is not JSON: {err}") from err
            if not isinstance(value, dict):
                raise ConfigurationError(f"config_rules[{i}]: resource_value is a JSON object in a string")
            try:
                if found["param"] == "modulation-profile":
                    changes.append(Change(found["link"], "modulation", check_profile(value.get("profile"))))
                else:
                    changes.append(
                        Change(found["link"], "tx_power_dbm", check_tx_power(value.get("powerDbm")))
                    )
            except ValueError as err:
                raise ConfigurationError(f"config_rules[{i}]: {err}") from err
        return changes

    def apply(self, changes: list[Change], radios: bool) -> None:
        """Record the changes in the controller's view, and in the radios unless they stay unchanged."""
        t = self.clock.seconds()
        for change in changes:
            link = self.links[change.link]
            link.advance(t)
            setattr(link.requested, change.param, change.value)
            if radios:
                setattr(link.applied, change.param, change.value)

    async def configure(self, device: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """A configuration request, answered as the behaviors in force decide."""
        changes = self.parse_changes(device, body)
        keys = [f"/radio-link[{c.link}]/{PARAMS[c.param]}" for c in changes]

        def hit(spec: Any) -> bool:
            return matches(spec.match, device, keys)

        reply = {"device_uuid": {"uuid": device}}
        rejected = self.take(RejectSpec, hit)
        if rejected is not None:
            reject = rejected[1]
            return reject.status, {"message": reject.message}
        delayed = self.take(TimeoutSpec, hit)
        if delayed is not None:
            timeout = delayed[1]
            if timeout.applies:
                self.apply(changes, radios=True)
            await asyncio.sleep(parse_duration(timeout.delay).total_seconds())
            if timeout.applies:
                return 200, reply
            return 504, {"message": "the controller timed out"}
        unapplied = self.take(AckWithoutEffectSpec, hit)
        self.apply(changes, radios=unapplied is None)
        return 200, reply

    def counters(self, links: list[str]) -> dict[str, Any]:
        t = self.clock.seconds()
        return {
            "time": iso(self.clock.now()),
            "links": [self.links[link].counters(t).as_json(link) for link in links],
        }


class Unavailable(Exception):
    """The controller gives no useful answer."""
