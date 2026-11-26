"""Build the type catalog into its index (guide Section 11.4).

Every entry is a YAML file at catalog/<id>/<version>.yaml, and every area has a manifest at
catalog/<area>/area.yaml. The build validates each entry against the schema of its kind, checks it against
the others, and indexes it by identity and version with the digest of its canonical JSON form (RFC 8785).
A finding names the file and the rule it breaks; a catalog with findings is not published."""

import hashlib
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import rfc8785
import yaml
from pydantic import BaseModel, ValidationError
from u6g.generated.catalog.action_schema import ActionTypeEntry
from u6g.generated.catalog.binding_schema import ControllerBindingEntry
from u6g.generated.catalog.common_schema import CatalogArea
from u6g.generated.catalog.contract_schema import ServiceContractEntry
from u6g.generated.catalog.insight_schema import InsightTypeEntry
from u6g.generated.catalog.kpi_schema import ObjectiveKpiEntry
from u6g.generated.catalog.metric_schema import MetricEntry
from u6g.generated.catalog.parameter_schema import ControlParameterEntry
from u6g.generated.catalog.reason_schema import ReasonCodeEntry
from u6g.generated.catalog.source_schema import SourceKindEntry
from u6g.generated.catalog.verification_schema import VerificationMethodEntry

KINDS: dict[str, type[BaseModel]] = {
    "Metric": MetricEntry,
    "ControlParameter": ControlParameterEntry,
    "ActionType": ActionTypeEntry,
    "InsightType": InsightTypeEntry,
    "ObjectiveKpi": ObjectiveKpiEntry,
    "VerificationMethod": VerificationMethodEntry,
    "ControllerBinding": ControllerBindingEntry,
    "SourceKind": SourceKindEntry,
    "ReasonCode": ReasonCodeEntry,
    "ServiceContract": ServiceContractEntry,
}

REF = re.compile(r"^(?P<id>[a-z0-9]+(?:[./-][a-z0-9]+)*)@(?P<version>[0-9]+\.[0-9]+\.[0-9]+)$")
SCHEME = "catalog://"

# The kind each field of an entry refers to, by the path of the field with list indices left out.
EXPECTED: dict[tuple[str, ...], tuple[str, ...]] = {
    ("sources",): ("SourceKind",),
    ("setBy",): ("ControllerBinding",),
    ("readBack", "metric"): ("Metric",),
    ("targets", "parameters"): ("ControlParameter",),
    ("controllerBindings", "binding"): ("ControllerBinding",),
    ("actionTypes",): ("ActionType",),
}
CARRIES = {"observation": ("Metric",), "insight": ("InsightType",), "intent": ("ActionType",)}


@dataclass(frozen=True)
class Finding:
    path: str
    rule: str  # schema, identity, reference, consistency or area
    message: str


@dataclass
class Catalog:
    root: Path
    entries: dict[str, dict[str, Any]] = field(default_factory=dict)  # "id@version" -> entry as written
    files: dict[str, str] = field(default_factory=dict)  # "id@version" -> file, relative to the root
    areas: dict[str, dict[str, Any]] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)

    def find(self, path: str, rule: str, message: str) -> None:
        self.findings.append(Finding(path, rule, message))


def parse_ref(text: str) -> tuple[str, str] | None:
    """The identity and version of a reference written with or without the catalog:// scheme."""
    match = REF.match(text.removeprefix(SCHEME))
    return None if match is None else (match["id"], match["version"])


def semver(version: str) -> tuple[int, int, int]:
    major, minor, patch = (int(x) for x in version.split("+")[0].split("-")[0].split("."))
    return major, minor, patch


