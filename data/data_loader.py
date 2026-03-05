"""
数据模块 - 负责读取历史行情数据
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings
from typing import Optional, Tuple
from config import DATA_PATH, DATE_COL, PRICE_COLS, VOLUME_COL


class DataLoader:
    """数据加载器"""
    
    def __init__(self, data_path: str = None):
        """
        初始化数据加载器
        
        Parameters:
        -----------
        data_path : str, optional
            数据文件路径，默认为config.py中的DATA_PATH
        """
        self.data_path = data_path or DATA_PATH
        self.data = None
        
    def load_data(self) -> pd.DataFrame:
        """
        加载股票数据
        
        Returns:
        --------
        pd.DataFrame
            加载的股票数据
        """
        # 检查文件是否存在
        if not Path(self.data_path).exists():
            raise FileNotFoundError(f"数据文件不存在: {self.data_path}")
        
        # 读取CSV文件
        try:
            self.data = pd.read_csv(
                self.data_path,
                parse_dates=[DATE_COL],
                date_parser=lambda x: pd.to_datetime(x, format='%Y-%m-%d')
            )
        except Exception as e:
            raise ValueError(f"读取数据文件失败: {e}")
        
        print(f"✅ 数据加载成功: {len(self.data)} 条记录")
        return self.data
    
    def validate_data(self, data: pd.DataFrame) -> Tuple[bool, str]:
        """
        验证数据完整性
        
        Parameters:
        -----------
        data : pd.DataFrame
            要验证的数据
            
        Returns:
        --------
        Tuple[bool, str]
            (是否有效, 验证消息)
        """
        if data is None or len(data) == 0:
            return False, "数据为空"
        
        # 1. 检查必需列
        required_cols = [DATE_COL] + PRICE_COLS + [VOLUME_COL]
        missing_cols = [col for col in required_cols if col not in data.columns]
        if missing_cols:
            return False, f"缺少必需列: {missing_cols}"
        
        # 2. 检查缺失值
        missing_values = data[required_cols].isnull().sum().sum()
        if missing_values > 0:
            warnings.warn(f"⚠️ 数据中存在 {missing_values} 个缺失值")
        
        # 3. 检查重复日期
        duplicate_dates = data[DATE_COL].duplicated().sum()
        if duplicate_dates > 0:
            warnings.warn(f"⚠️ 数据中存在 {duplicate_dates} 个重复日期")
        
        # 4. 检查价格合理性
        price_issues = []
        for price_col in PRICE_COLS:
            if (data[price_col] <= 0).any():
                price_issues.append(f"{price_col} 有非正数值")
        
        if price_issues:
            warnings.warn(f"⚠️ 价格数据问题: {', '.join(price_issues)}")
        
        return True, "数据验证通过"
    
    def sort_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        按时间排序数据（从旧到新）
        
        Parameters:
        -----------
        data : pd.DataFrame
            要排序的数据
            
        Returns:
        --------
        pd.DataFrame
            排序后的数据
        """
        if DATE_COL not in data.columns:
            raise ValueError(f"数据中缺少日期列: {DATE_COL}")
        
        sorted_data = data.sort_values(by=DATE_COL, ascending=True).reset_index(drop=True)
        print(f"✅ 数据已按时间排序: {sorted_data[DATE_COL].iloc[0]} 到 {sorted_data[DATE_COL].iloc[-1]}")
        return sorted_data
    
    def get_data_summary(self, data: pd.DataFrame) -> dict:
        """
        获取数据摘要信息
        
        Parameters:
        -----------
        data : pd.DataFrame
            
        Returns:
        --------
        dict
            数据摘要信息
        """
        summary = {
            "total_records": len(data),
            "date_range": f"{data[DATE_COL].min()} 到 {data[DATE_COL].max()}",
            "total_days": (data[DATE_COL].max() - data[DATE_COL].min()).days,
            "columns": list(data.columns),
            "missing_values": data.isnull().sum().to_dict(),
            "price_stats": {
                col: {
                    "min": data[col].min(),
                    "max": data[col].max(),
                    "mean": data[col].mean(),
                    "std": data[col].std()
                }
                for col in PRICE_COLS
            }
        }
        return summary
    
    def prepare_data(self) -> pd.DataFrame:
        """
        完整的数据准备流程
        
        Returns:
        --------
        pd.DataFrame
            准备好的数据
        """
        # 1. 加载数据
        data = self.load_data()
        
        # 2. 验证数据
        is_valid, message = self.validate_data(data)
        if not is_valid:
            raise ValueError(f"数据验证失败: {message}")
        print(f"✅ {message}")
        
        # 3. 排序数据
        data = self.sort_data(data)
        
        # 4. 输出摘要
        summary = self.get_data_summary(data)
        print(f"📊 数据摘要:")
        print(f"   - 总记录数: {summary['total_records']}")
        print(f"   - 日期范围: {summary['date_range']}")
        print(f"   - 总天数: {summary['total_days']} 天")
        
        return data


# 创建示例数据
def create_sample_data(output_path: str = "data/stock.csv"):
    """
    创建示例股票数据（如果真实数据不存在）
    
    Parameters:
    -----------
    output_path : str
        输出文件路径
    """
    # 生成日期范围（2023年全年）
    dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='B')  # 工作日
    
    # 生成随机价格数据（基于随机游走）
    np.random.seed(42)
    n = len(dates)
    
    # 起始价格
    start_price = 100
    
    # 生成收益率（正态分布）
    returns = np.random.normal(0.0005, 0.02, n)
    
    # 计算价格
    prices = start_price * np.exp(np.cumsum(returns))
    
    # 生成OHLCV数据
    data = pd.DataFrame({
        'date': dates,
        'open': prices * (1 + np.random.normal(0, 0.01, n)),
        'high': prices * (1 + np.abs(np.random.normal(0.02, 0.01, n))),
        'low': prices * (1 - np.abs(np.random.normal(0.02, 0.01, n))),
        'close': prices,
        'volume': np.random.randint(1000000, 5000000, n)
    })
    
    # 确保 high >= low, high >= open, high >= close, low <= open, low <= close
    data['high'] = data[['open', 'high', 'close']].max(axis=1)
    data['low'] = data[['open', 'low', 'close']].min(axis=1)
    
    # 保存数据
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(output_path, index=False)
    print(f"✅ 示例数据已创建: {output_path} ({len(data)} 条记录)")
    
    return data


if __name__ == "__main__":
    # 测试数据模块
    loader = DataLoader()
    
    # 如果数据文件不存在，创建示例数据
    if not Path(DATA_PATH).exists():
        print("📝 数据文件不存在，创建示例数据...")
        create_sample_data(DATA_PATH)
    
    # 加载并准备数据
    data = loader.prepare_data()
    print("\n📋 数据前5行:")
    print(data.head())
    print("\n📋 数据后5行:")
    print(data.tail())