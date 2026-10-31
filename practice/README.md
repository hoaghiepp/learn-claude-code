# Practice: Minimal Coding Agent Loop

This directory contains a minimal but practical coding agent — a single-file
command-line utility that turns an LLM into an autonomous shell agent
(`s1_agent_loop.py`).

## What it does

The agent reads a natural-language task from you, then autonomously reasons
and executes shell commands until the task is done:

1. You type a request at the `s01 >>` prompt.
2. The LLM decides which shell commands to run (via a `bash` tool).
3. The agent executes them, feeds the output back to the model, and loops
   until the model returns a final text answer.
4. The final answer is printed; the conversation persists across turns in
   the same session.

## Key features

- **Tool calling loop** — the core `agent_loop()` keeps a `messages` history
  and iterates until no more `tool_use` blocks appear.
- **Single tool: `bash`** — one tool that solves most tasks, with a 120s
  timeout and 50 KB output truncation to keep the context bounded.
- **Safety guardrails** — a small blocklist of destructive commands
  (recursively wiping root, superuser elevation, power control, redirecting
  to the null device) is rejected before execution.
- **Cross-platform system prompt** — tells the model whether the shell is
  Windows `cmd.exe` or Unix-like, so it picks compatible syntax.
- **Clean REPL** — colored prompt using zero-width ANSI escape wrapping
  (`\001`/`\002`) so Readline renders correctly; `q`, `exit`, or empty
  input quits.
- **Provider-agnostic config** — built on the Anthropic SDK but
  configurable via environment variables (`OPENAI_API_KEY`,
  `OPENAI_BASE_URL`, `MODEL_ID`), so it can point at any compatible
  gateway.

## Usage

```bash
pip install anthropic python-dotenv
export OPENAI_API_KEY=...     # or put it in a .env file
export OPENAI_BASE_URL=...
export MODEL_ID=...
python s1_agent_loop.py
```

Example session:

```text
s01 >> list the three largest files in this directory

$ ls -S | head -3
...
```

## How it works

```text
user query ──▶ build messages ──▶ client.messages.create(tools=[bash])
                     ▲                        │
                     │                        ▼
             append tool_results        tool_use blocks?
                     │                  yes ──▶ run_bash() ──┘
                     └────────────────── no  ──▶ print final text
```

- `run_bash()` executes each command via `subprocess.run(shell=True)` in the
  current working directory, capturing stdout + stderr with sane bounds and
  replacing undecodable bytes.
- Tool results are appended as `tool_result` user messages, then the loop
  calls the model again.
- Multi-turn memory works because the same `history` list is reused between
  queries.

## Notes

- The `OpenAI` import is currently unused (the Anthropic client is active);
  kept for easy switching between providers.
- The blocklist in `run_bash()` is intentionally basic — extend it for any
  real deployment.
