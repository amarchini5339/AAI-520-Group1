#!/usr/bin/env python
# coding: utf-8

# In[6]:


# create_crewai_yf_agent.py
from __future__ import annotations

import json
import logging
import time
import traceback
from typing import Any, Dict, Optional, TypedDict

# LangGraph
try:
    from langgraph.graph import StateGraph, END
except Exception as e:  # pragma: no cover
    raise ImportError("langgraph is required. Install with: pip install langgraph") from e

# CrewAI tool base
try:
    from pydantic import BaseModel, Field
    from crewai.tools import BaseTool
except Exception as e:  # pragma: no cover
    raise ImportError("CrewAI and Pydantic are required. Install with: pip install crewai pydantic") from e

# Dynamic import helper to locate your notebook-exported module or notebook import
import importlib
import importlib.util
import os
import sys

def _try_import_module(names):
    for name in names:
        try:
            return importlib.import_module(name)
        except Exception:
            continue
    return None

_candidates = ["yahooFinance", "yahoo_finance_agent", "yahoo_finance", "yfinance_agent", "yahooFinance_ipynb"]
yf_module = _try_import_module(_candidates)

if yf_module is None:
    cwd_files = os.listdir(".")
    py_candidates = [f for f in cwd_files if f.lower().startswith("yahoo") and f.lower().endswith(".py")]
    if py_candidates:
        path = os.path.abspath(py_candidates[0])
        spec = importlib.util.spec_from_file_location("yahoo_finance_dynamic", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["yahoo_finance_dynamic"] = mod
        spec.loader.exec_module(mod)  # type: ignore
        yf_module = mod

if yf_module is None:
    # Last resort: try import-ipynb if present and a notebook file exists
    nb_candidates = [f for f in cwd_files if f.lower().startswith("yahoo") and f.lower().endswith(".ipynb")]
    if nb_candidates:
        try:
            import import_ipynb  # type: ignore
            yf_module = importlib.import_module(os.path.splitext(nb_candidates[0])[0])
        except Exception:
            pass

if yf_module is None:
    raise ImportError(
        "Unable to import your YahooFinanceAgent module. Place your YahooFinanceAgent .py or .ipynb file in this folder "
        "and ensure it is importable under a yahoo* name."
    )

log = logging.getLogger(__name__)

class YFState(TypedDict, total=False):
    ticker: str
    period_days: int
    context: Dict[str, Any]
    result: Any

class YFAgentAdapter:
    """Adapter that calls your YahooFinanceAgent.analyze(symbol, period_days)."""

    def __init__(self, module=yf_module):
        AgentClass = getattr(module, "YahooFinanceAgent", None)
        if AgentClass is None:
            raise AttributeError("Module does not contain YahooFinanceAgent class")
        self._agent = AgentClass()

    def run(self, ticker: str, period_days: int = 365, context: Optional[Dict[str, Any]] = None):
        try:
            return self._agent.analyze(ticker, period_days=period_days)
        except Exception as e:
            log.exception("YahooFinanceAgent analyze() raised an exception")
            return {"error": str(e)}

def _execute_node(adapter: YFAgentAdapter):
    def _node(state: YFState) -> YFState:
        ticker = state.get("ticker", "")
        period_days = state.get("period_days", 365)
        ctx = state.get("context", {}) or {}

        # Ensure trace list exists in context and append a pre-call snapshot
        trace = ctx.setdefault("_trace", [])
        start_ts = time.time()
        trace.append({
            "step": "start_execute",
            "ticker": ticker,
            "period_days": period_days,
            "ts": start_ts,
        })

        try:
            result = adapter.run(ticker=ticker, period_days=period_days, context=ctx)
            end_ts = time.time()
            trace.append({
                "step": "completed_execute",
                "ticker": ticker,
                "duration_s": round(end_ts - start_ts, 3),
                "ts": end_ts,
            })
        except Exception as e:
            tb = traceback.format_exc()
            ts = time.time()
            trace.append({
                "step": "error_execute",
                "ticker": ticker,
                "error": str(e),
                "tb": tb,
                "ts": ts,
            })
            result = {"error": str(e)}

        # Return result and include the trace inside context for caller inspection
        return {**state, "result": result, "context": {**ctx, "_trace": trace}}
    return _node

def build_yf_graph(adapter: Optional[YFAgentAdapter] = None):
    adapter = adapter or YFAgentAdapter()
    graph = StateGraph(YFState)
    graph.add_node("execute", _execute_node(adapter))
    graph.set_entry_point("execute")
    graph.add_edge("execute", END)
    app = graph.compile()
    return app

class YFQueryInput(BaseModel):
    ticker: str = Field(..., description="Ticker symbol to analyze, e.g., 'AAPL'.")
    period_days: Optional[int] = Field(365, description="Days of history to fetch.")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional pass-through context.")

class YahooFinanceTool(BaseTool):
    name: str = "yahoo_finance_analysis"
    description: str = (
        "Run the YahooFinanceAgent analysis pipeline. "
        "Accepts ticker and optional period_days and returns the agent payload (JSON)."
    )
    args_schema: type = YFQueryInput

    def __init__(self, app=None, adapter: Optional[YFAgentAdapter] = None, **kwargs):
        super().__init__(**kwargs)
        self._adapter = adapter or YFAgentAdapter()
        self._app = app or build_yf_graph(self._adapter)

    def _run(self, ticker: str, period_days: int = 365, context: Optional[Dict[str, Any]] = None) -> str:
        if not isinstance(ticker, str) or not ticker.strip():
            raise ValueError("ticker must be a non-empty string, e.g., 'AAPL'")
        ticker = ticker.strip()
        state: YFState = {"ticker": ticker, "period_days": period_days, "context": context or {}}
        out: YFState = self._app.invoke(state)
        result = out.get("result")
        # Ensure the trace is included in returned JSON where possible
        combined = {"result": result, "context": out.get("context", {})}
        if isinstance(combined, (dict, list)):
            try:
                return json.dumps(combined, ensure_ascii=False)
            except Exception:
                return str(combined)
        return str(combined)

def create_crewai_yf_agent(agent_cls, role: str = "Yahoo Finance Analyst", goal: str = "", backstory: str = "", **kwargs):
    tool = YahooFinanceTool()
    agent = agent_cls(
        role=role or "Yahoo Finance Analyst",
        goal=goal or "Fetch and analyze historical prices and fundamentals using YahooFinanceAgent.",
        backstory=backstory or "An analyst agent that wraps the YahooFinanceAgent to produce ratings and indicators.",
        tools=[tool],
        allow_delegation=False,
        verbose=True,
        **kwargs,
    )

    def run_fn(ticker: str, period_days: int = 365, context: dict | None = None):
        return tool._run(ticker, period_days=period_days, context=context)

    object.__setattr__(agent, "run", run_fn)
    return agent


# In[7]:


# Run and print trace for a ticker using the created wrapper and Crew Agent classes
from crewai import Agent



# instantiate agent
agent = create_crewai_yf_agent(Agent)

# access the tool directly
tool = agent.tools[0]  # YahooFinanceTool

# build state and invoke the underlying LangGraph app to get structured state with trace
state = {"ticker": "AAPL", "period_days": 365, "context": {}}
out_state = tool._app.invoke(state)

# pretty-print result and trace
import json
print("=== Result payload ===")
print(json.dumps(out_state.get("result"), indent=2, ensure_ascii=False))
print("\n=== Trace ===")
trace = out_state.get("context", {}).get("_trace", [])
for i, t in enumerate(trace, 1):
    print(f"{i}. {t}")


# In[ ]:




