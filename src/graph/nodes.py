"""LangGraph capability nodes for the CSV-analysis agent.

Pipeline: load_profile -> build_prompt -> answer -> finalize, with a shared
handle_error sink. The privacy data boundary is enforced in ``build_prompt``,
which serializes ONLY the question + derived profile into the LLM prompt — the
raw DataFrame never enters graph state.
"""

import json
import re
import time
from pathlib import Path

import pandas as pd
from pandas.api import types as ptypes

from datasets.profiler import build_profile
from datasets.store import DatasetError, dataset_path
from graph.state import AgentState
from llm.client import LLMClient
from observability.events import get_logger

logger = get_logger("graph.nodes")

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "answer.md"

# Caps for the derived group aggregates that cross the boundary. These keep the
# prompt token-frugal and ensure no full column/row ever leaks — only DERIVED
# per-group scalars (sum/count/mean/ratio) cross. A grouping key is valid
# REGARDLESS of its cardinality: we bound the OUTPUT by emitting only the top-N
# groups by the relevant metric and flag truncation, rather than dropping the
# whole column. This is what lets high-cardinality keys (e.g. team1/team2) and
# multi-role entity unions reach the model.
_MAX_GROUP_COLS = 6          # categorical columns to break down by
_MAX_NUMERIC_COLS = 6        # numeric columns to aggregate
_MAX_GROUPS_PER_COL = 25     # top-N groups emitted per (cat, numeric) pair
_MAX_UNION_ENTITIES = 25     # top-N entities emitted per multi-role union
_MIN_MATCHES_FOR_RATIO = 3   # min appearances before a ratio ranking is trusted

# Hard ceiling on the single Gemini call so a hung request fails gracefully.
_ANSWER_TIMEOUT_S = 60.0

# Human-readable failure copy (never a stack trace) routed to handle_error.
_PROFILE_FAILURE_COPY = "Dataset not found or unreadable."
_PROMPT_FAILURE_COPY = "Could not prepare the question for analysis. Please try again."
_LLM_FAILURE_COPY = "Could not reach the analysis model — please retry."


def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8").strip()


def load_profile(state: AgentState) -> AgentState:
    """Re-profile the dataset's LOCAL CSV with pandas.

    Writes only the derived ``profile`` dict to state. The raw DataFrame stays
    inside ``build_profile`` and never reaches graph state — the local side of
    the privacy boundary.
    """
    dataset_id = state.get("dataset_id")
    try:
        profile = build_profile(dataset_id)
    except DatasetError as exc:
        logger.warning("load_profile_failed", dataset_id=dataset_id, error=str(exc))
        return {**state, "error": exc.message}
    except Exception as exc:  # noqa: BLE001 - surface as human copy, never a crash
        logger.error("load_profile_error", dataset_id=dataset_id, error=str(exc))
        return {**state, "error": _PROFILE_FAILURE_COPY}

    # Enrich the profile with bounded, DERIVED grouped aggregates computed
    # LOCALLY: per-(grouping key, numeric column) sum/count/mean/ratio for the
    # top-N groups, PLUS multi-role entity unions (per-entity totals, counts and
    # ratios like goals-per-match) when an entity recurs across paired role
    # columns. These are derived scalars — never raw rows — and are what let the
    # model answer group-by / "best average per X" / ratio / per-entity
    # questions over high-cardinality keys. The DataFrame stays local here and is
    # discarded when the function returns.
    try:
        profile = {**profile, "group_aggregates": _group_aggregates(dataset_id)}
    except Exception as exc:  # noqa: BLE001 - aggregates are best-effort, never fatal
        logger.warning("group_aggregates_failed", dataset_id=dataset_id, error=str(exc))

    logger.info(
        "load_profile",
        dataset_id=dataset_id,
        row_count=profile.get("row_count"),
        n_columns=len(profile.get("columns", [])),
    )
    return {**state, "profile": profile}


