from crewai.flow.flow import Flow, listen, start, and_
from crewai import Agent, Task, Crew, Process
from dotenv import load_dotenv
import os
from openai import OpenAI

# Import your SEC helper function
from researchers.tools.sec_tools import ticker_to_cik, get_recent_facts, calc_yoy_rev, calc_profit, calc_debt_to_equity, calc_positive_netincome, get_risks_mna


class sec_filing_flow(Flow):    
    def __init__(self):
        super().__init__()
        load_dotenv()
        openai_api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=openai_api_key)

    @start()
    def get_cik(self):
        # Retrieve the ticker from the flow state
        ticker = self.state.get("ticker")
        if not ticker:
            raise ValueError("No ticker provided. Pass one via kickoff(inputs={'ticker': 'AAPL'}).")

        print(f"Starting CIK lookup for {ticker}")

        # Call your local helper function


        
        cik = ticker_to_cik(ticker)

        # Save result in flow state
        self.state["cik"] = cik
        print(f"Found CIK for {ticker}: {cik}")
        return cik

    @listen('get_cik')
    def get_facts(self, cik):
        # This step can perform follow-up actions, like logging or enrichment
        facts = get_recent_facts(cik)
        self.state["facts"] = facts
        print(f"Retrieved {len(facts)} recent facts for CIK {cik} for ticker {self.state.get('ticker')}")
        return facts
    
    @listen('get_facts')
    def calc_financial_ratings(self, facts):
        yoy_json = calc_yoy_rev(facts)
        profit_json = calc_profit(facts)
        debt_json = calc_debt_to_equity(facts)
        income_json = calc_positive_netincome(facts)

        # Save all results in flow state
        self.state["financial_ratings"] = {
            "yoy": yoy_json,
            "profit": profit_json,
            "debt": debt_json,
            "income": income_json
        }

        print(f"Calculated financial ratings for CIK {self.state.get('cik')} for ticker {self.state.get('ticker')}")
        return self.state["financial_ratings"]
    
    @listen('get_cik')
    def get_risks_mna(self, cik):
        risks, mna = get_risks_mna(cik)

        client = self.client
        response = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": "You are a financial analysis expert."},
                {"role": "user", "content": f"Provide a rating from 1 'sell', 2 'underperform', 3 'hold', 4 'outperform', 5 'strong buy' for the following based on risk factors: {risks} and management discussion and analysis: {mna}. Respond with json only like {{'rating': 4, 'rationale': 'text'}}"}
            ]
        )
        self.state["risk_mna_rating"] = response.choices[0].message.content
        print(f"Calculated risk and MNA rating for CIK {self.state.get('cik')} for ticker {self.state.get('ticker')}")
        return self.state["risk_mna_rating"]
    
    @listen(and_('calc_financial_ratings', 'get_risks_mna'))
    def get_final_report(self):
        client = self.client
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are a financial analysis expert."},
                {"role": "user", "content": f"Provide a rating from 1 'sell', 2 'underperform', 3 'hold', 4 'outperform', 5 'strong buy' for the following based on {self.state['financial_ratings']} and risk/mna rating: {self.state['risk_mna_rating']}. Respond with json only like {{'rating': 4, 'rationale': 'text'}}. Give 20% weight for YoY, 20% weight for proffit, 15% weight for debt, 15% weight for income, 30% weight for risk/mna."}
            ]
        )
        return {'final result' : response.choices[0].message.content, 'financial_ratings': self.state['financial_ratings'], 'risk_mna_rating': self.state['risk_mna_rating']}

def run_sec_filing_flow(ticker: str):
    """Utility wrapper to run the sec_filing_flow for a given ticker."""
    flow = sec_filing_flow()
    result = flow.kickoff(inputs={"ticker": ticker})
    return result


# Define the agent that uses your Flow
sec_filing_flow_agent = Agent(
    role="SEC Analysis Agent",
    goal="Retrieve, calculate, and summarize SEC financial metrics for a given ticker symbol.",
    backstory="This agent uses the run_sec_filing_flow to analyze SEC filings and generate ratings."
)

# Define a CrewAI task that calls your local function
sec_filing_flow_task = Task(
    description="Run the run_sec_filing_flow for the given ticker {ticker} and return the JSON analysis result.",
    expected_output="JSON report containing CIK, financial metrics, and final rating.",
    agent=sec_filing_flow_agent,
    function=run_sec_filing_flow
)

# Optional: simple Crew for standalone runs or integration
sec_filing_flow_crew = Crew(
    agents=[sec_filing_flow_agent],
    tasks=[sec_filing_flow_task],
    process=Process.sequential
)

if __name__ == "__main__":
    # Initialize the flow
    flow = sec_filing_flow()

    # Run with your input
    result = flow.kickoff(inputs={"ticker": "FSLR"})

    print(f"\n Final Result: {result}")
