"""
结果模块 - 负责计算和输出回测结果
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import matplotlib.pyplot as plt
from datetime import datetime
from config import INITIAL_CAPITAL


class PerformanceMetrics:
    """性能指标计算器"""
    
    def __init__(self, portfolio_values: List[float], daily_returns: List[float], 
                 trades: List[Dict], initial_capital: float = None):
        """
        初始化性能指标计算器
        
        Parameters:
        -----------
        portfolio_values : List[float]
            每日资产价值列表
        daily_returns : List[float]
            日收益率列表
        trades : List[Dict]
            交易记录列表
        initial_capital : float, optional
            初始资金
        """
        self.portfolio_values = portfolio_values
        self.daily_returns = daily_returns
        self.trades = trades
        self.initial_capital = initial_capital or INITIAL_CAPITAL
        
        # 转换为pandas Series以便计算
        self.portfolio_series = pd.Series(portfolio_values)
        self.returns_series = pd.Series(daily_returns)
    
    def calculate_all_metrics(self) -> Dict:
        """
        计算所有性能指标
        
        Returns:
        --------
        dict
            所有性能指标
        """
        print("📊 计算性能指标...")
        
        metrics = {}
        
        # 基础收益指标
        metrics.update(self._calculate_return_metrics())
        
        # 风险指标
        metrics.update(self._calculate_risk_metrics())
        
        # 交易统计
        metrics.update(self._calculate_trade_metrics())
        
        # 其他指标
        metrics.update(self._calculate_other_metrics())
        
        return metrics
    
    def _calculate_return_metrics(self) -> Dict:
        """计算收益相关指标"""
        if len(self.portfolio_values) < 2:
            return {}
        
        initial_value = self.portfolio_values[0]
        final_value = self.portfolio_values[-1]
        
        # 总收益
        total_return_pct = (final_value - initial_value) / initial_value * 100
        
        # 年化收益（假设252个交易日）
        total_days = len(self.portfolio_values)
        years = total_days / 252
        if years > 0:
            cagr = ((final_value / initial_value) ** (1/years) - 1) * 100
        else:
            cagr = 0
        
        # 累计收益
        cumulative_return = (1 + self.returns_series).cumprod() - 1
        final_cumulative_return = cumulative_return.iloc[-1] * 100 if not cumulative_return.empty else 0
        
        return {
            "initial_capital": initial_value,
            "final_capital": final_value,
            "total_return_pct": total_return_pct,
            "annual_return_pct": cagr,
            "cumulative_return_pct": final_cumulative_return,
            "total_days": total_days,
            "years": years
        }
    
    def _calculate_risk_metrics(self) -> Dict:
        """计算风险相关指标"""
        if len(self.returns_series) < 2:
            return {}
        
        # 最大回撤
        max_drawdown_pct = self._calculate_max_drawdown()
        
        # 波动率（年化）
        volatility_pct = self.returns_series.std() * np.sqrt(252) * 100
        
        # 夏普比率（简化版，假设无风险利率为0）
        sharpe_ratio = 0
        if self.returns_series.std() > 0:
            sharpe_ratio = (self.returns_series.mean() * 252) / (self.returns_series.std() * np.sqrt(252))
        
        # 索提诺比率（简化版，只考虑下行风险）
        sortino_ratio = self._calculate_sortino_ratio()
        
        # 卡玛比率
        calmar_ratio = 0
        if max_drawdown_pct > 0:
            calmar_ratio = self.returns_series.mean() * 252 / (max_drawdown_pct / 100)
        
        return {
            "max_drawdown_pct": max_drawdown_pct,
            "volatility_pct": volatility_pct,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "calmar_ratio": calmar_ratio,
            "avg_daily_return_pct": self.returns_series.mean() * 100,
            "std_daily_return_pct": self.returns_series.std() * 100
        }
    
    def _calculate_max_drawdown(self) -> float:
        """计算最大回撤"""
        if len(self.portfolio_values) == 0:
            return 0.0
        
        portfolio_series = pd.Series(self.portfolio_values)
        rolling_max = portfolio_series.expanding().max()
        drawdowns = (portfolio_series - rolling_max) / rolling_max * 100
        max_drawdown = drawdowns.min()
        
        return abs(max_drawdown) if max_drawdown < 0 else 0.0
    
    def _calculate_sortino_ratio(self) -> float:
        """计算索提诺比率"""
        if len(self.returns_series) < 2:
            return 0.0
        
        # 只考虑负收益（下行风险）
        negative_returns = self.returns_series[self.returns_series < 0]
        if len(negative_returns) == 0:
            return 0.0
        
        downside_std = negative_returns.std()
        if downside_std == 0:
            return 0.0
        
        # 年化平均收益 / 年化下行标准差
        sortino_ratio = (self.returns_series.mean() * 252) / (downside_std * np.sqrt(252))
        return sortino_ratio
    
    def _calculate_trade_metrics(self) -> Dict:
        """计算交易相关指标"""
        if not self.trades:
            return {
                "total_trades": 0,
                "win_rate_pct": 0,
                "profit_factor": 0,
                "avg_trade_return_pct": 0,
                "total_fee": 0
            }
        
        total_trades = len(self.trades)
        
        # 计算总手续费
        total_fee = sum(trade.get('fee', 0) for trade in self.trades)
        
        # 计算胜率和盈亏比
        win_rate, profit_factor, avg_trade_return = self._analyze_trades()
        
        # 计算交易频率
        trade_frequency = total_trades / (len(self.portfolio_values) / 252) if len(self.portfolio_values) > 0 else 0
        
        return {
            "total_trades": total_trades,
            "win_rate_pct": win_rate,
            "profit_factor": profit_factor,
            "avg_trade_return_pct": avg_trade_return,
            "total_fee": total_fee,
            "trade_frequency_per_year": trade_frequency,
            "buy_trades": len([t for t in self.trades if t.get('type') == 'buy']),
            "sell_trades": len([t for t in self.trades if t.get('type') == 'sell'])
        }
    
    def _analyze_trades(self) -> Tuple[float, float, float]:
        """分析交易记录"""
        if len(self.trades) < 2:
            return 0.0, 0.0, 0.0
        
        # 找出完整的交易对（买入-卖出）
        trade_pairs = []
        i = 0
        
        while i < len(self.trades) - 1:
            if self.trades[i].get('type') == 'buy' and self.trades[i+1].get('type') == 'sell':
                buy_trade = self.trades[i]
                sell_trade = self.trades[i+1]
                
                buy_price = buy_trade.get('price', 0)
                sell_price = sell_trade.get('price', 0)
                
                if buy_price > 0:
                    trade_return = (sell_price - buy_price) / buy_price * 100
                    trade_pairs.append({
                        'buy_date': buy_trade.get('date'),
                        'sell_date': sell_trade.get('date'),
                        'buy_price': buy_price,
                        'sell_price': sell_price,
                        'return_pct': trade_return,
                        'is_winning': trade_return > 0
                    })
                
                i += 2  # 跳过这一对
            else:
                i += 1
        
        if not trade_pairs:
            return 0.0, 0.0, 0.0
        
        # 计算胜率
        winning_trades = len([p for p in trade_pairs if p['is_winning']])
        win_rate = (winning_trades / len(trade_pairs)) * 100
        
        # 计算盈亏比（盈利交易平均收益 / 亏损交易平均亏损）
        winning_returns = [p['return_pct'] for p in trade_pairs if p['return_pct'] > 0]
        losing_returns = [abs(p['return_pct']) for p in trade_pairs if p['return_pct'] < 0]
        
        profit_factor = 0
        if losing_returns and sum(winning_returns) > 0:
            profit_factor = sum(winning_returns) / sum(losing_returns)
        
        # 计算平均交易收益
        avg_trade_return = np.mean([p['return_pct'] for p in trade_pairs]) if trade_pairs else 0
        
        return win_rate, profit_factor, avg_trade_return
    
    def _calculate_other_metrics(self) -> Dict:
        """计算其他指标"""
        if len(self.returns_series) < 2:
            return {}
        
        # 偏度（收益分布的不对称性）
        skewness = self.returns_series.skew()
        
        # 峰度（收益分布的尖峰程度）
        kurtosis = self.returns_series.kurtosis()
        
        # 信息比率（相对于基准，这里使用0作为基准）
        information_ratio = 0
        if self.returns_series.std() > 0:
            information_ratio = self.returns_series.mean() / self.returns_series.std() * np.sqrt(252)
        
        # 胜率（日收益为正的天数比例）
        positive_days = (self.returns_series > 0).sum()
        daily_win_rate = positive_days / len(self.returns_series) * 100
        
        return {
            "skewness": skewness,
            "kurtosis": kurtosis,
            "information_ratio": information_ratio,
            "daily_win_rate_pct": daily_win_rate,
            "best_day_pct": self.returns_series.max() * 100,
            "worst_day_pct": self.returns_series.min() * 100
        }
    
    def print_summary_report(self, metrics: Dict = None):
        """
        打印总结报告
        
        Parameters:
        -----------
        metrics : dict, optional
            性能指标，如果为None则重新计算
        """
        if metrics is None:
            metrics = self.calculate_all_metrics()
        
        print("\n" + "="*70)
        print("📈 回测性能报告")
        print("="*70)
        
        # 收益部分
        print("\n💰 收益表现:")
        print(f"   初始资金:      ¥{metrics.get('initial_capital', 0):,.2f}")
        print(f"   最终资产:      ¥{metrics.get('final_capital', 0):,.2f}")
        print(f"   总收益:        {metrics.get('total_return_pct', 0):+.2f}%")
        print(f"   年化收益:      {metrics.get('annual_return_pct', 0):+.2f}%")
        print(f"   累计收益:      {metrics.get('cumulative_return_pct', 0):+.2f}%")
        
        # 风险部分
        print("\n⚠️  风险指标:")
        print(f"   最大回撤:      {metrics.get('max_drawdown_pct', 0):.2f}%")
        print(f"   年化波动率:    {metrics.get('volatility_pct', 0):.2f}%")
        print(f"   夏普比率:      {metrics.get('sharpe_ratio', 0):.3f}")
        print(f"   索提诺比率:    {metrics.get('sortino_ratio', 0):.3f}")
        print(f"   卡玛比率:      {metrics.get('calmar_ratio', 0):.3f}")
        
        # 交易部分
        print("\n📊 交易统计:")
        print(f"   总交易次数:    {metrics.get('total_trades', 0)} 次")
        print(f"   胜率:          {metrics.get('win_rate_pct', 0):.1f}%")
        print(f"   盈亏比:        {metrics.get('profit_factor', 0):.2f}")
        print(f"   平均交易收益:  {metrics.get('avg_trade_return_pct', 0):.2f}%")
        print(f"   年交易频率:    {metrics.get('trade_frequency_per_year', 0):.1f} 次/年")
        print(f"   总手续费:      ¥{metrics.get('total_fee', 0):,.2f}")
        
        # 其他指标
        print("\n📈 其他指标:")
        print(f"   日收益胜率:    {metrics.get('daily_win_rate_pct', 0):.1f}%")
        print(f"   最佳单日收益:  {metrics.get('best_day_pct', 0):.2f}%")
        print(f"   最差单日收益:  {metrics.get('worst_day_pct', 0):.2f}%")
        print(f"   偏度:          {metrics.get('skewness', 0):.3f}")
        print(f"   峰度:          {metrics.get('kurtosis', 0):.3f}")
        
        print("="*70)
    
    def plot_performance_charts(self, dates: Optional[List] = None):
        """
        绘制性能图表
        
        Parameters:
        -----------
        dates : List, optional
            日期列表，用于x轴
        """
        try:
            fig = plt.figure(figsize=(16, 12))
            
            # 1. 资产曲线
            ax1 = plt.subplot(3, 2, 1)
            if dates is not None and len(dates) == len(self.portfolio_values):
                ax1.plot(dates, self.portfolio_values, linewidth=2, color='blue')
            else:
                ax1.plot(self.portfolio_values, linewidth=2, color='blue')
            
            ax1.axhline(y=self.initial_capital, color='red', linestyle='--', alpha=0.5, label='初始资金')
            ax1.set_title('资产曲线 (Equity Curve)')
            ax1.set_xlabel('时间')
            ax1.set_ylabel('资产价值 (¥)')
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            
            # 2. 累计收益曲线
            ax2 = plt.subplot(3, 2, 2)
            cumulative_returns = (1 + self.returns_series).cumprod() - 1
            
            if dates is not None and len(dates) == len(cumulative_returns):
                ax2.plot(dates, cumulative_returns * 100, linewidth=2, color='green')
            else:
                ax2.plot(cumulative_returns * 100, linewidth=2, color='green')
            
            ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            ax2.set_title('累计收益 (Cumulative Return)')
            ax2.set_xlabel('时间')
            ax2.set_ylabel('累计收益 (%)')
            ax2.grid(True, alpha=0.3)
            
            # 3. 回撤图
            ax3 = plt.subplot(3, 2, 3)
            portfolio_series = pd.Series(self.portfolio_values)
            rolling_max = portfolio_series.expanding().max()
            drawdowns = (portfolio_series - rolling_max) / rolling_max * 100
            
            if dates is not None and len(dates) == len(drawdowns):
                ax3.fill_between(dates, drawdowns, 0, color='red', alpha=0.3)
                ax3.plot(dates, drawdowns, color='red', linewidth=1)
            else:
                ax3.fill_between(range(len(drawdowns)), drawdowns, 0, color='red', alpha=0.3)
                ax3.plot(drawdowns, color='red', linewidth=1)
            
            ax3.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            ax3.set_title('回撤 (Drawdown)')
            ax3.set_xlabel('时间')
            ax3.set_ylabel('回撤 (%)')
            ax3.grid(True, alpha=0.3)
            
            # 4. 日收益分布直方图
            ax4 = plt.subplot(3, 2, 4)
            ax4.hist(self.returns_series * 100, bins=50, alpha=0.7, color='blue', edgecolor='black')
            ax4.axvline(x=0, color='red', linestyle='--', alpha=0.5)
            ax4.set_title('日收益分布 (Daily Return Distribution)')
            ax4.set_xlabel('日收益 (%)')
            ax4.set_ylabel('频率')
            ax4.grid(True, alpha=0.3)
            
            # 5. 月度收益热力图（如果有日期）
            if dates is not None and len(dates) == len(self.returns_series):
                try:
                    # 创建日期索引的收益序列
                    returns_df = pd.DataFrame({
                        'date': dates,
                        'return': self.returns_series
                    })
                    returns_df['date'] = pd.to_datetime(returns_df['date'])
                    returns_df.set_index('date', inplace=True)
                    
                    # 计算月度收益
                    monthly_returns = returns_df['return'].resample('M').apply(
                        lambda x: (1 + x).prod() - 1
                    ) * 100
                    
                    # 创建月度收益数据框
                    monthly_returns_df = monthly_returns.reset_index()
                    monthly_returns_df['year'] = monthly_returns_df['date'].dt.year
                    monthly_returns_df['month'] = monthly_returns_df['date'].dt.month
                    
                    # 创建数据透视表
                    pivot_table = monthly_returns_df.pivot_table(
                        values='return', index='year', columns='month', aggfunc='sum'
                    )
                    
                    ax5 = plt.subplot(3, 2, 5)
                    im = ax5.imshow(pivot_table.values, cmap='RdYlGn', aspect='auto')
                    ax5.set_title('月度收益热力图 (Monthly Returns Heatmap)')
                    ax5.set_xlabel('月份')
                    ax5.set_ylabel('年份')
                    
                    # 设置刻度
                    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                    ax5.set_xticks(range(len(month_names)))
                    ax5.set_xticklabels(month_names[:pivot_table.shape[1]])
                    
                    # 添加颜色条
                    plt.colorbar(im, ax=ax5, label='收益 (%)')
                    
                    # 在格子中显示数值
                    for i in range(pivot_table.shape[0]):
                        for j in range(pivot_table.shape[1]):
                            value = pivot_table.iloc[i, j]
                            if not np.isnan(value):
                                color = 'black' if abs(value) < 5 else 'white'
                                ax5.text(j, i, f'{value:.1f}', ha='center', va='center', 
                                       color=color, fontsize=8)
                    
                except Exception as e:
                    ax5 = plt.subplot(3, 2, 5)
                    ax5.text(0.5, 0.5, '月度数据不足\n无法生成热力图', 
                           ha='center', va='center', transform=ax5.transAxes)
                    ax5.set_title('月度收益热力图')
                    ax5.axis('off')
            else:
                ax5 = plt.subplot(3, 2, 5)
                ax5.text(0.5, 0.5, '需要日期数据\n生成月度热力图', 
                       ha='center', va='center', transform=ax5.transAxes)
                ax5.set_title('月度收益热力图')
                ax5.axis('off')
            
            # 6. 滚动收益（12个月滚动）
            ax6 = plt.subplot(3, 2, 6)
            if len(self.returns_series) >= 252:  # 至少一年数据
                rolling_returns = (1 + self.returns_series).rolling(window=252).apply(
                    lambda x: x.prod() - 1
                ) * 100
                
                if dates is not None and len(dates) == len(rolling_returns):
                    ax6.plot(dates[251:], rolling_returns[251:], linewidth=2, color='purple')
                else:
                    ax6.plot(rolling_returns[251:], linewidth=2, color='purple')
                
                ax6.axhline(y=0, color='black', linestyle='-', alpha=0.3)
                ax6.set_title('12个月滚动年化收益 (12-Month Rolling Return)')
                ax6.set_xlabel('时间')
                ax6.set_ylabel('滚动年化收益 (%)')
            else:
                ax6.text(0.5, 0.5, '数据不足\n无法计算滚动收益\n(需要至少1年数据)', 
                       ha='center', va='center', transform=ax6.transAxes)
                ax6.set_title('12个月滚动年化收益')
                ax6.set_xlabel('时间')
                ax6.set_ylabel('滚动年化收益 (%)')
            
            ax6.grid(True, alpha=0.3)
            
            plt.tight_layout()
            plt.show()
            
        except ImportError:
            print("⚠️ Matplotlib未安装，无法绘制图表")
        except Exception as e:
            print(f"⚠️ 绘图失败: {e}")


if __name__ == "__main__":
    # 测试结果模块
    print("🧪 测试结果模块...")
    
    # 创建示例数据
    np.random.seed(42)
    n_days = 500
    
    # 生成随机收益序列
    daily_returns = np.random.normal(0.0005, 0.02, n_days)
    
    # 生成资产曲线
    initial_capital = 100000
    portfolio_values = initial_capital * np.exp(np.cumsum(daily_returns))
    
    # 生成示例交易记录
    trades = []
    for i in range(0, n_days, 50):
        if i + 1 < n_days:
            trades.append({
                'date': f'Day {i}',
                'type': 'buy',
                'price': portfolio_values[i] / 1000,
                'shares': 100,
                'fee': 10
            })
            trades.append({
                'date': f'Day {i+30}',
                'type': 'sell',
                'price': portfolio_values[i+30] / 1000,
                'shares': 100,
                'fee': 10
            })
    
    # 计算性能指标
    metrics_calc = PerformanceMetrics(portfolio_values, daily_returns, trades, initial_capital)
    metrics = metrics_calc.calculate_all_metrics()
    
    # 打印报告
    metrics_calc.print_summary_report(metrics)
    
    # 绘制图表
    dates = pd.date_range(start='2023-01-01', periods=n_days, freq='B')
    metrics_calc.plot_performance_charts(dates)
    
    print("\n✅ 结果模块测试完成！")
