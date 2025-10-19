import os
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

from pathlib import Path
from sec_cik_mapper import StockMapper

from bs4 import BeautifulSoup
import re
import requests
import json
from datetime import datetime

def ticker_to_cik(ticker: str) -> str:
    mapper = StockMapper()
    if ticker.upper() in mapper.ticker_to_cik:
        print(f"Ticker {ticker} CIK={mapper.ticker_to_cik[ticker]}")
        CIK = mapper.ticker_to_cik[ticker]
    else:
        print(f"Ticker {ticker} not found")
    return CIK

def get_recent_facts(CIK: str):
    """
    Fetches the most recent 10-Q or 10-K filing facts from SEC's companyfacts API.
    Returns a list of fact entries (concept, unit, value, end_date).
    """
    # 1. Configuration
    URL = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK.zfill(10)}.json"
    USER_AGENT = "Your Name (your.email@example.com)"  # <-- REQUIRED by SEC

    # 2. Fetch Data
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(URL, headers=headers)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"[Error] Could not fetch data for CIK {CIK}: {e}")
        return []

    # 3. Identify the most recent 10-Q or 10-K accession number
    latest_filing_accn = None
    latest_filed_date = datetime.min
    latest_form = None

    facts = data.get("facts", {}).get("us-gaap", {})

    for concept in facts.values():
        if "units" not in concept:
            continue
        for unit_facts in concept["units"].values():
            for fact in unit_facts:
                form = fact.get("form", "")
                # Skip other forms not 10-Q or 10-K
                if form not in ("10-Q", "10-K"):
                    continue

                filed_date_str = fact.get("filed")
                if not filed_date_str:
                    continue

                try:
                    filed_date = datetime.strptime(filed_date_str, "%Y-%m-%d")
                except ValueError:
                    continue

                if filed_date > latest_filed_date:
                    latest_filed_date = filed_date
                    latest_filing_accn = fact.get("accn")
                    latest_form = form

    if not latest_filing_accn:
        print(f"[Warning] No 10-Q or 10-K filings found for CIK {CIK}.")
        return []

    print(f"Most recent filing for CIK {CIK}: Form {latest_form}, Accession {latest_filing_accn}, Filed on {latest_filed_date.date()}")

    # 4. Extract all facts from the most recent filing
    most_recent_facts = []
    for concept_name, concept in facts.items():
        if "units" not in concept:
            continue
        for unit_name, unit_facts in concept["units"].items():
            for fact in unit_facts:
                if fact.get("accn") == latest_filing_accn:
                    most_recent_facts.append({
                        "concept": concept_name,
                        "unit": unit_name,
                        "value": fact.get("val"),
                        "end_date": fact.get("end"),
                        "form": fact.get("form"),
                        "accn": fact.get("accn")
                    })
    return most_recent_facts

# Calculate year-over-year revenue growth
def calc_yoy_rev(facts):
    # Filter the data for total revenue
    revenue_data = [item for item in facts if item['concept'].lower()[:7] == 'revenue']

    curr_end = max([item['end_date'] for item in revenue_data])
    prev_end = min([item['end_date'] for item in revenue_data])

    # Sum the quarterly values by year
    revenue_prev = sum(item['value'] for item in revenue_data if item['end_date'] == prev_end)
    revenue_curr = sum(item['value'] for item in revenue_data if item['end_date'] == curr_end)

    # Calculate the YoY growth
    if revenue_prev > 0:
        yoy_growth = ((revenue_curr - revenue_prev) / revenue_prev) * 100
    else:
        yoy_growth = float('inf') if revenue_curr > 0 else 0

    # # Print the results
    # print(f"Total Revenue for 2024: ${revenue_prev:,}")
    # print(f"Total Revenue for 2025: ${revenue_curr:,}")
    # print(f"Year-over-Year Revenue Growth: {yoy_growth:.2f}%")

    # 5 if greater than 15, 1 if less than 5, sliding scale between
    if yoy_growth > 15:
        return_val = 5
    elif yoy_growth < 5:
        return_val = 1
    else:
        return_val = yoy_growth / 5

    return {'yoy_growth': yoy_growth, 'ratintg': return_val, 'description' : "Year over year revenue growth as a percentage"}

# Calculate profit percent
def calc_profit(facts):
    revenue_data = [item for item in facts if item['concept'].lower()[:7] == 'revenue']
    curr_end = max([item['end_date'] for item in revenue_data])
    revenue_curr = sum(item['value'] for item in revenue_data if item['end_date'] == curr_end)

    profit_data = [item for item in facts if 'netincome' in item['concept'].lower()]
    curr_end = max([item['end_date'] for item in profit_data])

    # Sum the quarterly values by year
    net_income = sum(item['value'] for item in profit_data if item['end_date'] == curr_end)

    # print(f"{net_income:,} {revenue_curr:,}")

    net_profit_margin = (net_income / revenue_curr) * 100

    # print(net_profit_margin)

    if net_profit_margin > 10:
        return_val = 5
    elif net_profit_margin < 5:
        return_val = 1
    else:
        return_val = net_profit_margin / 5

    # print(f"{return_val:.2f}")
    return {'net_profit_margin': net_profit_margin, 'rating': return_val, 'description': "Net profit margin as a percentage"}

