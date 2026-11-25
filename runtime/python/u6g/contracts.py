"""The contracts in Python: the generated models, their Protocol Buffers form and the conversion between them.

The models are generated from the JSON Schemas under schemas/ into u6g.generated, and the messages of the
semantic objects from proto/u6g/impl/v1/semantic.proto into u6g.impl.v1 (guide Sections 3.4 and 19.2). Both
are generated from the same schemas, and the conversion goes through the JSON form they share, so that it
loses nothing: from_message(to_message(model), type(model)) equals the model."""

import types
import typing
from typing import Any

from google.protobuf import json_format
from google.protobuf.message import Message
from pydantic import BaseModel

from u6g.generated.descriptor.descriptor_schema import AgentDescriptor
from u6g.generated.envelope.execution_schema import ExecutionFeedback
from u6g.generated.envelope.insight_schema import Insight
from u6g.generated.envelope.intent_schema import Intent
from u6g.generated.envelope.observation_schema import Observation
from u6g.generated.runtime.runtime_config_schema import RuntimeConfig
from u6g.impl.v1 import semantic_pb2

__all__ = [
    "SEMANTIC_MESSAGES",
    "AgentDescriptor",
    "ExecutionFeedback",
    "Insight",
    "Intent",
    "Observation",
    "RuntimeConfig",
    "from_message",
    "platform_fields",
    "to_message",
]

SEMANTIC_MESSAGES: dict[type[BaseModel], type[Message]] = {
    Observation: semantic_pb2.Observation,
    Insight: semantic_pb2.Insight,
    Intent: semantic_pb2.Intent,
    ExecutionFeedback: semantic_pb2.ExecutionFeedback,
}


def to_message(model: BaseModel) -> Message:
    """The Protocol Buffers form of a semantic object."""
    message = SEMANTIC_MESSAGES[type(model)]()
    json_format.ParseDict(model.model_dump(mode="json", by_alias=True, exclude_none=True), message)
    return message


def from_message[M: BaseModel](message: Message, model_type: type[M]) -> M:
    """The model of a semantic object from its Protocol Buffers form, validated as on any other boundary."""
    data = json_format.MessageToDict(message, always_print_fields_with_no_presence=True)
    return model_type.model_validate(data)


def _nested_model(annotation: Any) -> type[BaseModel] | None:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    if typing.get_origin(annotation) in (typing.Union, types.UnionType):
        found = [m for m in map(_nested_model, typing.get_args(annotation)) if m is not None]
        return found[0] if len(found) == 1 else None
    return None


def platform_fields(model_type: type[BaseModel], prefix: str = "") -> list[str]:
    """The JSON Pointers of the fields the platform computes, from the readOnly marks of the schemas.

    The runtime refuses these fields from contributed logic and fills them itself (guide Section 3.4)."""
    pointers: list[str] = []
    for name, info in model_type.model_fields.items():
        pointer = f"{prefix}/{info.alias or name}"
        extra = info.json_schema_extra if isinstance(info.json_schema_extra, dict) else {}
        if extra.get("readOnly") is True:
            pointers.append(pointer)
            continue
        nested = _nested_model(info.annotation)
        if nested is not None:
            pointers.extend(platform_fields(nested, pointer))
    return pointers
