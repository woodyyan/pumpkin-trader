# 📈 单股票回测系统 (Single Stock Backtest System)

一个模块化的Python单股票回测系统，实现完整的回测流程。

## 🎯 功能特性

### ✅ 5个核心模块
1. **数据模块** - 读取历史行情数据，验证数据完整性
2. **指标模块** - 计算技术指标（MA20, MA60, ATR）
3. **策略模块** - 生成交易信号（趋势跟踪策略）
4. **回测引擎** - 模拟交易，考虑手续费和滑点
5. **结果模块** - 计算性能指标，生成报告和图表

### ✅ 完整功能清单
- [x] CSV数据读取和验证
- [x] 时间排序（从旧到新）
- [x] 移动平均线计算（MA20, MA60）
- [x] 平均真实波幅计算（ATR）
- [x] 均线交叉策略（金叉买入，死叉卖出）
- [x] 全仓交易，次日开盘价执行
- [x] 手续费计算（0.1%）
- [x] 资金变化记录
- [x] 性能指标计算（总收益、年化收益、最大回撤等）
- [x] 交易统计（胜率、交易次数等）
- [x] 资产曲线图表
- [x] 配置文件支持参数调整

## 🚀 快速开始

### 方式一：Web 界面化操作 (推荐)
本项目提供了一个基于 Streamlit 并且内置 Plotly 交互式图表的精美 Web 界面。你可以直接在网页中上传数据、调整策略参数（资金、手续费率、双均线天数）并查看结果。

**1. 安装依赖**
```bash
pip install -r requirements.txt
```

**2. 启动 Web 服务**
```bash
streamlit run app.py
```
启动后，浏览器会自动打开 `http://localhost:8501`。在左侧面板配置数据源（支持一键生成示例数据或上传你的 CSV 文件），然后点击「运行回测」即可开始分析。

---

### 方式二：命令行 CLI 操作
如果你习惯在终端中批量运行回测，本项目同样支持强大的命令行操作。

**运行回测**
```bash
# 基本用法（使用示例数据）
python main.py --create_sample

# 使用自定义数据
python main.py --data your_stock.csv

# 自定义参数
python main.py --capital 50000 --fee 0.002 --ma_short 10 --ma_long 30

# 显示静态图表
python main.py --create_sample --plot

# 详细输出
python main.py --create_sample --verbose
```

### 命令行参数
```
--data          股票数据文件路径 (默认: data/stock.csv)
--capital       初始资金 (默认: 100000)
--fee           交易手续费率 (默认: 0.001)
--ma_short      短期均线周期 (默认: 20)
--ma_long       长期均线周期 (默认: 60)
--create_sample 创建示例数据（如果数据文件不存在）
--plot          显示图表
--verbose       显示详细输出
--output        输出结果文件路径 (默认: output/results.csv)
```

## 📁 项目结构

```
stock_backtest_system/
├── config.py                    # 配置文件
├── main.py                      # 主程序
├── README.md                    # 项目文档
├── data/
│   ├── __init__.py
│   ├── data_loader.py          # 数据模块
│   └── stock.csv               # 示例数据（自动生成）
├── indicators/
│   ├── __init__.py
│   └── technical_indicators.py # 指标模块
├── strategy/
│   ├── __init__.py
│   └── trend_strategy.py       # 策略模块
├── engine/
│   ├── __init__.py
│   └── backtest_engine.py      # 回测引擎
├── result/
│   ├── __init__.py
│   └── metrics.py              # 结果模块
├── utils/                       # 工具函数
└── output/                      # 输出目录（自动生成）
```

## 📊 数据格式

### 输入数据要求
CSV文件必须包含以下列：
- `date` - 日期 (YYYY-MM-DD格式)
- `open` - 开盘价
- `high` - 最高价  
- `low` - 最低价
- `close` - 收盘价
- `volume` - 成交量

### 示例数据
```csv
date,open,high,low,close,volume
2023-01-01,100,102,98,101,2000000
2023-01-02,101,103,100,102,2100000
2023-01-03,102,104,101,103,2200000
```

## 🎯 策略说明

### 趋势跟踪策略（均线交叉）
- **买入信号**: MA20 上穿 MA60（金叉）
- **卖出信号**: MA20 下穿 MA60（死叉）
- **持仓规则**: 全仓买入，清仓卖出
- **执行价格**: 次日开盘价
- **手续费**: 0.1% 每次交易

### 可配置参数
在 `config.py` 中可以调整：
- 初始资金
- 交易手续费率
- 均线周期
- 数据文件路径
- 输出配置

## 📈 输出结果

### 控制台输出
```
📊 回测结果摘要
============================================================
初始资金:      ¥100,000.00
最终资产:      ¥165,432.10
总收益:        +65.43%
年化收益:      +12.34%
最大回撤:      18.25%
总交易次数:    34 次
胜率:          52.94%
```

### 输出文件
1. **完整回测结果** - `output/results.csv`
   - 包含每日价格、信号、持仓、资产等所有数据
2. **性能指标** - `output/performance_metrics.txt`
   - 所有计算出的性能指标

### 图表输出
- 资产曲线图
- 累计收益图
- 回撤图
- 日收益分布直方图
- 月度收益热力图
- 滚动收益图

## 🔧 开发指南

### 添加新指标
1. 在 `indicators/technical_indicators.py` 中添加新指标计算方法
2. 在 `config.py` 中添加相关参数
3. 更新策略模块以使用新指标

### 添加新策略
1. 在 `strategy/` 目录下创建新策略文件
2. 实现 `generate_signals()` 方法
3. 在主程序中添加策略选择选项

### 扩展回测功能
1. 在 `engine/backtest_engine.py` 中修改交易逻辑
2. 支持更多仓位管理方式
3. 添加更多风险控制功能

## 🧪 测试

### 运行单元测试
```bash
# 测试数据模块
python -m data.data_loader

# 测试指标模块
python -m indicators.technical_indicators

# 测试策略模块
python -m strategy.trend_strategy

# 测试回测引擎
python -m engine.backtest_engine

# 测试结果模块
python -m result.metrics
```

### 完整流程测试
```bash
# 完整回测流程
python main.py --create_sample --plot --verbose
```

## 📝 注意事项

1. **数据质量**: 确保输入数据没有缺失值和重复日期
2. **参数优化**: 回测结果对参数敏感，需谨慎优化
3. **过拟合风险**: 避免在历史数据上过度优化策略
4. **未来函数**: 确保策略只使用历史数据，避免使用未来信息
5. **手续费影响**: 高频交易时手续费影响显著

## 🔄 版本历史

### v1.0 (2026-03-06)
- 初始版本发布
- 5个核心模块实现
- 趋势跟踪策略
- 完整回测流程
- 性能指标计算
- 图表输出

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📧 联系

如有问题或建议，请通过GitHub Issues联系。