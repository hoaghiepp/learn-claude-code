#!/usr/bin/env python3
"""
s04_hooks.py - Hooks

Hooks run callbacks at fixed points in the agent loop:

    User prompt
         |
         v
    UserPromptSubmit
         |
         v
    +----------+      +-------+      +------------+      +-------+
    | messages | ---> |  LLM  | ---> | PreToolUse | ---> | Tool  |
    +----------+      +---+---+      | permission |      +---+---+
         ^                | stop     | log        |          |
         |                v          +------------+          v
         |            Stop hook                         PostToolUse
         |                                               |
         +---------------- tool_result ------------------+
"""

import os
import re
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from s2_tool_use import TOOL_HANDLERS, TOOLS
from anthropic import Anthropic

load_dotenv(override=True)
API_KEY = os.environ["OPENAI_API_KEY"]
BASE_URL = os.environ["OPENAI_BASE_URL"]
MODEL = os.environ["MODEL_ID"]

client = Anthropic(base_url=BASE_URL, api_key=API_KEY)

WORKDIR = Path.cwd()
print(f"{API_KEY}, {BASE_URL}, {MODEL}")

ENVIRONMENT_PROMPT = (
    "Windows: the bash tool runs through cmd.exe; use cmd.exe syntax, not Unix "
    "Bash or PowerShell syntax, and prefer dedicated file tools for file operations"
    if os.name == "nt"
    else "Unix-like: the bash tool runs the system shell"
)
SYSTEM = (
    f"You are a coding agent at {WORKDIR}. Environment: {ENVIRONMENT_PROMPT}. "
    "Use tools to solve tasks. Act, don't explain."
)


# s03 permission check logic, now wrapped as a hook
DENY_LIST = ["rm -rf /", "sudo", "shutdown", "reboot", "mkfs", "dd if="]
DESTRUCTIVE_COMMAND_WORD = re.compile(
    r"(?i)(?:^|[;&|()\n])\s*(?:rm|del)(?=\s|$|[;&|()])"
)
DESTRUCTIVE = ["rm ", "> /etc/", "chmod 777"]

HOOKS = {"UserPromptSubmit": [], "PreToolUse": [], "PostToolUse": [], "Stop": []}

def register_hook(event: str, callback):
    HOOKS[event].append(callback)

def trigger_hook(event: str, *args):
    for callback in HOOKS[event]:
        result = callback(*args)
        if result is not None:
            return result
    return None

def contain_destructive_command(command: str) -> bool:
    return bool(DESTRUCTIVE_COMMAND_WORD.search(command))

def permission_hook(block):
    """PreToolUse - include check permission"""
    if block.name == "bash":
        command = block.input.get("command", "")
        for pattern in DENY_LIST:
            if pattern in command:
                print(f"\n\033[31m[blocked] '{pattern}'\033[0m")
                return "Permission denied"
        if contain_destructive_command(command) or any(
          kw in command for kw in DESTRUCTIVE  
        ):
            print(f"\n\033[31m[blocked] '{pattern}'\033[0m")
            print(f"    Tool: {block.name}({block.input})")
            choice = input("    Allow [y/N]").strip().lower()
            if choice not in ("y", "yes"):
                return "Permission denied by user"
            
    if block.name in ("read_file", "write_file", "edit_file"):
        path = block.input.get("path", "")
        if not (WORKDIR / path).resolve().is_relative_to(WORKDIR):
            print(f"\n\033[33m[permission] Access outside workspace\033[0m")
            print(f"    Tool: {block.name} ({block.input})")
            choice = input("    Allow [y/N]").strip().lower()
            if choice not in ("y", "yes"):
                return "Permission denied by user"
    return None

def log_hook(block):
    """PreToolUse: log every tool call."""
    args_preview = str(list(block.input.values())[:2])[:60]
    print(f"\033[90m[HOOK] {block.name}({args_preview})\033[0m")
    return None

def large_output_hook(block, output):
    """PostToolUse: warn on large output."""
    if len(str(output)) > 100000:
        print(f"\033[33m[HOOK] Large output from {block.name}: {len(str(output))} chars\033[0m")
    return None

# UserPromptSubmit hook: log user input before it reaches the LLM
def context_inject_hook(query: str):
    print(f"\033[90m[HOOK] UserPromptSubmit: working in {WORKDIR}\033[0m")
    return None

# Stop hook: print summary when loop is about to exit
def summary_hook(messages: list):
    tool_count = sum(1 for m in messages
                     for b in (m.get("content") if isinstance(m.get("content"), list) else [])
                     if isinstance(b, dict) and b.get("type") == "tool_result")
    print(f"\033[90m[HOOK] Stop: session used {tool_count} tool calls\033[0m")
    return None

register_hook("UserPromptSubmit", context_inject_hook)
register_hook("Stop", summary_hook)
register_hook("PreToolUse", permission_hook)
register_hook("PreToolUse", log_hook)
register_hook("PostToolUse", large_output_hook)

def agent_loop(messages: list):
    while True:
        response = client.messages.create(
            model=MODEL, system=SYSTEM, tools=TOOLS,
            messages=messages, max_tokens=8000,
        )
        
        messages.append({"role": "assistant", "content": response.content})
        
        tool_calls = [
            block for block in response.content if block.type == "tool_use"
        ]
        
        if not tool_calls:
            force = trigger_hook("Stop", messages)
            if force:
                messages.append({"role": "user", "content": force})
                continue
            return
    
        results = []
        
        for block in tool_calls:
            blocked = trigger_hook("PreToolUse", block)
            if blocked:
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": str(blocked)})
                continue
            
            handler = TOOL_HANDLERS.get(block.name)
            output = handler(**block.input) if handler else f"Unknown: {block.name}"
            
            trigger_hook("PostToolUse", block, output)
            
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})
            
        messages.append({"role": "user", "content": results})
        
if __name__ == "__main__":
    print("s04: Hooks - extension logic on hooks, loop stays clean")
    print("Enter a question, press Enter to send. Type q to quit.\n")

    history = []
    
    while True:
        try:
            query = input("\001\033[36m\002s04 >> \001\033[0m\002")
        except (EOFError, KeyboardInterrupt):
            break
        
        if query.strip().lower() in ("q", "exit", ""):
            break
        
        trigger_hook("UserPromptSubmit", query)
        history.append({"role": "user", "content": query})
        agent_loop(history)
        for block in history[-1]["content"]:
            if getattr(block, "type", None) == "text":
                print(block.text)
        print()