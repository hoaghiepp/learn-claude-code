#!/usr/bin/env python3
"""
s05_todo_write.py - TodoWrite

The model tracks its progress through a TodoManager. After three rounds
without an update, the harness adds a reminder alongside the tool results.

    +----------+      +-------+      +--------------+
    |   User   | ---> |  LLM  | ---> | Tools        |
    |  prompt  |      |       |      | + todo_write |
    +----------+      +---^---+      +------+-------+
                          |                 | update
                          |          +------v----------+
                          |          | TodoManager     |
                          |          | [ ] pending     |
                          |          | [>] in progress |
                          |          | [x] completed   |
                          |          +------+----------+
                          | tool_result     |
                          +-----------------+

              rounds_since_todo >= 3 -> add <reminder>
"""

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
    "Before starting any multi-step task, use todo_write to plan your steps. "
    "Update status as you go."
)


from s2_tool_use import run_bash, run_read, run_write, run_edit, run_glob

class TodoManager:
    def __init__(self):
        self.items: list[dict] = []

    def update(self, todos: list | str) -> str:
        if isinstance(todos, str):
            try:
                todos = json.loads(todos)
            except json.JSONDecodeError:
                try:
                    todos = ast.literal_eval(todos)
                except (SyntaxError, ValueError) as e:
                    raise ValueError(f"todos must be a list or JSON array string") from e
    
        if not isinstance(todos, list):
            raise ValueError(f"todos must be a list")
        if len(todos) > 20:
            raise ValueError(f"todos must be less than 20 items")

        validated = []
        in_progress_count = 0
        for index, todo in enumerate(todos):
            content = str(todo.get("content", "")).strip()
            status = str(todo.get("status", "pending")).lower()
            if not content:
                raise ValueError(f"todos[{index}] requires content")
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"todos[{index}] has invalid status '{status}'")
            if status == "in_progress":
                in_progress_count += 1
            validated.append({"content": content, "status": status})

        if in_progress_count > 1:
            raise ValueError(f"todos cannot have more than one in progress item")

        self.items = validated
        return self.render()

    def render(self) -> str:
        if not self.items:
            return "No todos."

        lines = []
        for todo in self.items:
            marker = {
                "pending": "[ ]",
                "in_progress": "[>]",
                "completed": "[x]"
            }[todo["status"]]
            lines.append(f"{marker} {todo['content']}")
        
        done = sum(todo["status"] == "completed" for todo in self.items)
        lines.append(f"\n({done}/{len(self.items)} completed)")

        return "\n".join(lines)

TODO = TodoManager()


def run_todo_write(todos: list | str) -> str:
    try:
        output = TODO.update(todos)
    except ValueError as e:
        return f"Error: {e}"
    print(f"\n\033[33m## Current Tasks\033[0m\n{output}")
    return output

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
    # s05: new tool
    {"name": "todo_write", "description": "Create and manage a task list for your current coding session.",
     "input_schema": {"type": "object", "properties": {"todos": {"type": "array", "maxItems": 20, "items": {"type": "object", "properties": {"content": {"type": "string", "minLength": 1}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}}, "required": ["content", "status"]}}}, "required": ["todos"]}},
]

TOOL_HANDLERS = {
    "bash": run_bash, "read_file": run_read, "write_file": run_write,
    "edit_file": run_edit, "glob": run_glob, "todo_write": run_todo_write,
}

class HooksManager:
    def __init__(self):
        self.hooks = {
            "UserPromptSubmit": [],
            "PreToolUse": [],
            "PostToolUse": [],
            "Stop": [],
        }
        self.DENY_LIST = ["rm -rf /", "sudo", "shutdown", "reboot", "mkfs", "dd if="]
        self.DESTRUCTIVE_COMMAND_WORD = re.compile(
            r"(?i)(?:^|[;&|()\n])\s*(?:rm|del)(?=\s|$|[;&|()])"
        )
        self.DESTRUCTIVE = ["rm ", "> /etc/", "chmod 777"]
    
    def contain_destructive_command(self, command: str) -> bool:
        return any(keyword in command.lower() for keyword in self.DENY_LIST)
    
    def register_hook(self, event: str, callback):
        self.hooks[event].append(callback)
    
    def trigger_hooks(self, event: str, *args):
        for callback in self.hooks[event]:
            result = callback(*args)
            if result is not None:
                return result
        return None
    

    def permission_hook(self, block):
        if block.name == "bash":
            command = block.input.get("command", "").strip()
            for pattern in self.DENY_LIST:
                if pattern in command:
                    print(f"\n\033[31m[permission] Potentially destructive command\033[0m")
                    return "Permission denied by deny list"
            
            if self.contain_destructive_command(command) or any(
                keyword in command.lower() for keyword in self.DESTRUCTIVE
            ):
                print(f"\n\033[31m[permission] Potentially destructive command\033[0m")
                print(f"   Tool: {block.name}({block.input})")
                choice = input("   Allow? [y/N] ").strip().lower()
                if choice not in ("y", "yes"):
                    return "Permission denied by user"

        if block.name in ("read_file", "write_file", "edit_file"):
            path = block.input.get("path", "")
            if not (WORKDIR / path).resolve().is_relative_to(WORKDIR):
                print(f"\n\033[33m[permission] Access outside workspace\033[0m")
                print(f"   Tool: {block.name}({block.input})")
                choice = input("   Allow? [y/N] ").strip().lower()
                if choice not in ("y", "yes"):
                    return "Permission denied by user"
        return None


    def log_hook(self, block):
        """PreToolUse: log every tool call."""
        args_preview = str(list(block.input.values())[:2])[:60]
        print(f"\033[90m[HOOK] {block.name}({args_preview})\033[0m")
        return None

    def large_output_hook(self, block, output):
        """PostToolUse: warn on large output."""
        if len(str(output)) > 100000:
            print(f"\033[33m[HOOK] Large output from {block.name}: {len(str(output))} chars\033[0m")
        return None

    def context_inject_hook(self, query: str):
        """UserPromptSubmit: log working directory."""
        print(f"\033[90m[HOOK] UserPromptSubmit: working in {WORKDIR}\033[0m")
        return None
            
    def summary_hook(self, messages: list):
        """Stop: print tool call count."""
        tool_count = sum(1 for m in messages
                        for b in (m.get("content") if isinstance(m.get("content"), list) else [])
                        if isinstance(b, dict) and b.get("type") == "tool_result")
        print(f"\033[90m[HOOK] Stop: session used {tool_count} tool calls\033[0m")
        return None

    def auto_register_hooks(self):
        self.register_hook("UserPromptSubmit", self.context_inject_hook)
        self.register_hook("PreToolUse", self.permission_hook)
        self.register_hook("PreToolUse", self.log_hook)
        self.register_hook("PostToolUse", self.large_output_hook)
        self.register_hook("Stop", self.summary_hook)

HOOKS = HooksManager()
HOOKS.auto_register_hooks()

def agent_loop(messages: list):
    rounds_since_todo = 0
    while True:
        response = client.messages.create(
            model=MODEL, messages=messages, system=SYSTEM,
            tools=TOOLS, max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})

        tool_calls = [
            block for block in response.content if block.type == "tool_use"
        ]

        if not tool_calls:
            force = HOOKS.trigger_hook("Stop", messages)
            if force:
                messages.append({"role": "user", "content": force})
                continue
            return
        
        results = []
        used_todo = False
        for block in tool_calls:
            blocked = HOOKS.trigger_hook("PreToolUse", block)
            if blocked:
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": str(blocked)})
                continue

            handler = TOOL_HANDLERS.get(block.name)

            try:
                output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
            except Exception as e:
                output = f"Error: {e}"
                

            HOOKS.trigger_hook("PostToolUse", block, output)

            if block.name == "todo_write":
                used_todo = True
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": str(output)})

        rounds_since_todo = 0 if used_todo else rounds_since_todo + 1

        if rounds_since_todo >= 3:
            results.append({"type": "text",
                            "text": "Remember to update your todo list!"})
            rounds_since_todo = 0

        messages.append({"role": "user", "content": results})

if __name__ == "__main__":
    print("s05: TodoWrite - plan before execution")
    print("Enter a question, press Enter to send. Type q to quit.\n")

    history = []
    while True:
        try:
            # \001/\002 tell Readline the ANSI escapes have zero display width.
            query = input("\001\033[36m\002s05 >> \001\033[0m\002")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        HOOKS.trigger_hook("UserPromptSubmit", query)
        history.append({"role": "user", "content": query})
        agent_loop(history)
        for block in history[-1]["content"]:
            if getattr(block, "type", None) == "text":
                print(block.text)
        print()