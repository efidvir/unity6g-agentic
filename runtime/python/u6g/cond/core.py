"""The condition evaluator: the structure check and the evaluation of conditions in the fixed form of [FW].

A condition is a group over conditions (all, any or not), or the comparison of one named operand (a metric,
a feature, a parameter or an attribute) by one operator (eq, ne, lt, le, gt, ge, between or in) with a
literal or another named operand. The same evaluator serves the validity conditions of models, the
constraints of a Decision Engine and the preconditions of action types (guide Sections 6.3, 7.2 and 8.1).

Evaluation follows the three-valued logic of Kleene: a comparison whose operand has no value is unknown, and
so is a comparison of values that cannot be ordered. A group is decided as soon as its known members decide
it, and stays unknown otherwise. Every caller acts only on a condition that holds, so an unknown result fails
closed, and a result decided with some values missing stays the same when they arrive."""

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from u6g.generated.common.defs_schema import Condition, OperandRef

__all__ = [
    "DEFAULT_MAX_DEPTH",
    "GROUPS",
    "OPERATORS",
    "SUBJECTS",
    "Condition",
    "Declared",
    "Values",
    "Violation",
    "check",
    "depth",
    "evaluate",
    "holds",
    "parse",
]

SUBJECTS = ("metric", "feature", "param", "attribute")
OPERATORS = ("eq", "ne", "lt", "le", "gt", "ge", "between", "in")
GROUPS = ("all", "any", "not")
ORDERED = ("lt", "le", "gt", "ge", "between")

DEFAULT_MAX_DEPTH = 3
"""The deepest nesting of groups a condition may have; a single comparison has depth 0. Provisional until
[IMPL] sets the permitted depth (STATE.md)."""

Values = Mapping[tuple[str, str], Any]
"""The values the condition reads, by kind and name: ("metric", "link-state") -> "up". A missing key is a
value not known at evaluation time."""

FIELDS = {"not": "not_", "in": "in_"}


@dataclass(frozen=True)
class Declared:
    """The operand names a descriptor declares, by kind."""

    metric: frozenset[str] = frozenset()
    feature: frozenset[str] = frozenset()
    param: frozenset[str] = frozenset()
    attribute: frozenset[str] = frozenset()

    def has(self, kind: str, name: str) -> bool:
        names: frozenset[str] = getattr(self, kind)
        return name in names


@dataclass(frozen=True)
class Violation:
    """A breach of the fixed structure, with the JSON Pointer of the node within the condition."""

    pointer: str
    rule: str  # structure, operand, type or depth
    message: str


def parse(data: Mapping[str, Any]) -> Condition:
    """A condition from its JSON or YAML form, validated against the schema."""
    return Condition.model_validate(data)


def _get(node: Condition, key: str) -> Any:
    return getattr(node, FIELDS.get(key, key))


def _present(node: Condition, keys: Iterable[str]) -> list[str]:
    return [key for key in keys if _get(node, key) is not None]


def _children(node: Condition) -> list[tuple[str, Condition]]:
    out: list[tuple[str, Condition]] = []
    for key in ("all", "any"):
        members = _get(node, key)
        if members is not None:
            out.extend((f"/{key}/{i}", member) for i, member in enumerate(members))
    if node.not_ is not None:
        out.append(("/not", node.not_))
    return out


def depth(condition: Condition) -> int:
    """The nesting of groups: 0 for a comparison, 1 for a group of comparisons, and so on."""
    children = _children(condition)
    if not children:
        return 0
    return 1 + max(depth(child) for _, child in children)


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _operands(node: Condition, operator: str) -> list[Any]:
    value = _get(node, operator)
    return list(value) if operator in ("between", "in") else [value]


def check(condition: Condition, declared: Declared, max_depth: int = DEFAULT_MAX_DEPTH) -> list[Violation]:
    """Every breach of the fixed structure: the form of each node, the operands it names, the types of its
    literals and the depth of the whole. An empty list means the condition is well formed."""
    found: list[Violation] = []
    _check_node(condition, "", declared, found, root=True)
    if depth(condition) > max_depth:
        found.append(
            Violation("", "depth", f"the groups nest {depth(condition)} deep; the limit is {max_depth}")
        )
    return found