# Calculate debt to equity ratio
def calc_debt_to_equity(facts):
    total_debt = 0

    for item_name in ['LongTermDebtNoncurrent', 'LongTermDebtCurrent', 'ShortTermBorrowings']:
        debt_data = [item for item in facts if (item_name.lower() in item['concept'].lower())]
        if debt_data:
            curr_end = max([item['end_date'] for item in debt_data])
            debt_data = [item for item in facts if (item_name.lower() in item['concept'].lower()) and (item['end_date'] == curr_end)]

        if len(debt_data) == 1:
            debt_item = debt_data[0]['value']
        else:
            debt_item = 0
        total_debt += debt_item

    # print(total_debt)

    se_data = [item for item in facts if ('StockholdersEquity'.lower() == item['concept'].lower()) and (item['end_date'] == curr_end)]
    curr_end = max([item['end_date'] for item in se_data])
    se_data = [item for item in facts if ('StockholdersEquity'.lower() == item['concept'].lower()) and (item['end_date'] == curr_end)]

    if len(se_data) == 1:
        se = se_data[0]['value']
    else:
        se = 0

    debt_to_equity = total_debt / se

    #print(se)

    if debt_to_equity < 0.5:
        return_val = 5
    elif debt_to_equity > 1:
        return_val = 1
    else:
        return_val = (-8 * debt_to_equity) + 9

    # print(f"D_E={debt_to_equity} {return_val}")
    return {'debt_to_equity': debt_to_equity, 'rating': return_val, 'description': "Debt to equity ratio"}

# Calculate if net income is positive
def calc_positive_netincome(facts):
    for item_name in ['NetIncomeLoss']:
        
        cash_data = [item for item in facts if (item_name.lower() in item['concept'].lower())]

        curr_end = max([item['end_date'] for item in cash_data])

        net_income = sum(item['value'] for item in cash_data if item['end_date'] == curr_end)

        if net_income == None:
            net_income = 0

    if net_income > 0:
        return_val = 5
    elif net_income < 0:
        return_val = 1
    else:
        return_val = 3

    # print(net_income, return_val)
    return {'net_income': net_income, 'rating': return_val, 'description': "Positive net income"}

