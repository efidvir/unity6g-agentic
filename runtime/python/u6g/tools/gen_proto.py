"""Generate proto/u6g/impl/v1/semantic.proto from the JSON Schemas of the semantic objects.

Usage: python -m u6g.tools.gen_proto <schemas_dir> <proto_dir>

The semantic objects travel as JSON on the bus and on the Data Continuum, and as Protocol Buffers on direct
bindings and on the local socket (guide Section 3.4). This tool writes the Protocol Buffers form from the same
schemas, in the package u6g.impl.v1 that the logic service imports (guide Annex F.1), with a mapping that
keeps every JSON document whole:

- an object with properties becomes a message, named after its title or its $defs entry;
- a string, an integer, a number and a boolean become optional scalars, so that a zero value stays present;
  a string of format date-time becomes google.protobuf.Timestamp; enumerations stay strings;
- an object without properties becomes google.protobuf.Struct, or map<string, string> when its values are
  strings; a choice of types becomes google.protobuf.Value;
- an array becomes a repeated field. An empty list and an absent one are the same in Protocol Buffers, so an
  optional array or map must declare an empty default; the tool refuses a schema that does not.

Field numbers are kept in semantic.lock.json beside the proto file. A new field takes the next free number,
and a removed field leaves its number and name reserved (guide Annex F, compatibility), so that regeneration
keeps the number of every field."""

import json
import re
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOTS = [
    ("Observation", "envelope/observation.schema.json"),
    ("Insight", "envelope/insight.schema.json"),
    ("Intent", "envelope/intent.schema.json"),
    ("ExecutionFeedback", "envelope/execution.schema.json"),
]
PACKAGE = "u6g.impl.v1"
PROTO_PATH = Path("u6g/impl/v1/semantic.proto")
LOCK_NAME = "semantic.lock.json"
STRUCT = "google.protobuf.Struct"
VALUE = "google.protobuf.Value"
TIMESTAMP = "google.protobuf.Timestamp"
IMPORTS = {
    STRUCT: "google/protobuf/struct.proto",
    VALUE: "google/protobuf/struct.proto",
    TIMESTAMP: "google/protobuf/timestamp.proto",
}
SCALARS = {"string": "string", "integer": "int64", "number": "double", "boolean": "bool"}

Schema = dict[str, Any]


class MappingError(Exception):
    """A schema construct the lossless mapping does not cover."""


@dataclass
class FieldType:
    name: str
    label: str  # "optional", "repeated", "map" or "" for a message field


@dataclass
class Field:
    json_name: str
    proto_name: str
    type: FieldType
    comment: str


@dataclass
class Message:
    name: str
    comment: str
    source: str
    fields: list[Field] = field(default_factory=list)


def snake_case(name: str) -> str:
    text = re.sub(r"[^0-9A-Za-z]+", "_", name)
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", text)
    return text.strip("_").lower()


def default_json_name(proto_name: str) -> str:
    """The JSON name protoc derives from a field name."""
    out, upper = [], False
    for char in proto_name:
        if char == "_":
            upper = True
        elif upper:
            out.append(char.upper())
            upper = False
        else:
            out.append(char)
    return "".join(out)


def comment_lines(text: str, indent: str) -> list[str]:
    if not text:
        return []
    return [f"{indent}// {line}" for line in textwrap.wrap(text, width=100 - len(indent) - 3)]


