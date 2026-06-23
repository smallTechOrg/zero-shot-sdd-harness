import time
import structlog

from google import genai
from google.genai import types as gtypes

from config.settings import get_settings

log = structlog.get_logger()

GENERATE_SQL_TOOL = gtypes.Tool(
    function_declarations=[
        gtypes.FunctionDeclaration(
            name="generate_sql",
            description="Generate a SQLite SELECT query to answer the user's question",
            parameters=gtypes.Schema(
                type="OBJECT",
                properties={
                    "sql": gtypes.Schema(
                        type="STRING",
                        description="Valid SQLite SELECT statement",
                    ),
                    "explanation": gtypes.Schema(
                        type="STRING",
                        description="Plain-English explanation of what this query does",
                    ),
                },
                required=["sql", "explanation"],
            ),
        )
    ]
)


class GeminiProvider:
    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        key = api_key or settings.gemini_api_key
        if not key:
            raise RuntimeError(
                "AGENT_GEMINI_API_KEY is not set in .env — required for the Gemini provider"
            )
        self._client = genai.Client(api_key=key)
        self._model = model or settings.llm_model or self.DEFAULT_MODEL

    def plan_sql(self, system_prompt: str, question: str) -> tuple[str, str]:
        """Returns (sql, explanation). Retries 3x with exponential back-off."""
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=[
                        gtypes.Content(
                            role="user",
                            parts=[gtypes.Part(text=question)],
                        ),
                    ],
                    config=gtypes.GenerateContentConfig(
                        system_instruction=system_prompt,
                        tools=[GENERATE_SQL_TOOL],
                        tool_config=gtypes.ToolConfig(
                            function_calling_config=gtypes.FunctionCallingConfig(mode="ANY")
                        ),
                    ),
                )
                # Extract function call
                for part in response.candidates[0].content.parts:
                    if part.function_call and part.function_call.name == "generate_sql":
                        args = part.function_call.args
                        sql = (args.get("sql") or "").strip()
                        explanation = (args.get("explanation") or "").strip()
                        if sql:
                            return sql, explanation
                raise ValueError("Gemini did not return a generate_sql function call")
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    wait = 2 ** attempt
                    log.warning(
                        "gemini.retry",
                        attempt=attempt + 1,
                        wait_s=wait,
                        error=str(exc),
                    )
                    time.sleep(wait)
        raise RuntimeError(f"Gemini API failed after 3 attempts: {last_exc}") from last_exc

    # Legacy helpers kept for backward compat (old nodes used these)
    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        from google.genai import types
        config = types.GenerateContentConfig(
            system_instruction=system,
        ) if system else None
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        return response.text

    def call_with_tools(self, prompt: str, tools: list, *, system: str | None = None) -> dict | None:
        from google.genai import types
        config = types.GenerateContentConfig(
            tools=tools,
            system_instruction=system,
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        try:
            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if part.function_call is not None:
                        fc = part.function_call
                        return {"name": fc.name, "args": dict(fc.args)}
        except (AttributeError, IndexError, TypeError):
            pass
        return None

    def call_json(self, prompt: str, *, system: str | None = None) -> str:
        from google.genai import types
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            system_instruction=system,
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        return response.text or ""


_provider: GeminiProvider | None = None


def get_gemini_provider() -> GeminiProvider:
    global _provider
    if _provider is None:
        _provider = GeminiProvider()
    return _provider


def reset_gemini_provider() -> None:
    """For tests — resets singleton so monkeypatch takes effect."""
    global _provider
    _provider = None
