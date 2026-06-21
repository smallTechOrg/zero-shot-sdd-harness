# Code Interpreter

**Category:** Tool & Resource Access  
**Status:** Extended

## Intent

Allow the agent to generate, execute, and observe code (Python, SQL, JavaScript, shell) as a tool call — enabling dynamic computation, data analysis, and tasks that exceed what LLM reasoning alone can do reliably.

## When to use

- Numerical calculations, statistical analysis, or data transformations that require correctness beyond LLM arithmetic
- Generating charts, plots, or structured reports from data
- Tasks where the exact logic is determined at runtime (dynamic query generation, custom aggregations)
- Agents that need to create new capabilities on the fly ("code-as-tool" for tasks not covered by the static tool registry)
- Data cleaning, format conversion, or text processing at scale

**Security requirement:** Code execution must always be sandboxed. Never enable the code interpreter tool without a sandbox. See Implementation notes.

## How it works

The code interpreter is registered as a `Compute` category tool in the Tool Registry:

```
Tool: python_interpreter
  type: compute
  capability: execute
    parameters:
      code: { type: string, required: true }
      timeout_seconds: { type: integer, default: 30 }
```

The ReAct loop invokes it like any other tool:

```yaml
states:
  compute_average:
    type: tool_call
    tool_name: python_interpreter
    capability_name: execute
    arguments:
      code: |
        data = [12.5, 14.2, 11.8, 13.9, 15.1]
        avg = sum(data) / len(data)
        print(f"Average: {avg:.2f}")
    on_success: report_result
    on_error: handle_compute_error
```

The executor:
1. Receives the code string
2. Runs it in an isolated sandbox
3. Returns stdout + stderr + return value (or error)
4. Result is appended to `tool_call_history` and available to the next `plan_action` call

The LLM reads the output and generates the next step — which may be another code execution (to refine), a different tool call, or a FINAL ANSWER.

## Sandbox options

| Option | Description | Production-ready |
|---|---|---|
| **Docker container** | Run each execution in a fresh container; full isolation | Yes |
| **E2B** | Hosted sandbox-as-a-service; fast spin-up; Python/JS support | Yes |
| **Pyodide / WASM** | Run Python in-process via WebAssembly; no subprocess; limited stdlib | Limited (no network/file I/O) |
| **gVisor / Firecracker** | Lightweight VM-level isolation; faster than full Docker | Yes (infra investment required) |
| **subprocess with limits** | `subprocess.run` with `timeout` and `resource` limits; weaker isolation | Development only |

## Resource limits (mandatory)

Every sandbox must enforce:

| Limit | Recommended value |
|---|---|
| CPU time | 30 seconds |
| Wall-clock timeout | 60 seconds |
| Memory | 256 MB |
| Network access | Disabled by default |
| File system write | Only to a designated `/tmp/scratchpad`; not the host FS |
| Process count | 1 (no `subprocess`, `os.fork`) |

## Variants

| Variant | Description |
|---|---|
| **SQL interpreter** | Agent generates SQL, executor runs it against a read-only DB connection |
| **Shell interpreter** | Agent generates shell commands; highest risk — require explicit enable and extreme sandbox hardening |
| **Multi-language** | Support Python + JavaScript in the same agent; route by task type |
| **Stateful session** | Maintain interpreter state across multiple tool calls in the same run (variables persist between calls) |
| **Artifact output** | Execution produces files (CSV, PNG chart); files are stored and referenced in the agent's response |

## Related patterns

- [02-tool-registry.md](02-tool-registry.md) — code interpreter registered as a `Compute` tool
- [01-react-loop.md](01-react-loop.md) — code execution is one iteration of the ReAct loop
- [05-self-correction.md](05-self-correction.md) — syntax errors and runtime errors are recoverable; the LLM sees the traceback and corrects
- [14-guardrails.md](14-guardrails.md) — output guardrail should scan generated code for dangerous patterns before execution
- [10-rag.md](10-rag.md) — code interpreter and RAG are frequently combined: retrieve schema/docs, then generate code to query the data

## Implementation notes

- Scan generated code for dangerous patterns before executing (even in a sandbox): `import os`, `subprocess`, `socket`, `open` with write mode, `eval`, `exec`. Block or warn on these patterns.
- Never run generated code in the same process as the agent or web server. Always fork to a subprocess or isolated container.
- Return the full traceback on error — the LLM uses the traceback to diagnose and correct the code. A truncated error message leads to worse self-correction.
- For stateful sessions, store the interpreter state (variables, imported libraries) in the run's checkpoint. Stateful sessions accumulate memory; enforce periodic resets.
- Test the sandbox escape: verify that code like `import subprocess; subprocess.run(["rm", "-rf", "/"])` is blocked, not just timed out.
