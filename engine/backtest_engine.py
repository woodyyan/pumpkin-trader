"""
回测引擎模块 - 负责模拟交易
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from config import INITIAL_CAPITAL, TRANSACTION_FEE, EXECUTION_PRICE


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, data: pd.DataFrame, initial_capital: float = None, fee: float = None):
        """
        初始化回测引擎
        
        Parameters:
        -----------
        data : pd.DataFrame
            包含信号的数据
        initial_capital : float, optional
            初始资金，默认为config.py中的INITIAL_CAPITAL
        fee : float, optional
            交易手续费率，默认为config.py中的TRANSACTION_FEE
        """
        self.data = data.copy()
        self.initial_capital = initial_capital or INITIAL_CAPITAL
        self.fee_rate = fee or TRANSACTION_FEE
        self.execution_price = EXECUTION_PRICE
        
        # 回测结果
        self.cash = []  # 现金序列
        self.shares = []  # 持仓股数序列
        self.portfolio_value = []  # 总资产序列
        self.trades = []  # 交易记录
        self.daily_returns = []  # 日收益率序列
        
        # 当前状态
        self.current_cash = self.initial_capital
        self.current_shares = 0
        self.current_position = 0  # 持仓方向
        self.current_date = None
        
    def run_backtest(self) -> pd.DataFrame:
        """
        运行回测
        
        Returns:
        --------
        pd.DataFrame
            包含回测结果的数据
        """
        print("🚀 开始运行回测...")
        print(f"  初始资金: ¥{self.initial_capital:,.2f}")
        print(f"  手续费率: {self.fee_rate*100:.2f}%")
        print(f"  执行价格: {self.execution_price}")
        
        # 初始化结果列表
        self.cash = []
        self.shares = []
        self.portfolio_value = []
        self.trades = []
        self.daily_returns = []
        
        # 重置当前状态
        self.current_cash = self.initial_capital
        self.current_shares = 0
        self.current_position = 0
        
        # 确保数据有必要的列
        required_cols = ['signal', 'close', 'open']
        for col in required_cols:
            if col not in self.data.columns:
                raise ValueError(f"数据中缺少必要列: {col}")
        
        # 检查是否包含交易比例信号(用于网格交易等部分建仓策略)
        has_signal_size = 'signal_size' in self.data.columns
        
        # 如果有日期列，使用日期
        if 'date' in self.data.columns:
            dates = self.data['date'].tolist()
        else:
            dates = list(range(len(self.data)))
        
        # 运行回测
        for i in range(len(self.data)):
            self.current_date = dates[i]
            
            # 获取当前数据
            current_signal = self.data['signal'].iloc[i]
            current_size = self.data['signal_size'].iloc[i] if has_signal_size else 1.0
            
            # 如果是 NaN 或者 0 就不交易
            if pd.isna(current_size) or current_size <= 0:
                current_size = 1.0 if not has_signal_size else 0.0
                
            current_close = self.data['close'].iloc[i]
            current_open = self.data['open'].iloc[i]
            
            # 确定执行价格
            if self.execution_price == "next_open" and i < len(self.data) - 1:
                execution_price = self.data['open'].iloc[i+1]
            else:
                execution_price = current_close
            
            # 处理交易信号 (移除仓位限制以支持多次买入/卖出，具体由策略生成size控制)
            if current_signal == 'buy' and current_size > 0:
                self._execute_buy(execution_price, i, current_size)
                
            elif current_signal == 'sell' and current_size > 0 and self.current_shares > 0:
                self._execute_sell(execution_price, i, current_size)
            
            # 计算当前资产
            current_value = self._calculate_portfolio_value(current_close)
            
            # 记录每日状态
            self.cash.append(self.current_cash)
            self.shares.append(self.current_shares)
            self.portfolio_value.append(current_value)
            
            # 计算日收益率
            if i == 0:
                daily_return = 0.0
            else:
                daily_return = (current_value - self.portfolio_value[i-1]) / self.portfolio_value[i-1]
            self.daily_returns.append(daily_return)
        
        # 将结果添加到数据中
        self.data['cash'] = self.cash
        self.data['shares'] = self.shares
        self.data['portfolio_value'] = self.portfolio_value
        self.data['daily_return'] = self.daily_returns
        
        # 计算累计收益
        self.data['cumulative_return'] = (1 + pd.Series(self.daily_returns)).cumprod() - 1
        
        # 输出回测摘要
        self._print_backtest_summary()
        
        return self.data
    
    def _execute_buy(self, price: float, index: int, size_pct: float = 1.0):
        """执行买入操作
        size_pct: 买入资金占当前可用资金的比例 (0.0 ~ 1.0)
        """
        if price <= 0:
            print(f"⚠️ 第{index}天: 买入价格无效 ({price})")
            return
        
        # 计算可买入股数（支持部分资金买入）
        available_cash = self.current_cash * size_pct
        fee = available_cash * self.fee_rate
        investable_cash = available_cash - fee
        
        shares_to_buy = int(investable_cash / price)
        
        if shares_to_buy <= 0:
            return
        
        # 计算实际花费
        cost = shares_to_buy * price
        total_fee = cost * self.fee_rate
        total_cost = cost + total_fee
        
        # 更新状态
        self.current_shares += shares_to_buy
        self.current_cash -= total_cost
        self.current_position = 1
        
        # 记录交易
        trade = {
            'date': self.current_date,
            'type': 'buy',
            'price': price,
            'shares': shares_to_buy,
            'amount': cost,
            'fee': total_fee,
            'cash_after': self.current_cash,
            'shares_after': self.current_shares
        }
        self.trades.append(trade)
        
        if hasattr(self, 'verbose') and self.verbose:
            print(f"✅ 第{index}天: 买入 {shares_to_buy} 股 @ ¥{price:.2f}, 花费 ¥{total_cost:.2f} (含手续费 ¥{total_fee:.2f})")
    
    def _execute_sell(self, price: float, index: int, size_pct: float = 1.0):
        """执行卖出操作
        size_pct: 卖出持仓股数的比例 (0.0 ~ 1.0)
        """
        if self.current_shares <= 0:
            return
        
        if price <= 0:
            print(f"⚠️ 第{index}天: 卖出价格无效 ({price})")
            return
        
        # 计算卖出数量
        shares_to_sell = int(self.current_shares * size_pct)
        if shares_to_sell <= 0:
            return
            
        revenue = shares_to_sell * price
        fee = revenue * self.fee_rate
        net_revenue = revenue - fee
        
        # 更新状态
        self.current_cash += net_revenue
        self.current_shares -= shares_to_sell
        
        if self.current_shares == 0:
            self.current_position = 0
        
        # 记录交易
        trade = {
            'date': self.current_date,
            'type': 'sell',
            'price': price,
            'shares': shares_to_sell,
            'amount': revenue,
            'fee': fee,
            'cash_after': self.current_cash,
            'shares_after': self.current_shares
        }
        self.trades.append(trade)
        
        if hasattr(self, 'verbose') and self.verbose:
            print(f"✅ 第{index}天: 卖出 {shares_to_sell} 股 @ ¥{price:.2f}, 收入 ¥{net_revenue:.2f} (含手续费 ¥{fee:.2f})")
    
    def _calculate_portfolio_value(self, current_price: float) -> float:
        """计算当前总资产价值"""
        stock_value = self.current_shares * current_price
        return self.current_cash + stock_value
    
    def _print_backtest_summary(self):
        """打印回测摘要"""
        if len(self.portfolio_value) == 0:
            print("⚠️ 回测结果为空")
            return
        
        initial_value = self.portfolio_value[0]
        final_value = self.portfolio_value[-1]
        total_return = (final_value - initial_value) / initial_value * 100
        
        # 计算年化收益（假设252个交易日）
        total_days = len(self.portfolio_value)
        years = total_days / 252
        if years > 0:
            annual_return = ((final_value / initial_value) ** (1/years) - 1) * 100
        else:
            annual_return = 0
        
        # 计算最大回撤
        max_drawdown = self._calculate_max_drawdown()
        
        # 交易统计
        total_trades = len(self.trades)
        buy_trades = len([t for t in self.trades if t['type'] == 'buy'])
        sell_trades = len([t for t in self.trades if t['type'] == 'sell'])
        
        print("\n" + "="*60)
        print("📊 回测结果摘要")
        print("="*60)
        print(f"初始资金:      ¥{initial_value:,.2f}")
        print(f"最终资产:      ¥{final_value:,.2f}")
        print(f"总收益:        {total_return:+.2f}%")
        print(f"年化收益:      {annual_return:+.2f}%")
        print(f"最大回撤:      {max_drawdown:.2f}%")
        print(f"总交易次数:    {total_trades} 次")
        print(f"买入交易:      {buy_trades} 次")
        print(f"卖出交易:      {sell_trades} 次")
        print(f"回测天数:      {total_days} 天")
        
        if total_trades > 0:
            total_fee = sum(t['fee'] for t in self.trades)
            print(f"总手续费:      ¥{total_fee:,.2f}")
            avg_trade_return = total_return / (total_trades / 2) if total_trades > 0 else 0
            print(f"平均交易收益:   {avg_trade_return:.2f}%")
        
        print("="*60)
    
    def _calculate_max_drawdown(self) -> float:
        """计算最大回撤"""
        if not self.portfolio_value:
            return 0.0
        
        portfolio_series = pd.Series(self.portfolio_value)
        rolling_max = portfolio_series.expanding().max()
        drawdowns = (portfolio_series - rolling_max) / rolling_max * 100
        max_drawdown = drawdowns.min()
        
        return abs(max_drawdown) if max_drawdown < 0 else 0.0
    
    def get_trade_log(self) -> pd.DataFrame:
        """
        获取交易日志
        
        Returns:
        --------
        pd.DataFrame
            交易日志
        """
        if not self.trades:
            return pd.DataFrame()
        
        return pd.DataFrame(self.trades)
    
    def get_performance_metrics(self) -> Dict:
        """
        获取性能指标
        
        Returns:
        --------
        dict
            性能指标字典
        """
        if len(self.portfolio_value) == 0:
            return {}
        
        initial_value = self.portfolio_value[0]
        final_value = self.portfolio_value[-1]
        total_return_pct = (final_value - initial_value) / initial_value * 100
        
        # 年化收益
        total_days = len(self.portfolio_value)
        years = total_days / 252
        if years > 0:
            cagr = ((final_value / initial_value) ** (1/years) - 1) * 100
        else:
            cagr = 0
        
        # 夏普比率（简化版，假设无风险利率为0）
        daily_returns_series = pd.Series(self.daily_returns)
        sharpe_ratio = 0
        if daily_returns_series.std() > 0:
            sharpe_ratio = (daily_returns_series.mean() * 252) / (daily_returns_series.std() * np.sqrt(252))
        
        # 胜率（需要计算每笔交易的收益）
        win_rate = self._calculate_win_rate()
        
        metrics = {
            "initial_capital": initial_value,
            "final_capital": final_value,
            "total_return_pct": total_return_pct,
            "annual_return_pct": cagr,
            "max_drawdown_pct": self._calculate_max_drawdown(),
            "total_trades": len(self.trades),
            "win_rate_pct": win_rate,
            "sharpe_ratio": sharpe_ratio,
            "total_days": total_days,
            "total_fee": sum(t['fee'] for t in self.trades) if self.trades else 0,
            "avg_daily_return_pct": daily_returns_series.mean() * 100,
            "volatility_pct": daily_returns_series.std() * 100 * np.sqrt(252)
        }
        
        return metrics
    
    def _calculate_win_rate(self) -> float:
        """计算胜率"""
        if len(self.trades) < 2:
            return 0.0
        
        # 找出完整的买入-卖出交易对
        winning_trades = 0
        total_paired_trades = 0
        
        i = 0
        while i < len(self.trades) - 1:
            if self.trades[i]['type'] == 'buy' and self.trades[i+1]['type'] == 'sell':
                buy_price = self.trades[i]['price']
                sell_price = self.trades[i+1]['price']
                
                if sell_price > buy_price:
                    winning_trades += 1
                
                total_paired_trades += 1
                i += 2  # 跳过这一对
            else:
                i += 1
        
        if total_paired_trades == 0:
            return 0.0
        
        return (winning_trades / total_paired_trades) * 100
    
    def plot_equity_curve(self):
        """绘制资产曲线"""
        try:
            import matplotlib.pyplot as plt
            
            if not self.portfolio_value:
                print("⚠️ 没有回测数据可绘制")
                return
            
            fig, axes = plt.subplots(2, 1, figsize=(14, 10))
            
            # 资产曲线
            ax1 = axes[0]
            
            # 如果有日期，使用日期作为x轴
            if 'date' in self.data.columns:
                x_data = self.data['date']
            else:
                x_data = range(len(self.portfolio_value))
            
            ax1.plot(x_data, self.portfolio_value, linewidth=2, color='blue', label='Portfolio Value')
            ax1.axhline(y=self.initial_capital, color='red', linestyle='--', alpha=0.5, label='Initial Capital')
            
            # 标记交易点
            trade_dates = []
            trade_prices = []
            trade_types = []
            
            for trade in self.trades:
                if 'date' in trade:
                    trade_dates.append(trade['date'])
                    trade_prices.append(trade['price'] * 10)  # 缩放以便在图上显示
                    trade_types.append(trade['type'])
            
            if trade_dates:
                buy_dates = [d for d, t in zip(trade_dates, trade_types) if t == 'buy']
                buy_values = [self.portfolio_value[self.data['date'] == d].iloc[0] if 'date' in self.data.columns 
                            else self.portfolio_value[0] for d in buy_dates]
                
                sell_dates = [d for d, t in zip(trade_dates, trade_types) if t == 'sell']
                sell_values = [self.portfolio_value[self.data['date'] == d].iloc[0] if 'date' in self.data.columns 
                             else self.portfolio_value[0] for d in sell_dates]
                
                if buy_dates:
                    ax1.scatter(buy_dates, buy_values, color='green', s=100, marker='^', label='Buy', zorder=5)
                
                if sell_dates:
                    ax1.scatter(sell_dates, sell_values, color='red', s=100, marker='v', label='Sell', zorder=5)
            
            ax1.set_title('Portfolio Equity Curve')
            ax1.set_xlabel('Date' if 'date' in self.data.columns else 'Day')
            ax1.set_ylabel('Portfolio Value (¥)')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # 回撤图
            ax2 = axes[1]
            
            # 计算回撤
            portfolio_series = pd.Series(self.portfolio_value)
            rolling_max = portfolio_series.expanding().max()
            drawdowns = (portfolio_series - rolling_max) / rolling_max * 100
            
            ax2.fill_between(x_data, drawdowns, 0, color='red', alpha=0.3)
            ax2.plot(x_data, drawdowns, color='red', linewidth=1)
            ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            
            ax2.set_title('Drawdown')
            ax2.set_xlabel('Date' if 'date' in self.data.columns else 'Day')
            ax2.set_ylabel('Drawdown (%)')
            ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            plt.show()
            
        except ImportError:
            print("⚠️ Matplotlib未安装，无法绘制图表")
        except Exception as e:
            print(f"⚠️ 绘图失败: {e}")


if __name__ == "__main__":
    # 测试回测引擎
    print("🧪 测试回测引擎...")
    
    # 创建示例数据
    from data.data_loader import create_sample_data, DataLoader
    from indicators.technical_indicators import TechnicalIndicators
    from strategy.trend_strategy import TrendStrategy
    
    # 加载数据
    loader = DataLoader()
    if not loader.data_path.exists():
        create_sample_data(str(loader.data_path))
    
    data = loader.prepare_data()
    
    # 计算指标
    indicator_calc = TechnicalIndicators(data)
    data_with_indicators = indicator_calc.calculate_all_indicators()
    
    # 生成信号
    strategy = TrendStrategy(data_with_indicators)
    data_with_signals = strategy.generate_signals()
    
    # 运行回测
    engine = BacktestEngine(data_with_signals)
    results = engine.run_backtest()
    
    # 获取性能指标
    metrics = engine.get_performance_metrics()
    print("\n📈 详细性能指标:")
    for key, value in metrics.items():
        if 'pct' in key:
            print(f"  {key}: {value:.2f}%")
        elif key in ['sharpe_ratio', 'avg_daily_return_pct', 'volatility_pct']:
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")
    
    # 显示交易日志
    trade_log = engine.get_trade_log()
    if not trade_log.empty:
        print(f"\n📝 交易日志 ({len(trade_log)} 笔交易):")
        print(trade_log.head(10))
        if len(trade_log) > 10:
            print(f"... 还有 {len(trade_log) - 10} 笔交易")
    
    # 显示最后10天的状态
    print("\n📋 最后10天回测状态:")
    cols_to_show = ['date', 'close', 'signal', 'cash', 'shares', 'portfolio_value', 'daily_return']
    cols_to_show = [c for c in cols_to_show if c in results.columns]
    print(results[cols_to_show].tail(10))
    
    # 尝试绘制资产曲线
    engine.plot_equity_curve()
