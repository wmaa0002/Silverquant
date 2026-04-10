"""
技术指标计算库
"""
import pandas as pd
import numpy as np
from typing import Optional


class TechnicalIndicators:
    """技术指标计算器"""
    
    def __init__(self, df: pd.DataFrame):
        """
        初始化
        
        Args:
            df: 包含OHLCV数据的DataFrame
        """
        self.df = df.copy()
        self.close = df['close']
        self.open = df['open']
        self.high = df['high']
        self.low = df['low']
        self.volume = df['volume']
    
    # ==================== 移动平均线 ====================
    
    def ma(self, period: int = 20) -> pd.Series:
        """简单移动平均线"""
        return self.close.rolling(window=period).mean()
    
    def ema(self, period: int = 20) -> pd.Series:
        """指数移动平均线"""
        return self.close.ewm(span=period, adjust=False).mean()
    
    def wma(self, period: int = 20) -> pd.Series:
        """加权移动平均线"""
        weights = np.arange(1, period + 1)
        return self.close.rolling(window=period).apply(
            lambda x: np.dot(x, weights) / weights.sum(), raw=True
        )
    
    # ==================== MACD ====================
    
    def macd(
        self,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> pd.DataFrame:
        """
        MACD指标
        
        Returns:
            DataFrame包含dif, dea, histogram
        """
        ema_fast = self.ema(fast)
        ema_slow = self.ema(slow)
        
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        histogram = dif - dea
        
        return pd.DataFrame({
            'dif': dif,
            'dea': dea,
            'histogram': histogram
        })
    
    # ==================== KDJ ====================
    
    def kdj(self, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
        """
        KDJ指标
        
        Args:
            n: RSV计算周期
            m1: K平滑系数
            m2: D平滑系数
        
        Returns:
            DataFrame包含k, d, j
        """
        low_list = self.low.rolling(window=n, min_periods=n).min()
        high_list = self.high.rolling(window=n, min_periods=n).max()
        
        rsv = (self.close - low_list) / (high_list - low_list) * 100
        
        k = pd.Series(index=self.close.index, dtype=float)
        d = pd.Series(index=self.close.index, dtype=float)
        
        k.iloc[:n-1] = 50
        d.iloc[:n-1] = 50
        
        for i in range(n-1, len(self.close)):
            if pd.isna(rsv.iloc[i]):
                k.iloc[i] = k.iloc[i-1]
                d.iloc[i] = d.iloc[i-1]
            else:
                k.iloc[i] = (2/3) * k.iloc[i-1] + (1/3) * rsv.iloc[i]
                d.iloc[i] = (2/3) * d.iloc[i-1] + (1/3) * k.iloc[i]
        
        j = 3 * k - 2 * d
        
        return pd.DataFrame({'k': k, 'd': d, 'j': j})
    
    # ==================== RSI ====================
    
    def rsi(self, period: int = 14) -> pd.Series:
        """
        RSI相对强弱指标
        
        Args:
            period: 计算周期
        """
        delta = self.close.diff()
        
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    # ==================== 布林带 ====================
    
    def bollinger_bands(
        self,
        period: int = 20,
        std_dev: float = 2.0
    ) -> pd.DataFrame:
        """
        布林带
        
        Args:
            period: 计算周期
            std_dev: 标准差倍数
        
        Returns:
            DataFrame包含upper, mid, lower
        """
        mid = self.ma(period)
        std = self.close.rolling(window=period).std()
        
        upper = mid + (std * std_dev)
        lower = mid - (std * std_dev)
        
        return pd.DataFrame({
            'upper': upper,
            'mid': mid,
            'lower': lower
        })
    
    # ==================== 波动率 ====================
    
    def volatility(self, period: int = 20) -> pd.Series:
        """
        历史波动率（收益率标准差）
        
        Args:
            period: 计算周期
        """
        returns = self.close.pct_change()
        return returns.rolling(window=period).std() * np.sqrt(252)  # 年化
    
    def atr(self, period: int = 14) -> pd.Series:
        """
        平均真实波幅（ATR）
        
        Args:
            period: 计算周期
        """
        high_low = self.high - self.low
        high_close = np.abs(self.high - self.close.shift())
        low_close = np.abs(self.low - self.close.shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    # ==================== 成交量指标 ====================
    
    def volume_ma(self, period: int = 20) -> pd.Series:
        """成交量移动平均"""
        return self.volume.rolling(window=period).mean()
    
    def obv(self) -> pd.Series:
        """OBV能量潮"""
        obv = pd.Series(index=self.close.index, dtype=float)
        obv.iloc[0] = self.volume.iloc[0]
        
        for i in range(1, len(self.close)):
            if self.close.iloc[i] > self.close.iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] + self.volume.iloc[i]
            elif self.close.iloc[i] < self.close.iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] - self.volume.iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]
        
        return obv
    
    # ==================== 趋势指标 ====================
    
    def adx(self, period: int = 14) -> pd.Series:
        """
        ADX平均趋向指数
        
        Args:
            period: 计算周期
        """
        # +DM和-DM
        plus_dm = self.high.diff()
        minus_dm = self.low.diff().abs()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        # 真实波幅
        tr = pd.concat([
            self.high - self.low,
            (self.high - self.close.shift()).abs(),
            (self.low - self.close.shift()).abs()
        ], axis=1).max(axis=1)
        
        # 平滑
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        # DX和ADX
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx = dx.rolling(window=period).mean()
        
        return adx
    
    def ichimoku(
        self,
        tenkan_period: int = 9,
        kijun_period: int = 26,
        senkou_b_period: int = 52
    ) -> pd.DataFrame:
        """
        一目均衡表
        
        Returns:
            DataFrame包含tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b, chikou_span
        """
        # 转换线 (Tenkan-sen)
        tenkan_high = self.high.rolling(window=tenkan_period).max()
        tenkan_low = self.low.rolling(window=tenkan_period).min()
        tenkan_sen = (tenkan_high + tenkan_low) / 2
        
        # 基准线 (Kijun-sen)
        kijun_high = self.high.rolling(window=kijun_period).max()
        kijun_low = self.low.rolling(window=kijun_period).min()
        kijun_sen = (kijun_high + kijun_low) / 2
        
        # 先行上线 (Senkou Span A)
        senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(kijun_period)
        
        # 先行下线 (Senkou Span B)
        senkou_b_high = self.high.rolling(window=senkou_b_period).max()
        senkou_b_low = self.low.rolling(window=senkou_b_period).min()
        senkou_span_b = ((senkou_b_high + senkou_b_low) / 2).shift(kijun_period)
        
        # 延迟线 (Chikou Span)
        chikou_span = self.close.shift(-kijun_period)
        
        return pd.DataFrame({
            'tenkan_sen': tenkan_sen,
            'kijun_sen': kijun_sen,
            'senkou_span_a': senkou_span_a,
            'senkou_span_b': senkou_span_b,
            'chikou_span': chikou_span
        })
    
    # ==================== 计算所有指标 ====================
    
    def calculate_all(self) -> pd.DataFrame:
        """计算所有技术指标"""
        result = self.df.copy()
        
        # 移动平均线
        result['ma_5'] = self.ma(5)
        result['ma_10'] = self.ma(10)
        result['ma_20'] = self.ma(20)
        result['ma_60'] = self.ma(60)
        result['ema_12'] = self.ema(12)
        result['ema_26'] = self.ema(26)
        
        # MACD
        macd_df = self.macd()
        result['macd_dif'] = macd_df['dif']
        result['macd_dea'] = macd_df['dea']
        result['macd_histogram'] = macd_df['histogram']
        
        # KDJ
        kdj_df = self.kdj()
        result['kdj_k'] = kdj_df['k']
        result['kdj_d'] = kdj_df['d']
        result['kdj_j'] = kdj_df['j']
        
        # RSI
        result['rsi_6'] = self.rsi(6)
        result['rsi_12'] = self.rsi(12)
        result['rsi_24'] = self.rsi(24)
        
        # 布林带
        bb_df = self.bollinger_bands()
        result['boll_upper'] = bb_df['upper']
        result['boll_mid'] = bb_df['mid']
        result['boll_lower'] = bb_df['lower']
        
        # 波动率
        result['volatility_20d'] = self.volatility(20)
        result['atr_14'] = self.atr(14)
        
        # 成交量指标
        result['volume_ma_20'] = self.volume_ma(20)
        result['obv'] = self.obv()
        
        return result