def digest(entry: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(rfc8785.dumps(entry)).hexdigest()


def load(root: Path) -> Catalog:
    """Read and validate every manifest and entry under root, then check the entries against each other."""
    catalog = Catalog(root=root)
    for path in sorted(root.rglob("*.yaml")):
        rel = path.relative_to(root).as_posix()
        try:
            data = yaml.safe_load(path.read_text())
        except yaml.YAMLError as err:
            catalog.find(rel, "schema", f"not YAML: {err}")
            continue
        if path.name == "area.yaml":
            _load_area(catalog, rel, data)
        else:
            _load_entry(catalog, rel, data)
    for ref, entry in catalog.entries.items():
        _check_entry(catalog, catalog.files[ref], entry)
    _check_codes(catalog)
    return catalog


def _load_area(catalog: Catalog, rel: str, data: Any) -> None:
    try:
        area = CatalogArea.model_validate(data)
    except ValidationError as err:
        catalog.find(rel, "schema", _first(err))
        return
    parts = rel.split("/")
    if len(parts) != 2 or parts[0] != area.area:
        catalog.find(
            rel, "identity", f"the manifest of area {area.area} lives at catalog/{area.area}/area.yaml"
        )
        return
    catalog.areas[area.area] = data


def _load_entry(catalog: Catalog, rel: str, data: Any) -> None:
    kind = data.get("kind") if isinstance(data, dict) else None
    model = KINDS.get(kind) if isinstance(kind, str) else None
    if model is None:
        catalog.find(rel, "schema", f"unknown kind {kind!r}; the kinds are {', '.join(KINDS)}")
        return
    try:
        model.model_validate(data)
    except ValidationError as err:
        catalog.find(rel, "schema", _first(err))
        return
    expected = f"{data['id']}/{data['version']}.yaml"
    if rel != expected:
        catalog.find(rel, "identity", f"the entry {data['id']}@{data['version']} lives at {expected}")
        return
    ref = f"{data['id']}@{data['version']}"
    catalog.entries[ref] = data
    catalog.files[ref] = rel


def _first(err: ValidationError) -> str:
    first = err.errors()[0]
    where = "/".join(str(x) for x in first["loc"]) or "(root)"
    return f"{where}: {first['msg']}" + (
        f" (and {err.error_count() - 1} more)" if err.error_count() > 1 else ""
    )


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, (*path, str(key)))
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child, path)
    elif isinstance(value, str) and parse_ref(value) is not None:
        yield path, value


def _check_entry(catalog: Catalog, rel: str, entry: dict[str, Any]) -> None:
    area = catalog.areas.get(entry["id"].split("/")[0])
    if area is None:
        catalog.find(rel, "area", f"no manifest for the area of {entry['id']}")
    else:
        if entry["owner"] != area["owner"]:
            catalog.find(rel, "area", f"the owner is {area['owner']}, the owner of the area")
        object_class = entry.get("objectClass") or entry.get("targets", {}).get("objectClass")
        if object_class is not None and object_class not in area["objectClasses"]:
            catalog.find(rel, "area", f"the object class {object_class} is not one of the area's")
    for path, text in _walk(entry):
        if path and path[0] == "parameters" and entry["kind"] == "ActionType":
            continue  # the JSON Schema of the action's parameters
        target = catalog.entries.get(text.removeprefix(SCHEME))
        if target is None:
            catalog.find(rel, "reference", f"{'/'.join(path)}: {text} does not resolve")
            continue
        kinds = EXPECTED.get(path)
        if path == ("carries",):
            kinds = CARRIES.get(entry.get("flow", ""))
        if kinds is not None and target["kind"] not in kinds:
            catalog.find(
                rel,
                "reference",
                f"{'/'.join(path)}: {text} is a {target['kind']}; the field takes a {' or '.join(kinds)}",
            )
    check = CHECKS.get(entry["kind"])
    if check is not None:
        check(catalog, rel, entry)


def _methods(catalog: Catalog) -> dict[str, dict[str, Any]]:
    return {e["method"]: e for e in catalog.entries.values() if e["kind"] == "VerificationMethod"}


def _check_action(catalog: Catalog, rel: str, action: dict[str, Any]) -> None:
    ref = f"{action['id']}@{action['version']}"
    for binding in action["controllerBindings"]:
        target = catalog.entries.get(binding["binding"])
        if target is None or target["kind"] != "ControllerBinding":
            continue
        if ref not in target["actionTypes"]:
            catalog.find(
                rel, "consistency", f"the binding {binding['binding']} does not list this action type"
            )
        for operation in binding["operations"]:
            if operation not in target["operations"]:
                catalog.find(rel, "consistency", f"{binding['binding']} has no operation {operation}")
    wanted = action["targets"]["objectClass"]
    for param in action["targets"]["parameters"]:
        target = catalog.entries.get(param)
        if target is not None and target.get("objectClass") != action["targets"]["objectClass"]:
            catalog.find(
                rel,
                "consistency",
                f"{param} describes {target.get('objectClass')}; the action targets {wanted}",
            )
    methods = _methods(catalog)
    names = set(action["parameters"].get("properties", {}))
    for verification in action["verification"]:
        if verification["method"] not in methods:
            catalog.find(
                rel, "consistency", f"no verification method {verification['method']} in the catalog"
            )
        for path, value in _walk_params(verification.get("predicate", {})):
            if value not in names:
                catalog.find(
                    rel,
                    "consistency",
                    f"the predicate names {value} at {path}; the action's parameters are {sorted(names)}",
                )


