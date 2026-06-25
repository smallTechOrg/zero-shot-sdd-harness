"""Unit tests for single-level parsing + the optional Phase-B `capability` field."""
from data_analysis_agent.graph.execution import observation, parse_tool_call


def test_parse_free_sql_has_no_capability_key():
    call, err = parse_tool_call('{"tool": "s", "arguments": {"query": "SELECT 1"}}')
    assert err is None
    assert call == {"tool": "s", "arguments": {"query": "SELECT 1"}}   # byte-identical to Phase A


def test_parse_generated_tool_carries_capability():
    call, err = parse_tool_call('{"tool": "s", "capability": "top", "arguments": {"n": 1}}')
    assert err is None
    assert call["tool"] == "s" and call["capability"] == "top" and call["arguments"] == {"n": 1}


def test_parse_missing_tool_is_error():
    call, err = parse_tool_call('{"arguments": {}}')
    assert call is None and err is not None


def test_parse_bad_json_is_error():
    call, err = parse_tool_call("not json")
    assert call is None and err is not None


def test_observation_omits_capability_when_absent():
    assert observation("s", {"query": "SELECT 1"}, "r", False) == {
        "tool": "s", "arguments": {"query": "SELECT 1"}, "result": "r", "is_error": False
    }


def test_observation_includes_capability_when_present():
    entry = observation("s", {"n": 1}, "r", False, "top")
    assert entry["capability"] == "top"
