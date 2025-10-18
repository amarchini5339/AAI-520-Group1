
import os
import json
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from News_Agent import NewsAgent  

# Load environment variables
load_dotenv()

# Initialize LLM (Gemini 2.5 Flash) 
llm = LLM(
    model="gemini/gemini-2.5-flash",
    api_key=os.getenv("G_API_KEY")  # Google Gemini API key
)

# Define function to call your custom NewsAgent
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

# Define CrewAI Agent 
news_agent_wrapper = Agent(
    role="News Analysis Agent",
    goal="Fetch and analyze recent news for a given company and summarize sentiment.",
    backstory="This agent uses NewsAgent to collect and analyze company-related news articles.",
    llm=llm,  # Attach Gemini as the reasoning model
)



# Define CrewAI Task 
news_agent_task = Task(
    description="Run NewsAgent workflow for {company} and return analysis result.",
    expected_output=""" 
    Required JSON format:
    {
  "company": "{company}",
  "date": "<ISO8601 timestamp of analysis>",
  "sentiment_summary": {
      "overall_sentiment": "<Positive | Neutral | Negative>",
      "positive_articles": <number>,
      "neutral_articles": <number>,
      "negative_articles": <number>,
      "main_topic": ["theme 1", "theme 2", "..."],
      "good_news": ["point 1", "point 2", "..."],
      "bad_news": ["point 1", "point 2", "..."],
      "neutral_news": ["point 1", "point 2", "..."]
  },
  "feedback": "<short summary evaluating completeness and quality of analysis>"
} 

Rules:
1. Always return valid JSON only — no explanations, markdown, or extra text.
2. Always include all keys exactly as shown.
3. Count the number of articles correctly for each sentiment.
4. Summaries (main_topic, good_news, bad_news, feedback) should be concise and informative.
5. Dates must be in ISO8601 format (YYYY-MM-DDTHH:MM:SS).
""",
    agent=news_agent_wrapper,
    function= run_news_agent,
    )


# Define Crew 
news_agent_crew = Crew(
    agents=[news_agent_wrapper],
    tasks=[news_agent_task],
    process=Process.sequential,
)

# Optional test run 
if __name__ == "__main__":
    print(" Running NewsAgent CrewAI pipeline...\n")
    result = news_agent_crew.kickoff(inputs={"company": "Microsoft"})
    print("\n Final Result:")
    # Try to get the JSON safely
    try:
        # Check if CrewAI result is a dict already
        if hasattr(result, "raw"):
            clean_output = result.raw.strip('`').strip()
            if clean_output.startswith("json"):
                clean_output = clean_output[4:].strip()
            parsed = json.loads(clean_output)
        else:
            # Already a dict
            parsed = result
    except json.JSONDecodeError:
        parsed = {"error": "Invalid JSON returned by NewsAgent", "raw_result": getattr(result, "raw", str(result))}

    # Pretty print
    print(json.dumps(parsed, indent=2))
