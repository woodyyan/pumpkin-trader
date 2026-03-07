import akshare as ak
import pandas as pd
from datetime import datetime
import streamlit as st
import threading
import time
import queue

def fetch_data_worker(ticker, start_str, end_str, market, result_queue):
    """在独立线程中执行下载，包含多数据源轮询容灾机制"""
    errors = []
    
    if market == "a_share":
        # 针对 A 股，我们尝试多个不同的 Akshare 接口（代表不同数据源）
        
        # 数据源1：东方财富 (stock_zh_a_hist)
        try:
            df = ak.stock_zh_a_hist(symbol=ticker, period="daily", start_date=start_str, end_date=end_str, adjust="qfq")
            if df is not None and not df.empty:
                result_queue.put(('success', df, '东方财富 (EastMoney)'))
                return
        except Exception as e:
            errors.append(f"东财接口失败: {str(e)}")
            
        # 数据源2：新浪财经 (stock_zh_a_daily)
        try:
            # 新浪接口需要加前缀 sh/sz
            prefix = "sh" if ticker.startswith(('6', '5')) else "sz"
            symbol_sina = f"{prefix}{ticker}"
            # 注意新浪接口日期不带中划线，可能需要适配，或者使用专门的新浪函数
            df = ak.stock_zh_a_daily(symbol=symbol_sina, start_date=start_str, end_date=end_str, adjust="qfq")
            if df is not None and not df.empty:
                result_queue.put(('success', df, '新浪财经 (Sina Finance)'))
                return
        except Exception as e:
            errors.append(f"新浪接口失败: {str(e)}")
            
        # 数据源3：网易财经 (stock_zh_a_hist_163) (仅部分支持，作为最后备用)
        try:
            # 尝试网易接口（通常不用调整复权，取历史原生或特定格式）
            df = ak.stock_zh_a_hist(symbol=ticker, period="daily", start_date=start_str, end_date=end_str, adjust="")
            if df is not None and not df.empty:
                result_queue.put(('success', df, '网易财经/备用通道'))
                return
        except Exception as e:
            errors.append(f"备用接口失败: {str(e)}")
            
    elif market == "hk":
        # 港股暂时只用默认通道，也可以加轮询
        try:
            df = ak.stock_hk_hist(symbol=ticker, period="daily", start_date=start_str, end_date=end_str, adjust="qfq")
            if df is not None and not df.empty:
                result_queue.put(('success', df, '东方财富-港股 (EastMoney HK)'))
                return
        except Exception as e:
            errors.append(f"港股主接口失败: {str(e)}")
            
        try:
            df = ak.stock_hk_daily(symbol=ticker) # 新浪港股历史
            # 需要截取时间
            df = df[(df.index >= pd.to_datetime(start_date)) & (df.index <= pd.to_datetime(end_date))]
            if df is not None and not df.empty:
                 result_queue.put(('success', df, '新浪财经-港股 (Sina HK)'))
                 return
        except Exception as e:
            errors.append(f"港股备用接口失败: {str(e)}")

    # 如果所有数据源都失败了，把收集到的错误抛出
    error_msg = " | ".join(errors)
    result_queue.put(('error', error_msg, None))


@st.cache_data(ttl=3600*24, show_spinner=False)
def fetch_stock_data(ticker, start_date, end_date):
    """
    Fetch stock data from Akshare using multiple data sources as fallbacks.
    Returns (DataFrame, source_name)
    """
    try:
        # Convert dates to string format required by Akshare (YYYYMMDD)
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        
        df = None
        source_used = "未知"
        market = "unknown"
        
        # Determine market based on ticker pattern
        if len(ticker) == 5 and ticker.isdigit():
            market = "hk"
        elif len(ticker) == 6 and ticker.isdigit():
            market = "a_share"
        else:
            raise ValueError(f"无法识别的股票代码格式: {ticker}。A股请用6位数字，港股请用5位数字。")
            
        # 使用线程和队列来实现超时控制
        result_queue = queue.Queue()
        thread = threading.Thread(target=fetch_data_worker, args=(ticker, start_str, end_str, market, result_queue))
        thread.start()
        
        # 等待最多30秒
        thread.join(timeout=30.0)
        
        if thread.is_alive():
            raise TimeoutError(f"请求超时(>30秒)。所有数据源连接均已放弃。请检查网络。")
            
        if not result_queue.empty():
            status, result, source = result_queue.get()
            if status == 'error':
                 raise Exception(f"所有数据源均连接失败。详细排查: {result}")
            else:
                df = result
                source_used = source
        else:
            raise Exception("获取数据时发生未知异常，未返回结果。")
            
        if df is None or df.empty:
            raise ValueError(f"未能在任何数据源中找到 {ticker} 的交易记录。")
            
        # Rename columns (由于不同数据源返回的列名可能不同，做模糊映射)
        # 标准东财列名
        rename_map = {
            '日期': 'date', '开盘': 'open', '收盘': 'close',
            '最高': 'high', '最低': 'low', '成交量': 'volume', '成交额': 'amount',
            'date': 'date', 'open': 'open', 'close': 'close', 'high': 'high', 'low': 'low', 'volume': 'volume'
        }
        # 重命名确实存在的列
        actual_rename = {col: rename_map[col] for col in df.columns if col in rename_map}
        df = df.rename(columns=actual_rename)
        
        # 如果有些接口把日期放在 index
        if 'date' not in df.columns and df.index.name == 'date':
            df = df.reset_index()
            
        # Ensure date format
        df['date'] = pd.to_datetime(df['date'])
        
        # Select and reorder columns needed by the engine
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"数据源 {source_used} 返回的数据缺失必要字段: {col}")
                
        df = df[required_cols]
        
        # Ensure numeric types
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        return df, source_used
        
    except Exception as e:
        raise e
