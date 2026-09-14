import pytest
from adii.contracts import ToolResult
from adii.investigator.provider import ScriptedProvider, ScriptExhaustedError


def test_same_script_produces_same_ordered_sequence_every_run():
    script = ["first response", "second response", "final response"]

    first_run = ScriptedProvider(script)
    second_run = ScriptedProvider(script)

    assert [first_run.respond() for _ in script] == script
    assert [second_run.respond() for _ in script] == script


def test_script_exhaustion_raises_named_error():
    provider = ScriptedProvider(["only response"])
    provider.respond()

    with pytest.raises(ScriptExhaustedError, match="no responses remaining"):
        provider.respond()


def test_empty_script_is_rejected_at_construction():
    with pytest.raises(ValueError, match="at least one response"):
        ScriptedProvider([])


def test_no_argument_call_records_none_observation():
    provider = ScriptedProvider(["response"])

    assert provider.respond() == "response"
    assert provider.received_observations == (None,)
    assert provider.received_context == ((),)


def test_observations_do_not_change_scripted_output_order():
    first_observation = ToolResult("call-1", "fake_tool", "OK", {"value": "first"})
    second_observation = ToolResult("call-2", "fake_tool", "DENIED", {"value": "second"})
    provider = ScriptedProvider(["first response", "second response"])

    assert (
        provider.respond(
            observation=first_observation,
            observations=(first_observation,),
        )
        == "first response"
    )
    assert (
        provider.respond(
            observation=second_observation,
            observations=(first_observation, second_observation),
        )
        == "second response"
    )
    assert provider.received_observations == (first_observation, second_observation)
    assert provider.received_context == (
        (first_observation,),
        (first_observation, second_observation),
    )


def test_received_observations_does_not_expose_mutable_internal_storage():
    provider = ScriptedProvider(["response"])
    provider.respond()

    observations = provider.received_observations
    observations += (ToolResult("call-1", "fake_tool", "OK"),)

    assert isinstance(provider.received_observations, tuple)
    assert provider.received_observations == (None,)


def test_received_context_does_not_expose_mutable_internal_storage():
    observation = ToolResult("call-1", "fake_tool", "OK")
    provider = ScriptedProvider(["response"])
    provider.respond(observations=(observation,))

    contexts = provider.received_context
    contexts += ((observation, observation),)

    assert isinstance(provider.received_context, tuple)
    assert provider.received_context == ((observation,),)