def _walk_params(node: Any, path: str = "predicate") -> Iterator[tuple[str, str]]:
    if isinstance(node, dict):
        for key, child in node.items():
            if key == "param" and isinstance(child, str):
                yield path, child
            else:
                yield from _walk_params(child, f"{path}/{key}")
    elif isinstance(node, list):
        for i, child in enumerate(node):
            yield from _walk_params(child, f"{path}/{i}")


def _check_binding(catalog: Catalog, rel: str, binding: dict[str, Any]) -> None:
    ref = f"{binding['id']}@{binding['version']}"
    for action_ref in binding["actionTypes"]:
        action = catalog.entries.get(action_ref)
        if action is not None and action["kind"] == "ActionType":
            if ref not in [b["binding"] for b in action["controllerBindings"]]:
                catalog.find(rel, "consistency", f"{action_ref} does not name this binding")


def _check_parameter(catalog: Catalog, rel: str, param: dict[str, Any]) -> None:
    method = param["readBack"]["method"]
    if method not in _methods(catalog):
        catalog.find(rel, "consistency", f"no verification method {method} in the catalog")
    if method == "msObservation" and "metric" not in param["readBack"]:
        catalog.find(rel, "consistency", "a read-back by observation names its metric")
    if method == "controllerQuery":
        for binding_ref in param["setBy"]:
            binding = catalog.entries.get(binding_ref, {})
            if binding.get("stateReflectsDevice") is not True:
                catalog.find(
                    rel,
                    "consistency",
                    f"{binding_ref} does not reflect the device; controllerQuery is invalid",
                )


def _check_contract(catalog: Catalog, rel: str, contract: dict[str, Any]) -> None:
    if contract["contribution"] == "flow" and "flow" not in contract:
        catalog.find(rel, "consistency", "a flow contract names its flow")
    if contract["contribution"] == "platformService" and "consumedAt" not in contract:
        catalog.find(rel, "consistency", "a platform service states where the platform consumes it")


CHECKS = {
    "ActionType": _check_action,
    "ControllerBinding": _check_binding,
    "ControlParameter": _check_parameter,
    "ServiceContract": _check_contract,
}


def _check_codes(catalog: Catalog) -> None:
    owners: dict[str, str] = {}
    for ref, entry in sorted(catalog.entries.items()):
        if entry["kind"] != "ReasonCode":
            continue
        code, ident = entry["code"], entry["id"]
        if code in owners and owners[code] != ident:
            catalog.find(
                catalog.files[ref], "consistency", f"the code {code} is also the entry {owners[code]}"
            )
        owners.setdefault(code, ident)
        if ident.rsplit("/", 1)[-1] != code.lower():
            catalog.find(catalog.files[ref], "identity", f"the entry of {code} is named {code.lower()}")


def build_index(catalog: Catalog) -> dict[str, Any]:
    """The index the service serves and the snapshot carries."""
    entries = {
        ref: {
            "kind": e["kind"],
            "id": e["id"],
            "version": e["version"],
            "owner": e["owner"],
            "deprecated": e["deprecated"],
            "digest": digest(e),
            "entry": e,
        }
        for ref, e in sorted(catalog.entries.items())
    }
    latest: dict[str, str] = {}
    for e in catalog.entries.values():
        if e["id"] not in latest or semver(e["version"]) > semver(latest[e["id"]]):
            latest[e["id"]] = e["version"]
    codes = {e["code"]: ref for ref, e in sorted(catalog.entries.items()) if e["kind"] == "ReasonCode"}
    return {
        "areas": dict(sorted(catalog.areas.items())),
        "entries": entries,
        "latest": dict(sorted(latest.items())),
        "reasonCodes": dict(sorted(codes.items())),
    }
