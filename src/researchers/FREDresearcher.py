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

# Import the FRED analysis logic
try:
    from researchers import fred_tools as fred_agent
except Exception as e:  # pragma: no cover
    raise ImportError(
        "Unable to import fred_tools.py. Ensure it is on PYTHONPATH and importable."
    ) from e

log = logging.getLogger(__name__)

class FREDState(TypedDict, total=False):
    query: str
    context: Dict[str, Any]
    result: Any

class FREDAgentAdapter:
    def __init__(self, module=fred_agent):
        self._module = module
        self._entrypoint = getattr(module, "main")

    def run(self, query: str, context=None):
        # Treat query as ticker
        return self._entrypoint(query)

def create_crewai_fred_agent(agent_class):
    """
    Create a CrewAI agent for FRED economic analysis.
    """
    agent = FREDAgentAdapter()
    
    class FREDAnalysisTool(BaseTool):
        name: str = "fred_analysis"
        description: str = "Analyzes economic indicators from FRED to assess their impact on a given stock ticker"

        def _run(self, query: str) -> Dict[str, Any]:
            return agent.run(query)

        async def _arun(self, query: str) -> Dict[str, Any]:
            return self._run(query)

    return agent_class(
        name="FRED Economic Analyst",
        role="Economic Research Specialist",
        goal="Analyze macroeconomic indicators from FRED to assess their impact on specific stocks",
        backstory="""You are an expert economic analyst with deep knowledge of how 
        macroeconomic indicators affect stock performance. You use FRED data to provide 
        insights about the economic environment's impact on specific companies.""",
        allow_delegation=False,
        tools=[FREDAnalysisTool()]
    )
