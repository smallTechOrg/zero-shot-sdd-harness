# Golden-Path UI Smoke Test

**Mandatory before Phase 2 passes** for any project with a UI or HTTP surface.

## What it is

An automated test that walks the **full primary user journey** end-to-end through the HTTP/UI layer, asserting not only status codes but also that **rendered content actually looks correct** to a human.

A test that checks `response.status_code == 200` and nothing else is not a smoke test. It lets bugs through where the server returns 200 but shows three empty bullets where an article should be.

## Why it exists

Unit tests on the repository layer prove the DB works. Status-code assertions prove routes are wired up. Neither proves the user-visible result is sensible. The smoke test closes that gap.

Bugs this test catches that other tests miss:
- Stub LLM output that looks nothing like the real thing (outline bullets rendered as an article body)
- Template engine signature changes (e.g. Starlette 1.0 `TemplateResponse(request, name, ctx)` vs. the older `TemplateResponse(name, {...})`)
- Forms that POST successfully but render an empty list afterward because the query is wrong
- Redirects that go to a page which then 500s

## Required test structure

Pick the single most important user flow (the one from `spec/vision.md` § Success Criteria). Exercise it end-to-end:

1. **GET** every page on the happy path. Assert each returns 200 and the page contains nav/layout markers proving the template rendered.
2. **POST** each form. Assert 303 and follow the `Location` header.
3. **GET** the final artifact page (e.g. the article detail). Assert:
   - Status 200
   - The user's input is reflected (topic, name, etc.)
   - The **rendered body has real structure** — for article-like content, assert `<p>`, `<h2>`, or paragraph breaks are present. Bare `<ul>` is not enough.
   - The page length passes a sanity threshold (e.g. `len(page) > 600`)
4. **GET** list/index pages to confirm the new artifact appears there.

## Python / FastAPI reference

```python
from fastapi.testclient import TestClient

def test_golden_path_ui_flow(db):
    client = TestClient(create_app())
    # 1. home renders
    assert "Voices" in client.get("/").text

    # 2. create parent entity
    r = client.post("/voices", data={...}, follow_redirects=False)
    assert r.status_code == 303

    # 3. form lists the new entity
    form = client.get("/writers/new").text
    assert "V1" in form

    # 4. generate the artifact and follow the redirect
    r = client.post("/articles", data={...}, follow_redirects=False)
    assert r.status_code == 303, r.text
    article_id = r.headers["location"].rsplit("/", 1)[-1]

    # 5. the detail page must render the artifact, not just 200
    page = client.get(f"/articles/{article_id}").text
    assert "<article>" in page
    assert "<p>" in page or "<h2" in page  # paragraph/heading structure
    assert len(page) > 600                  # sanity
```

## Running the live server as part of the smoke

For Phase 2 sign-off the agent must **also** start the server with `uv run python -m <pkg>` and hit `/health` plus at least one page with `curl` to prove the app boots in a real process — not only via `TestClient`. Report the curl exit codes in the session log.

## Where it lives

- File: `tests/integration/test_pipeline.py` (or a dedicated `test_golden_path.py`)
- Runs as part of `uv run pytest`
- No LLM API key required — uses the stub provider
