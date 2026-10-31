#!/usr/bin/env python3
"""
s03_permission.py - Permission System

Three gates inserted before tool execution:

    Gate 1: Hard deny list (rm -rf /, sudo, ...)
    Gate 2: Rule matching (write outside workspace? destructive cmd?)
    Gate 3: User approval (pause and wait for confirmation)

    +----------+      +-------+      +--------------+      +---------------+
    |   User   | ---> |  LLM  | ---> | Permission   | ---> | Tool Dispatch |
    |  prompt  |      |       |      | 1. deny list |      | execute       |
    +----------+      +---+---+      | 2. rules     |      +-------+-------+
                          ^          | 3. approval  |              |
                          |          +------+-------+              |
                          |                 | deny                 |
                          |                 v                      v
                          |          +-------------------------------+
                          +----------+ tool_result: denied or output |
                                     +-------------------------------+

Only one line added to the agent loop:

    if not check_permission(block):
        continue

Builds on s02 (multi-tool). Usage:

    python s03_permission/code.py
    Needs: pip install anthropic python-dotenv + ANTHROPIC_API_KEY in .env
"""

import os
import subprocess

from dotenv import load_dotenv
from openai import OpenAI
from anthropic import Anthropic
from pathlib import Path

from s2_tool_use import run_bash, run_edit, run_glob, run_read, run_write, TOOL_HANDLERS, TOOLS

load_dotenv(override=True)

API_KEY = os.environ["OPENAI_API_KEY"]
BASE_URL = os.environ["OPENAI_BASE_URL"]
MODEL = os.environ["MODEL_ID"]

WORKDIR = Path.cwd()
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
    f"You are a coding agent at {WORKDIR}. Environment: {ENVIRONMENT_PROMPT}. "
    "All destructive operations require user approval."
)

# deny list - always deny these commands
DENY_LIST = [
    "rm -rf /",
    "sudo",
    "shutdown",
    "reboot",
    "> /dev/sda",
    "mkfs",
    "dd if=",
]

# rule matching - check if the command is destructive
def check_deny_list(command:str) -> str | None:
    for pattern in DENY_LIST:
        if pattern in command:
            return f"\033[91m Error: {pattern} is not allowed"
    return None

import re
# rule matching - check if the command is destructive
DESTRUCTIVE_COMMAND_WORD = re.compile(
    r"(?i)(?:^|[;&|()\n])\s*(?:rm|del)(?=\s|$|[;&|()])"
)

def contains_destructive_command(command: str) -> bool:
    return bool(DESTRUCTIVE_COMMAND_WORD.search(command))

PERMISSION_RULES = [
    {"tools": ["read_file", "write_file", "edit_file"],
     "check": lambda args: not (WORKDIR / args.get("path", "")).resolve().is_relative_to(WORKDIR),
     "message": "Writing outside workspace"},
    {"tools": ["bash"],
     "check": lambda args: contains_destructive_command(args.get("command", "")) or
     any(kw in args.get("command", "") for kw in ["rm ", "> /etc/", "chmod 777"]),
     "message": "Potentially destructive command"},
]

def check_rules(tool_name: str, args: dict) -> str | None:
    for rule in PERMISSION_RULES:
        if tool_name in rule["tools"] and rule["check"](args):
            return rule["message"]
    return None

# User approval - wait for confirmation after rule match
def ask_user(tool_name: str, args: dict, reason: str) -> str:
    print(f"\n\033[33m[permission] {reason}\033[0m")
    print(f"    Tool: {tool_name}({args})")
    choice = input("    Allow? [y/N] ").strip().lower()
    return "allow" if choice in ("y", "yes") else "deny"

# pipeline
def check_permission(block) -> bool:
    if block.name == "bash":
        reason = check_deny_list(block.input.get("command", ""))
        if reason:
            print(f"\n\033[31m[blocked] {reason}\003[0m")
            return False
    reason = check_rules(block.name, block.input)
    if reason:
        decision = ask_user(block.name, block.input, reason)
        if decision == "deny":
            return False
    return True

def agent_loop(messages: list):
    while True:
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})

        tool_calls = [
            block for block in response.content if block.type == "tool_use"
        ]
        if not tool_calls:
            return

        results = []
        for block in tool_calls:
            print(f"\033[36m> {block.name}\033[0m")

            # s03 change: run through permission pipeline before executing
            if not check_permission(block):
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": "Permission denied."})
                continue

            handler = TOOL_HANDLERS.get(block.name)
            output = handler(**block.input) if handler else f"Unknown: {block.name}"
            print(str(output)[:200])
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})

        messages.append({"role": "user", "content": results})

if __name__ == "__main__":
    print("s03: Permission")
    print("Enter a question, press Enter to send. Type q to quit.\n")

    history = []
    while True:
        try:
            # \001/\002 tell Readline the ANSI escapes have zero display width.
            query = input("\001\033[36m\002s03 >> \001\033[0m\002")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        for block in history[-1]["content"]:
            if getattr(block, "type", None) == "text":
                print(block.text)
        print()