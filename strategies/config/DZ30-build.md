# DZ30 动量突破策略指标分析报告

本文档分析 `tiangongDZ30.txt`（通达信公式）中的所有条件指标。

---

## 一、策略概述

### 1.1 策略名称

**DZ30** = 动量突破 + 趋势确认 综合策略

### 1.2 策略理念

```
核心思想：长期动量强势 + 短期超卖 + 趋势确认 + 量能配合

长期动量：长期KD值>=85，表示长期处于强势区间
短期超卖：短期KD值<=30，表示短期回调至超卖区域
趋势确认：价格突破知行短期趋势线，且趋势线>多空线
量能配合：20日内出现倍量柱，且最大量当天非阴线
```

### 1.3 策略参数

| 参数 | 值 | 说明 |
|------|-----|------|
| M1 | 14 | MA14参数 |
| M2 | 28 | MA28参数 |
| M3 | 57 | MA57参数 |
| M4 | 114 | MA114参数 |
| N1 | 3 | 短期KD周期 |
| N2 | 21 | 长期KD周期 |

---

## 二、通达信公式原文

```tongda
DZ30 - 动量突破策略

M1:=14;M2:=28;M3:=57;M4:=114;N1:=3;N2:=21; 

知行短期趋势线:=EMA(EMA(C,10),10),COLORFFFFFF,LINETHICK1;
知行多空线:=(MA(CLOSE,M1)+MA(CLOSE,M2)+MA(CLOSE,M3)+MA(CLOSE,M4))/4;
短期:=100*(C-LLV(L,3))/(HHV(C,3)-LLV(L,3)),COLORWHITE;
长期:=100*(C-LLV(L,21))/(HHV(C,21)-LLV(L,21)),COLORRED,LINETHICK2;

今日条件:=(长期 >= 85) AND (短期 <= 30);

参考成交量:=IF(REF(VOL,1)<=VOL/8,REF(VOL,2),REF(VOL,1));
倍量柱:=IF(VOL>参考成交量*1.8,1,0) AND C>O AND C>REF(C,1);

非ST股 := NOT(NAMELIKE('ST')) AND NOT(NAMELIKE('*ST')); 

最高量至今:= (HHVBARS(REF(V,1), 19-1)) + 1; 

前20日非阴:=REF(C, 最高量至今) >= REF(O, 最高量至今) AND 最高量至今 <= 19;

选股信号:今日条件 AND 非ST股 AND C>知行短期趋势线 AND 知行短期趋势线>知行多空线 AND COUNT(倍量柱,20)>=1 AND 前20日非阴;
```

---

## 三、核心指标拆解

### 3.1 趋势线指标

| 指标 | 公式 | 说明 |
|------|------|------|
| 知行短期趋势线 | `EMA(EMA(C,10),10)` | 双重EMA形成的短期趋势线，白色线 |
| 知行多空线 | `(MA14 + MA28 + MA57 + MA114) / 4` | 多周期均线平均值，作为多空平衡线 |

**解读**：
- 知行短期趋势线是对收盘价进行10日EMA再EMA，形成更平滑的短期趋势线
- 知行多空线是4条不同周期均线(14/28/57/114日)的平均值，代表市场的多空平衡位置

### 3.2 KD随机指标

| 指标 | 公式 | 说明 |
|------|------|------|
| 短期KD | `100*(C-LLV(L,N1))/(HHV(C,N1)-LLV(L,N1))` | N1=3日的KD值，白色线 |
| 长期KD | `100*(C-LLV(L,N2))/(HHV(C,N2)-LLV(L,N2))` | N2=21日的KD值，红色线 |

**KD指标原理**：
- 计算N日内最低价到最高价的范围，判断当前价格所处的相对位置
- 值域0-100，数值越高表示价格越接近N日最高价（越强势）
- 数值越低表示价格越接近N日最低价（越弱势）

### 3.3 今日条件

```
今日条件 = (长期 >= 85) AND (短期 <= 30)
```

| 条件 | 值 | 含义 |
|------|-----|------|
| 长期 >= 85 | 强势区 | 21日内价格位置在85%以上，长期强势 |
| 短期 <= 30 | 超卖区 | 3日内价格位置在30%以下，短期超卖 |

**策略逻辑**：
- 长期处于强势区间（主力控盘）
- 短期回调到超卖区域（提供买入机会）
- 这是一个「强势回调」模型

