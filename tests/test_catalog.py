"""Work item 0.4: the type catalog builds into an index and a signed snapshot that verifies, the entries of
guide Table 17-1 resolve, and so does every catalog reference of the guide's examples."""

import asyncio
import json
import re
import shutil
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml
from u6g_catalog.app import create_app
from u6g_catalog.build import Catalog, build_index, load, parse_ref
from u6g_catalog.snapshot import archive, keygen, sign, verify

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog"
EXAMPLES = ROOT / "examples" / "contracts"

# Guide Table 17-1, the principal entries of the transport domain, row by row.
TABLE_17_1 = {
    "object classes": [
        "mw-link",
        "mw-radio",
        "eth-port",
        "path",
        "l2vpn-service",
        "l3vpn-service",
        "network-slice",
        "site",
    ],
    "metrics": [
        "transport/metric/rsl",
        "transport/metric/mse",
        "transport/metric/modulation",
        "transport/metric/capacity",
        "transport/metric/errored-seconds",
        "transport/metric/severely-errored-seconds",
        "transport/metric/utilization",
        "transport/metric/one-way-delay",
        "transport/metric/delay-variation",
        "transport/metric/packet-loss",
        "transport/metric/slice-slo-compliance",
        "kpi/link-availability",
    ],
    "control parameters": [
        "transport/param/modulation-min",
        "transport/param/modulation-max",
        "transport/param/tx-power",
        "transport/param/channel",
        "transport/param/bandwidth",
        "transport/param/service-path",
        "transport/param/slice-capacity",
        "transport/param/protection-state",
    ],
    "action types": [
        "transport/action/set-modulation-profile",
        "transport/action/set-modulation-limits",
        "transport/action/set-tx-power",
        "transport/action/move-service-path",
        "transport/action/resize-slice",
        "transport/action/switch-protection",
    ],
    "source kinds": [
        "transport/source/sdn-telemetry",
        "transport/source/radio-counters",
        "transport/source/gnmi-stream",
        "transport/source/netconf-state",
        "transport/source/restconf-state",
        "transport/source/snmp",
        "transport/source/twamp-light",
        "transport/source/context-broker",
    ],
    "controller bindings": ["transport/binding/tfs-nbi", "transport/binding/intent-engine"],
    "verification methods": [
        "platform/verification/ms-observation",
        "platform/verification/controller-query",
    ],
}


@pytest.fixture(scope="module")
def built() -> tuple[Catalog, dict[str, Any]]:
    catalog = load(CATALOG)
    return catalog, build_index(catalog)


def test_the_catalog_builds_without_findings(built: tuple[Catalog, dict[str, Any]]) -> None:
    catalog, index = built
    assert catalog.findings == []
    assert set(index["areas"]) == {"transport", "platform", "kpi"}
    kinds = {e["kind"] for e in index["entries"].values()}
    assert len(kinds) == 10, "every kind of [FW] Section 3.6 has entries"


@pytest.mark.parametrize("row", sorted(TABLE_17_1))
def test_the_entries_of_table_17_1_resolve(built: tuple[Catalog, dict[str, Any]], row: str) -> None:
    _, index = built
    if row == "object classes":
        assert set(TABLE_17_1[row]) <= set(index["areas"]["transport"]["objectClasses"])
        return
    missing = [ident for ident in TABLE_17_1[row] if ident not in index["latest"]]
    assert missing == []


