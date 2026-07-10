"""Settings — defaults, env overrides, provider key detection. No LLM key required.

(LLM client provider-construction behaviour is covered by the graph slice's tests.)
"""


def _fresh_settings(monkeypatch, tmp_path, **env):
    monkeypatch.setenv("AGENT_DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    import config.settings as m

    m._settings = None
    return m.get_settings()


def test_project_defaults(monkeypatch):
    for var in (
        "AGENT_LLM_MODEL",
        "AGENT_ARTIFACTS_DIR",
        "AGENT_GEMINI_INPUT_COST_PER_MTOK",
        "AGENT_GEMINI_OUTPUT_COST_PER_MTOK",
    ):
        monkeypatch.delenv(var, raising=False)
    from config.settings import Settings

    s = Settings(_env_file=None)  # pure code defaults — ignore the developer's .env
    assert s.llm_model == "gemini-2.5-pro"
    assert s.artifacts_dir == "data/artifacts"
    assert s.gemini_input_cost_per_mtok == 1.25
    assert s.gemini_output_cost_per_mtok == 10.0
    assert s.database_url == "sqlite:///./data/agent.db"


def test_artifacts_dir_env_override(monkeypatch, tmp_path):
    s = _fresh_settings(monkeypatch, tmp_path, AGENT_ARTIFACTS_DIR="/tmp/somewhere/else")
    assert s.artifacts_dir == "/tmp/somewhere/else"


def test_cost_rates_env_override(monkeypatch, tmp_path):
    s = _fresh_settings(
        monkeypatch,
        tmp_path,
        AGENT_GEMINI_INPUT_COST_PER_MTOK="2.5",
        AGENT_GEMINI_OUTPUT_COST_PER_MTOK="15.0",
    )
    assert s.gemini_input_cost_per_mtok == 2.5
    assert s.gemini_output_cost_per_mtok == 15.0


def test_gemini_key_detected_from_env(monkeypatch, tmp_path):
    s = _fresh_settings(
        monkeypatch,
        tmp_path,
        AGENT_ANTHROPIC_API_KEY="",
        AGENT_GEMINI_API_KEY="AIza-fake",
        AGENT_LLM_PROVIDER="",
    )
    assert s.gemini_api_key == "AIza-fake"
    assert s.anthropic_api_key == ""


def test_explicit_provider_wins(monkeypatch, tmp_path):
    s = _fresh_settings(
        monkeypatch,
        tmp_path,
        AGENT_ANTHROPIC_API_KEY="sk-ant-fake",
        AGENT_GEMINI_API_KEY="AIza-fake",
        AGENT_LLM_PROVIDER="gemini",
    )
    assert s.llm_provider == "gemini"
