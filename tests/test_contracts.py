"""Work item 0.2: the schemas and the generated models validate the examples of the guide and agree on what
they reject, and the Protocol Buffers form of the semantic objects keeps them whole."""

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, ValidationError
from referencing import Registry, Resource
from u6g.contracts import (
    AgentDescriptor,
    ExecutionFeedback,
    Insight,
    Intent,
    Observation,
    RuntimeConfig,
    from_message,
    platform_fields,
    to_message,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
EXAMPLES = ROOT / "examples" / "contracts"

CASES: list[tuple[str, str, type[BaseModel]]] = [
    ("descriptor/descriptor.schema.json", "descriptor/link-assurance.yaml", AgentDescriptor),
    ("envelope/observation.schema.json", "envelope/observation.json", Observation),
    ("envelope/insight.schema.json", "envelope/insight.json", Insight),
    ("envelope/intent.schema.json", "envelope/intent.json", Intent),
    ("envelope/execution.schema.json", "envelope/execution.json", ExecutionFeedback),
    ("runtime/runtime-config.schema.json", "runtime/runtime-config.de.yaml", RuntimeConfig),
]
SEMANTIC = [case for case in CASES if case[0].startswith("envelope/")]


def load(name: str) -> Any:
    return yaml.safe_load((EXAMPLES / name).read_text())


def registry() -> Registry:
    resources = []
    for path in SCHEMAS.rglob("*.schema.json"):
        resources.append((path.resolve().as_uri(), Resource.from_contents(json.loads(path.read_text()))))
    return Registry().with_resources(resources)


REGISTRY = registry()


def validator(schema: str) -> Draft202012Validator:
    return Draft202012Validator(
        {"$ref": (SCHEMAS / schema).resolve().as_uri()}, registry=REGISTRY, format_checker=FormatChecker()
    )


def normalized(value: Any) -> Any:
    """Equal JSON values compare equal: instants by their time, whatever the digits of their fraction."""
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalized(v) for v in value]
    if isinstance(value, str) and len(value) >= 20 and value[10:11] == "T" and value.endswith("Z"):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value


@pytest.mark.parametrize("path", sorted(SCHEMAS.rglob("*.schema.json")), ids=lambda p: p.name)
def test_schema_is_valid_2020_12(path: Path) -> None:
    schema = json.loads(path.read_text())
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$comment"].startswith("Provisional:"), "provisional until [IMPL] Annex A arrives"


@pytest.mark.parametrize(("schema", "example", "model"), CASES, ids=[c[1] for c in CASES])
def test_schema_validates_example(schema: str, example: str, model: type[BaseModel]) -> None:
    errors = [e.message for e in validator(schema).iter_errors(load(example))]
    assert errors == []


@pytest.mark.parametrize(("schema", "example", "model"), CASES, ids=[c[1] for c in CASES])
def test_model_validates_example_and_dumps_it_back(schema: str, example: str, model: type[BaseModel]) -> None:
    data = load(example)
    instance = model.model_validate(data)
    dumped = instance.model_dump(mode="json", by_alias=True, exclude_unset=True)
    assert normalized(dumped) == normalized(data)
    assert model.model_validate(dumped) == instance


# Each mutation must be refused by the schema and by the model alike: (example, path, change).
DELETE = object()
MUTATIONS: list[tuple[str, tuple[str | int, ...], Any]] = [
    ("envelope/observation.json", ("envelope", "generation"), 0),
    ("envelope/observation.json", ("envelope", "quality", "coverage"), DELETE),
    ("envelope/observation.json", ("metric",), "catalog://transport/metric/rsl"),
    ("envelope/observation.json", ("unexpected",), 1),
    ("envelope/insight.json", ("confidence",), 1.5),
    ("envelope/insight.json", ("envelope", "validity"), "unknown"),
    ("envelope/insight.json", ("envelope", "model", "digest"), "sha256:9b1e"),
    ("envelope/insight.json", ("payload",), DELETE),
    ("envelope/intent.json", ("envelope", "verdict", "kind"), "maybe"),
    ("envelope/intent.json", ("envelope", "rationale", "reasonCode"), "preempt fade"),
    ("envelope/intent.json", ("envelope", "rationale"), DELETE),
    ("envelope/intent.json", ("targets",), []),
    ("envelope/intent.json", ("envelope", "traceparent"), "00-4bf92f-01"),
    ("envelope/execution.json", ("envelope", "intent"), "obs-a90c33f1"),
    ("envelope/execution.json", ("attempt", "n"), 0),
    ("envelope/execution.json", ("envelope", "times", "outcome"), "yesterday"),
    ("descriptor/link-assurance.yaml", ("tuple", "de", "mode"), "half"),
    ("descriptor/link-assurance.yaml", ("operations", "loopBudget"), "5s"),
    ("descriptor/link-assurance.yaml", ("actionSpace", 0, "rateLimit"), DELETE),
    ("descriptor/link-assurance.yaml", ("objectives", 0, "direction"), "up"),
    ("descriptor/link-assurance.yaml", ("functions", "de", "constraints", 0, "all", 0, "nearly"), 1),
    ("runtime/runtime-config.de.yaml", ("capability",), "dm"),
    ("runtime/runtime-config.de.yaml", ("descriptor", "digest"), "sha256:5c0d"),
]