def references(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [r for v in value.values() for r in references(v)]
    if isinstance(value, list):
        return [r for v in value for r in references(v)]
    if isinstance(value, str) and (
        value.startswith("catalog://") or re.fullmatch(r"[a-z]+/[a-z]+/[a-z0-9-]+@[0-9.]+", value)
    ):
        return [value]
    return []


def test_every_reference_of_the_examples_resolves(built: tuple[Catalog, dict[str, Any]]) -> None:
    _, index = built
    found: list[str] = []
    codes: list[str] = []
    for path in sorted(EXAMPLES.rglob("*.*")):
        if path.suffix not in (".json", ".yaml"):
            continue
        data = yaml.safe_load(path.read_text())
        found += references(data)
        text = path.read_text()
        codes += re.findall(r"\b(?:DEC|ACT|FAB)-[A-Z0-9-]+\b", text)
    assert len(set(found)) >= 20
    unresolved = [
        ref
        for ref in sorted(set(found))
        if "{}@{}".format(*parse_ref(ref) or ("?", "?")) not in index["entries"]
    ]
    assert unresolved == []
    assert sorted(set(codes) - set(index["reasonCodes"])) == []


# The checks of the build


def mutated(tmp_path: Path, relative: str, change: Any) -> Catalog:
    copy = tmp_path / "catalog"
    shutil.copytree(CATALOG, copy)
    path = copy / relative
    data = yaml.safe_load(path.read_text())
    change(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return load(copy)


@pytest.mark.parametrize(
    ("relative", "change", "rule"),
    [
        (
            "transport/metric/rsl/1.2.0.yaml",
            lambda d: d.update(sources=["transport/source/carrier-pigeon@1.0.0"]),
            "reference",
        ),
        (
            "transport/metric/rsl/1.2.0.yaml",
            lambda d: d.update(sources=["transport/metric/mse@1.0.0"]),
            "reference",
        ),
        ("transport/metric/rsl/1.2.0.yaml", lambda d: d.update(version="1.3.0"), "identity"),
        ("transport/metric/rsl/1.2.0.yaml", lambda d: d.pop("unit", None) or d.pop("definition"), "schema"),
        ("transport/metric/rsl/1.2.0.yaml", lambda d: d.update(objectClass="mw-antenna"), "area"),
        ("transport/metric/rsl/1.2.0.yaml", lambda d: d.update(owner="framework"), "area"),
        (
            "transport/action/set-tx-power/1.0.0.yaml",
            lambda d: d["controllerBindings"][0].update(operations=["device.reboot"]),
            "consistency",
        ),
        (
            "transport/action/set-tx-power/1.0.0.yaml",
            lambda d: d["verification"][0]["predicate"]["eq"].update(param="power"),
            "consistency",
        ),
        (
            "transport/binding/intent-engine/1.0.0.yaml",
            lambda d: d["actionTypes"].append("transport/action/set-tx-power@1.0.0"),
            "consistency",
        ),
        (
            "transport/param/tx-power/1.0.0.yaml",
            lambda d: d.update(readBack={"method": "controllerQuery"}),
            "consistency",
        ),
        ("platform/reason/act-ok/1.0.0.yaml", lambda d: d.update(code="ACT-REJECTED"), "consistency"),
        ("platform/reason/act-ok/1.0.0.yaml", lambda d: d.pop("provenance"), "schema"),
        (  # a KPI sample type TeraFlowSDN does not declare
            "transport/metric/rsl/1.2.0.yaml",
            lambda d: d["teraflowsdn"].update(kpiSampleType="KPISAMPLETYPE_RADIO_RAIN_RATE"),
            "consistency",
        ),
        (  # a driver TeraFlowSDN does not declare
            "transport/param/tx-power/1.0.0.yaml",
            lambda d: d["teraflowsdn"].update(deviceDriver="DEVICEDRIVER_PIGEON"),
            "consistency",
        ),
        (  # verified on a product the driver does not mark as checked on a real device
            "transport/metric/rsl/1.2.0.yaml",
            lambda d: d["hardware"].update(verifiedOn=["IP-50C"]),
            "consistency",
        ),
        (  # provisional on a product the portfolio does not know
            "transport/metric/rsl/1.2.0.yaml",
            lambda d: d["hardware"].update(provisionalOn=["Brand X"]),
            "consistency",
        ),
        (  # verified while products remain to check
            "transport/metric/rsl/1.2.0.yaml",
            lambda d: d["hardware"].update(status="verified", verifiedOn=["MH-T261"]),
            "consistency",
        ),
        (  # provisional with nothing left to check
            "transport/metric/mse/1.0.0.yaml",
            lambda d: d["hardware"].update(provisionalOn=[]),
            "consistency",
        ),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_the_build_reports_each_breach(tmp_path: Path, relative: str, change: Any, rule: str) -> None:
    catalog = mutated(tmp_path, relative, change)
    assert rule in [f.rule for f in catalog.findings], catalog.findings


def test_an_entry_verified_on_the_checked_product_builds(tmp_path: Path) -> None:
    catalog = mutated(
        tmp_path,
        "transport/metric/mcs-tx/1.0.0.yaml",
        lambda d: d["hardware"].update(status="verified", verifiedOn=["MH-T261"], provisionalOn=[]),
    )
    assert catalog.findings == []


# What TeraFlowSDN declares, read from its sources


def write_tree(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


TFS_TREE = {
    "proto/kpi_sample_types.proto": """syntax = "proto3";
enum KpiSampleType {
    KPISAMPLETYPE_UNKNOWN = 0;
    KPISAMPLETYPE_BYTES_RECEIVED = 202;
    KPISAMPLETYPE_ML_CONFIDENCE = 401;  //. can be used by both optical and L3
    KPISAMPLETYPE_RADIO_RX_LEVEL_DBM = 801;  // received signal level
}
""",
    "proto/context.proto": """syntax = "proto3";
enum DeviceDriverEnum {
  DEVICEDRIVER_UNDEFINED = 0; // also used for emulated
  DEVICEDRIVER_CERAGON = 22;
}
enum ServiceTypeEnum {
  SERVICETYPE_UNKNOWN = 0;
  SERVICETYPE_L2NM = 2;
}
""",
    "src/common/DeviceTypes.py": """from enum import Enum
class DeviceTypeEnum(Enum):
    NETWORK = 'network'
    CERAGON_WIRELESS = 'ceragon-wireless'
""",
    "src/device/service/drivers/__init__.py": """DRIVERS = []
DRIVERS.append(
    (EmulatedDriver, [
        {FilterFieldEnum.DEVICE_TYPE: [], FilterFieldEnum.DRIVER: [DeviceDriverEnum.DEVICEDRIVER_UNDEFINED]}
    ]))
if LOAD_ALL_DEVICE_DRIVERS:
    DRIVERS.append(
        (CeragonDriver, [
            {FilterFieldEnum.DEVICE_TYPE: [DeviceTypeEnum.CERAGON_WIRELESS],
             FilterFieldEnum.DRIVER: DeviceDriverEnum.DEVICEDRIVER_CERAGON}
        ]))
""",
    "src/service/service/service_handlers/__init__.py": """SERVICE_HANDLERS = [
    (CeragonTransportServiceHandler, [
        {FilterFieldEnum.SERVICE_TYPE: [ServiceTypeEnum.SERVICETYPE_L2NM],
         FilterFieldEnum.DEVICE_DRIVER: DeviceDriverEnum.DEVICEDRIVER_CERAGON}
    ]),
]
""",
    "src/nbi/service/ietf_l2vpn/yang/ietf-l2vpn-svc@2018-10-09.yang": "module ietf-l2vpn-svc {}\n",
    "src/nbi/service/tfs_api/__init__.py": "",
    "src/nbi/service/ietf_network_slice/yang/ietf-network-slice-service@2024-08-28.yang": """module x {
  identity service-slo-metric-type {
    description
      "Base identity for Network Slice Service SLO metric type.";
  }

  identity two-way-bandwidth {
    base service-slo-metric-type;
    description
      "SLO bandwidth metric. Minimum guaranteed bandwidth between
       two SDPs at any time.";
  }

  identity vlan-id {
    base attachment-circuit-tag-type;
  }
}
""",
    "src/device/service/drivers/ceragon/portfolio.py": """FLAVOR_TG = "siklu_tg"
_CATALOG = [
    ProductSpec("MH-T261", "MultiHaul TG", "MultiHaul", FLAVOR_TG, (), 1.8, api_verified=True),
    ProductSpec("MH-T260", "MultiHaul TG", "MultiHaul", FLAVOR_TG, (), 1.8),
]
""",
}


def test_the_reader_takes_what_teraflowsdn_declares(tmp_path: Path) -> None:
    from u6g_catalog.tfs import read_model

    model = read_model(write_tree(tmp_path, TFS_TREE))
    assert model["kpiSampleTypes"][2] == {
        "name": "KPISAMPLETYPE_ML_CONFIDENCE",
        "value": 401,
        "comment": "can be used by both optical and L3",
    }
    assert model["kpiSampleTypes"][3]["comment"] == "received signal level"
    assert model["deviceDrivers"][-1] == {"name": "DEVICEDRIVER_CERAGON", "value": 22}
    assert model["deviceTypes"] == [
        {"name": "NETWORK", "value": "network"},
        {"name": "CERAGON_WIRELESS", "value": "ceragon-wireless"},
    ]
    assert model["drivers"] == [
        {"driverClass": "EmulatedDriver", "deviceTypes": [], "drivers": ["DEVICEDRIVER_UNDEFINED"]},
        {
            "driverClass": "CeragonDriver",
            "deviceTypes": ["CERAGON_WIRELESS"],
            "drivers": ["DEVICEDRIVER_CERAGON"],
        },
    ]
    assert model["serviceHandlers"] == [
        {
            "handlerClass": "CeragonTransportServiceHandler",
            "serviceTypes": ["SERVICETYPE_L2NM"],
            "drivers": ["DEVICEDRIVER_CERAGON"],
        }
    ]
    assert model["northbound"] == [
        {"interface": "ietf_l2vpn", "yang": ["ietf-l2vpn-svc@2018-10-09"]},
        {"interface": "ietf_network_slice", "yang": ["ietf-network-slice-service@2024-08-28"]},
    ]
    assert model["sloMetricTypes"] == {
        "module": "ietf-network-slice-service@2024-08-28",
        "identities": [
            {
                "identity": "two-way-bandwidth",
                "description": "SLO bandwidth metric. "
                "Minimum guaranteed bandwidth between two SDPs at any time.",
            }
        ],
    }
    assert model["ceragonPortfolio"] == [
        {"model": "MH-T260", "family": "MultiHaul TG", "apiFlavor": "siklu_tg", "apiVerified": False},
        {"model": "MH-T261", "family": "MultiHaul TG", "apiFlavor": "siklu_tg", "apiVerified": True},
    ]


def test_import_writes_the_model_once_and_check_reports_drift(tmp_path: Path) -> None:
    from u6g_catalog.__main__ import main

    tree = write_tree(tmp_path / "tfs", TFS_TREE)
    binding = tmp_path / "binding.yaml"
    binding.write_text((CATALOG / "transport/binding/tfs-nbi/2.0.0.yaml").read_text())
    args = [str(tree), "--source", "owner/teraflowsdn@abc1234", "--binding", str(binding)]
    assert main(["import-tfs", *args]) == 0
    model = yaml.safe_load(binding.read_text())["model"]
    assert model["source"] == "owner/teraflowsdn@abc1234" and len(model["kpiSampleTypes"]) == 4
    assert main(["import-tfs", *args, "--check"]) == 0
    (tree / "proto/kpi_sample_types.proto").write_text(
        TFS_TREE["proto/kpi_sample_types.proto"].replace("    KPISAMPLETYPE_BYTES_RECEIVED = 202;\n", "")
    )
    assert main(["import-tfs", *args, "--check"]) == 1
    assert yaml.safe_load(binding.read_text())["model"] == model  # --check writes nothing


def test_the_binding_holds_what_the_fork_declares(built: tuple[Catalog, dict[str, Any]]) -> None:
    catalog, _ = built
    model = catalog.entries["transport/binding/tfs-nbi@2.0.0"]["model"]
    kpis = {k["name"]: k["value"] for k in model["kpiSampleTypes"]}
    assert kpis["KPISAMPLETYPE_RADIO_RX_LEVEL_DBM"] == 801
    assert [p["model"] for p in model["ceragonPortfolio"] if p["apiVerified"]] == ["MH-T261"]
    ceragon = [d for d in model["drivers"] if d["driverClass"] == "CeragonDriver"]
    assert ceragon[0]["deviceTypes"] == ["MICROWAVE_RADIO_SYSTEM", "CERAGON_WIRELESS", "PACKET_RADIO_ROUTER"]
    slo = [i["identity"] for i in model["sloMetricTypes"]["identities"]]
    assert {"two-way-bandwidth", "two-way-delay-maximum"} <= set(slo)
    every_metric = [e for e in catalog.entries.values() if e["kind"] == "Metric" and "teraflowsdn" in e]
    assert every_metric and all(e["teraflowsdn"]["kpiSampleType"] in kpis for e in every_metric)


def test_every_entry_says_where_it_comes_from(built: tuple[Catalog, dict[str, Any]]) -> None:
    catalog, _ = built
    assert all(entry["provenance"] for entry in catalog.entries.values())


# The snapshot


def test_the_snapshot_is_reproducible_and_its_signature_verifies(
    built: tuple[Catalog, dict[str, Any]],
) -> None:
    catalog, index = built
    snapshot = archive(catalog, index)
    assert archive(load(CATALOG), build_index(load(CATALOG))) == snapshot
    private_pem, public_pem = keygen()
    signature = sign(snapshot, private_pem)
    verify(snapshot, signature, public_pem)
    with pytest.raises(ValueError, match="differs"):
        verify(snapshot + b"\0", signature, public_pem)
    with pytest.raises(ValueError, match="another key"):
        verify(snapshot, signature, keygen()[1])
    forged = {**signature, "signature": sign(b"another snapshot", private_pem)["signature"]}
    with pytest.raises(ValueError, match="does not verify"):
        verify(snapshot, forged, public_pem)


# The service


def test_the_service_resolves_references(built: tuple[Catalog, dict[str, Any]]) -> None:
    _, index = built

    async def scenario() -> None:
        transport = httpx.ASGITransport(app=create_app(index))
        async with httpx.AsyncClient(transport=transport, base_url="http://catalog") as client:
            resolved = (
                await client.get("/v1/resolve", params={"ref": "catalog://transport/metric/rsl@1.2.0"})
            ).json()
            assert resolved["kind"] == "Metric"
            assert resolved["digest"] == index["entries"]["transport/metric/rsl@1.2.0"]["digest"]
            assert (
                await client.get("/v1/resolve", params={"ref": "catalog://transport/metric/rsl@9.9.9"})
            ).status_code == 404
            assert (await client.get("/v1/resolve", params={"ref": "rsl"})).status_code == 400
            entry = (await client.get("/v1/entries/transport/action/set-modulation-profile@1.1.0")).json()
            assert entry["entry"]["idempotent"] is True
            actions = (await client.get("/v1/entries", params={"kind": "ActionType"})).json()["entries"]
            assert len(actions) == 6
            assert (await client.get("/v1/latest/transport/metric/capacity")).json()[
                "ref"
            ] == "transport/metric/capacity@1.1.0"
            code = (await client.get("/v1/reason-codes/ACT-UNVERIFIED")).json()
            assert code["entry"]["category"] == "actuation"
            assert (await client.get("/v1/health")).json()["entries"] == len(index["entries"])

    asyncio.run(scenario())


def test_the_index_records_the_digest_of_each_entry(built: tuple[Catalog, dict[str, Any]]) -> None:
    _, index = built
    digests = [e["digest"] for e in index["entries"].values()]
    assert len(set(digests)) == len(digests)
    assert all(re.fullmatch(r"sha256:[0-9a-f]{64}", d) for d in digests)
    assert json.loads(json.dumps(index)) == index
