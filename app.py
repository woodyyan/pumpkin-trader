import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
import os
import sys

# Add project root to python path to allow importing project modules
sys.path.insert(0, str(Path(__file__).parent))

from config import INITIAL_CAPITAL, TRANSACTION_FEE, MA_SHORT, MA_LONG
from data.data_loader import create_sample_data, DataLoader
from indicators.technical_indicators import TechnicalIndicators
from strategy.trend_strategy import TrendStrategy
from strategy.grid_strategy import GridStrategy
from strategy.mean_reversion_strategy import MeanReversionStrategy
from strategy.range_trading_strategy import RangeTradingStrategy
from engine.backtest_engine import BacktestEngine
from result.metrics import PerformanceMetrics

st.set_page_config(page_title="单股票回测系统", page_icon="📈", layout="wide")

# ================= UI 样式美化 =================
st.markdown("""
<style>
    /* 隐藏 Streamlit 默认的 Header 和 Footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* 优化指标卡片外观 */
    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        border-left: 4px solid #4361ee;
    }
    
    /* 深色模式下的卡片适配 */
    @media (prefers-color-scheme: dark) {
        div[data-testid="metric-container"] {
            background-color: #1e1e1e;
            box-shadow: 0 2px 4px rgba(255, 255, 255, 0.05);
            border-left: 4px solid #3a86ff;
        }
    }
    
    /* 标题样式 */
    .main-header {
        font-weight: 700;
        color: #1f2937;
        margin-bottom: 0px;
    }
    .sub-header {
        color: #6c757d;
        font-size: 1.1rem;
        margin-bottom: 30px;
    }
    @media (prefers-color-scheme: dark) {
        .main-header { color: #f8f9fa; }
        .sub-header { color: #adb5bd; }
    }
</style>
""", unsafe_allow_html=True)

def run_backtest(data_df, capital, fee, strategy_name, strategy_params):
    """运行回测逻辑并返回结果和指标"""
    # 计算技术指标
    indicator_calc = TechnicalIndicators(data_df)
    
    # 临时覆盖全局配置以计算均线
    import config
    original_ma_short = config.MA_SHORT
    original_ma_long = config.MA_LONG
    
    # 动态附加所需的技术指标
    if strategy_name == "趋势跟踪(双均线)":
        config.MA_SHORT = strategy_params['ma_short']
        config.MA_LONG = strategy_params['ma_long']
        data_with_indicators = indicator_calc.calculate_all_indicators()
    elif strategy_name == "均值回归(布林带)":
        data_with_indicators = indicator_calc.data
        upper, mid, lower = indicator_calc.calculate_bollinger_bands(period=strategy_params['bb_period'])
        data_with_indicators['BB_upper'] = upper
        data_with_indicators['BB_mid'] = mid
        data_with_indicators['BB_lower'] = lower
    elif strategy_name == "区间交易(RSI)":
        data_with_indicators = indicator_calc.data
        period = strategy_params['rsi_period']
        data_with_indicators[f'RSI_{period}'] = indicator_calc.calculate_rsi(period=period)
    else: # 网格交易可能不需要复杂的额外指标
        data_with_indicators = indicator_calc.data
    
    # 生成交易信号
    if strategy_name == "趋势跟踪(双均线)":
        strategy = TrendStrategy(data_with_indicators)
    elif strategy_name == "网格交易":
        strategy = GridStrategy(data_with_indicators, grid_count=strategy_params['grid_count'], grid_step_pct=strategy_params['grid_step'])
    elif strategy_name == "均值回归(布林带)":
        strategy = MeanReversionStrategy(data_with_indicators, bb_period=strategy_params['bb_period'])
    elif strategy_name == "区间交易(RSI)":
        strategy = RangeTradingStrategy(data_with_indicators, rsi_period=strategy_params['rsi_period'], 
                                        rsi_low=strategy_params['rsi_low'], rsi_high=strategy_params['rsi_high'])
        
    data_with_signals = strategy.generate_signals()
    
    # 运行回测
    engine = BacktestEngine(data_with_signals, capital, fee)
    results = engine.run_backtest()
    trades = engine.get_trade_log()
    
    # 分析结果
    portfolio_values = results['portfolio_value'].tolist()
    daily_returns = results['daily_return'].tolist()
    trades_dict = trades.to_dict('records')
    
    metrics_calc = PerformanceMetrics(portfolio_values, daily_returns, trades_dict, capital)
    metrics = metrics_calc.calculate_all_metrics()
    
    # 恢复全局配置
    config.MA_SHORT = original_ma_short
    config.MA_LONG = original_ma_long
    
    return results, trades, metrics, strategy_params

