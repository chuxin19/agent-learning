#!/usr/bin/env python3
"""
Agentic AI Demo — Build Your First AI Agent
YouTube Tutorial: "Agentic AI for Beginners: Full Course 2026"

Requirements:
  pip install anthropic

Setup:
  export ANTHROPIC_API_KEY="sk-ant-..."   # Mac/Linux
  $env:ANTHROPIC_API_KEY = "sk-ant-..."  # Windows PowerShell
"""

import anthropic
import json
import math

# ─── Client Setup ─────────────────────────────────────────────────────────────
# Reads ANTHROPIC_API_KEY automatically from your environment
client = anthropic.Anthropic()


# ─── Step 1: Define Tools ─────────────────────────────────────────────────────
# Each tool is a JSON schema. The model reads 'description' to decide when to use it.
# Write clear, specific descriptions — vague ones lead to wrong tool calls.

tools = [
    {
        "name": "calculate",
        "description": (
            "Evaluate a mathematical expression and return the numeric result. "
            "Use this for any calculation: arithmetic, compound interest, percentages, etc. "
            "Example expression: '5000 * (1 + 0.07) ** 5'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A Python math expression using numbers, operators (+,-,*,/,**), and math functions (sqrt, log, etc.)"
                }
            },
            "required": ["expression"]
        }
    },
    {
        "name": "save_memory",
        "description": "Save a key-value pair to the agent's working memory for use in later steps.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key":   {"type": "string", "description": "Identifier for this memory entry"},
                "value": {"type": "string", "description": "Data to store"}
            },
            "required": ["key", "value"]
        }
    },
    {
        "name": "recall_memory",
        "description": "Retrieve a previously saved value from memory using its key.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "The key used when saving"}
            },
            "required": ["key"]
        }
    },
    {
        "name": "web_search",
        "description": (
            "Search the web for current information, news, or data. "
            "Use this when you need up-to-date facts not in your training data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query string"}
            },
            "required": ["query"]
        }
    }
]


# ─── Step 2: Implement Tool Logic ─────────────────────────────────────────────

# Persistent memory across agent steps
_memory: dict[str, str] = {}

# Restrict eval() to math functions only — never expose builtins to eval
_SAFE_MATH_NAMESPACE = {
    k: v for k, v in math.__dict__.items() if not k.startswith("_")
}
_SAFE_MATH_NAMESPACE["__builtins__"] = {}


def execute_tool(name: str, inputs: dict) -> str:
    """Execute a tool by name and return its string result to the agent."""

    if name == "calculate":
        try:
            result = eval(inputs["expression"], _SAFE_MATH_NAMESPACE)
            return f"{result:.4f}"
        except Exception as e:
            return f"Calculation error: {e}"

    elif name == "save_memory":
        _memory[inputs["key"]] = inputs["value"]
        return f"Saved '{inputs['key']}' = '{inputs['value']}'"

    elif name == "recall_memory":
        value = _memory.get(inputs["key"])
        return value if value else f"No memory found for key '{inputs['key']}'"

    elif name == "web_search":
        # --- Production: Replace this block with a real search API ---
        # Brave Search: https://brave.com/search/api/
        # Tavily:       https://tavily.com
        # Example (Brave):
        #   import requests
        #   r = requests.get("https://api.search.brave.com/res/v1/web/search",
        #       params={"q": inputs["query"]}, headers={"X-Subscription-Token": BRAVE_API_KEY})
        #   return r.json()["web"]["results"][0]["description"]
        # ---------------------------------------------------------------
        return (
            f"[Simulated search for: '{inputs['query']}']\n"
            "Top results:\n"
            "• Agentic AI adoption grew 340% in 2025 (McKinsey, 2026)\n"
            "• 70% of Fortune 500 companies are now piloting AI agents\n"
            "• LangGraph, AutoGen, and Claude are the leading frameworks\n"
            "• Key trend: Multi-agent systems replacing entire workflows"
        )

    return f"Unknown tool: '{name}'"


# ─── Step 3: The Agentic Loop ─────────────────────────────────────────────────

def run_agent(task: str, max_steps: int = 15) -> str:
    """
    Execute the ReAct agent loop:
      THINK (model) → ACT (tool call) → OBSERVE (result) → repeat until done.

    Args:
        task:      The natural-language task for the agent.
        max_steps: Safety limit — stops if the agent hasn't finished in time.

    Returns:
        The agent's final text response.
    """
    print(f"\n{'='*60}")
    print(f"AGENT TASK:\n{task}")
    print(f"{'='*60}\n")

    messages = [{"role": "user", "content": task}]
    step = 0

    while step < max_steps:
        step += 1
        print(f"--- Step {step}: Thinking... ---")

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            tools=tools,
            messages=messages
        )

        # ── Agent is finished ───────────────────────────────────────────────
        if response.stop_reason == "end_turn":
            final_text = next(
                (b.text for b in response.content if hasattr(b, "text")),
                "No response generated."
            )
            print(f"\n{'='*60}")
            print(f"FINAL ANSWER:\n{final_text}")
            print(f"{'='*60}\n")
            return final_text

        # ── Process tool calls ──────────────────────────────────────────────
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []

        for block in response.content:
            if block.type == "tool_use":
                print(f"  Tool: {block.name}")
                print(f"  Input: {json.dumps(block.input)}")

                result = execute_tool(block.name, block.input)

                print(f"  Output: {result}\n")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result
                })

        messages.append({"role": "user", "content": tool_results})

    return "Max steps reached. Partial work saved in memory."


# ─── Run the Demo ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_agent(
        "I want to invest $5,000 at 7% annual compound interest for 5 years. "
        "Calculate the final amount, save it to memory as 'investment_result', "
        "then recall it to confirm it was saved, "
        "then search the web for the latest agentic AI trends, "
        "and finally write me a short paragraph summarizing both the investment "
        "outcome and the key AI trends you found."
    )