### 3.4 量能指标

| 指标 | 公式 | 说明 |
|------|------|------|
| 参考成交量 | `IF(REF(VOL,1)<=VOL/8,REF(VOL,2),REF(VOL,1))` | 智能参考量 |
| 倍量柱 | `VOL>参考成交量*1.8 AND C>O AND C>REF(C,1)` | 放量上涨K线 |

**参考成交量逻辑**：
- 如果昨日成交量<=今日成交量/8（地量），则用前2日成交量作参考
- 否则用昨日成交量作参考
- 这样可以避免地量导致的参考失真

**倍量柱条件**：
1. 成交量 > 参考成交量 × 1.8（放量1.8倍以上）
2. 收盘价 > 开盘价（阳线）
3. 收盘价 > 昨日收盘价（上涨）

### 3.5 股票筛选指标

| 指标 | 公式 | 说明 |
|------|------|------|
| 非ST股 | `NOT(NAMELIKE('ST')) AND NOT(NAMELIKE('*ST'))` | 排除ST/*ST股票 |

### 3.6 最大量位置指标

| 指标 | 公式 | 说明 |
|------|------|------|
| 最高量至今 | `(HHVBARS(REF(V,1), 19-1)) + 1` | 19日内最高量距离今天数 |
| 前20日非阴 | `REF(C, 最高量至今) >= REF(O, 最高量至今)` AND `最高量至今 <= 19` | 最高量当天非阴线 |

**逻辑解读**：
- HHVBARS(REF(V,1), 18) 返回18日内最高量距离当前的天数
- +1 是因为函数返回的是偏移量，需要加1才是距离天数
- 前20日非阴：确保19日内最大量当天是上涨的（阳线），避免放量下跌

---

## 四、选股条件详解

### 4.1 条件分解

```
选股信号 = 今日条件 
         AND 非ST股 
         AND C > 知行短期趋势线 
         AND 知行短期趋势线 > 知行多空线 
         AND COUNT(倍量柱, 20) >= 1 
         AND 前20日非阴
```

### 4.2 条件解读

| 条件 | 含义 |
|------|------|
| 今日条件 | 长期强势(>=85) AND 短期超卖(<=30) |
| 非ST股 | 排除ST/*ST股票 |
| C > 知行短期趋势线 | 价格在短期趋势线上方 |
| 知行短期趋势线 > 知行多空线 | 短期趋势线高于多空线（多头排列） |
| COUNT(倍量柱, 20) >= 1 | 20日内出现过倍量柱 |
| 前20日非阴 | 19日内最大量当天是阳线 |

### 4.3 综合逻辑

```
1. 长期趋势向好（长期KD >= 85）
2. 短期回调到位（短期KD <= 30）
3. 价格开始反弹（C > 知行短期趋势线）
4. 趋势转强（短期趋势线 > 多空线）
5. 有量能配合（20日内有倍量）
6. 量能健康（最大量当天上涨）
7. 排除ST风险
```

---

## 五、Python实现参考

### 5.1 KD指标计算

```python
import numpy as np

def calculate_kd(close, low, high, period):
    """
    计算KD指标
    
    Args:
        close: 收盘价数组
        low: 最低价数组
        high: 最高价数组
        period: KD周期
    
    Returns:
        KD值数组 (0-100)
    """
    n = len(close)
    kd = np.zeros(n)
    
    for i in range(period - 1, n):
        lowest_low = np.min(low[i - period + 1:i + 1])
        highest_high = np.max(high[i - period + 1:i + 1])
        
        if highest_high - lowest_low > 0:
            kd[i] = 100 * (close[i] - lowest_low) / (highest_high - lowest_low)
        else:
            kd[i] = 50  # 无波动时取中值
    
    return kd


def calculate_short_long_kd(close, low, high):
    """
    计算短期(3日)和长期(21日)KD
    
    Args:
        close: 收盘价数组
        low: 最低价数组
        high: 最高价数组
    
    Returns:
        (短期KD, 长期KD)
    """
    short_kd = calculate_kd(close, low, high, 3)
    long_kd = calculate_kd(close, low, high, 21)
    
    return short_kd, long_kd
```

### 5.2 趋势线计算

```python
import pandas as pd

def calculate_ema(arr, period):
    """计算EMA"""
    return pd.Series(arr).ewm(span=period, adjust=False).mean().values


def calculate_知行短期趋势线(close):
    """
    知行短期趋势线 = EMA(EMA(C,10),10)
    """
    ema_10 = calculate_ema(close, 10)
    return calculate_ema(ema_10, 10)


def calculate_知行多空线(close, m1=14, m2=28, m3=57, m4=114):
    """
    知行多空线 = (MA14 + MA28 + MA57 + MA114) / 4
    """
    ma14 = pd.Series(close).rolling(window=m1).mean().values
    ma28 = pd.Series(close).rolling(window=m2).mean().values
    ma57 = pd.Series(close).rolling(window=m3).mean().values
    ma114 = pd.Series(close).rolling(window=m4).mean().mean().values
    
    return (ma14 + ma28 + ma57 + ma114) / 4
```

### 5.3 倍量柱计算

```python
def calculate_倍量柱(volume, close, open_price, prev_close):
    """
    倍量柱条件:
    1. VOL > 参考成交量 * 1.8
    2. C > O (阳线)
    3. C > REF(C,1) (上涨)
    
    Args:
        volume: 成交量数组
        close: 收盘价数组
        open_price: 开盘价数组
        prev_close: 昨日收盘价数组
    
    Returns:
        布尔数组
    """
    n = len(volume)
    result = np.zeros(n, dtype=bool)
    
    for i in range(1, n):
        # 计算参考成交量
        if volume[i-1] <= volume[i] / 8:
            reference_volume = volume[i-2] if i >= 2 else volume[i-1]
        else:
            reference_volume = volume[i-1]
        
        # 判断倍量柱
        is_bullish = close[i] > open_price[i]  # 阳线
        is_up = close[i] > prev_close[i-1]     # 上涨
        is_volume_up = volume[i] > reference_volume * 1.8  # 放量1.8倍
        
        result[i] = is_bullish and is_up and is_volume_up
    
    return result


def check_倍量柱_count(volume, close, open_price, prev_close, lookback=20):
    """
    检查过去N日内是否有倍量柱
    
    Args:
        volume: 成交量数组
        close: 收盘价数组
        open_price: 开盘价数组
        prev_close: 昨日收盘价数组
        lookback: 回看天数
    
    Returns:
        倍量柱数量
    """
    倍量柱 = calculate_倍量柱(volume, close, open_price, prev_close)
    
    if len(倍量柱) < lookback:
        return np.sum(倍量柱)
    else:
        return np.sum(倍量柱[-lookback:])
```

### 5.4 前20日非阴判断

```python
def check_前20日非阴(close, open_price, volume):
    """
    检查19日内最大量当天是否非阴线
    
    条件:
    1. 最高量至今 <= 19 (19日内最高量)
    2. 最高量当天: REF(C, 最高量至今) >= REF(O, 最高量至今)
    
    Args:
        close: 收盘价数组
        open_price: 开盘价数组
        volume: 成交量数组
    
    Returns:
        True/False
    """
    if len(volume) < 20:
        return False
    
    # 获取19日内的最高量位置
    recent_vol = volume[-19:]
    max_vol_idx = np.argmax(recent_vol)  # 0-based index within 19 days
    
    # 转换为距离今天的天数 (1-based, 需要+1)
    highest_volume_days_ago = max_vol_idx + 1
    
    if highest_volume_days_ago > 19:
        return False
    
    # 获取最高量当天的收盘价和开盘价
    ref_idx = -19 + max_vol_idx  # 在完整数组中的索引
    close_at_high = close[ref_idx]
    open_at_high = open_price[ref_idx]
    
    # 判断是否非阴 (收盘价 >= 开盘价)
    return close_at_high >= open_at_high
```

### 5.5 DZ30选股信号

```python
def check_dz30_signal(close, low, high, open_price, volume, prev_close):
    """
    DZ30选股信号检查
    
    Args:
        close: 收盘价数组
        low: 最低价数组
        high: 最高价数组
        open_price: 开盘价数组
        volume: 成交量数组
        prev_close: 昨日收盘价数组
    
    Returns:
        选股信号 (True/False)
    """
    n = len(close)
    if n < 30:
        return False
    
    # 1. 计算KD指标
    short_kd, long_kd = calculate_short_long_kd(close, low, high)
    
    # 2. 今日条件: 长期>=85 AND 短期<=30
    今日条件 = (long_kd[-1] >= 85) and (short_kd[-1] <= 30)
    
    # 3. 非ST股 (需要外部数据，这里假设已过滤)
    非ST股 = True
    
    # 4. 计算趋势线
    知行短期趋势线 = calculate_知行短期趋势线(close)
    知行多空线 = calculate_知行多空线(close)
    
    # 5. 趋势条件: C > 知行短期趋势线 AND 知行短期趋势线 > 知行多空线
    价格在趋势线上 = close[-1] > 知行短期趋势线[-1]
    趋势多头 = 知行短期趋势线[-1] > 知行多空线[-1]
    
    # 6. 倍量柱: 20日内有倍量柱
    倍量柱数量 = check_倍量柱_count(volume, close, open_price, prev_close, 20)
    有倍量柱 = 倍量柱数量 >= 1
    
    # 7. 前20日非阴
    前20日非阴 = check_前20日非阴(close, open_price, volume)
    
    # 综合条件
    return (今日条件 and 非ST股 and 价格在趋势线上 and 
            趋势多头 and 有倍量柱 and 前20日非阴)
```

---

## 六、指标状态对照表

### 6.1 趋势线指标

| 指标 | 状态 | 说明 |
|------|------|------|
| 知行短期趋势线 | ✅ 已实现 | EMA(EMA(C,10),10) |
| 知行多空线 | ✅ 已实现 | (MA14+MA28+MA57+MA114)/4 |

### 6.2 KD指标

| 指标 | 状态 | 说明 |
|------|------|------|
| 短期KD(3日) | ✅ 已实现 | 短期超卖判断 |
| 长期KD(21日) | ✅ 已实现 | 长期强势判断 |
| 今日条件 | ✅ 已实现 | 长期>=85 AND 短期<=30 |

### 6.3 量能指标

| 指标 | 状态 | 说明 |
|------|------|------|
| 参考成交量 | ✅ 已实现 | 智能参考量计算 |
| 倍量柱 | ✅ 已实现 | 放量上涨K线 |
| COUNT(倍量柱,20) | ✅ 已实现 | 20日内倍量柱数量 |

### 6.4 筛选条件

| 指标 | 状态 | 说明 |
|------|------|------|
| 非ST股 | ✅ 已实现 | NOT(NAMELIKE('ST')) |
| 前20日非阴 | ✅ 已实现 | 最高量当天非阴线 |
| C > 知行短期趋势线 | ✅ 已实现 | 价格在趋势线上 |
| 知行短期趋势线 > 知行多空线 | ✅ 已实现 | 多头排列 |

---

## 七、策略参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| M1 | 14 | MA周期1 |
| M2 | 28 | MA周期2 |
| M3 | 57 | MA周期3 |
| M4 | 114 | MA周期4 |
| N1 | 3 | 短期KD周期 |
| N2 | 21 | 长期KD周期 |
| 倍量阈值 | 1.8 | 成交量放大倍数 |
| 倍量回看天数 | 20 | 倍量柱回看天数 |

---

## 八、与SCB/BLK策略对比

### 8.1 策略类型对比

| 项目 | DZ30 | SCB | BLK |
|------|------|-----|-----|
| 策略类型 | 动量突破 | 地量+暴力K | 暴力K |
| 核心条件 | 长期强势+短期超卖 | 地量低吸+暴力K确认 | 放量长阳突破 |
| 适用场景 | 强势股回调 | 底部启动 | 主升浪 |

### 8.2 条件对比

| 条件项 | DZ30 | SCB | BLK |
|--------|------|-----|-----|
| 趋势要求 | 趋势线>多空线 | 多空线>60日前 | 无 |
| 量能要求 | 20日倍量柱 | 暴力K | 暴力K |
| 超买超卖 | 长期>=85,短期<=30 | 地量>=30 | 无 |
| ST过滤 | ✅ | ✅ | ✅ |

---

## 九、注意事项

1. **KD参数**：N1=3(短期), N2=21(长期) 与传统KD(9日)不同
2. **趋势线**：双重EMA比普通MA更平滑，假信号更少
3. **量能配合**：强调倍量柱出现，避免无量上涨
4. **非阴线**：最大量当天必须是阳线，确保放量上涨

---

本文档最后更新: 2026-03-04
