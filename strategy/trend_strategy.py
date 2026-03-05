"""
策略模块 - 负责生成交易信号
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Tuple
from enum import Enum
from config import MA_SHORT, MA_LONG


class Signal(Enum):
    """交易信号枚举"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    EXIT = "exit"  # 平仓信号


class TrendStrategy:
    """趋势跟踪策略（均线交叉策略）"""
    
    def __init__(self, data: pd.DataFrame):
        """
        初始化趋势策略
        
        Parameters:
        -----------
        data : pd.DataFrame
            包含指标的数据
        """
        self.data = data.copy()
        self.signals = pd.Series(index=data.index, dtype=object)
        self.positions = pd.Series(index=data.index, dtype=int)  # 持仓方向：1=多仓，-1=空仓，0=空仓
        self.current_position = 0  # 当前持仓
        
        # 策略参数
        self.ma_short_col = f'MA{MA_SHORT}'
        self.ma_long_col = f'MA{MA_LONG}'
        
    def generate_signals(self) -> pd.DataFrame:
        """
        生成交易信号
        
        Returns:
        --------
        pd.DataFrame
            包含信号的数据
        """
        print("📡 开始生成交易信号...")
        
        # 确保指标存在
        if self.ma_short_col not in self.data.columns or self.ma_long_col not in self.data.columns:
            raise ValueError(f"数据中缺少必要的均线指标: {self.ma_short_col}, {self.ma_long_col}")
        
        # 初始化信号
        self.signals = pd.Series(Signal.HOLD.value, index=self.data.index)
        self.positions = pd.Series(0, index=self.data.index)
        
        # 生成信号
        for i in range(1, len(self.data)):
            # 跳过NaN值
            if pd.isna(self.data[self.ma_short_col].iloc[i]) or pd.isna(self.data[self.ma_long_col].iloc[i]):
                continue
            
            # 获取当前和前一日数据
            ma_short_today = self.data[self.ma_short_col].iloc[i]
            ma_long_today = self.data[self.ma_long_col].iloc[i]
            ma_short_yesterday = self.data[self.ma_short_col].iloc[i-1]
            ma_long_yesterday = self.data[self.ma_long_col].iloc[i-1]
            
            # 检查金叉（买入信号）
            golden_cross = (ma_short_yesterday <= ma_long_yesterday) and (ma_short_today > ma_long_today)
            
            # 检查死叉（卖出信号）
            death_cross = (ma_short_yesterday >= ma_long_yesterday) and (ma_short_today < ma_long_today)
            
            # 生成信号
            if golden_cross:
                self.signals.iloc[i] = Signal.BUY.value
                self.current_position = 1  # 建立多仓
            elif death_cross:
                self.signals.iloc[i] = Signal.SELL.value
                self.current_position = 0  # 平仓（清仓）
            else:
                self.signals.iloc[i] = Signal.HOLD.value
            
            # 记录持仓
            self.positions.iloc[i] = self.current_position
        
        # 将信号添加到数据中
        self.data['signal'] = self.signals
        self.data['position'] = self.positions
        
        # 统计信号
        self._analyze_signals()
        
        return self.data
    
    def _analyze_signals(self):
        """分析信号统计信息"""
        signal_counts = self.signals.value_counts()
        
        print("📊 信号生成统计:")
        print(f"   - 总信号数: {len(self.signals)}")
        for signal, count in signal_counts.items():
            percentage = count / len(self.signals) * 100
            print(f"   - {signal}: {count} 次 ({percentage:.1f}%)")
        
        # 计算交易次数（买入+卖出）
        buy_signals = (self.signals == Signal.BUY.value).sum()
        sell_signals = (self.signals == Signal.SELL.value).sum()
        total_trades = min(buy_signals, sell_signals)  # 配对交易
        
        print(f"   - 买入信号: {buy_signals} 次")
        print(f"   - 卖出信号: {sell_signals} 次")
        print(f"   - 潜在交易次数: {total_trades} 次")
    
    def get_signal_details(self) -> Dict:
        """
        获取信号详细信息
        
        Returns:
        --------
        dict
            信号详情
        """
        # 获取所有买入信号
        buy_signals = self.data[self.data['signal'] == Signal.BUY.value]
        sell_signals = self.data[self.data['signal'] == Signal.SELL.value]
        
        details = {
            "buy_signals": {
                "count": len(buy_signals),
                "dates": buy_signals['date'].tolist() if 'date' in self.data.columns else [],
                "prices": buy_signals['close'].tolist() if 'close' in self.data.columns else []
            },
            "sell_signals": {
                "count": len(sell_signals),
                "dates": sell_signals['date'].tolist() if 'date' in self.data.columns else [],
                "prices": sell_signals['close'].tolist() if 'close' in self.data.columns else []
            },
            "hold_periods": self._calculate_hold_periods()
        }
        
        return details
    
    def _calculate_hold_periods(self) -> List[Dict]:
        """
        计算持仓周期
        
        Returns:
        --------
        List[Dict]
            持仓周期列表
        """
        hold_periods = []
        in_position = False
        start_idx = None
        start_date = None
        start_price = None
        
        for i in range(len(self.data)):
            signal = self.signals.iloc[i]
            position = self.positions.iloc[i]
            
            if signal == Signal.BUY.value and not in_position:
                # 开始持仓
                in_position = True
                start_idx = i
                start_date = self.data['date'].iloc[i] if 'date' in self.data.columns else i
                start_price = self.data['close'].iloc[i] if 'close' in self.data.columns else None
            
            elif signal == Signal.SELL.value and in_position:
                # 结束持仓
                in_position = False
                end_date = self.data['date'].iloc[i] if 'date' in self.data.columns else i
                end_price = self.data['close'].iloc[i] if 'close' in self.data.columns else None
                
                # 计算持仓信息
                hold_days = i - start_idx
                if start_price and end_price:
                    return_pct = (end_price - start_price) / start_price * 100
                else:
                    return_pct = None
                
                hold_periods.append({
                    "start": start_date,
                    "end": end_date,
                    "hold_days": hold_days,
                    "start_price": start_price,
                    "end_price": end_price,
                    "return_pct": return_pct
                })
        
        # 如果最后还有持仓
        if in_position and start_idx is not None:
            end_idx = len(self.data) - 1
            end_date = self.data['date'].iloc[end_idx] if 'date' in self.data.columns else end_idx
            end_price = self.data['close'].iloc[end_idx] if 'close' in self.data.columns else None
            
            hold_days = end_idx - start_idx
            if start_price and end_price:
                return_pct = (end_price - start_price) / start_price * 100
            else:
                return_pct = None
            
            hold_periods.append({
                "start": start_date,
                "end": end_date,
                "hold_days": hold_days,
                "start_price": start_price,
                "end_price": end_price,
                "return_pct": return_pct,
                "is_open": True  # 标记为未平仓
            })
        
        return hold_periods
    
    def plot_signals(self, n_days: int = 100):
        """
        绘制信号图
        
        Parameters:
        -----------
        n_days : int
            显示的天数
        """
        try:
            import matplotlib.pyplot as plt
            
            # 获取最后n_days的数据
            plot_data = self.data.tail(n_days).copy()
            
            fig, axes = plt.subplots(2, 1, figsize=(14, 10))
            
            # 价格、均线和信号图
            ax1 = axes[0]
            
            # 绘制价格
            ax1.plot(plot_data.index, plot_data['close'], label='Close', linewidth=2, color='black', alpha=0.7)
            
            # 绘制均线
            if self.ma_short_col in plot_data.columns:
                ax1.plot(plot_data.index, plot_data[self.ma_short_col], label=f'MA{MA_SHORT}', alpha=0.7, color='blue')
            
            if self.ma_long_col in plot_data.columns:
                ax1.plot(plot_data.index, plot_data[self.ma_long_col], label=f'MA{MA_LONG}', alpha=0.7, color='red')
            
            # 标记买入信号
            buy_signals = plot_data[plot_data['signal'] == Signal.BUY.value]
            if not buy_signals.empty:
                ax1.scatter(buy_signals.index, buy_signals['close'], 
                          color='green', s=150, marker='^', label='Buy Signal', zorder=5)
            
            # 标记卖出信号
            sell_signals = plot_data[plot_data['signal'] == Signal.SELL.value]
            if not sell_signals.empty:
                ax1.scatter(sell_signals.index, sell_signals['close'], 
                          color='red', s=150, marker='v', label='Sell Signal', zorder=5)
            
            ax1.set_title(f'Trend Strategy Signals (Last {n_days} Days)')
            ax1.set_xlabel('Index')
            ax1.set_ylabel('Price')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # 持仓图
            ax2 = axes[1]
            
            # 绘制持仓
            ax2.fill_between(plot_data.index, 0, plot_data['position'], 
                           alpha=0.3, color='green', label='Position (1=Long, 0=Flat)')
            ax2.plot(plot_data.index, plot_data['position'], linewidth=2, color='green')
            
            ax2.set_title('Position Over Time')
            ax2.set_xlabel('Index')
            ax2.set_ylabel('Position')
            ax2.set_ylim(-0.5, 1.5)
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            plt.show()
            
        except ImportError:
            print("⚠️ Matplotlib未安装，无法绘制图表")
        except Exception as e:
            print(f"⚠️ 信号绘图失败: {e}")


