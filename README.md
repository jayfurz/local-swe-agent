# local-swe-agent (`swea`)

A coding-agent harness built on the [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) that drives a **local OpenAI-compatible model** (vLLM, Ollama, llama.cpp, LM Studio, …) through real software-engineering work: explore a repo, edit code, run commands, and iterate until tests pass.

No cloud APIs involved: point it at any `http://…/v1` endpoint and it works. Tracing is disabled; nothing leaves your machine except requests to the base URL you configure.

## Quick start

```bash
uv sync

# one-shot task in the current directory
uv run swea "add a --verbose flag to cli.py and cover it with a test"

# interactive REPL, different workspace, explicit endpoint + model
uv run swea --workspace ~/code/myproj \
            --base-url http://localhost:8009/v1 \
            --model qwen3.5-27b \
```

Configuration is flags > environment > defaults:

| Flag | Env | Default |
|---|---|---|
| `--base-url` | `SWEA_BASE_URL`, `OPENAI_BASE_URL` | `http://localhost:8009/v1` |
| `--model` | `SWEA_MODEL` | auto-detected from `GET /v1/models` |
| `--api-key` | `SWEA_API_KEY`, `OPENAI_API_KEY` | `local` |
| `--workspace` | — | current directory |
| `--max-turns` | — | 40 |
| `--temperature` | — | 0.1 |

Conversations persist with `--session NAME` (stored in `~/.local/share/swea/sessions.db`); `--continue` resumes the `default` session.

## Serving a model

**vLLM** (weights in `/mnt/data/models`, 2×GPU, tool calling on):

```bash
vllm serve /mnt/data/models/<model-dir> \
  --served-model-name qwen3.5-27b \
  --port 8009 \
  --tensor-parallel-size 2 \
  --max-model-len 32768 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes
```

Notes: Qwen3/Qwen2.5 chat templates speak Hermes-style tool calls (`--tool-call-parser hermes`); **Qwen3-Coder** models need `--tool-call-parser qwen3_xml` instead. Pre-quantized AWQ/GPTQ checkpoints are auto-detected — do **not** pass `--quantization awq` (it pins the slower non-Marlin kernel).

**Ollama**:

```bash
ollama serve &
ollama pull qwen3-coder:30b
uv run swea --base-url http://localhost:11434/v1 --model qwen3-coder:30b "…"
```

Any model you use must support **tool/function calling** — that's the whole game here. Coder-tuned instruct models (Qwen3-Coder, Qwen2.5-Coder-32B, Devstral, GLM-4.x) work best.

OpenCode users: the same endpoint plugs into an `@ai-sdk/openai-compatible` provider entry in `~/.config/opencode/opencode.json` — the harness and OpenCode can share one server.

## How it works

```
src/swea/
  config.py   HarnessConfig + model auto-detection (GET /v1/models)
  prompt.py   system prompt: explore → plan → edit → verify with tests → report
  tools.py    workspace-rooted tools: bash, read_file, write_file, edit_file,
              list_dir, glob_files, grep
  agent.py    Agent wired to OpenAIChatCompletionsModel(base_url=…) — the
              Chat Completions API, which every local server implements
  cli.py      streaming CLI: live text, ▶ tool-call lines, output previews
```

Design choices that matter for local models:

- **Chat Completions, not Responses**: local servers rarely implement the Responses API; `OpenAIChatCompletionsModel` keeps the wire format universal.
- **Minimal request surface**: only `temperature` is sent; every other `ModelSettings` field stays `None` so it's omitted — strict servers reject unknown params.
- **Model-visible errors**: tools never raise; they return `error: …` strings so the model reads the failure and adapts instead of crashing the run.
- **Workspace jail for file tools**: paths resolving outside `--workspace` are refused. `bash` runs with the workspace as cwd but is *not* sandboxed — run it in a container/VM if you don't trust the model or the task.

## Tests

```bash
uv run pytest
```

Unit tests cover every tool (including path-escape rejection, edit uniqueness, output truncation). End-to-end tests run the full agent loop against a **scripted mock OpenAI server** (`tests/mock_server.py` — SSE streaming and all), so the whole harness is verified without a GPU. The mock is also handy for demos:

```bash
uv run python tests/mock_server.py               # serves a canned coding session, prints its URL
uv run swea --base-url http://127.0.0.1:<port>/v1 --workspace /tmp/demo "write and test calc.py"
```
