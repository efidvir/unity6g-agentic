# The mock controller

Design note of work item 0.7, the transport part. The mock stands in for the transport SDN controller on a
development machine and in the local environment (guide Section 19.9), so that the Monitoring System, the
Actuator and its transaction engine can be tested on every path without a controller or radios.

Run it with `uv run python -m u6g_mockctl --config services/mockctl/u6g_mockctl/topologies/transport-small.yaml`.

## Interfaces

| Path | What it serves | Behaviors |
|---|---|---|
| `GET /tfs-api/devices`, `device_ids`, `device/<uuid>` | Devices with their config rules, endpoints and status, in the JSON of the tfs-api of TeraFlowSDN | silence |
| `PUT /tfs-api/device/<uuid>` | Configuration: the config rules of the body are applied | every behavior |
| `GET /tfs-api/links`, `link_ids`, `link/<uuid>` | Radio links with their two endpoints and capacity | silence |
| `GET /mock/v1/controller/version` | The interface and its version, which the adapter compares with its pinned range | silence, versionChange |
| `GET /mock/v1/telemetry/counters?links=` | The counters of the radio links, polled | silence of scope all |
| `GET /mock/v1/telemetry/stream?interval=&count=&links=` | The same counters as server-sent events, one sample per interval of simulated time | silence of scope all |
| `/mock/v1/behaviors`, `/mock/v1/clock`, `/mock/v1/health` | Steering: add, list and remove behaviors; read or step the clock | none |

The counters carry the metric names of the catalog: `rsl` (dBm), `mse` (dB), `modulation`, `capacity` (Mbps),
`errored-seconds`, `link-state` and `tx-power` (dBm).

## The simulated topology

The configuration file lists the devices (radio units), the radio links between their endpoints, the rain
fades and the behaviors to start with. A link is up while its received level stays above the sensitivity of
its modulation profile; the received level is the transmit power plus the antenna gains, less the path loss,
the fades and a fluctuation drawn per second from the seed. The example topology fades `link-0041` by 25 dB
for ten minutes: 256QAM goes down at the peak, and 64QAM, at 510 Mbps, stays up, which is the case the
link-assurance agent is built for.

A link keeps two configurations: the controller's view, which the device's config rules report, and the
radios', which the counters report. They differ only under acknowledgement without effect, and the
Actuator learns of it through the Monitoring System: the catalog entry of this binding states that the
controller's view does not reflect the device (guide Section 8.3).

The clock runs at a scale of real time, or by hand in tests (`POST /mock/v1/clock/step {"by": "PT30S"}`).

## Behaviors

Each behavior is set in the file or posted at run time, with an explicit `count` of the requests it affects
(a number, or `unlimited`) and, for configuration requests, a `match` on devices and resource keys (`{}` for
every request).

| Kind | Fields | Effect | Path of the transaction engine it exercises |
|---|---|---|---|
| `reject` | `status`, `message` | The request is refused; nothing changes | Rejected outcome |
| `timeout` | `delay`, `applies` | The answer comes after the delay, in real time; with `applies` the change is made at once, without it the late answer is 504 | Unresolved outcome, then read-back finding the change made or not |
| `silence` | `scope` (`api` or `all`) | Requests get no answer until the behavior is removed; then they get 503 | Unresolved outcome with the controller unreachable; a binding fault |
| `versionChange` | `version` | The reported interface version changes | Binding fault; actuation blocked |
| `ackWithoutEffect` | | Acknowledged, and recorded in the controller's view; the radios stay as they were | Acknowledged but unverified |

## Open points

- The config rules of the radio-link parameters follow a convention of the mock:
  `/radio-link[<link>]/modulation-profile` with `{"profile": ...}` and `/radio-link[<link>]/tx-power` with
  `{"powerDbm": ...}`, set through either device of the link. The keys of the real driver replace them when
  the binding of the transport domain settles them (`STATE.md`, questions).
- The tfs-api reports no interface version; how the transport adapter learns the version of a real
  controller is settled with work item 1.7. The mock serves it at `/mock/v1/controller/version`.
- The E2 node simulator for the RAN adapter completes work item 0.7 with the RAN.
