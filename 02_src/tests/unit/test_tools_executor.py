"""The executor keeps the four statuses apart, validates before dispatch, and stamps
evidence ids. Each test names the conformance requirement it pins."""
from __future__ import annotations

import pytest
from adii.contracts import ToolCall
from adii.tools import (
    Denied,
    Parameter,
    Rejected,
    ToolExecutor,
    ToolSpec,
    evidence_id,
    validate_arguments,
)

ECHO = ToolSpec(
    name="echo", description="returns what it was given",
    parameters=(Parameter("text", "string"),
                Parameter("times", "integer", required=False),
                Parameter("mode", "string", required=False, enum=("loud", "quiet"))))


def call(name: str = "echo", **arguments: object) -> ToolCall:
    return ToolCall(call_id="c1", name=name, arguments=arguments)


@pytest.fixture
def executor() -> ToolExecutor:
    ex = ToolExecutor()
    ex.register(ECHO, lambda text, times=1, mode="quiet": {"text": text * times, "mode": mode})
    return ex


class TestStatuses:
    def test_a_valid_call_executes_and_returns_ok(self, executor):
        result = executor.execute(call(text="hi", times=2))
        assert result.ok and result.content["text"] == "hihi"

    def test_an_unknown_tool_is_denied_without_reaching_any_handler(self):
        reached = []
        ex = ToolExecutor()
        ex.register(ECHO, lambda **kw: reached.append(kw) or {})
        result = ex.execute(call("delete_table", table="orders"))
        assert result.status == "DENIED"
        assert "delete_table" in result.content["error"]
        assert result.content["known_tools"] == ["echo"]
        assert reached == []

    def test_a1_a_wrong_typed_argument_is_rejected_not_a_crash(self, executor):
        result = executor.execute(call(text=123))
        assert result.status == "REJECTED"
        assert "'text' must be a string" in result.content["error"]

    def test_a_boolean_is_not_an_integer(self, executor):
        result = executor.execute(call(text="x", times=True))
        assert result.status == "REJECTED"

    def test_a_missing_required_argument_is_rejected_with_its_name(self, executor):
        result = executor.execute(call())
        assert result.status == "REJECTED"
        assert "missing required argument 'text'" in result.content["error"]

    def test_an_unknown_argument_is_rejected_and_the_accepted_ones_named(self, executor):
        result = executor.execute(call(text="x", tabel="orders"))
        assert result.status == "REJECTED"
        assert "unknown argument 'tabel'" in result.content["error"]
        assert "mode" in result.content["error"]

    def test_an_enum_violation_is_rejected(self, executor):
        result = executor.execute(call(text="x", mode="shouty"))
        assert result.status == "REJECTED"
        assert "loud" in result.content["error"]

    def test_b1_a_handler_that_refuses_is_denied(self):
        ex = ToolExecutor()
        ex.register(ECHO, lambda **kw: (_ for _ in ()).throw(Denied("outside scope")))
        result = ex.execute(call(text="x"))
        assert result.status == "DENIED" and result.content["error"] == "outside scope"

    def test_b1_a_handler_that_pushes_back_is_rejected(self):
        ex = ToolExecutor()
        ex.register(ECHO, lambda **kw: (_ for _ in ()).throw(Rejected("no such thing")))
        result = ex.execute(call(text="x"))
        assert result.status == "REJECTED" and result.content["error"] == "no such thing"

    def test_b1_a_handler_that_breaks_is_our_error_not_the_models(self):
        ex = ToolExecutor()
        ex.register(ECHO, lambda **kw: 1 / 0)
        result = ex.execute(call(text="x"))
        assert result.status == "ERROR"
        assert result.content["error"].startswith("ZeroDivisionError")

    def test_a_handler_returning_a_non_object_is_our_error(self):
        ex = ToolExecutor()
        ex.register(ECHO, lambda **kw: "just a string")
        assert ex.execute(call(text="x")).status == "ERROR"

    def test_d3_a_handler_returning_non_json_is_our_error(self):
        ex = ToolExecutor()
        ex.register(ECHO, lambda **kw: {"cost": float("nan")})
        result = ex.execute(call(text="x"))
        assert result.status == "ERROR" and "strict JSON" in result.content["error"]