# ================= 侧边栏 =================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/line-chart.png", width=60)
    st.markdown("## ⚙️ 策略参数配置")
    st.divider()
    
    st.markdown("### 📁 数据源")
    data_source = st.radio("选择数据", ["生成示例数据", "上传CSV文件"], label_visibility="collapsed")
    uploaded_file = None
    if data_source == "上传CSV文件":
        uploaded_file = st.file_uploader("上传您的股票数据 (CSV)", type="csv")
        st.caption("CSV需包含列: date, open, high, low, close, volume")
    
    st.divider()
    st.markdown("### 💰 资金与费用")
    capital = st.number_input("初始资金 (¥)", min_value=1000, value=int(INITIAL_CAPITAL), step=1000)
    fee_pct = st.slider("手续费率 (%)", min_value=0.0, max_value=2.0, value=TRANSACTION_FEE*100, step=0.01)
    fee = fee_pct / 100.0
    
    st.divider()
    st.markdown("### 📊 策略选择与参数")
    strategy_name = st.selectbox("选择交易策略", ["趋势跟踪(双均线)", "网格交易", "均值回归(布林带)", "区间交易(RSI)"])
    
    strategy_params = {}
    if strategy_name == "趋势跟踪(双均线)":
        col_ma1, col_ma2 = st.columns(2)
        with col_ma1:
            strategy_params['ma_short'] = st.number_input("短期均线", min_value=1, max_value=100, value=int(MA_SHORT), step=1)
        with col_ma2:
            strategy_params['ma_long'] = st.number_input("长期均线", min_value=5, max_value=250, value=int(MA_LONG), step=1)
    
    elif strategy_name == "网格交易":
        strategy_params['grid_count'] = st.number_input("网格数量 (单边)", min_value=1, max_value=20, value=5, step=1)
        grid_step_pct = st.number_input("网格步长 (%)", min_value=0.1, max_value=10.0, value=5.0, step=0.5)
        strategy_params['grid_step'] = grid_step_pct / 100.0
        
    elif strategy_name == "均值回归(布林带)":
        strategy_params['bb_period'] = st.number_input("布林带周期", min_value=5, max_value=100, value=20, step=1)
        
    elif strategy_name == "区间交易(RSI)":
        strategy_params['rsi_period'] = st.number_input("RSI 周期", min_value=2, max_value=50, value=14, step=1)
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            strategy_params['rsi_low'] = st.number_input("买入线(超卖)", min_value=10, max_value=50, value=30, step=5)
        with col_r2:
            strategy_params['rsi_high'] = st.number_input("卖出线(超买)", min_value=50, max_value=90, value=70, step=5)

    start_btn = st.button("🚀 运行回测", use_container_width=True, type="primary")

# ================= 主页面 =================
st.markdown('<h1 class="main-header">📈 量化交易回测系统</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">支持多种经典量化策略的可视化回测分析平台</p>', unsafe_allow_html=True)

