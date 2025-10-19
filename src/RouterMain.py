# src/RouterMain.py
# Main flow router for financial analysis using multiple agents
from crewai.flow.flow import Flow, listen, start, router, or_
from crewai import Agent, Crew, Task
from dotenv import load_dotenv
from litellm import completion

# Import yahoo finance ticker finder
from researchers.tools import yahoo_find_ticker as yft

# Import necessary functions and classes from other researchers
from researchers.SECresearcher import run_sec_filing_agent, _safe_parse_json, _load_openai_client
from researchers.News_Agent_Crew import news_agent_crew
from researchers.FREDresearcher import create_crewai_fred_agent
from researchers.YahooFinanceCrew import run_yahoo_finance_agent

# Import logging for debugging
import logging

# Load environment variables
load_dotenv()

# Define the main financial analysis flow
class FinancialAnalysisFlow(Flow):
    # Use a lightweight model for intermediate steps
    model = "gpt-5-mini"

    # Initialize the flow with tracing enabled
    def __init__(self):
        # Initialize state and logging
        super().__init__(tracing=True)
        logging.basicConfig(level=logging.INFO)
        self.log = logging.getLogger(__name__)
        self.state['debug'] = False  # default debug to False
        self.client = _load_openai_client()  # Initialize OpenAI client

    # Define the start of the flow
    @start()
    def get_ticker(self):
        self.log.info("Starting flow")
        print(f"Flow State ID: {self.state['id']}")

        if 'debug' in self.state:
            # Get debug flag from state, default to False
            self.state['debug'] = self.state.get('debug', False)

        # Get user-provided prompt or fallback to Microsoft
        prompt = self.state.get("prompt", "Microsoft")
        if self.state["debug"]:
            print(f"Prompt: {prompt}")

        try:
            best = yft.yahoo_find_ticker(prompt)
            self.state["best"] = best
            print(best)
            return best
        except Exception as e:
            best = {"symbol": "ERROR", "name": str(e), "exch": "", "exchDisp": "", "type": "", "typeDisp": ""}
            self.state["best"] = best
            return best
    # Define the router for equity check
    @router(get_ticker)
    def check_equity(self):
        type = self.state["best"]["typeDisp"]

        if type == "":
            return "UNKNOWN_BRANCH"
        elif type == "EQUITY":
            return "EQUITY_BRANCH"
        else:
            return "NON_EQUITY_BRANCH"
    
    # Define the handler for unknown security types
    @listen('UNKNOWN_BRANCH')
    def handle_unknown(self):
        symbol = self.state["best"]["symbol"]
        print(f"Unknown branch for {symbol} - cannot proceed with research.")
        self.state["error"] = f"Unknown security type for symbol: {symbol}"
        return 'ERROR_DONE'
    
    # Define the handler for equity securities
    @listen('EQUITY_BRANCH')
    def get_sec_agent(self):
        symbol = self.state["best"]["symbol"]
        print(f"Equity branch for {symbol} - running SEC research agent...")

        try:
            # Run the SEC filing analysis agent
            result = run_sec_filing_agent({"ticker": symbol})
            self.state["sec_result"] = result
            if self.state["debug"]:
                print(self.state["sec_result"])
            print(f"SEC Research completed for {symbol}")
        except Exception as e:
            print(f"Error running SEC agent: {e}")
            self.state["sec_result"] = {}
        return "SEC_DONE"
 
    @listen('get_sec_agent')
    def get_yahoo_agent(self):
        symbol = self.state["best"]["symbol"]
        # Run the Yahoo Finance research agent
        yahoo_result = run_yahoo_finance_agent({"ticker": symbol})
        self.state["yahoo_result"] = yahoo_result
        if self.state["debug"]:
            print(self.state["yahoo_result"])
        print(f"Yahoo branch for {symbol} - proceeding to do yahoo research")
        return 'YAHOO_DONE'
    
    @listen(or_('NON_EQUITY_BRANCH', 'get_yahoo_agent'))
    def get_fred_agent(self):
        symbol = self.state["best"]["symbol"]
        try:
            print(f"FRED branch for {symbol} - running FRED research agent...")
            # Create FRED agent
            fred_agent = create_crewai_fred_agent(Agent)
            # Create a task for economic analysis
            task = Task(
                description=f"Analyze economic indicators from FRED for their impact on {symbol}",
                agent=fred_agent,
                input_payload={"ticker": symbol},
                expected_output="JSON with 1-5 rating and economic analysis")

            # Create and run the crew
            crew = Crew(agents=[fred_agent], tasks=[task])
            self.log.info("Starting economic analysis...")
            result = crew.kickoff()
            
        except Exception as e:
            print(f"Error running FRED agent: {e}")
            self.state["fred_result"] = {}
            return 'ERROR_DONE'

        self.state["fred_result"] = result
        if self.state["debug"]:
            print(self.state["fred_result"])
        print(f"Yahoo done branch for {symbol} - proceeding to do fred research")
        return 'FRED_DONE'
    
    @listen('get_fred_agent')
    def get_news_agent(self):
        symbol = self.state["best"]["symbol"]
        print(f"News branch for {symbol} - proceeding to do news research")
        try:
            # Run the News agent crew
            result = news_agent_crew.kickoff(inputs={"company": symbol})
            self.state["news_result"] = result
            if self.state["debug"]:
                print(self.state["news_result"])
        except Exception as e:
            print(f"Error running News agent: {e}")
            self.state["news_result"] = {}
            return 'ERROR_DONE'
        print(f"NewsAgent Crew completed for {symbol}")
        return 'NEWS_DONE'
    
    @listen('get_news_agent')
    def finalize(self):
        symbol = self.state["best"]["symbol"]
        print(self.state)
        print(f"Complete analysis for {symbol} - finalizing flow")
        try:
            # Final synthesis using advanced model
            response = self.client.chat.completions.create(
            model="gpt-5", # use advanced model for final synthesis
            messages=[
                {"role": "system", "content": "You are a financial analysis expert."},
                {
                    "role": "user",
                    "content": (
                        "Provide a rating from 1 'sell', 2 'underperform', 3 'hold', "
                        "4 'outperform', 5 'strong buy' based on the following context. "
                        f"SEC Report JSON: {self.state['sec_result']}. "
                        f"FRED JSON: {self.state['fred_result']}. "
                        f"News JSON: {self.state['news_result']}. "
                        f"Yahooo Finance JSON: {self.state['yahoo_result']}. "
                        "Respond with easy to read report only like rating and rationale. "
                        "Create a concise rationale for your rating.  List bull and bear cases for investment."
                        "Explain how macroeconomic factors from FRED influenced your rating and how changing interest rates might impact the company's performance."
                    ),
                },
            ],
        )
        except Exception as e:
            print(f"Error during final analysis: {e}")
            self.state["final_result"] = {}
            return 'ERROR_DONE'

        final_result = _safe_parse_json(response.choices[0].message.content)
        self.state["final_result"] = final_result
        print(self.state["final_result"])
        print(f"Final analysis completed for {symbol}")
        return self.state

# --- Run the flow ---
flow = FinancialAnalysisFlow()

flow.plot()  # visualize flow

# Example run using Apple as prompt
result = flow.kickoff(inputs={"prompt": "Apple", "debug": True})