def _check_node(
    node: Condition, pointer: str, declared: Declared, found: list[Violation], root: bool
) -> None:
    groups, subjects, operators = _present(node, GROUPS), _present(node, SUBJECTS), _present(node, OPERATORS)
    if node.id is not None and not root:
        found.append(
            Violation(pointer + "/id", "structure", "only a whole condition, a constraint, is named")
        )
    if groups:
        if len(groups) > 1:
            found.append(Violation(pointer, "structure", f"one group per node; found {', '.join(groups)}"))
        if subjects or operators:
            found.append(Violation(pointer, "structure", "a group carries no comparison of its own"))
        for suffix, child in _children(node):
            _check_node(child, pointer + suffix, declared, found, root=False)
        return
    if len(subjects) != 1:
        found.append(
            Violation(
                pointer, "structure", "a comparison names exactly one of metric, feature, param, attribute"
            )
        )
    if len(operators) != 1:
        found.append(Violation(pointer, "structure", "a comparison has exactly one operator"))
    for kind in subjects:
        name = _get(node, kind)
        if not declared.has(kind, name):
            found.append(Violation(f"{pointer}/{kind}", "operand", f"the {kind} {name!r} is not declared"))
    for operator in operators:
        literals: list[Any] = []
        for i, operand in enumerate(_operands(node, operator)):
            where = f"{pointer}/{operator}" + (f"/{i}" if operator in ("between", "in") else "")
            if isinstance(operand, OperandRef):
                for kind in _present_ref(operand):
                    name = getattr(operand, kind)
                    if not declared.has(kind, name):
                        found.append(
                            Violation(f"{where}/{kind}", "operand", f"the {kind} {name!r} is not declared")
                        )
            else:
                literals.append(operand)
                if operator in ORDERED and not _is_number(operand):
                    found.append(Violation(where, "type", f"{operator} compares numbers; found {operand!r}"))
        if operator == "between" and len(literals) == 2 and all(map(_is_number, literals)):
            if literals[0] > literals[1]:
                found.append(
                    Violation(f"{pointer}/between", "type", "the lower bound exceeds the upper bound")
                )


def _present_ref(ref: OperandRef) -> list[str]:
    return [kind for kind in ("param", "metric", "feature") if getattr(ref, kind) is not None]


_UNKNOWN = object()


def _value(operand: Any, values: Values) -> Any:
    if isinstance(operand, OperandRef):
        kinds = _present_ref(operand)
        if len(kinds) != 1:
            return _UNKNOWN
        return values.get((kinds[0], getattr(operand, kinds[0])), _UNKNOWN)
    return operand


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if _is_number(a) and _is_number(b):
        return bool(a == b)
    return type(a) is type(b) and a == b


def _compare(operator: str, subject: Any, operand: Any) -> bool | None:
    if subject is _UNKNOWN or operand is _UNKNOWN:
        return None
    if operator == "eq":
        return _same(subject, operand)
    if operator == "ne":
        return not _same(subject, operand)
    if not (_is_number(subject) and _is_number(operand)):
        return None
    if operator == "lt":
        return bool(subject < operand)
    if operator == "le":
        return bool(subject <= operand)
    if operator == "gt":
        return bool(subject > operand)
    return bool(subject >= operand)


def _all(results: Iterable[bool | None]) -> bool | None:
    seen = list(results)
    if any(r is False for r in seen):
        return False
    return None if any(r is None for r in seen) else True


def _any(results: Iterable[bool | None]) -> bool | None:
    seen = list(results)
    if any(r is True for r in seen):
        return True
    return None if any(r is None for r in seen) else False


def evaluate(condition: Condition, values: Values) -> bool | None:
    """True or False where the values decide the condition; None where they leave it unknown. A malformed node
    is unknown: check() reports it, and evaluation fails closed on it."""
    groups, subjects, operators = (
        _present(condition, GROUPS),
        _present(condition, SUBJECTS),
        _present(condition, OPERATORS),
    )
    if groups:
        if len(groups) != 1 or subjects or operators:
            return None
        if condition.all is not None:
            return _all(evaluate(member, values) for member in condition.all)
        if condition.any is not None:
            return _any(evaluate(member, values) for member in condition.any)
        inner = evaluate(condition.not_, values) if condition.not_ is not None else None
        return None if inner is None else not inner
    if len(subjects) != 1 or len(operators) != 1:
        return None
    kind, operator = subjects[0], operators[0]
    subject = values.get((kind, _get(condition, kind)), _UNKNOWN)
    operands = [_value(o, values) for o in _operands(condition, operator)]
    if operator == "between":
        return _all([_compare("ge", subject, operands[0]), _compare("le", subject, operands[1])])
    if operator == "in":
        return _any(_compare("eq", subject, operand) for operand in operands)
    return _compare(operator, subject, operands[0])


def holds(condition: Condition, values: Values) -> bool:
    """Whether the condition is known to hold; unknown counts as not holding."""
    return evaluate(condition, values) is True
