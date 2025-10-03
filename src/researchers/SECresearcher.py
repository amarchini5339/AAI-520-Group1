from agent import Agent

class SECresearcher(Agent):
    def process(self, symbol):
        """
        Example: Fetch SEC filings from EDGAR.
        """
        self.remember(f"Fetching SEC filings for {symbol}")
        # TODO: call EDGAR API to get 10-K, 10-Q filings
        return {"source": "SEC", "data": f"SEC filings for {symbol}"}