class SimpleStrategy:
    """简化版策略（仅生成信号，不管理持仓）"""
    
    @staticmethod
    def generate_simple_signals(data: pd.DataFrame) -> pd.DataFrame:
        """
        生成简化信号（仅信号，无持仓管理）
        
        Parameters:
        -----------
        data : pd.DataFrame
            包含指标的数据
            
        Returns:
        --------
        pd.DataFrame
            包含信号的数据
        """
        data = data.copy()
        
        # 确保指标存在
        ma_short_col = f'MA{MA_SHORT}'
        ma_long_col = f'MA{MA_LONG}'
        
        if ma_short_col not in data.columns or ma_long_col not in data.columns:
            raise ValueError(f"数据中缺少必要的均线指标")
        
        # 初始化信号列
        data['signal'] = Signal.HOLD.value
        
        # 生成信号
        for i in range(1, len(data)):
            if pd.isna(data[ma_short_col].iloc[i]) or pd.isna(data[ma_long_col].iloc[i]):
                continue
            
            ma_short_today = data[ma_short_col].iloc[i]
            ma_long_today = data[ma_long_col].iloc[i]
            ma_short_yesterday = data[ma_short_col].iloc[i-1]
            ma_long_yesterday = data[ma_long_col].iloc[i-1]
            
            # 金叉：买入
            if (ma_short_yesterday <= ma_long_yesterday) and (ma_short_today > ma_long_today):
                data.loc[data.index[i], 'signal'] = Signal.BUY.value
            
            # 死叉：卖出
            elif (ma_short_yesterday >= ma_long_yesterday) and (ma_short_today < ma_long_today):
                data.loc[data.index[i], 'signal'] = Signal.SELL.value
        
        return data


