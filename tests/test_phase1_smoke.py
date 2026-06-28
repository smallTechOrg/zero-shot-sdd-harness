"""Graph compiles / imports without any env vars."""


def test_graph_compiles_without_env():
    from graph.agent import agentic_ai

    assert agentic_ai is not None


def test_runner_and_engine_import():
    from graph.runner import run_question  # noqa: F401
    from analysis.engine import AnalysisEngine  # noqa: F401
    from analysis.loader import load_dataset_metadata  # noqa: F401


def test_models_present():
    from db.models import Dataset, Question, AnalysisStep, CostRecord  # noqa: F401
