# News_Agent_Crew.py
import os
import json
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from News_Agent import NewsAgent  # your custom agent class

# Load environment variables
load_dotenv()

# --- Initialize LLM (Gemini 2.5 Flash) ---
llm = LLM(
    model="gemini/gemini-2.5-flash",
    api_key=os.getenv("G_API_KEY")  # Google Gemini API key
)

# --- Define function to call your custom NewsAgent ---
def run_news_agent(company: str):
    """
    Runs the NewsAgent workflow for a given company and returns the result.
    """
    agent = NewsAgent(
        gemini_api_key=os.getenv("G_API_KEY"),
        news_api_key=os.getenv("NEWS_API_KEY")
    )
    result = agent.run(company)
    try:
        return json.loads(result)  # parse JSON string if valid
    except json.JSONDecodeError:
        return {"error": "Invalid JSON returned by NewsAgent", "raw_result": result}

# --- Define CrewAI Agent ---
news_agent_wrapper = Agent(
    role="News Analysis Agent",
    goal="Fetch and analyze recent news for a given company and summarize sentiment.",
    backstory="This agent uses NewsAgent to collect and analyze company-related news articles.",
    llm=llm,  # Attach Gemini as the reasoning model
)

# --- Define CrewAI Task ---
news_agent_task = Task(
    description="Run NewsAgent workflow for {company} and return analysis result.",
    expected_output="JSON report containing articles, sentiment summary, and feedback.",
    agent=news_agent_wrapper,
    function=run_news_agent,
)

# --- Define Crew ---
news_agent_crew = Crew(
    agents=[news_agent_wrapper],
    tasks=[news_agent_task],
    process=Process.sequential,
)

# --- Optional test run ---
if __name__ == "__main__":
    print(" Running NewsAgent CrewAI pipeline...\n")
    result = news_agent_crew.kickoff(inputs={"company": "Microsoft"})
    print("\n Final Result:")
    clean_output = result.raw.strip('`').strip()
    if clean_output.startswith("json"):
        clean_output = clean_output[4:].strip()

    parsed = json.loads(clean_output)
    print(json.dumps(parsed, indent=2))
