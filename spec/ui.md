# UI

Single page, Next.js 15 static export, served at **http://localhost:8001/app/**. Tailwind v4. One screen with three zones: upload, ask, result. Plus clearly-labelled non-functional stubs for deferred features so the page shows the full vision without a stub being mistaken for a bug.

## Layout

```
┌───────────────────────────────────────────────────────────┐
│  Data Analysis Agent                                      │
│  Ask questions about your data — answers computed locally  │
├───────────────────────────────────────────────────────────┤
│  [ Upload zone ]                                          │
│   Drag & drop or choose a CSV file                         │
│   ( ○ CSV   ○ Excel .xlsx — Coming soon [disabled] )       │
│   → after upload: "sales.csv · 1,240 rows × 7 cols ✓"      │
├───────────────────────────────────────────────────────────┤
│  [ Question zone ]  (enabled only after a dataset is ready)│
│   ┌──────────────────────────────────────────┐  [ Ask ]    │
│   │ e.g. What is the average amount per region?│            │
│   └──────────────────────────────────────────┘            │
│   ▢ Visualize result  — Coming soon [disabled]             │
├───────────────────────────────────────────────────────────┤
│  [ Result zone ]                                          │
│   Answer:  <plain-language explanation>                    │
│   ▸ Analysis code (pandas)        [code block, monospace]  │
│   ▸ Steps / output                [captured stdout]        │
├───────────────────────────────────────────────────────────┤
│  [ History ]  — Coming soon [disabled placeholder list]    │
└───────────────────────────────────────────────────────────┘
```

## Interactions (real, Phase 1)

1. **Upload.** User selects a `.csv`. Frontend `POST /datasets` (multipart). On success, shows filename + row/column count + a green ready check, and enables the Question zone. On error, shows the `detail.message`.
2. **Ask.** User types a question, clicks **Ask** (disabled while empty or while a request is in flight). Frontend `POST /analyses` with `{ dataset_id, question }`. Loading state shows "Analyzing…".
3. **Result.** On completion, the Result zone shows:
   - **Answer** — the plain-language `answer`, prominently.
   - **Analysis code** — the `code` field in a monospace code block (collapsible, expanded by default). This is mandatory and always shown — it is the core "show its work" requirement.
   - **Steps / output** — the `steps` field (captured stdout) in a collapsible block.
   - On `status=failed`: a clear failure message (the `answer`) plus the last attempted code/steps; never a raw stack trace as the headline.

## Labelled non-functional stubs (Phase 1 — NOT bugs)

Each is visibly disabled/greyed and tagged **"Coming soon"** so the user sees the roadmap without confusion:

| Stub | Appears as | Becomes real in |
|------|-----------|-----------------|
| **Excel (.xlsx)** | a disabled radio/option next to CSV in the upload zone, labelled "Coming soon" | Phase 2 |
| **Visualize result** | a disabled checkbox under the question input, labelled "Coming soon" | deferred (charts) |
| **History** | a disabled placeholder panel at the bottom showing "Your past questions will appear here — Coming soon" | deferred |

## Surface ownership (for slicing)

- `frontend/src/app/page.tsx` — page composition + upload/ask/result state and fetch calls.
- `frontend/src/app/components/*` — `UploadZone`, `QuestionInput`, `ResultView` (answer + code block + steps), `ComingSoon` badge/stub components.

> The frontend builds in parallel against the API contract in `spec/api.md` — no code dependency on backend slices.
