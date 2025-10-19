"""
run_sec_agent.py
"""

import logging
from crewai import Agent, Crew, Task
from SECresearcher import create_crewai_sec_agent

# Configure logging (optional but useful)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def main():
    # 1 Create the SEC analysis agent
    sec_agent = create_crewai_sec_agent(Agent)

    # 2 Create a Crew task that asks the agent to analyze a ticker
    ticker = "MSFT"  # change to any ticker
    log.info(f"Creating Crew task for ticker: {ticker}")

    # Build a single Task that instructs the agent to run on the ticker.
    # The exact Task API may vary by crewai version; this uses a common pattern.
    task = Task(
        description=f"Analyze SEC filings for ticker {ticker}",
        agent=sec_agent,
        input_payload={"ticker": ticker},
        expected_output="JSON with rating and extracted risk/opportunity bullets",
    )

    # Create a Crew with our agent and a single task and kickoff the workflow
    crew = Crew(agents=[sec_agent], tasks=[task])
    log.info("Kicking off Crew workflow...")
    result = crew.kickoff()

    # Display the results from the Crew
    print("\n=== Crew Result ===")
    print(result)

    # Direct call is still available for quick testing (uncomment):
    # direct_result = sec_agent.run(ticker)
    # print(direct_result)

if __name__ == "__main__":
    main()