def _group_aggregates(dataset_id: str) -> dict:
    """Compute DERIVED, bounded grouped + multi-role-union aggregates LOCALLY.

    Returns a two-block dict::

        {
          "groups": {
            cat_col: {
              num_col: {
                "groups": {grp: {"sum", "count", "mean", "ratio"}},  # top-N by sum
                "total_groups": int,
                "truncated": bool,
                "metric": "sum",
              }
            }
          },
          "entity_unions": {
            union_name: {
              "role_columns": [...], "metric_columns": [...],
              "metric": "goals_per_match", "min_count_for_ranking": 3,
              "entities": {entity: {"total", "count", "ratio"}},  # top-N by ratio
              "total_entities": int, "truncated": bool,
            }
          },
        }

    A grouping key is valid REGARDLESS of cardinality — only the OUTPUT is capped
    to the top-N groups by the relevant metric, with a truncation marker so the
    model does not over-claim completeness. Only derived scalars cross the
    boundary; the raw DataFrame stays local and is discarded on return.
    """
    df = pd.read_csv(dataset_path(dataset_id))

    numeric_cols = [
        str(c)
        for c in df.columns
        if ptypes.is_numeric_dtype(df[c]) and not ptypes.is_bool_dtype(df[c])
    ][:_MAX_NUMERIC_COLS]

    # Any non-numeric column is a candidate grouping key — cardinality no longer
    # excludes it; we cap the emitted GROUPS instead. Cap only the NUMBER of
    # grouping columns to keep tokens bounded.
    cat_cols = [
        str(c)
        for c in df.columns
        if not (ptypes.is_numeric_dtype(df[c]) and not ptypes.is_bool_dtype(df[c]))
    ][:_MAX_GROUP_COLS]

    groups = _group_blocks(df, cat_cols, numeric_cols, dataset_id)
    unions = _entity_unions(df, dataset_id)

    return {"groups": groups, "entity_unions": unions}


def _group_blocks(
    df: pd.DataFrame,
    cat_cols: list[str],
    numeric_cols: list[str],
    dataset_id: str,
) -> dict:
    """Per-(grouping key, numeric column) derived stats for the top-N groups by sum.

    Emits sum/count/mean and the derived ratio (sum÷count == mean) per group, plus
    ``total_groups``/``truncated`` so the model knows when only the top-N are shown.
    """
    blocks: dict[str, dict] = {}
    for cat in cat_cols:
        per_numeric: dict[str, dict] = {}
        for num in numeric_cols:
            grouped = df.groupby(cat, dropna=True)[num]
            sums = grouped.sum()
            means = grouped.mean()
            counts = grouped.count()

            total_groups = int(len(sums))
            # Bound the OUTPUT: keep the top-N groups by sum (the usual "highest
            # total" question), never the whole high-cardinality column.
            top_index = sums.sort_values(ascending=False).index[:_MAX_GROUPS_PER_COL]
            truncated = total_groups > len(top_index)
            if truncated:
                logger.info(
                    "group_aggregates_truncated",
                    dataset_id=dataset_id,
                    column=cat,
                    numeric=num,
                    total_groups=total_groups,
                    kept=len(top_index),
                )

            per_group: dict[str, dict] = {}
            for group in top_index:
                cnt = int(counts[group])
                per_group[str(group)] = {
                    "sum": _round(sums[group]),
                    "count": cnt,
                    "mean": _round(means[group]),
                    "ratio": _round(means[group]),  # sum÷count
                }
            per_numeric[num] = {
                "groups": per_group,
                "total_groups": total_groups,
                "truncated": truncated,
                "metric": "sum",
            }
        if per_numeric:
            blocks[cat] = per_numeric
    return blocks


def _role_stem(name: str) -> tuple[str, str] | None:
    """Split a numbered/suffixed role column into ``(stem, suffix)``.

    ``team1`` -> ``("team", "1")``; ``score2`` -> ``("score", "2")``. Returns
    ``None`` for columns with no trailing number/role suffix.
    """
    m = re.match(r"^(.*?)[\s_-]*(\d+)$", str(name))
    if not m or not m.group(1):
        return None
    return m.group(1).lower(), m.group(2)


