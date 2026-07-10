"""Full-pipeline runs — real Gemini, tmp DB, real DXF/SVG artefacts on disk.

Needs all three backend slices (domain-engine, drawing, graph-llm); the drawing
guard skips with a precise reason while the sibling slice is still landing.
"""

import json
from pathlib import Path

import ezdxf

CANONICAL_PROMPT = (
    "single box culvert, 4 m clear span, 3 m height, 2.5 m cushion, "
    "BG single line, 25t loading"
)


def _params(row: dict) -> dict:
    assert row["params_json"], f"run {row['id']} has no params_json"
    return json.loads(row["params_json"])


def _steps(row: dict) -> dict:
    return {s["name"]: s["status"] for s in json.loads(row["steps_json"])}


def _artifact_dir(settings, run_id: str) -> Path:
    return Path(settings.artifacts_dir) / run_id


def test_canonical_prompt_completes_end_to_end(
    require_gemini, drawing_ready, make_session, run_and_wait, get_run,
    get_artifacts, _integration_settings,
):
    session_id = make_session()

    run_id, events = run_and_wait(session_id, CANONICAL_PROMPT)

    # Terminal event and persisted outcome
    assert events[-1]["event"] == "done", f"events: {[e['event'] for e in events]}"
    assert events[-1]["data"] == {"status": "completed", "verdict": None}
    row = get_run(run_id)
    assert row["status"] == "completed"

    # Extraction: the canonical parameters, exactly
    params = _params(row)
    assert params["clear_span_m"] == 4.0
    assert params["clear_height_m"] == 3.0
    assert params["cushion_m"] == 2.5
    assert params["gauge"] == "BG"
    assert params["loading_standard"] == "25t-2008"

    # Accounting: real tokens, real cost, real duration
    assert row["prompt_tokens"] > 0
    assert row["cost_usd"] > 0
    assert row["duration_ms"] > 0
    assert row["completed_at"] is not None

    # Step tracker persisted truthfully: stubs skipped, real steps done
    steps = _steps(row)
    assert steps["Understand"] == "done"
    assert steps["Extract"] == "done"
    assert steps["Analyse"] == "done"
    assert steps["Check"] == "skipped"
    assert steps["Draw"] == "done"
    assert steps["Review"] == "skipped"

    # Artefacts on disk: genuine DXF (audit-clean) + SVG
    art_dir = _artifact_dir(_integration_settings, run_id)
    dxf_path = art_dir / "ga.dxf"
    svg_path = art_dir / "ga.svg"
    assert dxf_path.exists() and dxf_path.stat().st_size > 0
    assert svg_path.exists() and svg_path.stat().st_size > 0
    auditor = ezdxf.readfile(dxf_path).audit()
    assert not auditor.has_errors, [str(e) for e in auditor.errors]

    # Artefact DB rows + SSE events with the API-contract URL shape
    artifacts = get_artifacts(run_id)
    assert {a["kind"] for a in artifacts} == {"ga_dxf", "ga_svg"}
    assert all(a["size_bytes"] > 0 for a in artifacts)
    artefact_events = [e["data"] for e in events if e["event"] == "artefact"]
    assert [a["kind"] for a in artefact_events] == ["ga_dxf", "ga_svg"]
    for data in artefact_events:
        assert data["url"] == f"/api/designs/{run_id}/artifacts/{data['filename']}"

    # The design plan streams before extraction completes
    event_kinds = [
        (e["event"], e["data"].get("step"), e["data"].get("status")) for e in events
    ]
    first_narration = next(i for i, e in enumerate(events) if e["event"] == "narration")
    extract_done = next(
        i for i, k in enumerate(event_kinds) if k == ("step", "Extract", "done")
    )
    assert first_narration < extract_done

    # Running token events after every LLM call, plus the finalize total
    token_events = [e["data"] for e in events if e["event"] == "tokens"]
    assert len(token_events) >= 3  # understand + extract + finalize
    assert token_events[-1]["cost_usd"] > 0
    assert token_events[-1]["session_total_cost_usd"] >= token_events[-1]["cost_usd"]


def test_refinement_turn_carries_params_forward_and_regenerates(
    require_gemini, drawing_ready, make_session, run_and_wait, get_run,
    _integration_settings,
):
    session_id = make_session()
    first_id, first_events = run_and_wait(session_id, CANONICAL_PROMPT)
    assert first_events[-1]["data"]["status"] == "completed"

    second_id, second_events = run_and_wait(session_id, "increase the fill to 4 m")

    assert second_events[-1]["data"] == {"status": "completed", "verdict": None}
    second = get_run(second_id)
    params = _params(second)
    assert params["cushion_m"] == 4.0            # the one named change
    assert params["clear_span_m"] == 4.0         # carried forward
    assert params["clear_height_m"] == 3.0       # carried forward

    # Full regeneration: the new run has its own artefacts on disk
    assert (_artifact_dir(_integration_settings, second_id) / "ga.dxf").exists()
    assert (_artifact_dir(_integration_settings, second_id) / "ga.svg").exists()

    # History intact: both runs keep their own params (audit trail)
    first = get_run(first_id)
    assert _params(first)["cushion_m"] == 2.5

    # Session cost total now spans both persisted runs
    final_tokens = [e["data"] for e in second_events if e["event"] == "tokens"][-1]
    assert final_tokens["session_total_cost_usd"] > final_tokens["cost_usd"]


def test_clarification_answer_completes_the_original_request(
    require_gemini, drawing_ready, make_session, run_and_wait, get_run,
    _integration_settings,
):
    session_id = make_session()
    first_id, first_events = run_and_wait(session_id, "box culvert 3 m height, 2 m cushion")
    assert first_events[-1]["data"]["status"] == "needs_input"

    second_id, second_events = run_and_wait(session_id, "4.5 m")

    assert second_events[-1]["data"] == {"status": "completed", "verdict": None}
    params = _params(get_run(second_id))
    assert params["clear_span_m"] == 4.5         # the answer
    assert params["clear_height_m"] == 3.0       # from the original request
    assert params["cushion_m"] == 2.0            # from the original request
    assert (_artifact_dir(_integration_settings, second_id) / "ga.dxf").exists()


def test_abnormally_high_cushion_is_flagged_and_run_proceeds(
    require_gemini, drawing_ready, make_session, run_and_wait, get_run,
    _integration_settings,
):
    session_id = make_session()

    run_id, events = run_and_wait(
        session_id, "box culvert 4000 mm clear span, 3 m height, 9 m cushion"
    )

    assert events[-1]["data"] == {"status": "completed", "verdict": None}
    row = get_run(run_id)
    params = _params(row)
    assert params["clear_span_m"] == 4.0         # mm → m conversion
    assert params["cushion_m"] == 9.0

    warning_events = [e["data"]["message"] for e in events if e["event"] == "warning"]
    assert any("ushion" in message for message in warning_events)
    warnings = json.loads(row["warnings_json"])
    assert any("ushion" in message for message in warnings)
    assert (_artifact_dir(_integration_settings, run_id) / "ga.dxf").exists()
