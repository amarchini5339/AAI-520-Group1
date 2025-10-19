import json
import os
from typing import Any, Dict

from crewai import Agent, Crew, Process, Task
from crewai.flow.flow import Flow, and_, listen, start
from dotenv import load_dotenv
from openai import OpenAI

try:
    # Import sec_tools from the tools package if available
    from tools.sec_tools import (
        calc_debt_to_equity,
        calc_positive_netincome,
        calc_profit,
        calc_yoy_rev,
        get_recent_facts,
        get_risks_mna as fetch_risks_mna,
        ticker_to_cik,
    )
except ImportError:
    # Fallback import if tools is not a package
    from researchers.tools.sec_tools import (  # type: ignore
        calc_debt_to_equity,
        calc_positive_netincome,
        calc_profit,
        calc_yoy_rev,
        get_recent_facts,
        get_risks_mna as fetch_risks_mna,
        ticker_to_cik,
    )

# === Helper functions ===
def _load_openai_client() -> OpenAI:
    load_dotenv()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
    return OpenAI(api_key=openai_api_key)


def _safe_parse_json(raw_content: str) -> Any:
    try:
        return json.loads(raw_content)
    except json.JSONDecodeError:
        return raw_content

from openai import OpenAI

# === SEC Filing Analysis Flow ===
class SECFilingAnalysis:
    # Initialize with OpenAI client
    def __init__(self):
        self.client = _load_openai_client()
        self.state = {}

    # === Public API ===
    def run(self, ticker: str):
        if not ticker:
            raise ValueError("No ticker provided. Example: run('AAPL')")

        cik = self._get_cik(ticker)
        facts = self._get_facts(cik)
        financial_ratings = self._calc_financial_ratings(facts)
        risk_mna_rating = self._get_risks_mna(cik)
        final_report = self._get_final_report(financial_ratings, risk_mna_rating)

        return {
            "final_result": final_report,
            "financial_ratings": financial_ratings,
            "risk_mna_rating": risk_mna_rating,
        }

    # === Individual steps ===

    # Get CIK from ticker
    def _get_cik(self, ticker: str):
        cik = ticker_to_cik(ticker)
        if not cik:
            raise ValueError(f"Unable to resolve CIK for ticker '{ticker}'.")
        self.state["cik"] = cik
        return cik

    # Get recent facts from CIK
    def _get_facts(self, cik: str):
        facts = get_recent_facts(cik)
        if not facts:
            raise ValueError(f"No recent facts returned for CIK '{cik}'.")
        self.state["facts"] = facts
        return facts

    # Calculate financial ratings
    def _calc_financial_ratings(self, facts):
        financial_ratings = {
            "yoy": calc_yoy_rev(facts),
            "profit": calc_profit(facts),
            "debt": calc_debt_to_equity(facts),
            "income": calc_positive_netincome(facts),
        }
        self.state["financial_ratings"] = financial_ratings
        return financial_ratings

    # Get risk/MNA rating
    def _get_risks_mna(self, cik: str):
        risks, mna = fetch_risks_mna(cik)

        response = self.client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": "You are a financial analysis expert."},
                {
                    "role": "user",
                    "content": (
                        "Provide a rating from 1 'sell', 2 'underperform', 3 'hold', "
                        "4 'outperform', 5 'strong buy' for the following based on risk factors: "
                        f"{risks} and management discussion and analysis: {mna}. "
                        "Respond with JSON only like {'rating': 4, 'rationale': 'text'}."
                    ),
                },
            ],
        )

        parsed_rating = _safe_parse_json(response.choices[0].message.content)
        self.state["risk_mna_rating"] = parsed_rating
        return parsed_rating

    # Get final report
    def _get_final_report(self, financial_ratings, risk_mna_rating):
        response = self.client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": "You are a financial analysis expert."},
                {
                    "role": "user",
                    "content": (
                        "Provide a rating from 1 'sell', 2 'underperform', 3 'hold', "
                        "4 'outperform', 5 'strong buy' based on the following context. "
                        f"Financial ratings: {financial_ratings}. "
                        f"Risk/MNA rating: {risk_mna_rating}. "
                        "Respond with JSON only like {'rating': 4, 'rationale': 'text'}. "
                        "Give 20% weight for YoY, 20% for profit, 15% for debt, "
                        "15% for income, 30% for risk/mna."
                    ),
                },
            ],
        )

        final_result = _safe_parse_json(response.choices[0].message.content)
        return final_result

# run SEC Filing Analysis as an Agent
def run_sec_filing_agent(inputs: dict):
    ticker = inputs.get("ticker")
    analyzer = SECFilingAnalysis()
    result = analyzer.run(ticker)
    return result

# Define the SEC Filing Agent
sec_filing_agent = Agent(
    role="Flow Runner",
    goal="Run the SEC filing analysis and return raw output",
    name="SEC Filing Agent",
    description="Executes SEC analysis and returns unmodified JSON",
    backstory="This agent runs the SEC filing analysis flow and returns the results as-is.",
    expected_output="Full JSON returned from sec_filing_flow, do not modify.",
    model="gpt-5-mini",
    run_function=run_sec_filing_agent,
)

if __name__ == "__main__":
    print(run_sec_filing_agent({"ticker": "AAPL"}))