"""
fred_tools.py - Core FRED analysis functionality
"""

import os
from datetime import datetime, timedelta
import pandas as pd
from fredapi import Fred
import openai
from typing import Dict, Any, Optional

def get_fred_data(ticker: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch and analyze economic indicators from FRED that might impact the given ticker.
    
    Args:
        ticker (str): The stock symbol to analyze
        api_key (str, optional): FRED API key. If not provided, will try to get from environment.
        
    Returns:
        dict: Analysis results with rating and context
    """
    # Initialize FRED API
    fred_key = api_key or os.getenv('FRED_API_KEY')
    if not fred_key:
        raise ValueError("FRED API key must be provided or set in FRED_API_KEY environment variable")
        
    fred = Fred(api_key=fred_key)
    
    # Core economic indicators
    indicators = {
        'CPIAUCSL': 'Consumer Price Index',
        'UNRATE': 'Unemployment Rate',
        'FEDFUNDS': 'Federal Funds Rate',
        'GDP': 'Gross Domestic Product',
        'INDPRO': 'Industrial Production Index'
    }
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    economic_data = {}
    
    try:
        # Fetch economic indicators
        for series_id, description in indicators.items():
            series = fred.get_series(
                series_id,
                observation_start=start_date.strftime('%Y-%m-%d'),
                observation_end=end_date.strftime('%Y-%m-%d')
            )
            
            if not series.empty:
                latest_value = series.iloc[-1]
                previous_value = series.iloc[-2] if len(series) > 1 else None
                pct_change = ((latest_value - previous_value) / previous_value * 100) if previous_value else None
                
                economic_data[series_id] = {
                    'description': description,
                    'latest_value': latest_value,
                    'previous_value': previous_value,
                    'pct_change': pct_change,
                    'last_updated': series.index[-1].strftime('%Y-%m-%d')
                }
        
        # Generate analysis using OpenAI
        return analyze_economic_data(economic_data, ticker)
        
    except Exception as e:
        return {
            "rating": 3,  # Neutral rating on error
            "analysis": f"Error fetching FRED data: {str(e)}",
            "details": {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        }

def analyze_economic_data(economic_data: Dict[str, Any], ticker: str) -> Dict[str, Any]:
    """Generate analysis of economic data using OpenAI."""
    openai_key = os.getenv('OPENAI_API_KEY')
    if not openai_key:
        raise ValueError("OpenAI API key must be set in OPENAI_API_KEY environment variable")
        
    openai.api_key = openai_key
    
    # Prepare economic data for the prompt
    data_points = []
    for series_id, data in economic_data.items():
        data_points.append(
            f"{data['description']}: Current value: {data['latest_value']:.2f}, "
            f"Change: {data['pct_change']:.2f}% (as of {data['last_updated']})"
        )
    
    economic_context = "\n".join(data_points)
    
    prompt = f"""As an economic analyst, analyze how these core economic indicators might impact {ticker} stock:

    Economic Indicators:
    {economic_context}

    Provide two things:
    1. A rating from 1-5 (where 1 is very unfavorable and 5 is very favorable) based on how the current economic environment affects {ticker}'s prospects.
    
    2. A brief analysis explaining the rating and key economic factors affecting {ticker}.

    Format your response as:
    RATING: [number 1-5]
    ANALYSIS: [your brief explanation]"""

    try:
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
        
        response_text = response.choices[0].message.content
        
        # Parse the response
        try:
            rating_line = [line for line in response_text.split('\n') if line.startswith('RATING:')][0]
            analysis_line = [line for line in response_text.split('\n') if line.startswith('ANALYSIS:')][0]
            
            rating = int(rating_line.split(':')[1].strip())
            analysis = analysis_line.split(':')[1].strip()
            
            return {
                "rating": rating,
                "analysis": analysis,
                "details": {
                    "indicators": economic_data,
                    "timestamp": datetime.now().isoformat()
                }
            }
        except (IndexError, ValueError) as e:
            return {
                "rating": 3,
                "analysis": f"Error parsing analysis: {response_text}",
                "details": {
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            }
            
    except Exception as e:
        return {
            "rating": 3,
            "analysis": f"Error generating analysis: {str(e)}",
            "details": {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        }

def main(ticker: str) -> Dict[str, Any]:
    """
    Main entry point for FRED analysis
    
    Args:
        ticker (str): Stock ticker to analyze
        
    Returns:
        dict: Analysis results with rating and context
    """
    return get_fred_data(ticker)