def get_latest_10k_text_url(cik: str, user_agent: str):
    # Step 1: fetch the submissions JSON
    padded = cik.zfill(10)
    submissions_url = f"https://data.sec.gov/submissions/CIK{padded}.json"
    headers = {"User-Agent": user_agent}
    resp = requests.get(submissions_url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    
    # Step 2: find the latest 10-K filing metadata
    filings = pd.DataFrame(data['filings']['recent'])
    # filter by form “10-K” (not “10-K/A”) — you might adapt that logic
    tenk_rows = filings[filings['form'] == '10-K']
    if tenk_rows.empty:
        raise ValueError("No 10-K filings found for this CIK")
    latest = tenk_rows.iloc[0]
    accession = latest['accessionNumber']
    primary_doc = latest['primaryDocument']
    
    # Step 3: build paths
    accession_nodash = accession.replace('-', '')
    cik_int = int(cik)  # for path part
    base = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/"
    
    # The HTML or .htm version:
    html_url = base + primary_doc
    
    # The .txt submission file often follows:
    # example: “CIK-yy-nnnnn.txt”
    # we can infer its name — sometimes the name is the same as `primaryDocument` but with `.txt`
    # common pattern: <cik>-<two digit year>-<5 digit seq>.txt
    # The JSON “accessionNumber” is like “0000320193-24-000123”
    # So txt filename might be “0000320193-24-000123.txt”
    txt_filename = f"{accession}.txt"
    txt_url = base + txt_filename
    
    return {
        "html_url": html_url,
        "txt_url": txt_url,
        "accession": accession,
        "primary_document": primary_doc
    }

# Get risks and MNA from most recent 10-K since these are often not listed in 10-Q
def get_risks_mna(CIK: str):
    txt_url = get_latest_10k_text_url(cik=CIK, user_agent="Your Name (your.email@example.com)")["txt_url"]
    headers = {"User-Agent": "Your Name (your.email@example.com)"}

    #print(txt_url)

    # Step 4: Download and extract Risk Factors section
    txt = requests.get(txt_url, headers=headers).text

    soup = BeautifulSoup(txt, "html.parser")
    clean_text = soup.get_text(separator=' ', strip=True)

    # Pattern for locating "Item 1A – Risk Factors" and its next section start
    pattern_risk_start = re.compile(
        r"(?i)item\s*1A\.[^a-zA-Z0-9]{0,10}",
        re.IGNORECASE
    )
    pattern_next_section = re.compile(
        r"(?is)item\s*(1B|2)[^a-zA-Z0-9]{0,10}"
    )

    # Find all matches (returns Match objects)
    matches_1a = list(pattern_risk_start.finditer(clean_text))
    matches_1b2 = list(pattern_next_section.finditer(clean_text))

    match_1a_list = []
    match_1b2_list = []

    if matches_1a:
        for i, match in enumerate(matches_1a, start=1):
            match_1a_list.append(match.start())
    else:
        print("No Item 1A – Risk Factors occurrences found.")

    if matches_1b2:
        for i, match in enumerate(matches_1b2, start=1):
            match_1b2_list.append(match.start())
    else:
        print("No Item 1B or Item 2 occurrences found.")

    # print(match_1a_list)
    # print(match_1b2_list)

    start_pos = match_1a_list[1]

    for item_pos in match_1b2_list:
        if item_pos > start_pos:
            end_pos = item_pos
            break

    # print(start_pos, end_pos)

    risk_text = clean_text[start_pos:end_pos]

    # Pattern for locating "Item 7" and its next section start
    pattern_risk_start = re.compile(
        r"(?i)item\s*7\.[^a-zA-Z0-9]{0,10}"
    )
    pattern_next_section = re.compile(
        r"(?is)item\s*8\.[^a-zA-Z0-9]{0,10}"
    )

    matches_7 = list(pattern_risk_start.finditer(clean_text))
    matches_8 = list(pattern_next_section.finditer(clean_text))

    match_7_list = []
    match_8_list = []

    if matches_7:
        for i, match in enumerate(matches_1a, start=1):
            match_7_list.append(match.start())
    else:
        print("No Item 7 occurrences found.")

    if matches_8:
        for i, match in enumerate(matches_8, start=1):
            match_8_list.append(match.start())
    else:
        print("No Item 8 occurrences found.")

    start_pos = match_7_list[1]

    for item_pos in match_8_list:
        if item_pos > start_pos:
            end_pos = item_pos
            break

    # print(start_pos, end_pos)

    mda_text = clean_text[start_pos:end_pos]
    return risk_text, mda_text

# This function was used in development but is not currently called in the flow, left for debugging
def prompt(risk_text: str, mda_text: str):
    load_dotenv()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": "You are a financial analysis expert."},
            {"role": "user", "content": f"Provide a rating from 1 'sell', 2 'underperform', 3 'hold', 4 'outperform', 5 'strong buy' for the following based on risk factors: {risk_text} and management discussion and analysis: {mda_text}. Respond with json only like {{'rating': 4, 'rationale': 'text'}}"}
        ]
    )
    return response.choices[0].message.content

# This function was used in development but is not currently called in the flow, left for debugging
def final_rating(risk_rating, yoy_rating, profit_rating, debt_equity_rating, net_income_rating):
    # Set weights for calculation
    weights = {
        'risk': 0.3,
        'yoy': 0.2,
        'profit': 0.2,
        'debt_equity': 0.15,
        'net_income': 0.15
    }
    
    # Calculate final score with weights
    final_score = (
        risk_rating * weights['risk'] +
        yoy_rating * weights['yoy'] +
        profit_rating * weights['profit'] +
        debt_equity_rating * weights['debt_equity'] +
        net_income_rating * weights['net_income']
    )
    
    # Determine recommendation based on final score
    if final_score >= 4:
        recommendation = 'strong buy'
    elif final_score >= 3.5:
        recommendation = 'outperform'
    elif final_score >= 2.5:
        recommendation = 'hold'
    elif final_score >= 1.5:
        recommendation = 'underperform'
    else:
        recommendation = 'sell'
    
    return final_score, recommendation

def main(ticker: str):
    CIK = ticker_to_cik(ticker)
    if CIK is None:
        print(f"Could not find CIK for ticker {ticker}. Exiting.")
        return
    else:
        print(f"Using CIK {CIK} for ticker {ticker}")

    facts = get_recent_facts(CIK)
    yoy_rating = calc_yoy_rev(facts)
    profit_rating = calc_profit(facts)
    debt_equity_rating = calc_debt_to_equity(facts)
    net_income_rating = calc_positive_netincome(facts)

    risk_text, mda_text = get_risks_mna(CIK)
    risk_dict = json.loads(prompt(risk_text, mda_text))

    risk_rating = risk_dict['rating']

    final_score, recommendation = final_rating(
        risk_rating,
        yoy_rating,
        profit_rating,
        debt_equity_rating,
        net_income_rating
    )
    print(f"rating {final_score}, recommendation: {recommendation} rationale: {risk_dict['rationale']}")
    return({'rating': final_score, 'recommendation': recommendation})

if __name__ == "__main__":
    main("AAPL")