"""The configuration of the mock controller: its interface, clock, simulated topology and behaviors.

Every field is required where it changes what the mock does, so that a run is reproduced from its file alone;
an absent field is refused with a diagnostic (AGENTS.md)."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DURATION = re.compile(
    r"^P(?:(?P<days>[0-9]+)D)?(?:T(?:(?P<hours>[0-9]+)H)?(?:(?P<minutes>[0-9]+)M)?(?:(?P<seconds>[0-9]+(?:\.[0-9]+)?)S)?)?$"
)


def parse_duration(text: str) -> timedelta:
    """An ISO 8601 duration of days, hours, minutes and seconds, for example PT15M or PT0.5S."""
    match = DURATION.match(text)
    if match is None or text in ("P", "PT") or text.endswith("T"):
        raise ValueError(f"{text!r} is not an ISO 8601 duration of days, hours, minutes and seconds")
    parts = {k: float(v) for k, v in match.groupdict().items() if v is not None}
    return timedelta(**parts)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class ControllerSpec(Strict):
    interface: str = Field(
        description="The interface the mock models, as the binding of the catalog names it"
    )
    version: str = Field(description="The interface version it reports until a behavior changes it")


class ClockSpec(Strict):
    epoch: datetime = Field(description="The simulated time at start")
    mode: Literal["realTime", "manual"]
    scale: float = Field(gt=0, description="Simulated seconds per real second, in realTime mode")

    @field_validator("epoch")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("the epoch is an instant in UTC")
        return value.astimezone(UTC)


class DeviceSpec(Strict):
    id: str
    site: str
    endpoints: list[str] = Field(min_length=1)


class EndpointRef(Strict):
    device: str
    endpoint: str


class LinkSpec(Strict):
    id: str
    a: EndpointRef
    b: EndpointRef
    bandwidth_mhz: float = Field(alias="bandwidthMhz", gt=0)
    path_loss_db: float = Field(alias="pathLossDb", gt=0)
    antenna_gain_db: float = Field(alias="antennaGainDb", ge=0, description="Both antennas together")
    modulation: str
    tx_power_dbm: float = Field(alias="txPowerDbm")


class FadeSpec(Strict):
    """A rain fade on one link: the attenuation rises to its peak, holds, and falls back."""

    link: str
    start: str
    rise: str
    hold: str
    fall: str
    peak_db: float = Field(alias="peakDb", gt=0)

    @field_validator("start", "rise", "hold", "fall")
    @classmethod
    def duration(cls, value: str) -> str:
        parse_duration(value)
        return value


class Match(Strict):
    """Which configuration requests a behavior affects: every one, or those naming these devices or keys."""

    devices: list[str] | None = None
    resource_keys: list[str] | None = Field(default=None, alias="resourceKeys")


Count = int | Literal["unlimited"]


class RejectSpec(Strict):
    kind: Literal["reject"]
    match: Match
    count: Count
    status: int = Field(ge=400, le=599)
    message: str


class TimeoutSpec(Strict):
    """The controller answers after the delay, in real time; with applies, it makes the change at once."""

    kind: Literal["timeout"]
    match: Match
    count: Count
    delay: str
    applies: bool

    @field_validator("delay")
    @classmethod
    def duration(cls, value: str) -> str:
        parse_duration(value)
        return value


class SilenceSpec(Strict):
    """The controller stops answering until the behavior is removed: its interface, or its telemetry too."""

    kind: Literal["silence"]
    count: Count
    scope: Literal["api", "all"]


class VersionChangeSpec(Strict):
    kind: Literal["versionChange"]
    count: Count
    version: str


class AckWithoutEffectSpec(Strict):
    """The controller acknowledges and records the change in its own view; the radios stay as they were."""

    kind: Literal["ackWithoutEffect"]
    match: Match
    count: Count


BehaviorSpec = Annotated[
    RejectSpec | TimeoutSpec | SilenceSpec | VersionChangeSpec | AckWithoutEffectSpec,
    Field(discriminator="kind"),
]


class MockConfig(Strict):
    controller: ControllerSpec
    clock: ClockSpec
    seed: int
    devices: list[DeviceSpec] = Field(min_length=1)
    links: list[LinkSpec] = Field(min_length=1)
    fades: list[FadeSpec]
    behaviors: list[BehaviorSpec]

    @model_validator(mode="after")
    def references(self) -> "MockConfig":
        devices = {d.id: set(d.endpoints) for d in self.devices}
        if len(devices) != len(self.devices):
            raise ValueError("device identities are unique")
        links = [link.id for link in self.links]
        if len(set(links)) != len(links):
            raise ValueError("link identities are unique")
        for link in self.links:
            for end in (link.a, link.b):
                if end.endpoint not in devices.get(end.device, set()):
                    raise ValueError(f"{link.id}: no endpoint {end.endpoint} on device {end.device}")
        for fade in self.fades:
            if fade.link not in links:
                raise ValueError(f"fade on unknown link {fade.link}")
        return self


def load_config(path: Path) -> MockConfig:
    return MockConfig.model_validate(yaml.safe_load(path.read_text()))
