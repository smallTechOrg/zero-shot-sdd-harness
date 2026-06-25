# Capability 1: Connect a Dataset → Create an MCP Server

## Overview

The user names a **dataset** and connects data to it; the system creates an **MCP server** bound 1:1 to
that dataset's URI. For the default `parquet` type, uploading a CSV converts it to Parquet under a
named directory (one CSV → one Parquet file → one table). For the external `postgresql` type (BETA,
flag-gated), the user supplies a connection URI instead. Either way the system creates **one
`McpServer` record** and then runs the **sync pipeline** (capability 4) to generate the server's
**tools, resources, and prompts**. The server then appears on the home page, ready for sessions and for
MCP clients. There is no separate dataset entity — the URI, type, physical-table catalog, and generated
JSONSchema all live on the server. **One dataset = one MCP server.**

## User-Facing Behaviour

1. The user enters a **dataset name**, picks a **type** (default "Upload CSV" / `parquet`; "Connect a
   database" / `postgresql` shown only when external datasets are enabled), and either selects a file
   (`.csv`/`.xlsx`/`.json`) or enters a connection URI, then clicks "Connect".
2. **Parquet:** the page first calls `POST /mcpserver/upload` (CSV → Parquet under
   `{datasets_dir}/{slug(name)}/{table}.parquet`, returns `parquet:///{name}`), then `POST /mcpserver`
   with that URI. **External:** the form submits straight to `POST /mcpserver` with the connection URI.
3. `POST /mcpserver` enforces **1:1** (rejects a duplicate URI/name), reads the dataset into a
   `physical_tables_json` catalog, and runs a **connection check before persisting** — parquet: the dir
   and each Parquet file readable; external: a real connect + `SELECT 1` + `information_schema`
   introspection (hard timeout). On failure the server is **never persisted** (rollback; sanitized error).
4. The server is inserted (version 1), then **`run_sync()`** generates its tools/resources/prompts (LLM,
   with deterministic stub offline; on any stage failure it falls back to templates so create never fails).
5. The user is redirected to the home page, where the new MCP server is listed.

## Inputs

- `dataset_name`: required — the dataset/server name (and the agent tool name). Must be unique.
- `dataset_type`: `parquet` (default) or `postgresql` (external, BETA, flag-gated).
- Parquet upload (`POST /mcpserver/upload`): `dataset_name` + a single `file` (`.csv`/`.xlsx`/`.json`).
- Create (`POST /mcpserver`): `dataset_uri` (+ `dataset_type`, optional `name`).

## Outputs

- One `McpServer` row: `name`, `title`, `description`, `type`, `uri` (unique), `version`,
  `dataset_schema_json`, `physical_tables_json`, `last_synced_at`, `last_sync_status`, `connection_error`.
- Generated capability rows (via sync): `mcp_tools`, `mcp_resources`, `mcp_prompts`.
- For parquet: a Parquet file per table under the dataset directory.
- Redirect to `GET /`.

## What Gets Stored

| Record | Key fields |
|--------|-----------|
| McpServer | name, title, description, type, uri, version, dataset_schema_json, physical_tables_json, last_synced_at, last_sync_status, connection_error |
| McpTool (×N) | name, title, description, input_schema_json, output_schema_json?, annotations_json?, sql_template, version/soft-delete envelope |
| McpResource (×N) | uri, name, title, description, mime_type, kind (`schema`/`primary_entity`/`secondary_entity`), content_json, envelope |
| McpPrompt (×N) | name, title, description, arguments_json, template_json, envelope |

No physical-table table — the catalog lives in `physical_tables_json` on the server.

## Re-sync

`POST /mcpserver/{id}/sync` re-runs the 5-stage pipeline incrementally (capability 4): regenerates
title/description/schema and the tools/resources/prompts, **bumps the version**, and **soft-deletes** any
capability the LLM drops. Sync re-runs the connection check and fails loudly before commit.

## Adding more data (Phase B)

Adding another CSV to an existing dataset = a new physical table = an MCP **`resources/add`** call (a new
entity), which cascades a partial sync of tools + prompts. Until Phase B ships, the home card's "Add CSV"
uploads the file and triggers a full re-sync.

## Error Cases

| Error | Behaviour |
|-------|-----------|
| No dataset name / file | JS validation; form does not submit |
| Duplicate dataset name or URI | 400; name/URI-taken message |
| Unsupported extension | 400; supported-types message |
| Parse/convert fails | 400; transaction rolled back |
| Connection check fails | Rollback; server never persisted; sanitized error |
| External type while flag off | 501; external option hidden in the UI |
| Disk write fails | 500; error.html |
| LLM sync stage fails | Silent fallback to templates; create still succeeds |

## Success Criteria

- After connecting, the MCP server appears on the home page with the correct table count and a generated
  title; its tools/resources/prompts are populated (LLM or fallback).
- For parquet, a Parquet file exists per table under the dataset directory.
- A failed connection check leaves no server persisted (no orphan rows or files).
- The dataset↔server URI is unique (a second create with the same URI is rejected).
- `POST /mcpserver/{id}` returns the generated tools/resources/prompts via MCP JSON-RPC.
- Re-syncing bumps the version and only soft-deletes.
