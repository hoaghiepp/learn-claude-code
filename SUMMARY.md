# Project Summary

Generated from `README.md` and `requirements.txt`.

---

## What This Project Is

**Learn Claude Code — Harness Engineering for Real Agents** (shareAI-lab, MIT license)

A hands-on tutorial that teaches you how to build the *harness* — the operational
environment around an LLM — that turns a model into a working agent, using Claude
Code as the reference implementation.

## Core Philosophy

> **Agency comes from the model. An Agent Product = Model + Harness.**

- Agency (perceive, reason, act) is *trained*, not coded. No amount of prompt
  chaining, node graphs, or if/else orchestration creates intelligence.
- But every agent needs a **harness** to operate in:
  `Harness = Tools + Knowledge + Observation + Action Interfaces + Permissions`
- The model is the driver; the harness is the vehicle. This repo builds the vehicle.
- Claude Code is elegant precisely because it does *not* try to be the agent — it
  gives the model tools, context management, and permission boundaries, then gets
  out of the way.

## Course Structure: 17 Progressive Lessons

Each chapter isolates one harness mechanism around one core agent loop
(LLM → check for `tool_use` → execute tools → loop):

| Chapters | Stage | Key Mechanisms |
|---|---|---|
| s01–s04 | Let the agent act | Agent loop, tool use/dispatch, permissions, hooks |
| s05–s06 | Handle complex work | TodoWrite planning, subagents (fresh `messages[]`) |
| s08 | Long context | Context compaction (4-step strategy) |
| s09 | Memory | Selection / extraction / consolidation across sessions |
| s10–s12 | Long-running tasks | Task system (disk-backed deps), background tasks, cron scheduler |
| s13 | Multi-agent | Teammates, atomic task claims, task-bound worktrees, typed protocols |
| s07, s14 | Knowledge & extension | On-demand skill loading, MCP external tools |
| s15 | Integration | All mechanisms around one loop |
| s16–s17 | Orchestration & closure | Workflow runtime with journal resume, goal-gated loop termination |

Each chapter ships a standalone runnable `code.py`, tri-lingual READMEs
(EN / 中文 / 日本語), and SVG diagrams where needed.

## How to Run

```sh
pip install -r requirements.txt
cp .env.example .env   # set ANTHROPIC_API_KEY

python s01_agent_loop/code.py   # start here
python s17_goal_loop/code.py    # endpoint
```

## Dependencies (`requirements.txt`)

Only 3 Python packages — intentionally minimal:

| Package | Version | Purpose |
|---|---|---|
| `anthropic` | >=0.25.0 | Claude API client (the agent loop's LLM backend) |
| `python-dotenv` | >=1.0.0 | Loads `.env` for `ANTHROPIC_API_KEY` |
| `pyyaml` | >=6.0 | YAML parsing (skills, task records, config) |

No agent framework, no orchestration library — the harness is built from scratch,
matching the course's philosophy: *"One loop & Bash is all you need."*

## Repository Layout

```
learn-claude-code/
  s01_agent_loop/ ... s17_goal_loop/   # current 17-lesson track (canonical)
  agents/                              # legacy 12-lesson runnable copies + s_full.py
  docs/                                # legacy 12-lesson docs (kept during migration)
  skills/                              # skill files used by s07
  tests/                               # pytest suite covering the mechanisms
  web/                                 # Next.js platform generated from the course
  practice/                            # scratch space
```

## Related Projects

- **Kode-CLI** (`npm i -g @shareai-lab/kode`) — open-source coding agent CLI
- **kode-agent-sdk** — embeddable agent library
- **claw0** — sister tutorial: always-on agents (heartbeat, cron, IM channels, Soul)

---

*Takeaway: Build the harness well, and the model will do the rest.*
