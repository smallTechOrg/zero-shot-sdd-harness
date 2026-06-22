import json
import logging

from google import genai
from google.genai import types

from data_analyst.agent.tools import TurnState, dispatch_tool_call, get_tool_definitions

logger = logging.getLogger(__name__)

_ROUND_LIMIT_MESSAGE = (
    "I was unable to complete the analysis in the allowed number of steps. "
    "Please try rephrasing your question or breaking it into smaller parts."
)


def _build_tool_config() -> types.Tool:
    """Build a google-genai Tool object from the tool definitions."""
    tool_defs = get_tool_definitions()
    declarations = []
    for t in tool_defs:
        params = t["parameters"]
        # Build Schema for parameters
        props = {}
        for prop_name, prop_schema in params.get("properties", {}).items():
            prop_type = prop_schema.get("type", "STRING")
            props[prop_name] = types.Schema(
                type=prop_type,
                description=prop_schema.get("description", ""),
            )
        schema = types.Schema(
            type=params.get("type", "OBJECT"),
            properties=props if props else None,
            required=params.get("required", []) or None,
        )
        declarations.append(
            types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=schema,
            )
        )
    return types.Tool(function_declarations=declarations)


def _has_function_calls(parts) -> bool:
    """Return True if any part contains a function call."""
    if not parts:
        return False
    return any(
        hasattr(p, "function_call") and p.function_call is not None
        for p in parts
    )


def _extract_text(parts) -> str:
    """Extract text from response parts, concatenating all text parts."""
    if not parts:
        return ""
    texts = []
    for p in parts:
        if hasattr(p, "text") and p.text:
            texts.append(p.text)
    return "\n".join(texts).strip()


def gemini_tool_loop(
    history: list[dict],
    user_message: str,
    state: TurnState,
    settings,
    system_prompt: str,
) -> str:
    """
    Run the Gemini tool-use loop.

    Args:
        history: list of {role, content} dicts representing prior turns
        user_message: the current user message
        state: TurnState tracking all tool call results within this turn
        settings: application settings (contains gemini_api_key, llm_model, max_tool_rounds)
        system_prompt: system instruction for Gemini

    Returns:
        The final text response from Gemini as a markdown string.
    """
    client = genai.Client(api_key=settings.gemini_api_key)
    tool_config = _build_tool_config()

    # Build the initial contents list from history
    contents: list[types.Content] = []
    for turn in history:
        role = "user" if turn["role"] == "user" else "model"
        contents.append(
            types.Content(role=role, parts=[types.Part(text=turn["content"])])
        )

    # Add the current user message
    contents.append(
        types.Content(role="user", parts=[types.Part(text=user_message)])
    )

    tool_call_rounds = 0
    max_rounds = settings.max_tool_rounds

    while tool_call_rounds < max_rounds:
        logger.debug(
            "gemini_tool_loop: session=%s round=%d contents=%d",
            state.session_id,
            tool_call_rounds,
            len(contents),
        )

        response = client.models.generate_content(
            model=settings.llm_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[tool_config],
            ),
        )

        # Guard: candidates may be empty on blocked/filtered responses
        if not response.candidates:
            logger.warning("gemini_tool_loop: no candidates in response for session %s", state.session_id)
            return "I was unable to generate a response. Please try again."
        candidate = response.candidates[0]
        # candidate.content or parts may be None when response has no content
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) if content is not None else None

        if not _has_function_calls(parts):
            # Final text response — no more tool calls
            text = _extract_text(parts)
            if not text:
                # Gemini returned something non-textual; log and return safe message
                logger.warning(
                    "gemini_tool_loop: no text in final response, parts=%s", parts
                )
                return "I was unable to generate a response. Please try again."
            return text

        # Check round limit before dispatching
        if tool_call_rounds >= max_rounds:
            logger.warning(
                "gemini_tool_loop: round limit %d exceeded for session %s",
                max_rounds,
                state.session_id,
            )
            return _ROUND_LIMIT_MESSAGE

        # Dispatch each function call
        tool_result_parts = []
        for part in (parts or []):
            if not (hasattr(part, "function_call") and part.function_call is not None):
                continue
            fn = part.function_call
            tool_name = fn.name
            # fn.args is a MapComposite — convert to plain dict
            try:
                tool_args = dict(fn.args) if fn.args else {}
            except Exception:
                tool_args = {}

            logger.info(
                "gemini_tool_loop: session=%s round=%d tool=%s args=%s",
                state.session_id,
                tool_call_rounds,
                tool_name,
                json.dumps(tool_args, default=str)[:200],
            )

            result = dispatch_tool_call(tool_name, tool_args, state)

            logger.debug(
                "gemini_tool_loop: tool=%s result_keys=%s",
                tool_name,
                list(result.keys()),
            )

            tool_result_parts.append(
                types.Part.from_function_response(
                    name=tool_name,
                    response={"output": json.dumps(result, default=str)},
                )
            )

        # Append the model's function call turn
        contents.append(types.Content(role="model", parts=parts or []))
        # Append the tool results as a user turn
        contents.append(types.Content(role="user", parts=tool_result_parts))

        tool_call_rounds += 1

    return _ROUND_LIMIT_MESSAGE