if start_btn:
    with st.spinner("⏳ 正在进行数据演算与图表渲染，请稍候..."):
        try:
            # 1. 获取数据
            if data_source == "生成示例数据":
                temp_path = "data/temp_sample.csv"
                os.makedirs("data", exist_ok=True)
                create_sample_data(temp_path)
                data_loader = DataLoader(temp_path)
                data_df = data_loader.prepare_data()
            else:
                if uploaded_file is None:
                    st.error("请先上传数据文件！")
                    st.stop()
                temp_path = "data/temp_upload.csv"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                data_loader = DataLoader(temp_path)
                data_df = data_loader.prepare_data()
            
            # 2. 运行回测
            results, trades, metrics, used_params = run_backtest(data_df, capital, fee, strategy_name, strategy_params)
            
            # 3. 结果展示 - 核心指标卡片
            st.markdown("### 📊 核心表现摘要")
            col1, col2, col3, col4, col5 = st.columns(5)
            
            final_cap = metrics.get('final_capital', 0)
            tot_ret = metrics.get('total_return_pct', 0)
            ann_ret = metrics.get('annual_return_pct', 0)
            max_dd = metrics.get('max_drawdown_pct', 0)
            win_rate = metrics.get('win_rate_pct', 0)
            
            col1.metric("初始资金", f"¥{capital:,.2f}")
            col2.metric("最终资产", f"¥{final_cap:,.2f}", f"{tot_ret:+.2f}%")
            col3.metric("年化收益率", f"{ann_ret:.2f}%", f"{ann_ret:+.2f}%")
            col4.metric("最大回撤", f"{max_dd:.2f}%", f"-{max_dd:.2f}%" if max_dd > 0 else "0%", delta_color="inverse")
            col5.metric("交易胜率", f"{win_rate:.1f}%")
            
            st.write("") # Spacer
            
            # 选项卡展示详细内容
            tab1, tab2, tab3 = st.tabs(["📉 交互式图表分析", "🧾 详细交易记录", "📜 完整指标报告"])
            
            with tab1:
                st.markdown("#### 资产曲线与回撤分析")
                # 绘制使用 Plotly 的资产曲线图
                fig_equity = go.Figure()
                fig_equity.add_trace(go.Scatter(x=results['date'], y=results['portfolio_value'], 
                                              mode='lines', name='总资产', line=dict(color='#4361ee', width=2),
                                              fill='tozeroy', fillcolor='rgba(67, 97, 238, 0.1)'))
                fig_equity.add_hline(y=capital, line_dash="dash", line_color="gray", annotation_text="初始资金")
                
                # 在资产图上标记买卖点
                if not trades.empty:
                    buy_trades = trades[trades['type'] == 'buy']
                    sell_trades = trades[trades['type'] == 'sell']
                    
                    if not buy_trades.empty:
                        # 找到买卖点对应的资产价值
                        buy_vals = [results[results['date'] == d]['portfolio_value'].iloc[0] if len(results[results['date'] == d])>0 else 0 for d in buy_trades['date']]
                        fig_equity.add_trace(go.Scatter(x=buy_trades['date'], y=buy_vals,
                                                      mode='markers', name='买入',
                                                      marker=dict(symbol='triangle-up', size=12, color='#2ecc71', line=dict(width=1, color='DarkSlateGrey'))))
                    if not sell_trades.empty:
                        sell_vals = [results[results['date'] == d]['portfolio_value'].iloc[0] if len(results[results['date'] == d])>0 else 0 for d in sell_trades['date']]
                        fig_equity.add_trace(go.Scatter(x=sell_trades['date'], y=sell_vals,
                                                      mode='markers', name='卖出',
                                                      marker=dict(symbol='triangle-down', size=12, color='#e74c3c', line=dict(width=1, color='DarkSlateGrey'))))
                
                fig_equity.update_layout(height=400, margin=dict(l=0, r=0, t=30, b=0), 
                                       hovermode="x unified", plot_bgcolor='rgba(0,0,0,0)',
                                       xaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)'),
                                       yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)'))
                st.plotly_chart(fig_equity, use_container_width=True)

                st.markdown(f"#### K线图与信号指标 ({strategy_name})")
                # 绘制带双均线的蜡烛图
                fig_candle = go.Figure()
                fig_candle.add_trace(go.Candlestick(x=results['date'],
                                                  open=results['open'], high=results['high'],
                                                  low=results['low'], close=results['close'],
                                                  name='K线'))
                
                # 动态添加策略特定的参考线
                if strategy_name == "趋势跟踪(双均线)":
                    ma_s_col = f"MA{used_params['ma_short']}"
                    ma_l_col = f"MA{used_params['ma_long']}"
                    if ma_s_col in results.columns:
                        fig_candle.add_trace(go.Scatter(x=results['date'], y=results[ma_s_col], mode='lines', name=f'短期均线', line=dict(color='#f39c12', width=1.5)))
                    if ma_l_col in results.columns:
                        fig_candle.add_trace(go.Scatter(x=results['date'], y=results[ma_l_col], mode='lines', name=f'长期均线', line=dict(color='#9b59b6', width=1.5)))
                
                elif strategy_name == "均值回归(布林带)":
                    if 'BB_upper' in results.columns:
                        fig_candle.add_trace(go.Scatter(x=results['date'], y=results['BB_upper'], mode='lines', name='布林带上轨', line=dict(color='rgba(255, 99, 132, 0.7)', dash='dash')))
                        fig_candle.add_trace(go.Scatter(x=results['date'], y=results['BB_lower'], mode='lines', name='布林带下轨', line=dict(color='rgba(46, 204, 113, 0.7)', dash='dash'), fill='tonexty', fillcolor='rgba(128,128,128,0.1)'))
                        fig_candle.add_trace(go.Scatter(x=results['date'], y=results['BB_mid'], mode='lines', name='布林带中轨', line=dict(color='rgba(52, 152, 219, 0.7)')))
                
                fig_candle.update_layout(height=500, margin=dict(l=0, r=0, t=30, b=0),
                                       xaxis_rangeslider_visible=False, hovermode="x unified",
                                       plot_bgcolor='rgba(0,0,0,0)',
                                       xaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)'),
                                       yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)'))
                st.plotly_chart(fig_candle, use_container_width=True)
                
                # 若为 RSI 策略，绘制独立的 RSI 指标图
                if strategy_name == "区间交易(RSI)" and f"RSI_{used_params['rsi_period']}" in results.columns:
                    rsi_col = f"RSI_{used_params['rsi_period']}"
                    fig_rsi = go.Figure()
                    fig_rsi.add_trace(go.Scatter(x=results['date'], y=results[rsi_col], mode='lines', name='RSI', line=dict(color='#8e44ad', width=2)))
                    fig_rsi.add_hline(y=used_params['rsi_high'], line_dash="dash", line_color="red", annotation_text="超买区")
                    fig_rsi.add_hline(y=used_params['rsi_low'], line_dash="dash", line_color="green", annotation_text="超卖区")
                    fig_rsi.update_layout(height=250, title="RSI 指标图", margin=dict(l=0, r=0, t=30, b=0), 
                                          plot_bgcolor='rgba(0,0,0,0)', yaxis=dict(range=[0, 100]))
                    st.plotly_chart(fig_rsi, use_container_width=True)
                
            with tab2:
                if trades.empty:
                    st.info("💡 本次回测没有产生任何满足条件的交易。")
                else:
                    st.markdown("#### 交易明细记录")
                    # 美化表格显示
                    display_trades = trades.copy()
                    display_trades['type'] = display_trades['type'].map({'buy': '🟢 买入', 'sell': '🔴 卖出'})
                    display_trades = display_trades.rename(columns={
                        'date': '日期', 'type': '方向', 'price': '成交价(¥)', 
                        'shares': '股数', 'amount': '交易金额(¥)', 'fee': '手续费(¥)',
                        'cash_after': '剩余现金(¥)', 'shares_after': '剩余持仓'
                    })
                    st.dataframe(display_trades.style.format({
                        '成交价(¥)': '{:.2f}', '交易金额(¥)': '{:.2f}', '手续费(¥)': '{:.2f}', '剩余现金(¥)': '{:.2f}'
                    }), use_container_width=True)
                    
            with tab3:
                st.markdown("#### 综合风险分析报告")
                c1, c2, c3 = st.columns(3)
                
                with c1:
                    st.markdown("**💰 收益指标**")
                    st.write(f"- **总收益率:** {metrics.get('total_return_pct', 0):.2f}%")
                    st.write(f"- **年化收益率:** {metrics.get('annual_return_pct', 0):.2f}%")
                    st.write(f"- **平均日收益:** {metrics.get('avg_daily_return_pct', 0):.4f}%")
                    
                with c2:
                    st.markdown("**⚠️ 风险指标**")
                    st.write(f"- **最大回撤:** {metrics.get('max_drawdown_pct', 0):.2f}%")
                    st.write(f"- **年化波动率:** {metrics.get('volatility_pct', 0):.2f}%")
                    st.write(f"- **夏普比率:** {metrics.get('sharpe_ratio', 0):.4f}")
                    
                with c3:
                    st.markdown("**🔄 交易统计**")
                    st.write(f"- **总交易次数:** {metrics.get('total_trades', 0)} 次")
                    st.write(f"- **交易胜率:** {metrics.get('win_rate_pct', 0):.1f}%")
                    st.write(f"- **总手续费支出:** ¥{metrics.get('total_fee', 0):,.2f}")
                    st.write(f"- **回测天数:** {metrics.get('total_days', 0)} 天")

        except Exception as e:
            st.error(f"❌ 回测过程中发生错误: {e}")
            st.exception(e)
else:
    # 引导页占位提示
    st.info("👈 请在左侧面板配置数据源和回测参数，然后点击「运行回测」按钮开始分析。")
