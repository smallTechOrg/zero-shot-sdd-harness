"""Phase-1 backend-agent slice tests.

These exercise the LangGraph capability slot (load_profile → build_prompt →
answer → finalize, with the handle_error sink) and the ``run_agent`` runner.

- The end-to-end grounded-answer test hits the REAL Gemini API (key from .env).
  It skips ONLY if no Gemini key is present — never stubs as the default.
- The boundary test needs no LLM: it asserts the prompt built by ``build_prompt``
  contains no raw data row / DataFrame repr — only derived profile fields. This is
  the privacy dealbreaker proof.
- The graceful-failure test proves an unknown dataset yields a ``failed`` RunRow
  with human-readable copy and no exception escaping the runner.
"""

import io

import pandas as pd
import pytest
from sqlalchemy.orm import Session

from datasets.store import save_dataset
from datasets.profiler import build_profile
from db import session as session_module
from db.models import RunRow


# --------------------------------------------------------------------------- #
# Fixture: a frame where the FULL-DATA groupby-sum disagrees with a naive
# per-row / sampled view, so a passing answer proves real whole-file computation.
# --------------------------------------------------------------------------- #
_REGIONS = ["North", "South", "East", "West", "Central"]


def _make_skewed_sales_df() -> pd.DataFrame:
    """≥200 rows, ≥5 regions, engineered so the highest *total* revenue region
    is NOT the region with the highest individual rows.

    "South" gets the single largest per-row values (so any per-row / top-of-file
    sample would name South), but it appears rarely. "North" has modest per-row
    values yet appears far more often, so its TOTAL dominates. Only a full-data
    groupby-sum gets the right answer.
    """
    rows: list[dict] = []

    # North: 150 rows of modest revenue → large total.
    for i in range(150):
        rows.append({"region": "North", "revenue": 100.0 + (i % 5), "units": (i % 4) + 1})

    # South: 10 rows of very large revenue → small total despite biggest rows.
    for i in range(10):
        rows.append({"region": "South", "revenue": 900.0 + (i % 5), "units": (i % 4) + 1})

    # The remaining regions: small filler so there are >= 5 categories.
    filler = ["East", "West", "Central"]
    for i in range(60):
        region = filler[i % len(filler)]
        rows.append({"region": region, "revenue": 120.0 + (i % 7), "units": (i % 4) + 1})

    return pd.DataFrame(rows)


@pytest.fixture
def skewed_sales_id() -> str:
    """Save the skewed sales frame via the store and return its dataset_id."""
    df = _make_skewed_sales_df()
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    row = save_dataset(buf.getvalue().encode("utf-8"), "skewed_sales.csv")
    return row.id


@pytest.fixture
def skewed_sales_df() -> pd.DataFrame:
    return _make_skewed_sales_df()


def _require_gemini() -> None:
    from config.settings import get_settings

    if not get_settings().gemini_api_key:
        pytest.skip("No Gemini key set in .env (AGENT_GEMINI_API_KEY)")


# --------------------------------------------------------------------------- #
# WC-style fixture: a high-cardinality, multi-role entity dataset where each
# row is a match with two team columns + two score columns. The per-team
# goals-per-match metric (a derived cross-column ratio over a multi-role union)
# is ONLY computable by unioning (team1,score1) with (team2,score2) locally.
# Engineered so "Hungary" is the clear top average (>= 3 matches), mirroring the
# real World-Cup outcome.
# --------------------------------------------------------------------------- #
def _make_worldcup_df() -> pd.DataFrame:
    """Build a match-level frame with high-cardinality team columns where the
    per-team goals-per-match leader (min 3 matches) is unambiguously Hungary.

    goals(team)   = sum(score1 where team1==team) + sum(score2 where team2==team)
    matches(team) = count of rows where team appears as team1 OR team2
    gpm(team)     = goals / matches  (rank only teams with matches >= 3)
    """
    rows: list[dict] = []

    def match(t1, s1, s2, t2):
        rows.append({"team1": t1, "score1": s1, "score2": s2, "team2": t2})

    # Hungary: 4 matches, very high scoring → highest goals-per-match.
    # As team1: 6, 5, 4 ; as team2: 5 (score2). goals = 6+5+4+5 = 20, matches = 4 → 5.0
    match("Hungary", 6, 0, "Norway")
    match("Hungary", 5, 1, "Iceland")
    match("Hungary", 4, 2, "Wales")
    match("Brazil", 1, 5, "Hungary")

    # Bulgaria: 3 matches, strong but below Hungary. goals = 4+3+4 = 11, matches 3 → ~3.67
    match("Bulgaria", 4, 1, "Norway")
    match("Bulgaria", 3, 1, "Iceland")
    match("Wales", 0, 4, "Bulgaria")

    # Brazil: several modest matches → moderate average, well below Hungary.
    # already 1 above (the Brazil-Hungary match: score1=1 for Brazil)
    match("Brazil", 2, 1, "Norway")
    match("Brazil", 2, 0, "Iceland")
    match("Wales", 1, 2, "Brazil")  # Brazil score2 = 2
    # Brazil goals = 1 + 2 + 2 + 2 = 7, matches = 4 → 1.75

    # Germany: steady but lower per-match average.
    match("Germany", 2, 1, "Norway")
    match("Germany", 2, 2, "Iceland")
    match("Wales", 1, 2, "Germany")  # Germany score2 = 2
    # Germany goals = 2 + 2 + 2 = 6, matches = 3 → 2.0

    # A spread of additional distinct teams to push cardinality high (>25) and
    # ensure top-N truncation is exercised. Each plays >= 3 low-scoring matches
    # so none threatens Hungary's average.
    extra_teams = [f"Team{i:02d}" for i in range(30)]
    for t in extra_teams:
        match(t, 0, 0, "Norway")
        match(t, 1, 0, "Iceland")
        match("Wales", 0, 0, t)
        # each extra team: goals = 0 + 1 + 0 = 1, matches = 3 → 0.33

    return pd.DataFrame(rows)


