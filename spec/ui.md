# UI

## UI Type

Web single-page application (SPA). Chat interface with file upload and data profile sidebar. Served as a Next.js 15 static export at `http://localhost:8001/app/`.

---

## Layout

Two-panel layout (full viewport height):

- **Left panel (30% width, fixed):** File upload zone at top; profile summary card below once a file is uploaded.
- **Right panel (70% width):** Chat message list (scrollable, fills height); chat input fixed to the bottom.

---

## Views / Screens

### Screen: Main (single screen — the entire app)

**Purpose:** The user uploads a CSV, reviews the auto-generated profile card, then conducts a multi-turn conversation to explore the data.

---

#### Component: FileUpload (left panel, top section)

**Purpose:** Let the user upload a CSV file to begin the session.

**Key elements:**
- Dashed-border drag-and-drop zone with cloud-upload icon
- "Drop a CSV file here, or click to browse" label
- Subtext: "CSV only — Excel support coming in Phase 2"
- Accepted MIME types: `text/csv`, `.csv` extension

**States:**
- **Idle:** Dropzone visible, dashed border, grey icon
- **Dragging:** Blue highlighted border, "Drop it!" text
- **Uploading:** Dropzone replaced by a spinner + "Profiling your data..." text
- **Success:** Dropzone hidden; ProfileCard appears below
- **Error:** Red border on dropzone, error message below ("Upload failed: only CSV files are supported" or server error text)

**Phase 2 stub (visible, non-functional):**
- "Upload another file" button appears below the ProfileCard after a successful upload
- Visually present but disabled (greyed out)
- Clearly labelled "[Coming in Phase 2]"

---

#### Component: ProfileCard (left panel, below upload)

**Purpose:** Display the auto-computed profile of the uploaded CSV so the user understands the data before asking questions.

**Key elements:**
- Card header: filename (bold) + row count + column count as subtext (e.g. "1,250 rows · 8 columns")
- Column list: one row per column showing:
  - Column name
  - Dtype chip (colour-coded): blue for numeric (int64, float64), green for text/categorical (object), yellow for datetime, grey for other
  - Null percentage as a small inline progress bar + percentage label
  - Sample values as grey pills (first 3 non-null values)
- Quality flags section (only shown if flags exist):
  - Yellow badge with warning icon for WARNING flags
  - Red badge with error icon for ERROR flags
  - Flag message text (e.g. "42 duplicate rows detected")
- Phase 2 stub at card bottom:
  - "Export Data" button, disabled, greyed out, labelled "[Coming in Phase 2]"

---

#### Component: ChatMessage (right panel, message list area)

**Purpose:** Render one turn of the conversation (user or assistant).

**Key elements:**
- **User messages:** Right-aligned, blue filled bubble, white text
- **Assistant messages:** Left-aligned, white card with subtle grey border, black text
- **Loading placeholder:** Left-aligned card with an animated horizontal pulse bar (skeleton loader) while the server is processing
- **PlotlyChart (optional):** Rendered below assistant message text when chart_json is present

**Error assistant message:** Uses a red-tinted card background with a warning icon to distinguish error responses from normal answers.

---

#### Component: PlotlyChart (embedded in ChatMessage)

**Purpose:** Render an interactive Plotly chart from the JSON spec returned by the backend.

**Key elements:**
- Full width of the assistant message card
- Fixed height: 350px
- Interactive: zoom, pan, hover tooltips enabled (Plotly default controls)
- Rendered via `react-plotly.js` with dynamic import (to avoid SSR issues with Next.js static export)
- If `chart_json` is null or undefined, the component renders nothing (null return)

---

#### Component: ChatInput (right panel, fixed bottom)

**Purpose:** Let the user type and submit a question.

**Key elements:**
- Multi-line `textarea` (auto-grows, max 3 rows)
- "Send" button on the right side of the input row
- Keyboard shortcut: Enter submits (Shift+Enter for newline)
- "Analyzing your data..." status text appears below the input while waiting for a response
- Input and Send button are disabled while waiting for a response

**Optimistic update:** When the user submits, the user message appears in the chat list immediately before the server responds. A loading placeholder for the assistant message appears simultaneously.

---

## Interaction Flow

1. Page loads → left panel shows FileUpload dropzone; right panel shows an empty state placeholder: "Upload a CSV file to get started" (centered, grey text, with an arrow pointing left)
2. User drags a CSV onto the dropzone → spinner appears in the left panel with "Profiling your data..."
3. Profile card replaces the spinner — filename, row/column counts, column list with dtype chips, quality flags
4. User types a question in the chat input (right panel bottom) and clicks Send or presses Enter
5. User message appears immediately in the chat list (right-aligned, blue bubble)
6. Loading placeholder (animated pulse) appears as a pending assistant message
7. "Analyzing your data..." text appears below the input; input + Send button become disabled
8. Server responds: loading placeholder is replaced by the assistant message (text + optional Plotly chart)
9. Input re-enables; "Analyzing..." text disappears
10. User types a follow-up question; cycle repeats
11. Chat scrolls automatically to keep the latest message in view

---

## Non-Functional Stubs (clearly labelled in the UI)

All stubs are visually present but non-functional. They communicate future capability without suggesting current bugs.

| Stub | Location | Label |
|------|----------|-------|
| "Upload another file" button | Below ProfileCard in left panel | Disabled, labelled "[Coming in Phase 2]" |
| "Export Data" button | Footer of ProfileCard | Disabled, labelled "[Coming in Phase 2]" |
| Excel support note | FileUpload dropzone subtext | "CSV only — Excel support coming in Phase 2" |
| Multi-file hint | Empty state in right panel | "Compare files — coming in Phase 2" shown as a small badge below the main placeholder |

---

## Error States

| Scenario | UI Behaviour |
|----------|-------------|
| Upload error (invalid file type) | Red border on dropzone + red error message below: "Upload failed: only CSV files are supported" |
| Upload error (server error) | Same red border + message: "Upload failed: server error. Please try again." |
| Q&A agent error | Assistant message renders in a red-tinted card with a warning icon and the error text from the server |
| Network error / fetch failure | Toast notification at top-right: "Connection lost — please refresh" (auto-dismisses after 5 seconds) |
| No file uploaded, user tries to chat | Input area shows helper text: "Upload a CSV file first" (Send button remains disabled until a file is uploaded) |

---

## Technical Notes

- **API base URL:** `http://localhost:8001` — configurable via `NEXT_PUBLIC_API_URL` environment variable at build time
- **Session management:** Session ID created on first file upload via POST /sessions, stored in React component state (not localStorage). Session is ephemeral — refreshing the page starts a new session.
- **Chart rendering:** `react-plotly.js` loaded via Next.js dynamic import with `{ ssr: false }` to avoid SSR issues in static export mode
- **Tailwind v4:** Uses `@source` directive in globals.css for static export compatibility
- **Plotly output format:** Only Plotly JSON (object with `data` and `layout` keys) — never PNG images
- **Accessibility:** All interactive elements have aria-labels. Colour is not the only differentiator for dtype chips (include short text label as well as colour).
