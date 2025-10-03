from agent import Agent
from researchers.FREDresearcher import FREDResearcher
from researchers.YahooFinanceResearcher import YahooFinanceResearcher
from researchers.NewsResearcher import NewsResearcher
from researchers.SECresearcher import SECresearcher
from FinancialAnalyst import FinancialAnalyst
from ReportWriter import ReportWriter
from Coordinator import Coordinator

# -------------------------------
# Demo Run
# -------------------------------
if __name__ == "__main__":
    # Create specialist agents
    fred = FREDResearcher("FRED Researcher")
    yahoo = YahooFinanceResearcher("Yahoo Finance Researcher")
    news = NewsResearcher("News Researcher")
    sec = SECresearcher("SEC Researcher")

    analyst = FinancialAnalyst("Financial Analyst")
    writer = ReportWriter("Report Writer")

    # Coordinator with routing to all researchers
    coordinator = Coordinator("Coordinator", [fred, yahoo, news], analyst, writer)

    # Example run for stock symbol
    stock_symbol = "AAPL"
    final_report = coordinator.process(stock_symbol)

    print(final_report)
