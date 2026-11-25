"""Work item 0.3: the condition evaluator, with property tests over generated condition trees for the
structure, the declared operands, the depth limit and the results."""

from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st
from u6g.cond import DEFAULT_MAX_DEPTH, SUBJECTS, Declared, check, depth, evaluate, holds, parse

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTOR = yaml.safe_load((ROOT / "examples/contracts/descriptor/link-assurance.yaml").read_text())

DECLARED = Declared(
    metric=frozenset({"rsl", "link-state", "capacity", "modulation"}),
    feature=frozenset({"rain-rate-mm-h", "rsl-dbm-mean-10s"}),
    param=frozenset({"minCapacityMbps", "risk_threshold"}),
    attribute=frozenset({"tier"}),
)
NAMES = {kind: sorted(getattr(DECLARED, kind)) for kind in SUBJECTS}
KEYS = [(kind, name) for kind in SUBJECTS for name in NAMES[kind]]


# The conditions of the descriptor of guide Annex B


def test_precondition_of_an_action_type() -> None:
    pre = parse(DESCRIPTOR["actionSpace"][0]["preconditions"][0])
    assert check(pre, DECLARED) == []
    assert evaluate(pre, {("metric", "link-state"): "up"}) is True
    assert evaluate(pre, {("metric", "link-state"): "down"}) is False
    assert evaluate(pre, {}) is None
    assert not holds(pre, {})


def test_constraint_reads_a_parameter() -> None:
    constraint = parse(DESCRIPTOR["functions"]["de"]["constraints"][0])
    assert constraint.id == "min-capacity"
    assert check(constraint, DECLARED) == []
    params = {("param", "minCapacityMbps"): 400}
    assert evaluate(constraint, {("metric", "capacity"): 450.0, **params}) is True
    assert evaluate(constraint, {("metric", "capacity"): 350, **params}) is False
    assert evaluate(constraint, {("metric", "capacity"): 450.0}) is None


def test_validity_condition_of_a_model() -> None:
    validity = parse(DESCRIPTOR["modelHooks"][0]["validity"])
    assert check(validity, DECLARED) == []
    rain, rsl = ("feature", "rain-rate-mm-h"), ("feature", "rsl-dbm-mean-10s")
    assert evaluate(validity, {rain: 12, rsl: -41.7}) is True
    assert evaluate(validity, {rain: 95, rsl: -41.7}) is False
    assert evaluate(validity, {rain: 12, rsl: -80}) is False
    assert evaluate(validity, {rain: 95}) is False, "a known member decides the group"
    assert evaluate(validity, {rain: 12}) is None


# Structure, operands and types


@pytest.mark.parametrize(
    ("condition", "pointer", "rule"),
    [
        ({"metric": "rsl", "feature": "rsl-dbm-mean-10s", "lt": 1}, "", "structure"),
        ({"metric": "rsl", "lt": 1, "gt": 0}, "", "structure"),
        ({"metric": "rsl"}, "", "structure"),
        ({"all": [{"metric": "rsl", "lt": 1}], "any": [{"metric": "rsl", "gt": 0}]}, "", "structure"),
        ({"all": [{"metric": "rsl", "lt": 1}], "metric": "rsl"}, "", "structure"),
        ({"all": [{"id": "inner", "metric": "rsl", "lt": 1}]}, "/all/0/id", "structure"),
        ({"metric": "snr", "lt": 1}, "/metric", "operand"),
        ({"metric": "capacity", "ge": {"param": "maxCapacity"}}, "/ge/param", "operand"),
        ({"metric": "rsl", "lt": "low"}, "/lt", "type"),
        ({"metric": "rsl", "le": True}, "/le", "type"),
        ({"metric": "rsl", "between": [-25, -75]}, "/between", "type"),
        ({"not": {"not": {"not": {"not": {"metric": "rsl", "lt": 1}}}}}, "", "depth"),
    ],
)
def test_check_reports_the_breach(condition: dict[str, Any], pointer: str, rule: str) -> None:
    found = check(parse(condition), DECLARED)
    assert (pointer, rule) in [(v.pointer, v.rule) for v in found]


