# Capability: Markdown → HTML Answer Rendering (C6)

## What It Does
Renders the agent's Markdown answer (tables, bold, bullets, code, headings) to HTML for display.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| answer_markdown | string | finalize node | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer_html | string | `/ask` response |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| markdown-it-py | render md → html | fall back to escaped text |

## Business Rules
- Server renders `answer_html` from `answer_markdown` (markdown-it-py); both are returned.
- Tables, bold, bullets, fenced code, and headings must render.

## Success Criteria
- [ ] An answer containing a Markdown table renders as an HTML `<table>` in `answer_html`.
- [ ] Bold, bullets, code blocks, and headings render correctly.
- [ ] The UI displays the rendered HTML, not raw Markdown.