class TestEvidence:
    def test_every_ok_observation_carries_an_evidence_id(self, executor):
        result = executor.execute(call(text="x"))
        assert result.content["evidence_id"].startswith("ev-")

    def test_the_same_observation_gets_the_same_id(self, executor):
        first = executor.execute(call(text="x")).content["evidence_id"]
        second = executor.execute(call(text="x")).content["evidence_id"]
        assert first == second

    def test_a_different_observation_gets_a_different_id(self, executor):
        first = executor.execute(call(text="x")).content["evidence_id"]
        second = executor.execute(call(text="y")).content["evidence_id"]
        assert first != second

    def test_the_id_depends_on_content_not_only_arguments(self):
        one = evidence_id("t", {"a": 1}, {"rows": [1]})
        two = evidence_id("t", {"a": 1}, {"rows": [2]})
        assert one != two

    def test_refusals_carry_no_evidence_id(self, executor):
        assert "evidence_id" not in executor.execute(call(text=1)).content


class TestBudget:
    def test_a_spent_budget_is_denied_not_an_error(self):
        ex = ToolExecutor(max_calls=1)
        ex.register(ECHO, lambda **kw: {})
        assert ex.execute(call(text="x")).status == "OK"
        second = ex.execute(call(text="x"))
        assert second.status == "DENIED" and "budget" in second.content["error"]

    def test_rejected_arguments_do_not_consume_the_budget(self):
        ex = ToolExecutor(max_calls=1)
        ex.register(ECHO, lambda **kw: {})
        assert ex.execute(call(text=1)).status == "REJECTED"
        assert ex.execute(call(text="x")).status == "OK"

    @pytest.mark.parametrize("bad", [-1, True, 1.5, float("nan"), "3"])
    def test_a6_a7_a_bound_that_would_be_silently_disabled_is_refused(self, bad):
        with pytest.raises(ValueError):
            ToolExecutor(max_calls=bad)

    def test_zero_means_every_call_is_denied(self):
        ex = ToolExecutor(max_calls=0)
        ex.register(ECHO, lambda **kw: {})
        assert ex.execute(call(text="x")).status == "DENIED"


class TestRegistration:
    def test_a3_a_schema_form_that_cannot_be_validated_is_refused(self):
        with pytest.raises(ValueError, match="cannot"):
            Parameter("filters", "object")
        with pytest.raises(ValueError, match="cannot"):
            Parameter("ids", "array")

    @pytest.mark.parametrize("name", ["path", "file_path", "filename", "directory", "url"])
    def test_b3_a_parameter_that_looks_like_a_path_is_refused(self, name):
        with pytest.raises(ValueError, match="path"):
            Parameter(name, "string")

    def test_an_enum_must_match_its_own_type(self):
        with pytest.raises(ValueError):
            Parameter("n", "integer", enum=("one",))

    def test_a_duplicate_parameter_is_refused(self):
        with pytest.raises(ValueError, match="twice"):
            ToolSpec("t", "d", (Parameter("a", "string"), Parameter("a", "string")))

    def test_a_tool_must_describe_itself(self):
        with pytest.raises(ValueError):
            ToolSpec("t", "   ")

    def test_registering_the_same_name_twice_is_refused(self, executor):
        with pytest.raises(ValueError, match="already"):
            executor.register(ECHO, lambda **kw: {})

    def test_what_is_advertised_is_what_is_enforced(self, executor):
        [schema] = executor.advertised()
        assert schema["name"] == "echo"
        params = schema["parameters"]
        assert params["required"] == ["text"]
        assert params["additionalProperties"] is False
        assert params["properties"]["mode"]["enum"] == ["loud", "quiet"]
        assert set(params["properties"]) == {"text", "times", "mode"}
        assert validate_arguments(ECHO, {"text": "x"}) == []
