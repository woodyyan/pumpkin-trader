import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import os
import sys
import io
import contextlib

# Add project root to python path to allow importing project modules
sys.path.insert(0, str(Path(__file__).parent))

from config import INITIAL_CAPITAL, TRANSACTION_FEE, MA_SHORT, MA_LONG
from data.data_loader import create_sample_data, DataLoader
from indicators.technical_indicators import TechnicalIndicators
from strategy.trend_strategy import TrendStrategy
from engine.backtest_engine import BacktestEngine
from result.metrics import PerformanceMetrics

st.set_page_config(page_title="单股票回测系统", page_icon="📈", layout="wide")

def run_backtest(data_df, capital, fee, ma_short, ma_long):
    """运行回测逻辑并返回结果和指标"""
    # 步骤2: 计算技术指标
    indicator_calc = TechnicalIndicators(data_df)
    # 临时覆盖全局配置（在实际项目中可能需要改类使其接收参数）
    import config
    original_ma_short = config.MA_SHORT
    original_ma_long = config.MA_LONG
    config.MA_SHORT = ma_short
    config.MA_LONG = ma_long
    
    data_with_indicators = indicator_calc.calculate_all_indicators()
    
    # 步骤3: 生成交易信号
    strategy = TrendStrategy(data_with_indicators)
    data_with_signals = strategy.generate_signals()
    
    # 步骤4: 运行回测
    engine = BacktestEngine(data_with_signals, capital, fee)
    results = engine.run_backtest()
    trades = engine.get_trade_log()
    
    # 步骤5: 分析结果
    portfolio_values = results['portfolio_value'].tolist()
    daily_returns = results['daily_return'].tolist()
    trades_dict = trades.to_dict('records')
    
    metrics_calc = PerformanceMetrics(portfolio_values, daily_returns, trades_dict, capital)
    metrics = metrics_calc.calculate_all_metrics()
    
    # 恢复全局配置
    config.MA_SHORT = original_ma_short
    config.MA_LONG = original_ma_long
    
    return results, trades, metrics, engine, metrics_calc

# ================= UI 布局 =================

st.title("📈 单股票回测系统 (Web版)")
st.markdown("通过此界面，您可以上传股票数据、调整策略参数，并一键运行趋势跟踪（均线交叉）策略回测。")

# 侧边栏：参数配置
st.sidebar.header("⚙️ 参数配置")

st.sidebar.subheader("数据源")
data_source = st.sidebar.radio("选择数据", ["生成示例数据", "上传CSV文件"])
uploaded_file = None
if data_source == "上传CSV文件":
    uploaded_file = st.sidebar.file_uploader("上传您的股票数据 (CSV)", type="csv")
    st.sidebar.info("CSV需包含列: date, open, high, low, close, volume")

st.sidebar.subheader("资金与费用")
capital = st.sidebar.number_input("初始资金 (¥)", min_value=1000, value=int(INITIAL_CAPITAL), step=1000)
fee_pct = st.sidebar.number_input("手续费率 (%)", min_value=0.0, max_value=5.0, value=TRANSACTION_FEE*100, step=0.01)
fee = fee_pct / 100.0

st.sidebar.subheader("策略参数 (均线周期)")
ma_short = st.sidebar.number_input("短期均线", min_value=1, max_value=100, value=int(MA_SHORT), step=1)
ma_long = st.sidebar.number_input("长期均线", min_value=5, max_value=250, value=int(MA_LONG), step=1)

if st.sidebar.button("🚀 开始回测", use_container_width=True):
    with st.spinner("正在运行回测..."):
        try:
            # 1. 获取数据
            if data_source == "生成示例数据":
                # 使用临时文件生成和读取
                temp_path = "data/temp_sample.csv"
                os.makedirs("data", exist_ok=True)
                create_sample_data(temp_path)
                data_loader = DataLoader(temp_path)
                data_df = data_loader.prepare_data()
            else:
                if uploaded_file is None:
                    st.error("请先上传数据文件！")
                    st.stop()
                
                # 读取上传的文件
                temp_path = "data/temp_upload.csv"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                data_loader = DataLoader(temp_path)
                data_df = data_loader.prepare_data()
            
            # 2. 运行回测
            results, trades, metrics, engine, metrics_calc = run_backtest(
                data_df, capital, fee, ma_short, ma_long
            )
            
            # 3. 结果展示
            st.success("✅ 回测运行完成！")
            
            # 关键指标展示
            st.subheader("📊 回测摘要")
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("初始资金", f"¥{capital:,.2f}")
            col2.metric("最终资产", f"¥{metrics.get('final_capital', 0):,.2f}", f"{metrics.get('total_return_pct', 0):.2f}%")
            col3.metric("年化收益", f"{metrics.get('annual_return_pct', 0):.2f}%")
            col4.metric("最大回撤", f"{metrics.get('max_drawdown_pct', 0):.2f}%")
            col5.metric("胜率", f"{metrics.get('win_rate_pct', 0):.1f}%")
            
            # 选项卡展示详细内容
            tab1, tab2, tab3 = st.tabs(["📉 图表分析", "🧾 交易记录", "📜 详细指标"])
            
            with tab1:
                st.markdown("### 资产曲线图")
                # 捕获 matplotlib 绘图
                fig1 = plt.figure(figsize=(10, 6))
                plt.plot(pd.to_datetime(results['date']), results['portfolio_value'])
                plt.title('Portfolio Value')
                plt.xlabel('Date')
                plt.ylabel('Value (¥)')
                plt.grid(True)
                st.pyplot(fig1)
                
                st.markdown("### 性能分析图")
                # 创建一个上下文来捕获 metrics_calc.plot_performance_charts 内部的 figure
                # metrics.py 可能使用了 plt.show()，Streamlit 会自动抓取当前的 figure 或是需要修改绘图逻辑
                # 为了简便，我们重新绘制一些核心图表
                
                # 累计收益率
                fig2 = plt.figure(figsize=(10, 4))
                plt.plot(pd.to_datetime(results['date']), results['cumulative_return'] * 100)
                plt.title('Cumulative Return (%)')
                plt.grid(True)
                st.pyplot(fig2)
                
            with tab2:
                if trades.empty:
                    st.info("本次回测没有产生任何交易。")
                else:
                    st.dataframe(trades, use_container_width=True)
                    
            with tab3:
                st.json(metrics)

        except Exception as e:
            st.error(f"回测过程中发生错误: {e}")
            st.exception(e)
