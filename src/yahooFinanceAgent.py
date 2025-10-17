#!/usr/bin/env python
# coding: utf-8

# In[15]:


# YahooFinanceAgent v2 

import json
import time
from datetime import datetime, timedelta
from dateutil import parser as date_parser

import numpy as np
import pandas as pd
import yfinance as yf

# optional technical indicators library
try:
    from ta.momentum import RSIIndicator
except Exception:
    RSIIndicator = None

_YF_CACHE = {}
def _cache_get(key):
    v = _YF_CACHE.get(key)
    if v and (time.time() - v["ts"]) < 300:
        return v["value"]
    return None
def _cache_set(key, value):
    _YF_CACHE[key] = {"ts": time.time(), "value": value}

class YahooFinanceAgent:
    SOURCE = "YahooFinanceAgent"
    def __init__(self, session_name=None):
        self.session_name = session_name or "default"

    def _fetch_price_history(self, symbol, period_days=365):
        key = f"prices::{symbol}::{period_days}"
        cached = _cache_get(key)
        if cached is not None:
            return cached
        end = datetime.utcnow().date()
        start = end - timedelta(days=period_days + 7)
        # set auto_adjust explicitly to avoid FutureWarning
        df = yf.download(symbol, start=start.isoformat(), end=end.isoformat(),
                         progress=False, threads=False, auto_adjust=True)
        if df is None or df.empty:
            raise ValueError(f"No price data fetched for {symbol}")
        df = df.reset_index().rename(columns={"Date": "date"})
        df["date"] = pd.to_datetime(df["date"])
        _cache_set(key, df)
        return df



    def _fetch_ticker(self, symbol):
        key = f"ticker::{symbol}"
        cached = _cache_get(key)
        if cached is not None:
            return cached
        t = yf.Ticker(symbol)
        _cache_set(key, t)
        return t

    def _safe_get(self, obj, attr, default=None):
        try:
            return getattr(obj, attr, default) if obj is not None else default
        except Exception:
            return default

    def _compute_indicators(self, price_df):
        out = {}
        # Ensure DataFrame and locate Close column whether columns are single-level or multi-level
        df = price_df.copy().set_index("date").sort_index()
        cols = df.columns
        # detect MultiIndex columns like ('Close','AAPL') or single-level 'Close'
        if isinstance(cols, pd.MultiIndex):
            # find first level name 'Close' (case-sensitive)
            close_cols = [c for c in cols if c[0] == "Close"]
            if not close_cols:
                raise ValueError("Price DataFrame missing 'Close' column (multiindex)")
            close_series = df[close_cols[0]]
        else:
            if "Close" not in df.columns:
                # try lowercase fallback
                low = [c for c in df.columns if str(c).lower() == "close"]
                if not low:
                    raise ValueError("Price DataFrame missing 'Close' column")
                close_series = df[low[0]]
            else:
                close_series = df["Close"]
    
        # convert to numeric 1-D array and drop NaNs
        close_vals = pd.to_numeric(close_series, errors="coerce").to_numpy()
        # if close_series came from a DataFrame column (multiindex extraction) it may be 2-D; ensure 1-D
        if close_vals.ndim > 1:
            # if shape (n,1) flatten
            close_vals = close_vals.reshape(-1)
        mask = ~np.isnan(close_vals)
        close_vals = close_vals[mask]
        n = len(close_vals)
        if n == 0:
            raise ValueError("Empty close series after cleaning")
    
        # scalar-safe access using numpy indices
        latest = float(close_vals[-1])
        out["latest_close"] = latest
    
        # first/last dates from df index (after cleaning mask we approximate using original index)
        try:
            out["first_date"] = df.index[0].isoformat()
            out["last_date"] = df.index[-1].isoformat()
        except Exception:
            out["first_date"] = None
            out["last_date"] = None
    
        def pct_by_indices(latest_idx, prior_idx):
            if prior_idx < 0 or latest_idx < 0 or prior_idx >= n or latest_idx >= n:
                return None
            prior = close_vals[prior_idx]
            latest_v = close_vals[latest_idx]
            if prior == 0:
                return None
            return float((latest_v / prior) - 1)
    
        out["7d_return"] = pct_by_indices(n - 1, n - 8) if n >= 8 else None
        out["30d_return"] = pct_by_indices(n - 1, n - 31) if n >= 31 else None
        out["90d_return"] = pct_by_indices(n - 1, n - 91) if n >= 91 else None
        out["1y_return"] = pct_by_indices(n - 1, 0) if n >= 252 else None
    
        # Use pandas Series built from the cleaned numpy array for rolling ops
        close_series_clean = pd.Series(close_vals)
    
        out["sma_20"] = float(close_series_clean.rolling(window=20, min_periods=1).mean().iat[-1])
        out["sma_50"] = float(close_series_clean.rolling(window=50, min_periods=1).mean().iat[-1])
        out["sma_200"] = float(close_series_clean.rolling(window=200, min_periods=1).mean().iat[-1])
        out["price_vs_sma20"] = 1 if out["latest_close"] > out["sma_20"] else -1
        out["volatility_30d"] = float(close_series_clean.pct_change().rolling(window=21, min_periods=1).std().iat[-1])
    
        # max drawdown
        roll_max = close_series_clean.cummax()
        drawdown = (close_series_clean - roll_max) / roll_max
        out["max_drawdown"] = float(drawdown.min())
    
        # RSI 14 (safe fallback if ta not installed)
        try:
            if RSIIndicator is not None:
                rsi = RSIIndicator(close_series_clean, window=14)
                out["rsi_14"] = float(rsi.rsi().iat[-1])
            else:
                delta = close_series_clean.diff().dropna()
                up = delta.where(delta > 0, 0).rolling(14).mean()
                down = -delta.where(delta < 0, 0).rolling(14).mean()
                rs = up / down.replace(0, np.nan)
                last_rs = rs.iat[-1] if len(rs) > 0 else np.nan
                out["rsi_14"] = float(100 - (100 / (1 + last_rs))) if not np.isnan(last_rs) else None
        except Exception:
            out["rsi_14"] = None
    
        return out


    def _fetch_fundamentals(self, ticker_obj):
        out = {}
        try:
            info = ticker_obj.info or {}
        except Exception:
            info = {}
        # common fields, may be missing
        out["market_cap"] = info.get("marketCap")
        out["trailing_pe"] = info.get("trailingPE")
        out["forward_pe"] = info.get("forwardPE")
        out["peg_ratio"] = info.get("pegRatio")
        out["beta"] = info.get("beta")
        return out

    def _earnings_event_returns(self, ticker_obj, price_df):
        # attempt to fetch last earnings calendar and compute 7d pre/post returns around the last earnings date
        try:
            cal = ticker_obj.calendar
            # calendar may have nextEarningsDate etc; fallback to earnings_dates from history if available
            earnings = ticker_obj.get_earnings_dates(limit=5) if hasattr(ticker_obj, "get_earnings_dates") else None
        except Exception:
            earnings = None
        # fallback: attempt to read earnings from history property
        if earnings is None:
            try:
                eht = ticker_obj.earnings_dates if hasattr(ticker_obj, "earnings_dates") else None
                earnings = eht
            except Exception:
                earnings = None
        # convert to list of datetimes if possible
        event = None
        if isinstance(earnings, (list, tuple)) and len(earnings) > 0:
            # expect list of dicts with 'Earnings Date' or 'startdatetime'
            for e in earnings:
                if isinstance(e, dict) and ("startdatetime" in e or "Earnings Date" in e or "date" in e):
                    try:
                        # try many keys
                        d = e.get("startdatetime") or e.get("Earnings Date") or e.get("date")
                        event = date_parser.parse(d) if isinstance(d, str) else d
                        break
                    except Exception:
                        continue
        # as very last resort, try ticker.calendar nextEarningsDate
        if event is None:
            try:
                cal = ticker_obj.calendar
                if isinstance(cal, pd.DataFrame) and "Earnings Date" in cal.index:
                    event = cal.loc["Earnings Date"].values[0]
            except Exception:
                event = None
        # compute returns if we have event and prices
        if event is None:
            return {"last_earnings_date": None, "pre7_return": None, "post7_return": None}
        event_date = pd.to_datetime(event).date()
        df = price_df.copy().set_index("date").sort_index()
        try:
            pre_start = event_date - timedelta(days=10)
            pre_end = event_date - timedelta(days=1)
            post_start = event_date + timedelta(days=1)
            post_end = event_date + timedelta(days=10)
            pre = df.loc[(df.index.date >= pre_start) & (df.index.date <= pre_end)]["Close"]
            post = df.loc[(df.index.date >= post_start) & (df.index.date <= post_end)]["Close"]
            pre7 = float((pre.iloc[-1] / pre.iloc[0]) - 1) if len(pre) >= 2 else None
            post7 = float((post.iloc[-1] / post.iloc[0]) - 1) if len(post) >= 2 else None
            return {"last_earnings_date": event_date.isoformat(), "pre7_return": pre7, "post7_return": post7}
        except Exception:
            return {"last_earnings_date": event_date.isoformat(), "pre7_return": None, "post7_return": None}

    def _score_and_confidence(self, indicators, fundamentals, earnings_event):
        # Base score 3 neutral
        score = 3.0
        confidence = 0.5
        evidence = []

        # Momentum: 30d and 90d
        r30 = indicators.get("30d_return")
        r90 = indicators.get("90d_return")
        if r30 is not None:
            if r30 > 0.08:
                score += 0.8; confidence += 0.08; evidence.append("strong_30d_momentum")
            elif r30 > 0.02:
                score += 0.35; confidence += 0.04; evidence.append("mild_30d_momentum")
            elif r30 < -0.08:
                score -= 0.9; confidence += 0.07; evidence.append("strong_30d_down")
            elif r30 < -0.02:
                score -= 0.35; confidence += 0.03; evidence.append("mild_30d_down")
        if r90 is not None and r90 > 0.20:
            score += 0.4; confidence += 0.03; evidence.append("90d_strong_up")

        # SMA position
        if indicators.get("price_vs_sma20") == 1:
            score += 0.25; confidence += 0.03; evidence.append("above_sma20")
        else:
            score -= 0.15; confidence += 0.02; evidence.append("below_sma20")

        # Fundamentals
        pe = fundamentals.get("trailing_pe")
        fpe = fundamentals.get("forward_pe")
        peg = fundamentals.get("peg_ratio")
        if pe:
            if pe < 10:
                score += 0.4; confidence += 0.03; evidence.append("cheap_pe")
            elif pe > 60:
                score -= 0.5; confidence += 0.03; evidence.append("high_pe")
        if peg and peg < 1:
            score += 0.25; confidence += 0.02; evidence.append("low_peg")

        # Earnings event behavior
        post = earnings_event.get("post7_return")
        if post is not None:
            if post > 0.05:
                score += 0.4; confidence += 0.04; evidence.append("earnings_post_positive")
            elif post < -0.05:
                score -= 0.6; confidence += 0.05; evidence.append("earnings_post_negative")

        # Volatility impact on confidence
        vol = indicators.get("volatility_30d") or 0.0
        if vol > 0.06:
            confidence -= 0.12; evidence.append("high_volatility")
        elif vol < 0.02:
            confidence += 0.04; evidence.append("low_volatility")

        # RSI extreme adjustments
        rsi = indicators.get("rsi_14")
        if rsi is not None:
            if rsi > 75:
                score -= 0.25; evidence.append("rsi_overbought")
            elif rsi < 25:
                score += 0.25; evidence.append("rsi_oversold")

        # Data availability boosts confidence
        if fundamentals.get("market_cap"):
            confidence += 0.03
        if indicators.get("1y_return") is not None:
            confidence += 0.02

        # clamp and convert
        confidence = max(0.0, min(1.0, confidence))
        score = max(1.0, min(5.0, score))
        rating = int(round(score))
        rating = max(1, min(5, rating))
        return rating, float(confidence), evidence

    def analyze(self, symbol, period_days=365):
        start_ts = datetime.utcnow()
        try:
            prices = self._fetch_price_history(symbol, period_days)
        except Exception as e:
            return {
                "symbol": symbol,
                "rating": 3,
                "confidence": 0.12,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "source": self.SOURCE,
                "context": {"error": f"price_fetch_failed: {str(e)}"}
            }

        ticker = self._fetch_ticker(symbol)
        indicators = self._compute_indicators(prices)
        fundamentals = self._fetch_fundamentals(ticker)
        earnings_event = self._earnings_event_returns(ticker, prices)
        rating, confidence, evidence = self._score_and_confidence(indicators, fundamentals, earnings_event)

        rationale = []
        if evidence:
            rationale.append(" ; ".join(evidence))
        if fundamentals.get("trailing_pe") is not None:
            rationale.append(f"pe={fundamentals.get('trailing_pe')}")
        if earnings_event.get("post7_return") is not None:
            rationale.append(f"earn_post7={earnings_event.get('post7_return'):.3f}")

        context = {
            "key_indicators": indicators,
            "fundamentals": fundamentals,
            "earnings_event": earnings_event,
            "rationale": " | ".join(rationale) if rationale else None,
            "fetch_seconds": round((datetime.utcnow() - start_ts).total_seconds(), 2),
            "data_source": "yfinance"
        }

        payload = {
            "symbol": symbol,
            "rating": rating,
            "confidence": confidence,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": self.SOURCE,
            "context": context
        }
        return payload


# In[16]:


agent = YahooFinanceAgent()
out = agent.analyze("AAPL")   # or any ticker like "MSFT", "TSLA"
print(json.dumps(out, indent=2))


# In[17]:


agent = YahooFinanceAgent()
out = agent.analyze("MSFT")  
print(json.dumps(out, indent=2))


# In[18]:


agent = YahooFinanceAgent()
out = agent.analyze("TSLA")
print(json.dumps(out, indent=2))


# In[ ]:




