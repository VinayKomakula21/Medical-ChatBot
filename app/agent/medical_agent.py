"""LangGraph medical agent — Groq tool-calling over 4 free NIH/FDA tools.

Architecture:
    ┌─────────┐    tool_calls?    ┌──────────┐
    │   llm   │ ───────yes──────► │  tools   │
    │  (groq) │ ◄─── tool msgs ── │  (4 of)  │
    └─────────┘                   └──────────┘
         │ no
         ▼
        END

Why LangGraph (not raw function-calling loop):
  - Checkpointing is built-in (we don't enable persistence in v1 but it's a
    one-line change when needed).
  - Iteration cap + visible state shape make the graph debuggable in
    Langfuse / LangSmith.
  - It's the 2026-current resume keyword for agentic patterns.

Free-tier everything: Groq tool-use, LangGraph (MIT), all 4 tools target
free NIH/FDA endpoints.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_AGENT_SYSTEM_PROMPT = """You are MediBot, a medical research assistant with access to four tools:

- **search_pubmed(query)** — peer-reviewed literature (NIH PubMed)
- **lookup_drug_openfda(drug_name)** — FDA drug labels (indications, dosage, warnings)
- **check_drug_interactions(drug_names)** — NIH RxNorm drug-drug interactions
- **search_internal_kb(query)** — the user's uploaded medical documents

## When to use each tool
- Ask about a specific medication's indications/dosage/warnings → `lookup_drug_openfda`
- Ask if two+ meds can be taken together → `check_drug_interactions`
- Ask about clinical evidence or "what does the research say" → `search_pubmed`
- Ask about something likely in the user's uploaded docs → `search_internal_kb`
- General clinical knowledge → answer directly without tools

## Rules
- Call tools when the question would benefit; **don't call them when you already know the answer confidently**.
- Cite the tool you used in your final answer (e.g. "per OpenFDA label" or "per PubMed search").
- Never diagnose or prescribe — that requires a clinician.
- For emergency symptoms (chest pain, stroke signs, severe bleeding) start with "🚨 URGENT — call your local emergency number."
- Be concise. Use markdown headers + bullets for clarity.
- Always end with: "💡 For personalized medical advice, consult a healthcare professional."
"""


_compiled_graph: Any = None


def _build_graph() -> Any:
    """Construct the LangGraph state graph once, cache the compiled version."""
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph

    try:
        from langchain_groq import ChatGroq
        from langgraph.graph import START, MessagesState, StateGraph
        from langgraph.prebuilt import ToolNode, tools_condition
    except ImportError as exc:
        raise SystemExit(
            "Agent deps missing. Install with: pip install -r requirements.txt "
            f"(missing: {exc.name})"
        ) from exc

    from app.agent.tools import ALL_TOOLS

    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is required for the agent.")

    llm = ChatGroq(
        model=settings.AGENT_MODEL,
        api_key=settings.GROQ_API_KEY,
        temperature=0.2,
        max_tokens=600,
    )
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    def call_model(state: MessagesState) -> dict:
        # Inject the system prompt on the first call only.
        messages = state["messages"]
        if not messages or messages[0].type != "system":
            from langchain_core.messages import SystemMessage

            messages = [SystemMessage(content=_AGENT_SYSTEM_PROMPT)] + list(messages)
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("llm", call_model)
    builder.add_node("tools", ToolNode(ALL_TOOLS))

    builder.add_edge(START, "llm")
    # ToolNode + tools_condition is the canonical 2026 pattern: if the last
    # message has tool_calls, route to tools; else END.
    builder.add_conditional_edges("llm", tools_condition)
    builder.add_edge("tools", "llm")

    _compiled_graph = builder.compile()
    logger.info("LangGraph medical agent compiled (model=%s)", settings.AGENT_MODEL)
    return _compiled_graph


async def run_agent(user_message: str, trace: Any | None = None) -> dict:
    """Invoke the agent once. Returns {'answer': str, 'tool_calls': [...], 'iterations': int}.

    Hard cap of settings.AGENT_MAX_ITERATIONS by setting `recursion_limit` on
    the run config — LangGraph will raise if exceeded; we catch and return a
    polite fallback so the API contract is preserved.
    """
    from langchain_core.messages import HumanMessage
    from langgraph.errors import GraphRecursionError

    graph = _build_graph()

    # LangGraph's recursion_limit is per-node-visit, so cap × 2 since each
    # tool-cycle visits llm + tools.
    config = {"recursion_limit": settings.AGENT_MAX_ITERATIONS * 2}

    try:
        # ainvoke is async-native — no executor needed.
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=user_message)]},
            config=config,
        )
    except GraphRecursionError:
        return {
            "answer": (
                "I tried multiple sources but couldn't converge on an answer "
                "in the iteration budget. Please rephrase or narrow the question."
            ),
            "tool_calls": [],
            "iterations": settings.AGENT_MAX_ITERATIONS,
        }

    messages = result.get("messages", [])
    final_msg = messages[-1] if messages else None
    answer = (final_msg.content if final_msg is not None else "") or ""

    # Collect a flat list of tool calls for observability + the API response.
    tool_calls: list = []
    for m in messages:
        for tc in getattr(m, "tool_calls", None) or []:
            tool_calls.append(
                {
                    "name": tc.get("name") if isinstance(tc, dict) else tc.name,
                    "args": tc.get("args") if isinstance(tc, dict) else tc.args,
                }
            )

    return {
        "answer": answer,
        "tool_calls": tool_calls,
        "iterations": len(messages),
    }
