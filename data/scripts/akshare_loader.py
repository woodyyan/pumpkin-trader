import akshare as ak
import pandas as pd
from datetime import datetime
import streamlit as st

@st.cache_data(ttl=3600*24)
def fetch_stock_data(ticker, start_date, end_date):
    """
    Fetch stock data from Akshare and format it for the backtest engine.
    Supports A-shares (e.g., 600519, 000001) and HK-shares (e.g., 00700)
    """
    try:
        # Convert dates to string format required by Akshare (YYYYMMDD)
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        
        df = None
        market = "unknown"
        
        # Determine market based on ticker pattern
        # Simple heuristic: if it's 5 digits it's likely HK, if it starts with 6, 0, 3 it's likely A-share
        if len(ticker) == 5 and ticker.isdigit():
            market = "hk"
        elif len(ticker) == 6 and ticker.isdigit():
            market = "a_share"
            
        if market == "a_share":
            # For A-shares (daily data, qfq - forward adjusted)
            df = ak.stock_zh_a_hist(symbol=ticker, period="daily", start_date=start_str, end_date=end_str, adjust="qfq")
            
            # Rename columns to match what the engine expects
            rename_map = {
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount'
            }
            df = df.rename(columns=rename_map)
            
        elif market == "hk":
            # For HK-shares
            # Akshare's HK stock API uses forward adjusted by default when qfq is specified
            df = ak.stock_hk_hist(symbol=ticker, period="daily", start_date=start_str, end_date=end_str, adjust="qfq")
            
            # Rename columns to match what the engine expects
            rename_map = {
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount'
            }
            df = df.rename(columns=rename_map)
        else:
            raise ValueError(f"无法识别的股票代码格式: {ticker}。A股请用6位数字(如600519)，港股请用5位数字(如00700)。")
            
        if df is None or df.empty:
            raise ValueError(f"未能获取到代码 {ticker} 的数据，请检查代码是否正确或日期范围内是否有交易。")
            
        # Ensure date format
        df['date'] = pd.to_datetime(df['date'])
        
        # Select and reorder columns needed by the engine
        columns_to_keep = ['date', 'open', 'high', 'low', 'close', 'volume']
        df = df[columns_to_keep]
        
        # Ensure numeric types
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        return df
        
    except Exception as e:
        st.error(f"下载数据时出错: {str(e)}")
        return None
