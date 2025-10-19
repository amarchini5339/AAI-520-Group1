from __future__ import annotations
from openai import OpenAI
from dotenv import load_dotenv
import os
import inspect
import json
import logging
from typing import Any, Callable, Dict, Optional, TypedDict

# CrewAI tool base
try:
    from pydantic import BaseModel, Field
    from crewai.tools import BaseTool
except Exception as e:  # pragma: no cover
    raise ImportError(
        "CrewAI and Pydantic are required. Install with: pip install crewai pydantic"
    ) from e

# Import FRED tools
try:
    from tools import fred_tools as fred_agent
except ImportError:
    from researchers.tools import fred_tools as fred_agent

# Setup logging
log = logging.getLogger(__name__)

# load OpenAI client
def _load_openai_client() -> OpenAI:
    load_dotenv()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
    return OpenAI(api_key=openai_api_key)

# Define FRED State TypedDict
class FREDState(TypedDict, total=False):
    query: str
    context: Dict[str, Any]
    result: Any

# Define FREDAgentAdapter
class FREDAgentAdapter:
    def __init__(self, module=fred_agent):
        self._module = module
        self._entrypoint = getattr(module, "main")
        self.client = _load_openai_client()

    def run(self, query: str, context=None):
        # Treat query as ticker
        return self._entrypoint(query)

# Create CrewAI FRED Agent
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

    # Create the agent instance
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