class Mapper:
    def __init__(self, schemas: Path) -> None:
        self.schemas = schemas
        self.files: dict[str, Schema] = {}
        self.messages: dict[str, Message] = {}
        self.imports: set[str] = set()

    def load(self, rel: str) -> Schema:
        if rel not in self.files:
            self.files[rel] = json.loads((self.schemas / rel).read_text())
        return self.files[rel]

    def deref(self, ref: str, base: str) -> tuple[str, str, Schema]:
        target, _, pointer = ref.partition("#")
        rel = self.normalize(base if not target else (Path(base).parent / target).as_posix())
        parts = [p for p in pointer.split("/") if p]
        node: Any = self.load(rel)
        for part in parts:
            node = node[part]
        name = parts[-1] if parts else str(node.get("title", ""))
        return rel, name, node

    @staticmethod
    def normalize(rel: str) -> str:
        stack: list[str] = []
        for part in rel.split("/"):
            if part == "..":
                stack.pop()
            elif part not in ("", "."):
                stack.append(part)
        return "/".join(stack)

    def message(self, name: str, node: Schema, base: str) -> None:
        source = f"{base}#{name}"
        known = self.messages.get(name)
        if known is not None:
            if known.source != source:
                raise MappingError(f"{source} and {known.source} both map to the message {name}; rename one")
            return
        msg = Message(name=name, comment=node.get("description", ""), source=source)
        self.messages[name] = msg
        required = set(node.get("required", []))
        for json_name, prop in node.get("properties", {}).items():
            ftype = self.field_type(prop, base, f"{name}.{json_name}")
            optional = json_name not in required
            if optional and ftype.label in ("repeated", "map"):
                empty: Any = [] if ftype.label == "repeated" else {}
                if prop.get("default") != empty:
                    raise MappingError(
                        f"{base}: {name}.{json_name} is an optional array or map without an empty default; "
                        "declare the default so that the Protocol Buffers form keeps the document whole"
                    )
            msg.fields.append(
                Field(
                    json_name=json_name,
                    proto_name=snake_case(json_name),
                    type=ftype,
                    comment=self.describe(prop, base),
                )
            )

    def describe(self, prop: Schema, base: str) -> str:
        text = str(prop.get("description", ""))
        node, rel = prop, base
        while "$ref" in node and not text:
            rel, _, node = self.deref(node["$ref"], rel)
            text = str(node.get("description", "")) if not self.is_message(node) else ""
        values = self.enum_values(prop, base)
        if values:
            text = (text + " " if text else "") + "One of: " + ", ".join(values) + "."
        if prop.get("readOnly"):
            text = (text + " " if text else "") + "Computed by the platform."
        return text

    def enum_values(self, prop: Schema, base: str) -> list[str]:
        node, rel = prop, base
        while "$ref" in node:
            rel, _, node = self.deref(node["$ref"], rel)
        return [str(v) for v in node.get("enum", [])]

    @staticmethod
    def is_message(node: Schema) -> bool:
        return node.get("type") == "object" and bool(node.get("properties"))

    def field_type(self, node: Schema, base: str, where: str) -> FieldType:
        if "$ref" in node:
            rel, name, target = self.deref(node["$ref"], base)
            if self.is_message(target):
                self.message(name, target, rel)
                return FieldType(name, "")
            return self.field_type(target, rel, where)
        if "anyOf" in node or "oneOf" in node or isinstance(node.get("type"), list):
            self.imports.add(IMPORTS[VALUE])
            return FieldType(VALUE, "")
        kind = node.get("type")
        if kind == "object":
            if node.get("properties"):
                raise MappingError(
                    f"{where}: an object with properties needs a $defs entry naming its message"
                )
            extra = node.get("additionalProperties")
            if isinstance(extra, dict):
                inner = extra
                while "$ref" in inner:
                    _, _, inner = self.deref(inner["$ref"], base)
                if inner.get("type") == "string" and "format" not in inner:
                    return FieldType("map<string, string>", "map")
            self.imports.add(IMPORTS[STRUCT])
            return FieldType(STRUCT, "")
        if kind == "array":
            item = self.field_type(node.get("items", {}), base, where + "[]")
            if item.label in ("repeated", "map"):
                raise MappingError(f"{where}: arrays of arrays or of maps are outside the mapping")
            return FieldType(item.name, "repeated")
        if kind == "string" and node.get("format") == "date-time":
            self.imports.add(IMPORTS[TIMESTAMP])
            return FieldType(TIMESTAMP, "")
        if kind in SCALARS:
            return FieldType(SCALARS[kind], "optional")
        raise MappingError(f"{where}: the type {kind!r} is outside the mapping")


def number_fields(messages: dict[str, Message], lock: dict[str, Any]) -> dict[str, Any]:
    """Keep the numbers of the lock, give new fields the next free number, and reserve removed ones."""
    old = lock.get("messages", {})
    new: dict[str, Any] = {}
    for name in sorted(messages):
        entry = old.get(name, {"fields": {}, "reserved": {}})
        fields: dict[str, int] = dict(entry.get("fields", {}))
        reserved: dict[str, int] = dict(entry.get("reserved", {}))
        current = [f.json_name for f in messages[name].fields]
        for gone in [n for n in fields if n not in current]:
            reserved[gone] = fields.pop(gone)
        for json_name in current:
            if json_name not in fields:
                used = set(fields.values()) | set(reserved.values())
                fields[json_name] = max(used, default=0) + 1
                reserved.pop(json_name, None)
        new[name] = {"fields": fields, "reserved": dict(sorted(reserved.items(), key=lambda kv: kv[1]))}
    return {"package": PACKAGE, "messages": new}


def render(mapper: Mapper, lock: dict[str, Any]) -> str:
    out = [
        "// Code generated by u6g.tools.gen_proto from the JSON Schemas of the semantic objects.",
        "// DO NOT EDIT. Provisional: generated from the reference definitions of the implementation",
        "// guide, which stand in for [IMPL] Annex A until it arrives (work item D.3).",
        "//",
        "// The Protocol Buffers form of the semantic objects, for direct bindings and the local socket",
        "// (guide Section 3.4). Every JSON document maps here and back unchanged; the JSON names are the",
        "// field names of the proto3 JSON mapping. Field numbers are kept in semantic.lock.json.",
        'syntax = "proto3";',
        "",
        f"package {PACKAGE};",
        "",
    ]
    for path in sorted(mapper.imports):
        out.append(f'import "{path}";')
    if mapper.imports:
        out.append("")
    roots = [name for name, _ in ROOTS]
    order = roots + sorted(n for n in mapper.messages if n not in roots)
    for name in order:
        msg = mapper.messages[name]
        numbers = lock["messages"][name]
        out.extend(comment_lines(msg.comment, ""))
        out.append(f"message {name} {{")
        for f in msg.fields:
            out.extend(comment_lines(f.comment, "  "))
            option = ""
            if default_json_name(f.proto_name) != f.json_name:
                option = f' [json_name = "{f.json_name}"]'
            label = f.type.label + " " if f.type.label in ("optional", "repeated") else ""
            out.append(f"  {label}{f.type.name} {f.proto_name} = {numbers['fields'][f.json_name]}{option};")
        reserved = numbers["reserved"]
        if reserved:
            out.append("  reserved " + ", ".join(str(n) for n in reserved.values()) + ";")
            out.append("  reserved " + ", ".join(f'"{snake_case(n)}"' for n in reserved) + ";")
        out.append("}")
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


def generate(schemas: Path, proto_dir: Path) -> int:
    mapper = Mapper(schemas)
    try:
        for name, rel in ROOTS:
            root = mapper.load(rel)
            if root.get("title") != name:
                raise MappingError(f"{rel}: the title must be {name}")
            mapper.message(name, root, rel)
    except MappingError as err:
        print(f"gen_proto: {err}", file=sys.stderr)
        return 1
    target = proto_dir / PROTO_PATH
    lock_path = target.parent / LOCK_NAME
    lock = json.loads(lock_path.read_text()) if lock_path.exists() else {}
    lock = number_fields(mapper.messages, lock)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(mapper, lock))
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")
    print(f"gen_proto: {len(mapper.messages)} messages -> {target}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    return generate(Path(argv[0]), Path(argv[1]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
