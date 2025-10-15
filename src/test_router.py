from crewai.flow.flow import Flow, listen, start, router, or_
from dotenv import load_dotenv
from litellm import completion

from researchers.tools import yahoo_find_ticker as yft

from researchers.SECresearcher import sec_filing_flow_crew

from News_Agent_Crew import news_agent_crew

load_dotenv()

class ExampleFlow(Flow):
    model = "gpt-5-mini"

    @start()
    def get_ticker(self):
        print("Starting flow")
        print(f"Flow State ID: {self.state['id']}")

        # Get user-provided prompt or fallback to Microsoft
        prompt = self.state.get("prompt", "Microsoft")
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

    @router(get_ticker)
    def check_equity(self):
        type = self.state["best"]["typeDisp"]

        if type == "":
            return "UNKNOWN_BRANCH"
        elif type == "EQUITY":
            return "EQUITY_BRANCH"
        else:
            return "NON_EQUITY_BRANCH"
    
    @listen('EQUITY_BRANCH')
    def get_sec_agent(self):
        symbol = self.state["best"]["symbol"]
        print(f"Equity branch for {symbol} - running SEC research agent...")

        try:
            result = sec_filing_flow_crew.kickoff(inputs={"ticker": symbol})
            self.state["sec_result"] = result
            print(f"SEC Research completed for {symbol}")
        except Exception as e:
            print(f"Error running SEC agent: {e}")
            self.state["sec_result"] = {}
        return "SEC_DONE"
 
    @listen('get_sec_agent')
    def get_yahoo_agent(self):
        symbol = self.state["best"]["symbol"]
        print(f"Yahoo branch for {symbol} - proceeding to do yahoo research")
        return 'YAHOO_DONE'
    
    @listen(or_('NON_EQUITY_BRANCH', 'get_yahoo_agent'))
    def get_fred_agent(self):
        symbol = self.state["best"]["symbol"]
        print(f"Yahoo done branch for {symbol} - proceeding to do fred research")
        return 'FRED_DONE'
    
    @listen('get_fred_agent')
    def get_news_agent(self):
        symbol = self.state["best"]["symbol"]
        print(f"Fred done branch for {symbol} - proceeding to do news research")
        return 'NEWS_DONE'
    
    @listen('get_news_agent')
    def get_news_agent(self):
        symbol = self.state["best"]["symbol"]
        print(f"News branch for {symbol} - proceeding to do news research")
        result = news_agent_crew.kickoff(inputs={"company": symbol})
        self.state["news_result"] = result
        print(f"NewsAgent Crew completed for {symbol}")
        return 'NEWS_DONE'
    
    def finalize(self):
        symbol = self.state["best"]["symbol"]
        print(f"News done branch for {symbol} - finalizing flow")
        return self.state

# --- Run the flow ---
flow = ExampleFlow()

flow.plot()  # visualize flow

result = flow.kickoff(inputs={"prompt": "OpenAI",})

print(f"\nResult: {result}")
