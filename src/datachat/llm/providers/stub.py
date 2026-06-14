import json

from datachat.llm.providers.base import LLMProvider, LLMResult

_STUB_DASHBOARD_JSON = json.dumps({
    "insights": [
        "Stub insight: revenue appears to peak mid-year (no Gemini API key set).",
        "Stub insight: the dataset contains multiple files with consistent column schemas.",
        "Stub insight: set GEMINI_API_KEY to generate real data-driven insights.",
    ],
    "charts": [
        {
            "type": "bar",
            "title": "Stub Chart — Revenue by Month",
            "x_column": "month",
            "y_column": "revenue",
            "file": "combined",
            "reasoning": "Stub: bar chart showing category vs numeric value.",
        },
        {
            "type": "line",
            "title": "Stub Chart — Trend Over Time",
            "x_column": "month",
            "y_column": "revenue",
            "file": "combined",
            "reasoning": "Stub: line chart showing a time-series trend.",
        },
    ],
})


class StubLLMProvider(LLMProvider):
    """Deterministic stub — branches on node tags injected by pipeline nodes."""

    def generate(self, prompt: str) -> LLMResult:
        if "<node:query>" in prompt:
            text = (
                "**Stub answer (no Gemini API key set)**\n\n"
                "Based on the uploaded CSV data, here is a stub response. "
                "To get real answers, set the GEMINI_API_KEY environment variable.\n\n"
                "This stub confirms the pipeline is wired correctly end-to-end."
            )
        elif "<node:dashboard>" in prompt:
            text = _STUB_DASHBOARD_JSON
        else:
            text = "Stub response: unrecognised node tag."
        return LLMResult(text=text, input_tokens=0, output_tokens=0, cost_usd=0.0)