def _entity_unions(df: pd.DataFrame, dataset_id: str) -> dict:
    """Detect entities that recur across paired role columns and union them locally.

    Generic detection: a categorical "entity" stem (e.g. ``team`` from
    ``team1``/``team2``) is paired POSITIONALLY by suffix with a numeric "metric"
    stem (e.g. ``score`` from ``score1``/``score2``). For each entity we emit:

      - ``total``  = Σ metric where the entity appears in any role column
      - ``count``  = number of appearances across all role columns (matches played)
      - ``ratio``  = total ÷ count (e.g. goals-per-match)

    capped to the top-N entities by ratio (among those at/above the min-count
    threshold) with a truncation marker. Empty when no multi-role pairs exist
    (e.g. the region/revenue fixture), so this block is harmless there.
    """
    # Group columns by (stem -> {suffix: column}) for both entity (non-numeric)
    # and metric (numeric) candidates.
    entity_stems: dict[str, dict[str, str]] = {}
    metric_stems: dict[str, dict[str, str]] = {}
    for col in df.columns:
        parsed = _role_stem(col)
        if parsed is None:
            continue
        stem, suffix = parsed
        is_numeric = ptypes.is_numeric_dtype(df[col]) and not ptypes.is_bool_dtype(df[col])
        bucket = metric_stems if is_numeric else entity_stems
        bucket.setdefault(stem, {})[suffix] = str(col)

    unions: dict[str, dict] = {}
    for ent_stem, ent_cols in entity_stems.items():
        if len(ent_cols) < 2:
            continue  # needs at least two role columns to be "multi-role"
        # Find a metric stem whose suffixes positionally match the entity's.
        match_metric = None
        for met_stem, met_cols in metric_stems.items():
            if set(ent_cols).issubset(set(met_cols)):
                match_metric = (met_stem, met_cols)
                break
        if match_metric is None:
            continue
        met_stem, met_cols = match_metric

        # Union per entity across all shared role suffixes.
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for suffix, ent_col in ent_cols.items():
            met_col = met_cols[suffix]
            sub = df[[ent_col, met_col]].dropna(subset=[ent_col])
            grp = sub.groupby(ent_col)[met_col]
            for entity, total in grp.sum().items():
                key = str(entity)
                totals[key] = totals.get(key, 0.0) + float(total)
            for entity, cnt in grp.count().items():
                key = str(entity)
                counts[key] = counts.get(key, 0) + int(cnt)

        # Build per-entity derived records. Entities below the min-count threshold
        # are still emitted (flagged), but ranking uses only those at/above it.
        records: list[tuple[str, float, int, float]] = []
        for entity, total in totals.items():
            cnt = counts.get(entity, 0)
            ratio = (total / cnt) if cnt else None
            records.append((entity, total, cnt, ratio if ratio is not None else -1.0))

        # Rank by ratio among entities meeting the min-count threshold; emit the
        # top-N of those (the answerable set for "best average per entity").
        eligible = [r for r in records if r[2] >= _MIN_MATCHES_FOR_RATIO]
        eligible.sort(key=lambda r: r[3], reverse=True)
        total_entities = len(eligible)
        kept = eligible[:_MAX_UNION_ENTITIES]
        truncated = total_entities > len(kept)
        if truncated:
            logger.info(
                "entity_union_truncated",
                dataset_id=dataset_id,
                entity=ent_stem,
                metric=met_stem,
                total_entities=total_entities,
                kept=len(kept),
            )

        entities: dict[str, dict] = {}
        for entity, total, cnt, ratio in kept:
            entities[entity] = {
                "total": _round(total),
                "count": cnt,
                "ratio": _round(ratio),
            }

        if not entities:
            continue

        union_name = f"per_{ent_stem}_{met_stem}"
        unions[union_name] = {
            "role_columns": [ent_cols[s] for s in sorted(ent_cols)],
            "metric_columns": [met_cols[s] for s in sorted(ent_cols)],
            "metric": f"{met_stem}_per_{ent_stem}",
            "min_count_for_ranking": _MIN_MATCHES_FOR_RATIO,
            "entities": entities,
            "total_entities": total_entities,
            "truncated": truncated,
            "note": (
                f"Each {ent_stem} unioned across {sorted(ent_cols.values())}; "
                f"total={met_stem} summed, count=appearances, "
                f"ratio={met_stem} per {ent_stem}. Ranked by ratio over "
                f"{ent_stem}s with at least {_MIN_MATCHES_FOR_RATIO} appearances."
            ),
        }
    return unions


