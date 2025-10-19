import logging
from crewai import Agent, Crew, Task
from researchers.FREDresearcher import create_crewai_fred_agent

from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def main():
    load_dotenv()
    # Create the FRED analysis agent
    fred_agent = create_crewai_fred_agent(Agent)

    # Set the ticker to analyze
    ticker = "MSFT"  # change to any ticker
    log.info(f"Creating Crew task for ticker: {ticker}")

    # Create a task for economic analysis
    task = Task(
        description=f"Analyze economic indicators from FRED for their impact on {ticker}",
        agent=fred_agent,
        input_payload={"ticker": ticker},
        expected_output="JSON with 1-5 rating and economic analysis"
    )

    # Create and run the crew
    crew = Crew(agents=[fred_agent], tasks=[task])
    log.info("Starting economic analysis...")
    result = crew.kickoff()

    # Display results
    print("\n=== Economic Analysis Result ===")
    print(result)

if __name__ == "__main__":
    main()