def _expected_top_team(df: pd.DataFrame, min_matches: int = 3) -> str:
    """Compute the per-team goals-per-match leader LOCALLY with pandas."""
    teams = pd.unique(pd.concat([df["team1"], df["team2"]]).dropna())
    records = []
    for team in teams:
        as1 = df[df["team1"] == team]
        as2 = df[df["team2"] == team]
        goals = float(as1["score1"].sum()) + float(as2["score2"].sum())
        matches = int(len(as1) + len(as2))
        if matches >= min_matches:
            records.append((team, goals / matches))
    records.sort(key=lambda r: r[1], reverse=True)
    return str(records[0][0])


@pytest.fixture
def worldcup_id() -> str:
    df = _make_worldcup_df()
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    row = save_dataset(buf.getvalue().encode("utf-8"), "worldcup.csv")
    return row.id


@pytest.fixture
def worldcup_df() -> pd.DataFrame:
    return _make_worldcup_df()


# --------------------------------------------------------------------------- #
# 1. End-to-end grounded answer against REAL Gemini.
# --------------------------------------------------------------------------- #
def test_run_agent_names_highest_total_revenue_region(skewed_sales_id, skewed_sales_df):
    _require_gemini()
    from graph.runner import run_agent

    # The correct answer can ONLY come from a full-data groupby-sum.
    totals = skewed_sales_df.groupby("region")["revenue"].sum()
    expected_region = str(totals.idxmax())
    # Sanity: the per-row-max region differs from the full-total-max region,
    # so the fixture genuinely forces whole-file computation.
    naive_region = str(skewed_sales_df.loc[skewed_sales_df["revenue"].idxmax(), "region"])
    assert expected_region != naive_region

    run_id = run_agent(skewed_sales_id, "Which region has the highest total revenue?")
    assert run_id

    with Session(session_module._engine) as s:
        run = s.get(RunRow, run_id)

    assert run is not None
    assert run.status == "completed", f"run failed: {run.error_message}"
    assert run.error_message is None
    assert run.output_text and run.output_text.strip()
    assert run.dataset_id == skewed_sales_id
    assert run.input_text == "Which region has the highest total revenue?"

    # The grounded answer must NAME the full-data winner (case-insensitive).
    assert expected_region.lower() in run.output_text.lower(), (
        f"expected {expected_region!r} in answer, got: {run.output_text!r}"
    )


# --------------------------------------------------------------------------- #
# 2. Boundary assertion — build_prompt leaks no raw rows (no LLM needed).
# --------------------------------------------------------------------------- #
def test_build_prompt_contains_no_raw_rows(skewed_sales_id, skewed_sales_df):
    from graph.nodes import load_profile, build_prompt

    state = {
        "run_id": "test-run",
        "dataset_id": skewed_sales_id,
        "question": "Which region has the highest total revenue?",
        "error": None,
    }
    state = {**state, **load_profile(state)}
    assert state.get("error") is None
    assert state.get("profile")

    state = {**state, **build_prompt(state)}
    assert state.get("error") is None
    prompt = state["prompt"]
    assert isinstance(prompt, str) and prompt

    # The question must be present (it crosses the boundary by design).
    assert "highest total revenue" in prompt.lower()

    # No full raw data row may appear verbatim in the prompt.
    for i in range(len(skewed_sales_df)):
        full_row = ",".join(str(v) for v in skewed_sales_df.iloc[i].tolist())
        assert full_row not in prompt, f"raw row {i} leaked into prompt"

    # No full column may leak either.
    full_revenue_col = ",".join(str(v) for v in skewed_sales_df["revenue"].tolist())
    assert full_revenue_col not in prompt

    # The raw DataFrame repr must be absent.
    assert skewed_sales_df.to_string() not in prompt
    assert "DataFrame" not in prompt


