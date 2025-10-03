from agent import Agent

class YahooFinanceResearcher(Agent):
    def process(self, symbol):
        """
        Example: Get stock data from Yahoo Finance.
        """
        self.remember(f"Fetching Yahoo Finance data for {symbol}")
        # TODO: use yfinance library to fetch prices, financials
        return {"source": "YahooFinance", "data": f"Stock data for {symbol}"}