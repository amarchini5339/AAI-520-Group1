import os
from datetime import datetime, timedelta
import pandas as pd
from fredapi import Fred
from agent import Agent
import openai

class FREDResearcher(Agent):
    def __init__(self, api_key=None, openai_api_key=None):
        """
        Initialize the FRED Researcher with API keys.
        
        Args:
            api_key (str, optional): FRED API key. If not provided, will try to get from environment.
            openai_api_key (str, optional): OpenAI API key. If not provided, will try to get from environment.
        """
        super().__init__("FRED Researcher")
        self.api_key = api_key or os.getenv('FRED_API_KEY')
        self.openai_api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        
        if not self.api_key:
            raise ValueError("FRED API key must be provided or set in FRED_API_KEY environment variable")
        if not self.openai_api_key:
            raise ValueError("OpenAI API key must be provided or set in OPENAI_API_KEY environment variable")
            
        openai.api_key = self.openai_api_key
        self.fred = Fred(api_key=self.api_key)
        
        # Define core economic indicators
        self.indicators = {
            'CPIAUCSL': 'Consumer Price Index',
            'UNRATE': 'Unemployment Rate',
            'FEDFUNDS': 'Federal Funds Rate',
            'GDP': 'Gross Domestic Product',
            'INDPRO': 'Industrial Production Index'
        }

    def process(self, symbol):
        """
        Fetch and analyze economic indicators from FRED that might impact the given symbol.
        
        Args:
            symbol (str): The stock symbol to analyze
            
        Returns:
            dict: A dictionary containing the economic indicators and their latest values
        """
        self.remember(f"Fetching core economic indicators for analysis of {symbol}")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)  # Get 1 year of data
        
        economic_data = {}
        
        try:
            for series_id, description in self.indicators.items():
                self.remember(f"Fetching {description} (Series: {series_id})")
                
                # Get the data series from FRED
                series = self.fred.get_series(
                    series_id,
                    observation_start=start_date.strftime('%Y-%m-%d'),
                    observation_end=end_date.strftime('%Y-%m-%d')
                )
                
                if not series.empty:
                    latest_value = series.iloc[-1]
                    previous_value = series.iloc[-2] if len(series) > 1 else None
                    
                    # Calculate percentage change
                    pct_change = ((latest_value - previous_value) / previous_value * 100) if previous_value else None
                    
                    economic_data[series_id] = {
                        'description': description,
                        'latest_value': latest_value,
                        'previous_value': previous_value,
                        'pct_change': pct_change,
                        'last_updated': series.index[-1].strftime('%Y-%m-%d')
                    }
                    
                    self.remember(f"Latest {description}: {latest_value:.2f}")
                    if pct_change:
                        self.remember(f"{description} change: {pct_change:.2f}%")
            
            summary = self._generate_summary(economic_data, symbol)
            return {
                "source": "FRED",
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "indicators": economic_data,
                    "analysis": summary
                }
            }
            
        except Exception as e:
            error_msg = f"Error fetching FRED data: {str(e)}"
            self.remember(error_msg)
            return {
                "source": "FRED",
                "data": "Economic data unavailable",
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            }
    
    def _generate_summary(self, economic_data, symbol=None):
        """
        Generate a summary of the economic indicators using LLM analysis.
        
        Args:
            economic_data (dict): The collected economic data
            symbol (str, optional): The stock symbol being analyzed
            
        Returns:
            str: A detailed analysis of the economic situation
        """
        # Prepare the economic data for the prompt
        data_points = []
        for series_id, data in economic_data.items():
            data_points.append(
                f"{data['description']}: Current value: {data['latest_value']:.2f}, "
                f"Change: {data['pct_change']:.2f}% (as of {data['last_updated']})"
            )
        
        economic_context = "\n".join(data_points)
            
        prompt = f"""As an economic analyst, analyze how these core economic indicators might impact {symbol} stock:

        Economic Indicators:
        {economic_context}

        Please provide a concise analysis that covers:
        1. How these macroeconomic conditions might specifically affect {symbol}'s business and stock performance
        2. Key risks or opportunities for {symbol} based on these economic indicators
        3. How current monetary policy (Fed Funds Rate) might impact {symbol}'s valuation
        4. Whether the overall economic environment (GDP, CPI, Employment) is favorable for {symbol}

        Focus on making clear connections between the economic data and potential impacts on {symbol}.
        Keep the analysis brief but insightful."""

        try:
            self.remember("Generating LLM-based economic analysis")
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert economic analyst providing insights based on FRED economic data."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.7
            )
            
            analysis = response.choices[0].message.content
            self.remember(f"Generated economic analysis: {analysis}")
            print(analysis)
            return analysis
            
        except Exception as e:
            error_msg = f"Error generating LLM analysis: {str(e)}"
            self.remember(error_msg)
            return error_msg