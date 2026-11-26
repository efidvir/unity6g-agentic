"""The simulated radio links: their configuration, their channel under rain fades, and their counters.

The model is deliberately small. The received level is the transmit power plus the antenna gains, less the
path loss, the attenuation of the fades and a fluctuation of the channel. A link is up while that level stays
above the sensitivity of its modulation profile; a second counts as errored while the margin is under one
decibel or the link is down; the capacity follows the profile and the channel bandwidth. The fluctuation is
drawn per link and per second from the seed, so that a run is reproduced from its configuration."""

import hashlib
import math
import random
from dataclasses import dataclass, field

from u6g_mockctl.config import FadeSpec, LinkSpec, parse_duration

# Profile: (bits per symbol, sensitivity in dBm at 56 MHz). Illustrative values of a microwave radio.
PROFILES: dict[str, tuple[int, float]] = {
    "QPSK": (2, -85.0),
    "16QAM": (4, -79.0),
    "32QAM": (5, -76.0),
    "64QAM": (6, -73.0),
    "128QAM": (7, -70.0),
    "256QAM": (8, -67.0),
    "512QAM": (9, -64.0),
    "1024QAM": (10, -61.0),
}
SYMBOL_RATE_PER_MHZ = 85.0 / (2 * 56.0)  # Mbaud per MHz, so that QPSK carries 85 Mbps in 56 MHz
NOISE_FIGURE_DB = 5.0
BEST_MSE_DB = -38.0
ERRORED_MARGIN_DB = 1.0
FLUCTUATION_DB = 0.5
TX_POWER_RANGE_DBM = (0.0, 30.0)


def noise_floor_dbm(bandwidth_mhz: float) -> float:
    return -174.0 + 10.0 * math.log10(bandwidth_mhz * 1e6) + NOISE_FIGURE_DB


def sensitivity_dbm(profile: str, bandwidth_mhz: float) -> float:
    """The sensitivity of the table, moved with the noise of the bandwidth."""
    return PROFILES[profile][1] + 10.0 * math.log10(bandwidth_mhz / 56.0)


def capacity_mbps(profile: str, bandwidth_mhz: float) -> float:
    return round(PROFILES[profile][0] * SYMBOL_RATE_PER_MHZ * bandwidth_mhz, 1)


@dataclass
class RadioConfig:
    modulation: str
    tx_power_dbm: float


@dataclass
class Counters:
    rsl: float
    mse: float
    modulation: str
    capacity: float
    errored_seconds: int
    link_state: str
    tx_power: float

    def as_json(self, link: str) -> dict[str, object]:
        return {
            "link": link,
            "rsl": self.rsl,
            "mse": self.mse,
            "modulation": self.modulation,
            "capacity": self.capacity,
            "errored-seconds": self.errored_seconds,
            "link-state": self.link_state,
            "tx-power": self.tx_power,
        }


@dataclass
class Fade:
    start: float
    rise: float
    hold: float
    fall: float
    peak_db: float

    @classmethod
    def from_spec(cls, spec: FadeSpec) -> "Fade":
        def s(text: str) -> float:
            return parse_duration(text).total_seconds()

        return cls(
            start=s(spec.start), rise=s(spec.rise), hold=s(spec.hold), fall=s(spec.fall), peak_db=spec.peak_db
        )

    def attenuation(self, t: float) -> float:
        x = t - self.start
        if x <= 0:
            return 0.0
        if x < self.rise:
            return self.peak_db * x / self.rise
        x -= self.rise
        if x < self.hold:
            return self.peak_db
        x -= self.hold
        if x < self.fall:
            return self.peak_db * (1.0 - x / self.fall)
        return 0.0


@dataclass
class RadioLink:
    """One radio link: the configuration in the controller's view, the configuration in the radios, and the
    errored seconds counted so far."""

    spec: LinkSpec
    seed: int
    fades: list[Fade] = field(default_factory=list)
    requested: RadioConfig = field(init=False)
    applied: RadioConfig = field(init=False)
    errored_seconds: int = field(default=0, init=False)
    counted_until: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.requested = RadioConfig(self.spec.modulation, self.spec.tx_power_dbm)
        self.applied = RadioConfig(self.spec.modulation, self.spec.tx_power_dbm)

    def fluctuation(self, second: int) -> float:
        digest = hashlib.sha256(f"{self.seed}/{self.spec.id}/{second}".encode()).digest()
        return random.Random(int.from_bytes(digest[:8], "big")).gauss(0.0, FLUCTUATION_DB)  # noqa: S311

    def rsl(self, t: float) -> float:
        rain = sum(f.attenuation(t) for f in self.fades)
        nominal = self.applied.tx_power_dbm + self.spec.antenna_gain_db - self.spec.path_loss_db
        return nominal - rain + self.fluctuation(math.floor(t))

    def margin(self, t: float) -> float:
        return self.rsl(t) - sensitivity_dbm(self.applied.modulation, self.spec.bandwidth_mhz)

    def advance(self, t: float) -> None:
        """Count the errored seconds up to t with the configuration in force."""
        until = math.floor(t)
        for second in range(self.counted_until, until):
            if self.margin(second + 0.5) < ERRORED_MARGIN_DB:
                self.errored_seconds += 1
        self.counted_until = max(self.counted_until, until)

    def counters(self, t: float) -> Counters:
        self.advance(t)
        rsl = self.rsl(t)
        up = self.margin(t) >= 0.0
        snr = rsl - noise_floor_dbm(self.spec.bandwidth_mhz)
        return Counters(
            rsl=round(rsl, 1),
            mse=round(max(-snr, BEST_MSE_DB), 1),
            modulation=self.applied.modulation,
            capacity=capacity_mbps(self.applied.modulation, self.spec.bandwidth_mhz) if up else 0.0,
            errored_seconds=self.errored_seconds,
            link_state="up" if up else "down",
            tx_power=self.applied.tx_power_dbm,
        )


def check_profile(value: object) -> str:
    if not isinstance(value, str) or value not in PROFILES:
        raise ValueError(f"the profile must be one of {', '.join(PROFILES)}; found {value!r}")
    return value


def check_tx_power(value: object) -> float:
    low, high = TX_POWER_RANGE_DBM
    if isinstance(value, bool) or not isinstance(value, int | float) or not low <= value <= high:
        raise ValueError(f"the transmit power is a number of dBm from {low} to {high}; found {value!r}")
    return float(value)