# --------------------------------------------------------------------------- #
# 3. Graceful failure — unknown dataset, no exception escapes the runner.
# --------------------------------------------------------------------------- #
def test_run_agent_unknown_dataset_fails_gracefully():
    from graph.runner import run_agent

    run_id = run_agent("nonexistent-id", "anything at all?")
    assert run_id

    with Session(session_module._engine) as s:
        run = s.get(RunRow, run_id)

    assert run is not None
    assert run.status == "failed"
    assert run.output_text is None
    assert run.error_message and isinstance(run.error_message, str)
    assert "Traceback" not in run.error_message


# --------------------------------------------------------------------------- #
# 4. Edge: an average question stays grounded in the profile (REAL Gemini).
# --------------------------------------------------------------------------- #
def test_run_agent_answers_average_question(skewed_sales_id, skewed_sales_df):
    _require_gemini()
    from graph.runner import run_agent

    mean_units = float(skewed_sales_df["units"].mean())

    run_id = run_agent(skewed_sales_id, "What is the average number of units?")
    with Session(session_module._engine) as s:
        run = s.get(RunRow, run_id)

    assert run.status == "completed", f"run failed: {run.error_message}"
    assert run.output_text and run.output_text.strip()
    # The mean is small (~2.5); assert the rounded integer or one-decimal form
    # appears, proving grounding in the real profile statistic.
    candidates = {
        str(round(mean_units)),
        f"{mean_units:.1f}",
        f"{mean_units:.2f}",
    }
    assert any(c in run.output_text for c in candidates), (
        f"expected one of {candidates} in answer, got: {run.output_text!r}"
    )


# --------------------------------------------------------------------------- #
# 5. Multi-role / high-cardinality / derived-ratio: per-team goals-per-match
#    over a WC-style fixture (REAL Gemini). Proves the union + ratio aggregates
#    reach the model and that a high-cardinality grouping key is NOT dropped.
# --------------------------------------------------------------------------- #
def test_run_agent_names_best_average_goals_per_match_team(worldcup_id, worldcup_df):
    _require_gemini()
    from graph.runner import run_agent

    expected_team = _expected_top_team(worldcup_df, min_matches=3)
    # Sanity: the fixture really is high-cardinality (many distinct teams), so a
    # cap that excluded whole columns would have dropped team1/team2 entirely.
    n_distinct = int(pd.concat([worldcup_df["team1"], worldcup_df["team2"]]).nunique())
    assert n_distinct > 25, f"fixture not high-cardinality enough: {n_distinct} teams"

    run_id = run_agent(
        worldcup_id, "which teams have the best average goals per match?"
    )
    assert run_id

    with Session(session_module._engine) as s:
        run = s.get(RunRow, run_id)

    assert run is not None
    assert run.status == "completed", f"run failed: {run.error_message}"
    assert run.error_message is None
    assert run.output_text and run.output_text.strip()

    # The grounded answer must NAME the locally-correct leader (case-insensitive).
    assert expected_team.lower() in run.output_text.lower(), (
        f"expected {expected_team!r} in answer, got: {run.output_text!r}"
    )


# --------------------------------------------------------------------------- #
# 6. Boundary re-assert for the new aggregates: even with the WC fixture (whose
#    profile now carries derived group + entity-union blocks), build_prompt must
#    leak NO full raw row and NO full column — only derived scalars cross.
# --------------------------------------------------------------------------- #
def test_build_prompt_worldcup_contains_no_raw_rows(worldcup_id, worldcup_df):
    from graph.nodes import load_profile, build_prompt

    state = {
        "run_id": "test-run-wc",
        "dataset_id": worldcup_id,
        "question": "which teams have the best average goals per match?",
        "error": None,
    }
    state = {**state, **load_profile(state)}
    assert state.get("error") is None
    assert state.get("profile")

    # The new derived blocks must be present (the fix is in scope, not empty).
    aggs = state["profile"].get("group_aggregates")
    assert isinstance(aggs, dict) and aggs
    assert aggs.get("entity_unions"), "expected a derived entity-union block for WC fixture"

    state = {**state, **build_prompt(state)}
    assert state.get("error") is None
    prompt = state["prompt"]
    assert isinstance(prompt, str) and prompt

    # No full raw data row may appear verbatim in the prompt.
    for i in range(len(worldcup_df)):
        full_row = ",".join(str(v) for v in worldcup_df.iloc[i].tolist())
        assert full_row not in prompt, f"raw row {i} leaked into prompt"

    # No full column may leak either (the score/team columns stay local).
    for col in ("team1", "team2", "score1", "score2"):
        full_col = ",".join(str(v) for v in worldcup_df[col].tolist())
        assert full_col not in prompt, f"full column {col!r} leaked into prompt"

    assert worldcup_df.to_string() not in prompt
    assert "DataFrame" not in prompt