def mutate(data: Any, path: tuple[str | int, ...], change: Any) -> Any:
    out = copy.deepcopy(data)
    node = out
    for key in path[:-1]:
        node = node[key]
    if change is DELETE:
        del node[path[-1]]
    else:
        node[path[-1]] = change
    return out


@pytest.mark.parametrize(("example", "path", "change"), MUTATIONS, ids=lambda v: str(v))
def test_schema_and_model_refuse_the_same_mutation(
    example: str, path: tuple[str | int, ...], change: Any
) -> None:
    schema, _, model = next(c for c in CASES if c[1] == example)
    data = mutate(load(example), path, change)
    assert list(validator(schema).iter_errors(data)), "the schema accepts the mutation"
    with pytest.raises(ValidationError):
        model.model_validate(data)


@pytest.mark.parametrize(("schema", "example", "model"), SEMANTIC, ids=[c[1] for c in SEMANTIC])
def test_protocol_buffers_form_keeps_the_object_whole(
    schema: str, example: str, model: type[BaseModel]
) -> None:
    instance = model.model_validate(load(example))
    message = to_message(instance)
    wire = message.SerializeToString()
    assert from_message(type(message).FromString(wire), model) == instance


def test_gap_and_zero_values_survive_the_protocol_buffers_form() -> None:
    data = load("envelope/observation.json")
    del data["value"]
    data["envelope"]["quality"]["flags"] = ["gap"]
    data["envelope"]["quality"]["coverage"]["observed"] = 0
    instance = Observation.model_validate(data)
    back = from_message(to_message(instance), Observation)
    assert back == instance
    assert back.value is None
    assert back.envelope.quality.loss == 0.0
    assert back.envelope.quality.coverage.observed == 0


def test_platform_fields_follow_the_readonly_marks() -> None:
    intent = platform_fields(Intent)
    computed = {"/envelope/id", "/envelope/verdict", "/envelope/correlation", "/envelope/validUntil"}
    supplied = {"/envelope/urgency", "/envelope/rationale", "/envelope/confidence", "/actionType"}
    assert computed <= set(intent)
    assert not supplied & set(intent)
    assert platform_fields(Observation) == ["/envelope"]
    assert platform_fields(Insight) == ["/envelope"]
    execution = json.loads((SCHEMAS / "envelope/execution.schema.json").read_text())
    assert set(platform_fields(ExecutionFeedback)) == {f"/{name}" for name in execution["properties"]}


def required_paths(
    node: Any, data: Any, resolver: Any, path: tuple[str | int, ...] = ()
) -> list[tuple[str | int, ...]]:
    """The paths of the required members of a document, read from the schema where the document has them."""
    while "$ref" in node:
        resolved = resolver.lookup(node["$ref"])
        node, resolver = resolved.contents, resolved.resolver
    found: list[tuple[str | int, ...]] = []
    if isinstance(data, dict):
        found.extend((*path, key) for key in node.get("required", []))
        for key, sub in node.get("properties", {}).items():
            if key in data:
                found.extend(required_paths(sub, data[key], resolver, (*path, key)))
    elif isinstance(data, list) and isinstance(node.get("items"), dict):
        for i, item in enumerate(data):
            found.extend(required_paths(node["items"], item, resolver, (*path, i)))
    return found


MISSING = [
    (schema, example, path)
    for schema, example, _ in CASES
    for path in required_paths(
        json.loads((SCHEMAS / schema).read_text()),
        load(example),
        REGISTRY.resolver(base_uri=(SCHEMAS / schema).resolve().as_uri()),
    )
]


@pytest.mark.property
@pytest.mark.parametrize(
    ("schema", "example", "path"),
    MISSING,
    ids=lambda v: "/".join(map(str, v)) if isinstance(v, tuple) else str(v),
)
def test_a_message_missing_a_mandatory_structure_is_rejected(
    schema: str, example: str, path: tuple[str | int, ...]
) -> None:
    """[FW] 3.3.2 and 3.3.4: a message that lacks a mandatory structure is rejected at the boundary where it
    arrives; the schema and the model refuse each required member of the examples when it is removed."""
    model = next(m for s, _, m in CASES if s == schema)
    data = mutate(load(example), path, DELETE)
    assert list(validator(schema).iter_errors(data)), "the schema accepts the removal"
    with pytest.raises(ValidationError):
        model.model_validate(data)
