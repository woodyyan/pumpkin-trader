#!/usr/bin/env python3
"""
南瓜交易系统 - 主程序
系统分为5个模块：数据、指标、策略、回测、结果
"""

import sys
import os
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from config import DATA_PATH, INITIAL_CAPITAL, TRANSACTION_FEE, MA_SHORT, MA_LONG
from data.data_loader import DataLoader, create_sample_data
from indicators.technical_indicators import TechnicalIndicators
from strategy.trend_strategy import TrendStrategy
from engine.backtest_engine import BacktestEngine
from result.metrics import PerformanceMetrics


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='南瓜交易系统 (Pumpkin Trader)')
    
    parser.add_argument('--data', type=str, default=DATA_PATH,
                       help=f'股票数据文件路径 (默认: {DATA_PATH})')
    parser.add_argument('--capital', type=float, default=INITIAL_CAPITAL,
                       help=f'初始资金 (默认: {INITIAL_CAPITAL})')
    parser.add_argument('--fee', type=float, default=TRANSACTION_FEE,
                       help=f'交易手续费率 (默认: {TRANSACTION_FEE})')
    parser.add_argument('--ma_short', type=int, default=MA_SHORT,
                       help=f'短期均线周期 (默认: {MA_SHORT})')
    parser.add_argument('--ma_long', type=int, default=MA_LONG,
                       help=f'长期均线周期 (默认: {MA_LONG})')
    parser.add_argument('--create_sample', action='store_true',
                       help='创建示例数据（如果数据文件不存在）')
    parser.add_argument('--plot', action='store_true',
                       help='显示图表')
    parser.add_argument('--verbose', action='store_true',
                       help='显示详细输出')
    parser.add_argument('--output', type=str, default='output/results.csv',
                       help='输出结果文件路径 (默认: output/results.csv)')
    
    return parser.parse_args()


def main():
    """主函数"""
    print("="*70)
    print("🚀 南瓜交易系统 v1.0")
    print("="*70)
    
    # 解析参数
    args = parse_arguments()
    
    # 创建输出目录
    output_dir = Path(args.output).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 步骤1: 数据模块
    print("\n📊 步骤1: 数据准备")
    print("-"*40)
    
    data_loader = DataLoader(args.data)
    
    # 检查数据文件是否存在
    if not Path(args.data).exists():
        if args.create_sample:
            print("📝 数据文件不存在，创建示例数据...")
            create_sample_data(args.data)
        else:
            print(f"❌ 数据文件不存在: {args.data}")
            print("   请使用 --create_sample 参数创建示例数据")
            sys.exit(1)
    
    # 加载和准备数据
    try:
        data = data_loader.prepare_data()
        print(f"✅ 数据加载成功: {len(data)} 条记录")
    except Exception as e:
        print(f"❌ 数据加载失败: {e}")
        sys.exit(1)
    
    # 步骤2: 指标模块
    print("\n📈 步骤2: 计算技术指标")
    print("-"*40)
    print(f"   短期均线 (MA{args.ma_short})")
    print(f"   长期均线 (MA{args.ma_long})")
    
    try:
        indicator_calc = TechnicalIndicators(data)
        data_with_indicators = indicator_calc.calculate_all_indicators()
        print("✅ 指标计算完成")
    except Exception as e:
        print(f"❌ 指标计算失败: {e}")
        sys.exit(1)
    
    # 步骤3: 策略模块
    print("\n📡 步骤3: 生成交易信号")
    print("-"*40)
    print("   策略: 趋势跟踪策略 (均线交叉)")
    print(f"   规则: MA{args.ma_short} 上穿 MA{args.ma_long} → 买入")
    print(f"         MA{args.ma_short} 下穿 MA{args.ma_long} → 卖出")
    
    try:
        strategy = TrendStrategy(data_with_indicators)
        data_with_signals = strategy.generate_signals()
        print("✅ 信号生成完成")
    except Exception as e:
        print(f"❌ 信号生成失败: {e}")
        sys.exit(1)
    
    # 步骤4: 回测模块
    print("\n💰 步骤4: 运行回测")
    print("-"*40)
    print(f"   初始资金: ¥{args.capital:,.2f}")
    print(f"   手续费率: {args.fee*100:.2f}%")
    
    try:
        engine = BacktestEngine(data_with_signals, args.capital, args.fee)
        results = engine.run_backtest()
        print("✅ 回测完成")
    except Exception as e:
        print(f"❌ 回测失败: {e}")
        sys.exit(1)
    
    # 步骤5: 结果模块
    print("\n📊 步骤5: 分析结果")
    print("-"*40)
    
    try:
        # 获取回测数据
        portfolio_values = results['portfolio_value'].tolist()
        daily_returns = results['daily_return'].tolist()
        trades = engine.get_trade_log().to_dict('records')
        
        # 计算性能指标
        metrics_calc = PerformanceMetrics(
            portfolio_values, daily_returns, trades, args.capital
        )
        metrics = metrics_calc.calculate_all_metrics()
        
        # 打印报告
        metrics_calc.print_summary_report(metrics)
        
        # 保存结果
        results.to_csv(args.output, index=False)
        print(f"✅ 结果已保存到: {args.output}")
        
        # 保存性能指标
        metrics_file = str(output_dir / 'performance_metrics.txt')
        with open(metrics_file, 'w', encoding='utf-8') as f:
            f.write("回测性能指标\n")
            f.write("="*50 + "\n")
            for key, value in metrics.items():
                if 'pct' in key:
                    f.write(f"{key}: {value:.2f}%\n")
                elif isinstance(value, float):
                    f.write(f"{key}: {value:.4f}\n")
                else:
                    f.write(f"{key}: {value}\n")
        
        print(f"✅ 性能指标已保存到: {metrics_file}")
        
    except Exception as e:
        print(f"❌ 结果分析失败: {e}")
        sys.exit(1)
    
    # 显示图表
    if args.plot:
        print("\n🎨 步骤6: 生成图表")
        print("-"*40)
        
        try:
            # 绘制资产曲线
            engine.plot_equity_curve()
            
            # 绘制性能图表
            if 'date' in results.columns:
                dates = results['date'].tolist()
            else:
                dates = None
            
            metrics_calc.plot_performance_charts(dates)
            
            print("✅ 图表生成完成")
        except Exception as e:
            print(f"⚠️ 图表生成失败: {e}")
    
    # 最终输出
    print("\n" + "="*70)
    print("🎉 回测系统运行完成！")
    print("="*70)
    print("\n📁 输出文件:")
    print(f"   1. 完整回测结果: {args.output}")
    print(f"   2. 性能指标: {metrics_file}")
    
    if args.plot:
        print("   3. 图表: 已显示在屏幕上")
    
    print("\n🔍 快速查看结果:")
    print(f"   总收益: {metrics.get('total_return_pct', 0):.2f}%")
    print(f"   年化收益: {metrics.get('annual_return_pct', 0):.2f}%")
    print(f"   最大回撤: {metrics.get('max_drawdown_pct', 0):.2f}%")
    print(f"   胜率: {metrics.get('win_rate_pct', 0):.1f}%")
    print(f"   交易次数: {metrics.get('total_trades', 0)} 次")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)