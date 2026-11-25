"""Work item 0.2: the mapping of the semantic schemas to Protocol Buffers keeps its field numbers and refuses
what it cannot carry whole."""

import json
from pathlib import Path

import pytest
from u6g.tools import gen_proto
from u6g.tools.gen_proto import Field, FieldType, Mapper, MappingError, Message, number_fields

ROOT = Path(__file__).resolve().parents[1]


def message(name: str, *json_names: str) -> Message:
    fields = [Field(n, gen_proto.snake_case(n), FieldType("string", "optional"), "") for n in json_names]
    return Message(name=name, comment="", source=name, fields=fields)


def test_new_fields_take_the_next_number_and_removed_ones_stay_reserved() -> None:
    first = number_fields({"M": message("M", "a", "b", "c")}, {})
    assert first["messages"]["M"]["fields"] == {"a": 1, "b": 2, "c": 3}
    second = number_fields({"M": message("M", "a", "c", "d")}, first)
    assert second["messages"]["M"]["fields"] == {"a": 1, "c": 3, "d": 4}
    assert second["messages"]["M"]["reserved"] == {"b": 2}
    third = number_fields({"M": message("M", "c", "a", "d", "b")}, second)
    assert third["messages"]["M"]["fields"] == {"a": 1, "c": 3, "d": 4, "b": 5}
    assert third["messages"]["M"]["reserved"] == {}


def write_schema(tmp: Path, properties: dict[str, object], required: list[str]) -> Mapper:
    schema = {"title": "Thing", "type": "object", "required": required, "properties": properties}
    (tmp / "thing.schema.json").write_text(json.dumps(schema))
    return Mapper(tmp)


def test_an_optional_array_needs_an_empty_default(tmp_path: Path) -> None:
    mapper = write_schema(tmp_path, {"tags": {"type": "array", "items": {"type": "string"}}}, [])
    with pytest.raises(MappingError, match="empty default"):
        mapper.message("Thing", mapper.load("thing.schema.json"), "thing.schema.json")
    ok = write_schema(tmp_path, {"tags": {"type": "array", "items": {"type": "string"}, "default": []}}, [])
    ok.message("Thing", ok.load("thing.schema.json"), "thing.schema.json")
    assert ok.messages["Thing"].fields[0].type == FieldType("string", "repeated")


def test_types_map_as_documented(tmp_path: Path) -> None:
    properties = {
        "when": {"type": "string", "format": "date-time"},
        "count": {"type": "integer"},
        "ratio": {"type": "number"},
        "flag": {"type": "boolean"},
        "free": {"type": "object"},
        "labels": {"type": "object", "additionalProperties": {"type": "string"}},
        "either": {"type": ["number", "string"]},
    }
    mapper = write_schema(tmp_path, properties, list(properties))
    mapper.message("Thing", mapper.load("thing.schema.json"), "thing.schema.json")
    got = {f.json_name: f.type for f in mapper.messages["Thing"].fields}
    assert got == {
        "when": FieldType("google.protobuf.Timestamp", ""),
        "count": FieldType("int64", "optional"),
        "ratio": FieldType("double", "optional"),
        "flag": FieldType("bool", "optional"),
        "free": FieldType("google.protobuf.Struct", ""),
        "labels": FieldType("map<string, string>", "map"),
        "either": FieldType("google.protobuf.Value", ""),
    }


def test_checked_in_proto_matches_its_lock() -> None:
    lock = json.loads((ROOT / "proto/u6g/impl/v1/semantic.lock.json").read_text())
    proto = (ROOT / "proto/u6g/impl/v1/semantic.proto").read_text()
    for name, entry in lock["messages"].items():
        assert f"message {name} {{" in proto
        numbers = list(entry["fields"].values()) + list(entry["reserved"].values())
        assert len(numbers) == len(set(numbers)), f"{name} reuses a field number"
