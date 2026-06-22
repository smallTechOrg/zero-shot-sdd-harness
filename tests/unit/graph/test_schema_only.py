"""Token-economy guard: generate_sql sends schema (names+types), never row values."""
import graph.nodes as nodes


def test_generate_sql_prompt_is_schema_only(monkeypatch):
    captured = {}

    class FakeClient:
        def call_model(self, prompt, *, system=None):
            captured["prompt"] = prompt
            captured["system"] = system
            return "SELECT region FROM ds_x"

    monkeypatch.setattr(nodes, "LLMClient", lambda: FakeClient())

    state = {
        "question": "total revenue by region",
        "table_name": "ds_x",
        "schema": [
            {"name": "region", "type": "VARCHAR"},
            {"name": "revenue", "type": "BIGINT"},
        ],
    }
    out = nodes.generate_sql(state)
    assert out["sql"] == "SELECT region FROM ds_x"

    prompt = captured["prompt"]
    # column names + types present
    assert "region" in prompt and "revenue" in prompt
    assert "VARCHAR" in prompt and "BIGINT" in prompt
    assert "region: VARCHAR" in prompt
    # actual row values must never be present
    for forbidden in ["North", "South", "100", "250"]:
        assert forbidden not in prompt


def test_strip_fences():
    assert nodes._strip_fences("```sql\nSELECT 1\n```") == "SELECT 1"
    assert nodes._strip_fences("SELECT 1") == "SELECT 1"
