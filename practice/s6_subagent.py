#!/usr/bin/env python3
"""
s06_subagent.py - Subagents

The task tool runs a second agent loop with a fresh message list. Both
loops share the working directory, but only the final text returns to
the parent conversation.

    Parent agent                    Subagent
    +------------------+            +------------------+
    | messages=[...]   |            | messages=[prompt]|
    |                  |   task     |                  |
    | tool: task       | ---------> | own agent loop   |
    |                  |            | base tools only  |
    | tool_result      | <--------- | final text       |
    +------------------+            +------------------+

The subagent has no task tool, so it cannot delegate again.
"""
from s5_todo_write import HooksManager
from s2_tool_use import run_bash, run_read, run_write, run_edit, run_glob
import ast
import json
import os
import re
import subprocess
from pathlib import Path

try:
    import readline
    readline.parse_and_bind('set bind-tty-special-chars off')
except ImportError:
    pass

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)
API_KEY = os.environ["OPENAI_API_KEY"]
BASE_URL = os.environ["OPENAI_BASE_URL"]
MODEL = os.environ["MODEL_ID"]

client = Anthropic(base_url=BASE_URL, api_key=API_KEY)

WORKDIR = Path.cwd()

# s05 change: SYSTEM prompt adds planning guidance
ENVIRONMENT_PROMPT = (
    "Windows: the bash tool runs through cmd.exe; use cmd.exe syntax, not Unix "
    "Bash or PowerShell syntax, and prefer dedicated file tools for file operations"
    if os.name == "nt"
    else "Unix-like: the bash tool runs the system shell"
)
SYSTEM = (
    f"You are a coding agent at {WORKDIR}. Environment: {ENVIRONMENT_PROMPT}. "
    "Use task for focused exploration or a self-contained subtask."
)
SUB_SYSTEM = (
    f"You are a coding agent at {WORKDIR}. Environment: {ENVIRONMENT_PROMPT}. "
    "Complete the given task, then return a concise final answer."
)


BASE_TOOLS = [
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

BASE_HANDLERS = {
    "bash": run_bash,
    "read_file": run_read,
    "write_file": run_write,
    "edit_file": run_edit,
    "glob": run_glob,
}

HOOKS = HooksManager()
HOOKS.auto_register_hooks()


def execute_tool(block, handlers: dict) -> str:
    blocked = HOOKS.trigger_hooks("PreToolUse", block)
    if blocked:
        return str(blocked)

    handler = handlers.get(block.name)
    try:
        output = handler(
            **block.input) if handler else f"Unknown tool: {block.name}"
    except Exception as e:
        output = f"Error: {e}"

    HOOKS.trigger_hooks("PostToolUse", block, output)
    return output


SUB_TOOLS = list(BASE_TOOLS)
SUB_HANDLERS = dict(BASE_HANDLERS)


def extract_text(content) -> str:
    if not isinstance(content, list):
        return str(content)

    return "\n".join(
        getattr(block, "text", "")
        for block in content
        if getattr(block, "type", None) == "text"
    )


def run_subagent(prompt: str) -> str:
    print("\n\033[35m[Subagent started]\033[0m")
    messages = [{"role": "user", "content": prompt}]

    for _ in range(100):
        response = client.messages.create(
            model=MODEL,
            system=SUB_SYSTEM,
            tools=SUB_TOOLS,
            messages=messages,
            max_tokens=8000
        )

        messages.append({"role": "assistant", "content": response.content})

        tool_calls = [
            block for block in response.content if block.type == "tool_use"]
        if not tool_calls:
            force = HOOKS.trigger_hooks("Stop", messages)
            if force:
                messages.append({"role": "user", "content": force})
                continue
            print("\033[35m[Subagent done]\033[0m")
            return extract_text(response.content) or "(no summary)"

        results = []
        for block in tool_calls:
            output = execute_tool(block, SUB_HANDLERS)
            print(f"  \033[90m[sub] {block.name}: {output[:100]}\033[0m")
            results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": output})

        messages.append({"role": "user", "content": results})

    print("\033[35m[Subagent stopped]\033[0m")
    return "Subagent stopped after 30 turns without a final answer"


TASK_TOOL = {
    "name": "task",
    "description": "Run a subagent with fresh conversation context and return its final text.",
    "input_schema": {
        "type": "object",
        "properties": {"prompt": {"type": "string", "minLength": 1}},
        "required": ["prompt"],
    },
}

TOOLS = [*BASE_TOOLS, TASK_TOOL]
TOOL_HANDLERS = {**BASE_HANDLERS, "task": run_subagent}

# parent agent loop
def agent_loop(messages: list):
    while True:
        response = client.messages.create(
            model=MODEL,
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
            max_tokens=8000
        )

        messages.append({"role": "assistant", "content": response.content})

        tool_calls = [block for block in response.content if block.type == "tool_use"]

        if not tool_calls:
            force = HOOKS.trigger_hooks("Stop", messages)
            if force:
                messages.append({"role": "user", "content": force})
                continue
            return

        results = []
        for block in tool_calls:
            output = execute_tool(block, TOOL_HANDLERS)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})
        messages.append({"role": "user", "content": results})


if __name__ == "__main__":
    print("s06: Subagent - fresh messages, final text returns")
    print("Enter a question, press Enter to send. Type q to quit.\n")

    history = []
    while True:
        try:
            # \001/\002 tell Readline the ANSI escapes have zero display width.
            query = input("\001\033[36m\002s06 >> \001\033[0m\002")
        except (EOFError, KeyboardInterrupt):
            break
        HOOKS.trigger_hooks("UserPromptSubmit", query)
        history.append({"role": "user", "content": query})
        agent_loop(history)
        for block in history[-1]["content"]:
            if getattr(block, "type", None) == "text":
                print(block.text)
        print()