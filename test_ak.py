import akshare as ak
try:
    print("Testing A-share data...")
    df = ak.stock_zh_a_hist(symbol="600519", period="daily", start_date="20200101", end_date="20200110", adjust="qfq")
    print(f"Success! Got {len(df)} rows")
except Exception as e:
    print(f"Failed! Error: {e}")