def test_malformed_nodes_evaluate_to_unknown() -> None:
    assert (
        evaluate(parse({"metric": "rsl", "feature": "rsl-dbm-mean-10s", "lt": 1}), {("metric", "rsl"): 0})
        is None
    )
    assert (
        evaluate(parse({"all": [{"metric": "rsl", "lt": 1}], "metric": "rsl"}), {("metric", "rsl"): 0})
        is None
    )


def test_booleans_and_numbers_are_different_values() -> None:
    flag = ("metric", "link-state")
    assert evaluate(parse({"metric": "link-state", "eq": 1}), {flag: True}) is False
    assert evaluate(parse({"metric": "link-state", "eq": True}), {flag: True}) is True
    assert evaluate(parse({"metric": "link-state", "lt": 1}), {flag: False}) is None


def test_unordered_values_are_unknown() -> None:
    assert evaluate(parse({"metric": "modulation", "gt": 2}), {("metric", "modulation"): "64QAM"}) is None


# Property tests over generated condition trees

numbers = st.integers(-100, 100) | st.floats(-100, 100, allow_nan=False, allow_infinity=False)
literals = numbers | st.sampled_from(["up", "down", "64QAM"]) | st.booleans()
refs = st.sampled_from(["param", "metric", "feature"]).flatmap(
    lambda kind: st.sampled_from(NAMES[kind]).map(lambda name: {kind: name})
)


@st.composite
def comparisons(draw: st.DrawFn) -> dict[str, Any]:
    kind = draw(st.sampled_from(SUBJECTS))
    node: dict[str, Any] = {kind: draw(st.sampled_from(NAMES[kind]))}
    operator = draw(st.sampled_from(["eq", "ne", "lt", "le", "gt", "ge", "between", "in"]))
    if operator in ("lt", "le", "gt", "ge"):
        node[operator] = draw(numbers | refs)
    elif operator == "between":
        low, high = sorted(draw(st.lists(numbers, min_size=2, max_size=2)))
        node[operator] = [low, high]
    elif operator == "in":
        node[operator] = draw(st.lists(literals | refs, min_size=1, max_size=3))
    else:
        node[operator] = draw(literals | refs)
    return node


def conditions(levels: int) -> st.SearchStrategy[dict[str, Any]]:
    if levels == 0:
        return comparisons()
    inner = conditions(levels - 1)
    return st.one_of(
        comparisons(),
        st.lists(inner, min_size=1, max_size=3).map(lambda xs: {"all": xs}),
        st.lists(inner, min_size=1, max_size=3).map(lambda xs: {"any": xs}),
        inner.map(lambda x: {"not": x}),
    )


values = st.fixed_dictionaries({}, optional={key: literals for key in KEYS})
full_values = st.fixed_dictionaries({key: literals for key in KEYS})


@pytest.mark.property
@settings(max_examples=300)
@given(conditions(DEFAULT_MAX_DEPTH))
def test_generated_conditions_are_well_formed(tree: dict[str, Any]) -> None:
    """[FW] 3.5.18 and 3.11: every condition follows the fixed structure for conditions."""
    condition = parse(tree)
    assert depth(condition) <= DEFAULT_MAX_DEPTH
    assert check(condition, DECLARED) == []


@pytest.mark.property
@settings(max_examples=200)
@given(conditions(DEFAULT_MAX_DEPTH))
def test_nesting_beyond_the_limit_is_reported(tree: dict[str, Any]) -> None:
    """[FW] 3.5.18: a condition stays within the permitted depth."""
    deeper: dict[str, Any] = tree
    while depth(parse(deeper)) <= DEFAULT_MAX_DEPTH:
        deeper = {"not": deeper}
    assert [v.rule for v in check(parse(deeper), DECLARED)] == ["depth"]
    assert check(parse(deeper), DECLARED, max_depth=depth(parse(deeper))) == []


def first_comparison(tree: dict[str, Any], pointer: str = "") -> tuple[dict[str, Any], str]:
    for key in ("all", "any"):
        if key in tree:
            return first_comparison(tree[key][0], f"{pointer}/{key}/0")
    if "not" in tree:
        return first_comparison(tree["not"], f"{pointer}/not")
    return tree, pointer


@pytest.mark.property
@settings(max_examples=200)
@given(conditions(DEFAULT_MAX_DEPTH))
def test_an_undeclared_operand_is_reported_where_it_is(tree: dict[str, Any]) -> None:
    """[FW] 3.5.18: a condition names only operands the descriptor declares."""
    leaf, pointer = first_comparison(tree)
    kind = next(k for k in SUBJECTS if k in leaf)
    leaf[kind] = "undeclared-name"
    found = [(v.pointer, v.rule) for v in check(parse(tree), DECLARED)]
    assert (f"{pointer}/{kind}", "operand") in found


@pytest.mark.property
@settings(max_examples=300)
@given(conditions(DEFAULT_MAX_DEPTH), full_values, st.sets(st.sampled_from(KEYS)))
def test_a_decided_result_stays_when_more_values_arrive(
    tree: dict[str, Any], full: dict[tuple[str, str], Any], missing: set[tuple[str, str]]
) -> None:
    """[FW] 5.3.1 and 6.9: validity conditions and constraints are evaluated by machine. A missing value
    leaves a comparison unknown, which fails closed; a result decided without it stays the same with it."""
    condition = parse(tree)
    partial = {key: value for key, value in full.items() if key not in missing}
    decided = evaluate(condition, partial)
    if decided is not None:
        assert evaluate(condition, full) is decided


@pytest.mark.property
@settings(max_examples=300)
@given(st.lists(conditions(2), min_size=1, max_size=3), values)
def test_negation_follows_de_morgan(members: list[dict[str, Any]], known: dict[tuple[str, str], Any]) -> None:
    """[FW] 3.11: a condition is evaluable without an interpreter; its groups keep their logic."""
    left = evaluate(parse({"not": {"all": members}}), known)
    right = evaluate(parse({"any": [{"not": m} for m in members]}), known)
    assert left is right
    left = evaluate(parse({"not": {"any": members}}), known)
    right = evaluate(parse({"all": [{"not": m} for m in members]}), known)
    assert left is right


@pytest.mark.property
@settings(max_examples=300)
@given(conditions(2), values)
def test_double_negation_and_singleton_groups_change_nothing(
    tree: dict[str, Any], known: dict[tuple[str, str], Any]
) -> None:
    """[FW] 3.11: a condition is evaluable without an interpreter; its groups keep their logic."""
    result = evaluate(parse(tree), known)
    assert evaluate(parse({"not": {"not": tree}}), known) is result
    assert evaluate(parse({"all": [tree]}), known) is result
    assert evaluate(parse({"any": [tree]}), known) is result


@pytest.mark.property
@settings(max_examples=300)
@given(numbers, numbers, numbers | st.none())
def test_between_is_the_pair_of_bounds(a: float, b: float, rsl: float | None) -> None:
    """[FW] 3.11: the operators keep one meaning; between is a pair of inclusive bounds."""
    low, high = sorted((a, b))
    known = {} if rsl is None else {("metric", "rsl"): rsl}
    between = evaluate(parse({"metric": "rsl", "between": [low, high]}), known)
    pair = evaluate(parse({"all": [{"metric": "rsl", "ge": low}, {"metric": "rsl", "le": high}]}), known)
    assert between is pair


@pytest.mark.property
@settings(max_examples=300)
@given(st.lists(literals, min_size=1, max_size=4), literals | st.none())
def test_in_is_a_choice_of_equalities(options: list[Any], state: Any) -> None:
    """[FW] 3.11: the operators keep one meaning; in is a choice of equalities."""
    known = {} if state is None else {("metric", "link-state"): state}
    member = evaluate(parse({"metric": "link-state", "in": options}), known)
    choice = evaluate(parse({"any": [{"metric": "link-state", "eq": o} for o in options]}), known)
    assert member is choice
