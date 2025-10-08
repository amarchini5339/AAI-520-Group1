from __future__ import annotations

import inspect
import json
import logging
from typing import Any, Callable, Dict, Optional, TypedDict

# LangGraph
try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
except Exception as e:  # pragma: no cover
    raise ImportError(
        "langgraph is required. Install with: pip install langgraph"
    ) from e

# CrewAI tool base
try:
    from pydantic import BaseModel, Field
    from crewai.tools import BaseTool
except Exception as e:  # pragma: no cover
    raise ImportError(
        "CrewAI and Pydantic are required. Install with: pip install crewai pydantic"
    ) from e

# Your module that contains the analysis logic
try:
    import sec_tools as sec_agent  # Ensure this is importable from your working directory
except Exception as e:  # pragma: no cover
    raise ImportError(
        "Unable to import sec_tools.py Ensure it is on PYTHONPATH and importable."
    ) from e


log = logging.getLogger(__name__)


class SECState(TypedDict, total=False):
    query: str
    context: Dict[str, Any]
    result: Any

class SECAgentAdapter:
    def __init__(self, module=sec_agent):
        self._module = module
        self._entrypoint = getattr(module, "main")

    def run(self, query: str, context=None):
        # Treat query as ticker
        return self._entrypoint(query)

def _execute_node(adapter: SECAgentAdapter):
    def _node(state: SECState) -> SECState:
        query = state.get("query", "")
        context = state.get("context", {}) or {}
        result = adapter.run(query=query, context=context)
        return {**state, "result": result}

    return _node

def build_sec_graph(adapter: Optional[SECAgentAdapter] = None):
    adapter = adapter or SECAgentAdapter()
    graph = StateGraph(SECState)
    graph.add_node("execute", _execute_node(adapter))
    graph.set_entry_point("execute")
    graph.add_edge("execute", END)

    # Remove checkpointing for single-run use
    app = graph.compile()
    return app


class SECQueryInput(BaseModel):
    """Input schema for the SEC analysis tool.

    This tool accepts exactly one required field: `ticker` (e.g., 'AAPL').
    """
    ticker: str = Field(
        ...,
        description="Ticker symbol to analyze, e.g., 'AAPL' or 'MSFT'.",
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional extra parameters to pass through to sec_agent.",
    )


class SECAnalysisTool(BaseTool):
    name: str = "sec_analysis"
    description: str = (
        "Run a LangGraph-wrapped SEC analysis pipeline using functions from sec_agent.py. "
        "Pass a 'query' describing what to analyze, plus optional 'context'."
    )
    args_schema: type = SECQueryInput

    def __init__(self, app=None, adapter: Optional[SECAgentAdapter] = None, **kwargs):
        super().__init__(**kwargs)
        self._adapter = adapter or SECAgentAdapter()
        self._app = app or build_sec_graph(self._adapter)

    def _run(self, ticker: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Run the SEC analysis tool with a ticker string.

        This simplified entrypoint requires a ticker (e.g., 'AAPL').
        """
        if not isinstance(ticker, str) or not ticker.strip():
            raise ValueError("ticker must be a non-empty string, e.g., 'AAPL'")

        ticker = ticker.strip()

        # Build state and invoke the app
        state: SECState = {"query": ticker, "context": context or {}}
        out: SECState = self._app.invoke(state)
        result = out.get("result")
        if isinstance(result, (dict, list)):
            try:
                return json.dumps(result, ensure_ascii=False)
            except Exception:
                return str(result)
        return str(result)


def create_crewai_sec_agent(agent_cls, role: str = "SEC Analyst", goal: str = "", backstory: str = "", **kwargs):
    """Convenience: instantiate a CrewAI Agent with SECAnalysisTool attached.

    Parameters
    ----------
    agent_cls : type
        Pass the CrewAI Agent class, e.g., from crewai import Agent then agent_cls=Agent
    role : str
        Role name to assign to the agent.
    goal : str
        High-level goal for the agent.
    backstory : str
        Short backstory to provide context.
    kwargs : Any
        Additional keyword args passed to the CrewAI Agent constructor.
    """

    tool = SECAnalysisTool()
    agent = agent_cls(
        role=role or "SEC Analyst",
        goal=goal or "Analyze and extract insights from SEC filings and disclosures.",
        backstory=backstory
        or "A seasoned analyst who navigates SEC documents to provide actionable insights.",
        tools=[tool],
        allow_delegation=False,
        verbose=True,
        **kwargs,
    )

    def run_fn(query: str, context: dict | None = None):
        """Run the SECAnalysisTool directly."""
        return tool._run(query, context)

    # bypass pydantic restriction
    object.__setattr__(agent, "run", run_fn)

    return agent