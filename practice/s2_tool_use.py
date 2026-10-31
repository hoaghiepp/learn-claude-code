#!/usr/bin/env python3
"""
s02_tool_use.py - Tools

The agent loop from s01 does not change. This lesson adds four tools
and a dispatch map:

    +----------+      +-------+      +--------------------------+
    |   User   | ---> |  LLM  | ---> | Tool Dispatch            |
    |  prompt  |      |       |      | bash       -> run_bash   |
    +----------+      +---+---+      | read_file  -> run_read   |
                          ^          | write_file -> run_write  |
                          |          | edit_file  -> run_edit   |
                          +----------+ glob       -> run_glob   |
                          tool_result+--------------------------+

  + run_read / run_write / run_edit / run_glob
  + TOOL_HANDLERS instead of a hard-coded run_bash call
  + safe_path to keep file tools inside the workspace

Key insight: the loop stays the same; only tool registration and dispatch grow.
"""

from pathlib import Path
import os
import subprocess

from dotenv import load_dotenv
from openai import OpenAI
from anthropic import Anthropic

from s1_agent_loop import run_bash

load_dotenv(override=True)

WORKDIR = Path.cwd()
API_KEY = os.environ["OPENAI_API_KEY"]
BASE_URL = os.environ["OPENAI_BASE_URL"]
MODEL = os.environ["MODEL_ID"]

print(f"{API_KEY}, {BASE_URL}, {MODEL}")

# client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
client = Anthropic(api_key=API_KEY, base_url=BASE_URL)

ENVIRONMENT_PROMPT = (
    "Windows: the bash tool runs through cmd.exe; use cmd.exe syntax, not Unix "
    "Bash or PowerShell syntax, and prefer dedicated file tools for file operations"
    if os.name == "nt"
    else "Unix-like: the bash tool runs the system shell"
)
SYSTEM = (
    f"You are a coding agent at {os.getcwd()}. Environment: {ENVIRONMENT_PROMPT}. "
    "Use bash to solve tasks. Act, don't explain."
)

# run_bash is imported from s01

# new tools


def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_read(path: str, limit: int | None = None) -> str:
    try:
        lines = safe_path(path).read_text(encoding="utf-8").splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)
    except Exception as e:
        return f"\033[91m Error: {e}"


def run_write(path: str, content: str) -> str:
    try:
        file_path = safe_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        file_path = safe_path(path)
        text = file_path.read_text(encoding="utf-8")
        if old_text not in text:
            return f"\033[91m Error: text not found in {path}"
        file_path.write_text(text.replace(
            old_text, new_text, 1), encoding="utf-8")
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"


def run_glob(pattern: str) -> str:
    import glob as g
    try:
        matches = sorted({
            match for match in g.glob(pattern, root_dir=WORKDIR, recursive=True)
            if (WORKDIR / match).resolve().is_relative_to(WORKDIR)
        })
        shown = matches[:200]
        if len(matches) > 200:
            shown.append("... (more matches omitted; narrow the pattern)")
        return "\n".join(shown) if shown else "(no matches)"
    except Exception as e:
        return f"\033[91m Error: {e}"


# -- New in s02: tool definitions (one tool in s01, five in s02) --

TOOLS = [
         {"name": "bash", "description": "Run a shell command.",
          "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
         {"name": "read_file", "description": "Read file contents.",
             "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
         {"name": "write_file", "description": "Write content to a file.",
             "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
         {"name": "edit_file", "description": "Replace exact text in a file once.",
             "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
         {"name": "glob", "description": "Find files matching a glob pattern; ** matches recursively.",
             "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}},
         ]

# -- New in s02: dispatch map (replaces s01's hard-coded run_bash call) --

TOOL_HANDLERS = {
    "bash": run_bash, "read_file": run_read, "write_file": run_write,
    "edit_file": run_edit, "glob": run_glob,
}

def agent_loop(messages: list):
    while True:
        response = client.messages.create(
            messages=messages,
            system=SYSTEM,
            tools=TOOLS,
            model=MODEL,
            max_tokens=8000
        )
        
        messages.append({"role": "assistant", "content": response.content})
        
        tool_calls = [
            block for block in response.content if block.type == "tool_use"
        ]
        
        
        if not tool_calls:
            return

        results = []
        for block in tool_calls:
            print(f"\033[33m> {block.name}\033[0m ")
            handler = TOOL_HANDLERS.get(block.name)
            output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
            print(str(output)[:200])
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})
            
        messages.append({"role": "user", "content": results})


if __name__ == "__main__":
    print("s02: Tool Use - 4 tools added to s01")
    print("Enter a question, press Enter to send. Type q to quit.\n")
    
    history = []
    while True:
        try:
            query = input("\001\033[36m\002s02 >> \001\033[0m\002")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        for block in history[-1]["content"]:
            if getattr(block, "type", None) == "text":
                print(block.text)
        print()