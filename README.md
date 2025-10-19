##  Project Overview

This project implements an autonomous AI system that performs comprehensive financial analysis on companies and generates investment recommendations. The system coordinates multiple specialized AI agents to conduct multi-source research and synthesize findings into data-driven investment insights.

### Core Components

**RouterMain.py** - Main orchestration engine that coordinates all research agents  
**yahoo_find_ticker.py** - Company identification and ticker resolution service  
**SECresearcher.py** - SEC regulatory filings analysis agent  
**sec_tools.py** - SEC EDGAR API integration and financial calculation tools  
**YahooFinanceCrew.py** - Market data and technical analysis agent  
**FREDresearcher.py** - Economic data analysis agent wrapper  
**fred_tools.py** - FRED API integration and macroeconomic analysis  
**News_Agent_Crew.py** - News sentiment analysis crew wrapper  
**News_Agent.py** -  News research agent with self-reflection  


## 🔄 Workflow Process

### 1. Company Identification
- Input: Company name or ticker symbol
- Process: Resolves to official stock symbol using Yahoo Finance APIs
- Output: Symbol, company details, and security type classification

### 2. Intelligent Routing
- Analyzes security type (Equity vs Non-Equity)
- Routes to appropriate analysis path based on security classification
- Handles unknown security types with error reporting

### 3. Multi-Agent Research Pipeline

#### SEC Research Agent (Equities Only)
- Analyzes SEC EDGAR filings (10-K/10-Q reports)
- Calculates financial metrics: revenue growth, profit margins, debt ratios
- Assesses risk factors and management discussion
- Generates fundamental financial ratings

#### Yahoo Finance Agent
- Fetches real-time market data and price history
- Computes technical indicators: moving averages, RSI, volatility
- Analyzes fundamental data: P/E ratios, market cap, beta
- Assesses earnings event impacts
- Generates market-based investment ratings

#### FRED Economic Agent
- Monitors key economic indicators from Federal Reserve data
- Tracks CPI inflation, unemployment, interest rates, GDP growth
- Analyzes macroeconomic impact on company performance
- Provides economic environment assessment

#### News Sentiment Agent
- Fetches recent financial news using NewsAPI
- Performs AI-powered sentiment analysis using Gemini
- Classifies articles as positive, negative, or neutral
- Identifies key risks, opportunities, and market themes
- Implements self-reflection and iterative improvement

### 4. AI-Powered Synthesis
- Combins insights from all research agents
- Uses advanced GPT-5 for final analysis
- Generates investment rating (1-5 scale)
- Provides comprehensive rationale with bull/bear cases
- Explains macroeconomic factor impacts

## 🚀 Key Features

### Agent Functions
- **Research Planning**: Autonomous workflow planning for each analysis
- **Dynamic Tool Usage**: Integration with multiple external APIs and data sources
- **Self-Reflection**: Quality assessment and improvement identification
- **Cross-Session Learning**: Memory system for persistent knowledge

### Workflow Patterns
- **Prompt Chaining**: Sequential data processing (fetch → analyze → classify → summarize)
- **Routing**: Intelligent content direction to specialized agents
- **Evaluator-Optimizer**: Analysis generation → quality evaluation → refinement

### Technical Capabilities
- Multi-source data integration (SEC, Yahoo Finance, FRED, NewsAPI)
- Real-time market data processing
- Advanced AI analysis using multiple models (GPT, Gemini)
- Professional financial metrics and calculations
- Robust error handling and graceful degradation
