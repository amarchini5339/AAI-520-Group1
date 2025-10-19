import os
import requests
from datetime import datetime, timedelta
import google.generativeai as genai
from dotenv import load_dotenv
import json
load_dotenv() 

class NewsAgent:
    def __init__(self, gemini_api_key, news_api_key=None):
        """Initialize agent with memory and APIs."""
        self.news_api_key = news_api_key
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")
        self.memory = {}  # store previous company analyses

    # Planning: decide workflow steps 
    def plan_steps(self, company):
        return ["fetch_news", "analyze_sentiment", "self_reflect", "iterate_if_needed"]

   # Tool: fetch news 
    def fetch_news(self, company, max_articles=10):
        """Fetch recent news for the specified company, filtering only relevant articles."""
        if not self.news_api_key:
            # Dummy fallback if no API key provided
            return [
                f"{company} quarterly earnings positive",
                f"{company} launches new product",
                f"{company} market analysis favorable",
                f"{company} competitor developments",
                f"{company} regulatory updates"
            ][:max_articles]

        company_name = company.lower()
        url = f"https://newsapi.org/v2/everything?q={company_name}&sortBy=publishedAt&apiKey={self.news_api_key}&language=en&pageSize={max_articles*2}"
        try:
            response = requests.get(url)
            data = response.json()
            if data.get("status") != "ok":
                return [f"NewsAPI error: {data.get('message', 'Unknown error')}"]

            articles = data.get("articles", [])
            # Filter articles by company name in title or description
            relevant_articles = [
                article for article in articles
                if company_name in article.get("title", "").lower()
                or company_name in (article.get("description") or "").lower()
            ]

            if not relevant_articles:
                return [f"No recent news articles found for {company}"]

            return [
                f"{article.get('title', 'No title')} ({article.get('source', {}).get('name', 'Unknown source')})"
                for article in relevant_articles[:max_articles]
            ]

        except Exception as e:
            return [f"Error fetching news: {str(e)}"]


    #  Analyze sentiment and summarize 
    def analyze_sentiment(self, news_articles):
        text = "\n".join(news_articles[:10])
        prompt = f"""
You are a financial news sentiment analyzer.
1. Classify each article as Positive, Negative, or Neutral.
2. Extract key risks and opportunities.
3. Summarize overall sentiment for the company.

Articles:
{text}
"""
        response = self.model.generate_content(prompt)
        return response.text
    
    # Reanalyze only new or uncovered information
    def reanalyze_sentiment(self, new_articles, previous_summary):
        text = "\n".join(new_articles[:10])
        prompt = f"""
    You are a financial news sentiment analyzer refining a previous analysis.

    Your goal:
- Identify ONLY truly new insights, opportunities, risks, or sentiment shifts not mentioned before.
- show the article that provides the new insight
- Avoid repeating or restating anything already covered.
- Keep it short, plain, and non-academic (no jargon).

    Previous summary:
    {previous_summary}

    New articles:
    {text}
    """
        response = self.model.generate_content(prompt)
        return response.text

    # Self-reflection: evaluate analysis quality 
    def self_reflect(self, company, analysis):
        prompt = f"""
You are a financial research agent.
Evaluate the following analysis for {company}. 
- Does it cover key risks and opportunities?
- Is the overall sentiment clear?
- Suggest improvements if needed.

Analysis:
{analysis}
"""
        response = self.model.generate_content(prompt)
        feedback = response.text
        return feedback

    # Iteration: refine based on feedback 
    def iterate(self, company, feedback, previous_analysis=None):
        if "improve" in feedback.lower():
            news = self.fetch_news(company, max_articles=15)  # fetch more
            new_analysis = self.reanalyze_sentiment(news, previous_summary=previous_analysis or "")
            return new_analysis
        return None

    # Run the full agent workflow 
    def run(self, company):
        print(f" Planning steps for: {company}")
        steps = self.plan_steps(company)

        # Check memory first
        if company in self.memory:
            print(f"Found previous analysis for {company} in memory. Using it as base.")
            previous_result = self.memory[company]
            previous_news = previous_result.get("articles", [])
            previous_analysis = previous_result.get("refined_analysis", None)
        else:
            previous_news = []
            previous_analysis = None

        news = []
        analysis = previous_analysis
        feedback = None
        refined = None

        for step in steps:
            if step == "fetch_news":
                print("→ Fetching news...")
                news = self.fetch_news(company)
                if previous_news:
                    news = previous_news + news
                print(f"  Found {len(news)} articles:")
                for i, article in enumerate(news, 1):
                    print(f"    Article {i}: {article}\n")

            elif step == "analyze_sentiment":
                print("→ Analyzing sentiment...")
                if not analysis:
                    analysis = self.analyze_sentiment(news)
                print("  Sentiment analysis complete. Details:\n")
                print(analysis)
            elif step == "self_reflect":
                print("→ Self-reflection in progress...")
                feedback = self.self_reflect(company, analysis)
                print("  Self-reflection complete. Feedback:\n")
                print(feedback)

            elif step == "iterate_if_needed":
                print("→ Iterating if needed...")
                refined = self.iterate(company, feedback, previous_analysis=analysis)
                if refined:
                    analysis = refined
                    print("  Refined analysis applied:\n")
                    print(refined)


        # Prepare JSON-like output 
        result = {
            "agent": "NewsAgent",
            "company": company,
            "timestamp": datetime.now().isoformat(),
            "articles": news,
            "sentiment_summary": analysis,
            "feedback": feedback,
            "refined_analysis": refined or analysis
        }

        # Save to memory
        self.memory[company] = result
        print(f" Workflow complete. Memory updated for {company}.")

        # Return as JSON string (for easy integration later)
        return json.dumps(result, indent=2)


if __name__ == "__main__":
    agent = NewsAgent(
        gemini_api_key=os.getenv("G_API_KEY"),
        news_api_key=os.getenv("API_KEY")
    )
    result_json = agent.run("Microsoft")