def _round(value: object) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return round(f, 4)


def build_prompt(state: AgentState) -> AgentState:
    """Serialize ONLY ``{question, profile}`` into the LLM user prompt.

    THE BOUNDARY-ENFORCEMENT NODE: it provably constructs the LLM input from the
    derived profile alone — never the raw rows or the DataFrame. A test asserts no
    full data row appears in the resulting ``prompt``.
    """
    try:
        payload = {
            "question": state.get("question"),
            "profile": state.get("profile"),
        }
        # Compact JSON keeps tokens (and cost) low; the profile is already capped
        # to schema + summary stats + <=5 truncated examples by the profiler.
        prompt = json.dumps(payload, separators=(",", ":"), default=str)
    except Exception as exc:  # noqa: BLE001
        logger.error("build_prompt_failed", error=str(exc))
        return {**state, "error": _PROMPT_FAILURE_COPY}

    logger.info("build_prompt", prompt_len=len(prompt))
    return {**state, "prompt": prompt}


def answer(state: AgentState) -> AgentState:
    """The single Gemini call — sends the boundary-safe prompt, stores the answer.

    Wrapped with a timeout + try/except; any failure sets ``error`` and routes to
    handle_error. Logs model + prompt length + latency + completion length — never
    raw rows or the API key.
    """
    prompt = state.get("prompt", "")
    system = _load_system_prompt()
    started = time.monotonic()

    try:
        result = _call_with_timeout(prompt, system, _ANSWER_TIMEOUT_S)
    except TimeoutError as exc:
        logger.error("answer_timeout", error=str(exc), timeout_s=_ANSWER_TIMEOUT_S)
        return {**state, "error": _LLM_FAILURE_COPY}
    except Exception as exc:  # noqa: BLE001 - graceful failure, never a stack trace
        logger.error("answer_failed", error=str(exc))
        return {**state, "error": _LLM_FAILURE_COPY}

    latency_ms = int((time.monotonic() - started) * 1000)

    if not result or not result.strip():
        logger.error("answer_empty", latency_ms=latency_ms)
        return {**state, "error": _LLM_FAILURE_COPY}

    logger.info(
        "answer",
        model=_resolved_model(),
        prompt_len=len(prompt),
        latency_ms=latency_ms,
        completion_len=len(result),
    )
    return {**state, "answer": result.strip()}


def _resolved_model() -> str:
    """The model the provider will ACTUALLY use, for honest observability.

    ``AGENT_LLM_MODEL`` is blank in ``.env`` for this project, so logging the raw
    setting prints a misleading "default". Resolve the real effective model: the
    configured value when set, otherwise the active provider's default (Gemini's
    ``gemini-2.5-flash``). Never logs a secret — only the model name.
    """
    from config.settings import get_settings

    settings = get_settings()
    if settings.llm_model:
        return settings.llm_model

    provider = settings.llm_provider
    if not provider:
        provider = "gemini" if settings.gemini_api_key else (
            "anthropic" if settings.anthropic_api_key else ""
        )
    if provider == "gemini":
        from llm.providers.gemini import GeminiProvider

        return GeminiProvider.DEFAULT_MODEL
    if provider == "anthropic":
        try:
            from llm.providers.anthropic import AnthropicProvider

            return getattr(AnthropicProvider, "DEFAULT_MODEL", "anthropic-default")
        except Exception:  # noqa: BLE001
            return "anthropic-default"
    return "unknown"


def _call_with_timeout(prompt: str, system: str, timeout_s: float) -> str:
    """Run the single Gemini call under a hard wall-clock timeout.

    Uses a worker thread so a hung network call cannot block the run indefinitely.
    """
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(lambda: LLMClient().call_model(prompt, system=system))
        try:
            return future.result(timeout=timeout_s)
        except FuturesTimeout as exc:
            raise TimeoutError(
                f"Gemini call exceeded {timeout_s:.0f}s"
            ) from exc


def finalize(state: AgentState) -> AgentState:
    return {**state, "status": "completed"}


def handle_error(state: AgentState) -> AgentState:
    logger.warning(
        "run_failed",
        run_id=state.get("run_id"),
        error=state.get("error"),
    )
    return {**state, "status": "failed"}