if __name__ == "__main__":
    # 测试策略模块
    print("🧪 测试策略模块...")
    
    # 创建示例数据
    from data.data_loader import create_sample_data, DataLoader
    from indicators.technical_indicators import TechnicalIndicators
    
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
    
    # 输出信号详情
    details = strategy.get_signal_details()
    print("\n📊 信号详情:")
    print(f"  买入信号: {details['buy_signals']['count']} 次")
    print(f"  卖出信号: {details['sell_signals']['count']} 次")
    
    # 显示持仓周期
    hold_periods = details['hold_periods']
    print(f"\n📅 持仓周期 ({len(hold_periods)} 个):")
    for i, period in enumerate(hold_periods[:3]):  # 只显示前3个
        print(f"  周期 {i+1}: {period.get('start')} 到 {period.get('end')} "
              f"({period.get('hold_days')}天, 收益: {period.get('return_pct', 'N/A'):.1f}%)")
    
    if len(hold_periods) > 3:
        print(f"  ... 还有 {len(hold_periods) - 3} 个持仓周期")
    
    # 显示前20行数据
    print("\n📋 数据前20行（含信号）:")
    print(data_with_signals[['date', 'close', f'MA{MA_SHORT}', f'MA{MA_LONG}', 'signal', 'position']].head(20))
    
    # 尝试绘图
    strategy.plot_signals(150)