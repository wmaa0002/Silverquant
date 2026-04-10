# BLK暴力K策略构建文档

本文档分析`tiangongBLK.txt`中的条件，并与`通用数值.md`进行对比，标注已收录和未收录的指标。

---

## 一、BLK公式原文

```
非ST股 := NOT(NAMELIKE('ST')) AND NOT(NAMELIKE('*ST')); 

K线长度 := HIGH - LOW;

上影线 := HIGH - MAX(C, O);

波幅 := MA(TR, 30);

涨跌幅 := (C - REF(C, 1)) / REF(C, 1) * 100;

波动率 := 波幅 / REF(C, 1) * 100;

参考成交量 := IF(REF(VOL, 1) <= VOL / 8, REF(VOL, 2), REF(VOL, 1));

暴力K := C > REF(C, 1) 
    AND VOL > 参考成交量 * 1.8
    AND 涨跌幅 > 4
    AND 上影线 <= K线长度 / 3.5
    AND (REF(C, 1) - REF(O, 9)) / REF(O, 9) * 100 < 4
    AND (REF(C, 1) - REF(O, 4)) / REF(O, 4) * 100 < 4
    AND VOL > MA(VOL, 60);

暴力K AND 非ST股;
```

---

## 二、与通用数值.md对比

### ✅ 已收录的指标

| 指标名称 | BLK公式 | 通用数值.md | 说明 |
|----------|---------|-------------|------|
| 非ST股 | NOT(NAMELIKE('ST')) AND NOT(NAMELIKE('*ST')) | 策略中有ST股票过滤逻辑 | 股票状态判断 |
| K线长度 | HIGH - LOW | K线长度 = high - low | K线整体长度 |
| 上影线 | HIGH - MAX(C, O) | 上影线 = high - max(close, open) | 上影线长度 |
| 波幅 | MA(TR, 30) | 波幅 = mean(abs(high - low), 30日) | ⚠️ 计算方式略有不同 |
| 涨跌幅 | (C - REF(C, 1)) / REF(C, 1) * 100 | 涨跌幅 = (close - prev_close) / prev_close * 100 | 涨幅计算公式一致 |
| 波动率 | 波幅 / REF(C, 1) * 100 | 波动率 = 波幅 / prev_close * 100 | 波动率计算一致 |
| 参考成交量 | IF(REF(VOL, 1) <= VOL / 8, REF(VOL, 2), REF(VOL, 1)) | 参考成交量 = volume_arr[-2] if volume <= vol/8 else volume | 参考成交量定义一致 |
| 暴力K | (组合条件) | 暴力K = 涨幅>4 AND volume>参考成交量*1.8 AND 上影线<=K线长度/4 AND volume>VOL_MA60 | ⚠️ 阈值不同 |
| MA(VOL, 60) | VOL > MA(VOL, 60) | VOL_MA60 = volume的60日均值 | 成交量60日均线 |

### ⚠️ 参数差异

| 指标 | BLK公式 | 通用数值.md实现 | 差异说明 |
|------|---------|-----------------|----------|
| 暴力K-上影线 | 上影线 <= K线长度 / **3.5** | 上影线 <= K线长度 / **4** | BLK更严格 |
| 暴力K-前9日涨幅 | (REF(C, 1) - REF(O, 9)) / REF(O, 9) * 100 < **4** | **未实现** | 通用数值缺少此条件 |
| 暴力K-前4日涨幅 | (REF(C, 1) - REF(O, 4)) / REF(O, 4) * 100 < **4** | **未实现** | 通用数值缺少此条件 |
| 波幅计算 | MA(TR, 30) | mean(abs(high - low), 30日) | ⚠️ TR vs 简单振幅计算 |

### ❌ 未收录的指标

| 指标名称 | BLK公式 | 说明 |
|----------|---------|------|
| TR (True Range) | MA(TR, 30) | 真实波幅，标准公式为 max(H-L, abs(H-REF(C,1)), abs(L-REF(C,1))) |
| 前9日涨幅条件 | (REF(C, 1) - REF(O, 9)) / REF(O, 9) * 100 < 4 | 昨日收盘相对9日前涨幅<4% |
| 前4日涨幅条件 | (REF(C, 1) - REF(O, 4)) / REF(O, 4) * 100 < 4 | 昨日收盘相对4日前涨幅<4% |

---

## 三、BLK完整条件拆解

### 3.1 基础条件

```
C > REF(C, 1)          # 收盘价高于昨日收盘价
VOL > 参考成交量 * 1.8  # 成交量放大1.8倍以上
涨跌幅 > 4             # 涨幅大于4%
上影线 <= K线长度 / 3.5  # 上影线不超过K线长度的1/3.5
VOL > MA(VOL, 60)     # 成交量大于60日均量
```

### 3.2 新增限制条件（BLK特有）

```
# 昨日收盘相对9日前涨幅限制
(REF(C, 1) - REF(O, 9)) / REF(O, 9) * 100 < 4

# 昨日收盘相对4日前涨幅限制  
(REF(C, 1) - REF(O, 4)) / REF(O, 4) * 100 < 4
```

**条件解读：**
- 这两个条件限制了近期涨幅不能过大
- 意味着"暴力K"之前股价应该相对平稳
- 排除了连续大涨后的暴力拉升（可能是最后一涨）

### 3.3 最终筛选

```
暴力K AND 非ST股
```

---

## 四、与现有策略中暴力K的对比

### 天宫B1/B2策略中的暴力K定义

```python
暴力K = close > close_arr[-2] and volume > 参考成交量 * 1.8 and 涨跌幅 > 4 and (high - max(close, open_p)) <= (high - open_p) / 4 and volume > np.mean(volume_arr[-60:])
```

**对比差异：**

| 条件项 | BLK公式 | 现有策略实现 |
|--------|---------|--------------|
| 上影线比例 | <= 1/3.5 (≈28.6%) | <= 1/4 (25%) |
| 前9日涨幅限制 | < 4% | ❌ 无 |
| 前4日涨幅限制 | < 4% | ❌ 无 |

---

## 五、建议实现

如果要严格按照BLK公式实现暴力K，需要添加以下逻辑：

```python
def calculate_blk_暴力K(close, prev_close, open_price, high, low, volume, 
                        reference_volume, vol_ma60, close_arr, open_arr):
    """
    BLK暴力K计算
    
    条件:
    1. C > REF(C, 1) - 收盘价高于昨日
    2. VOL > 参考成交量 * 1.8 - 放量
    3. 涨跌幅 > 4 - 涨幅>4%
    4. 上影线 <= K线长度 / 3.5 - 上影线限制
    5. (REF(C, 1) - REF(O, 9)) / REF(O, 9) * 100 < 4 - 前9日涨幅限制
    6. (REF(C, 1) - REF(O, 4)) / REF(O, 4) * 100 < 4 - 前4日涨幅限制
    7. VOL > MA(VOL, 60) - 量能支撑
    """
    
    # K线长度
    k线长度 = high - low
    
    # 上影线
    上影线 = high - max(close, open_price)
    
    # 涨跌幅
    涨跌幅 = (close - prev_close) / prev_close * 100 if prev_close != 0 else 0
    
    # 条件1: 收盘价高于昨日
    cond1 = close > prev_close
    
    # 条件2: 成交量放大
    cond2 = volume > reference_volume * 1.8
    
    # 条件3: 涨幅>4%
    cond3 = 涨跌幅 > 4
    
    # 条件4: 上影线限制
    cond4 = 上影线 <= k线长度 / 3.5
    
    # 条件5: 前9日涨幅限制
    if len(close_arr) >= 10 and len(open_arr) >= 10:
        prev_close_9 = close_arr[-2]  # 昨日收盘
        open_9 = open_arr[-9]         # 9日前开盘
        if open_9 != 0:
            前9日涨幅 = (prev_close_9 - open_9) / open_9 * 100
            cond5 = 前9日涨幅 < 4
        else:
            cond5 = True
    else:
        cond5 = True
    
    # 条件6: 前4日涨幅限制
    if len(close_arr) >= 5 and len(open_arr) >= 5:
        prev_close_4 = close_arr[-2]  # 昨日收盘
        open_4 = open_arr[-4]         # 4日前开盘
        if open_4 != 0:
            前4日涨幅 = (prev_close_4 - open_4) / open_4 * 100
            cond6 = 前4日涨幅 < 4
        else:
            cond6 = True
    else:
        cond6 = True
    
    # 条件7: 量能支撑
    cond7 = volume > vol_ma60
    
    # 最终判断
    暴力K = cond1 and cond2 and cond3 and cond4 and cond5 and cond6 and cond7
    
    return 暴力K
```

---

## 六、TR真实波幅计算（可选优化）

BLK公式中波幅使用`MA(TR, 30)`，其中TR(True Range)的标准计算为：

```python
def calculate_tr(high, low, prev_close):
    """
    True Range 计算
    """
    tr1 = high - low
    tr2 = abs(high - prev_close)
    tr3 = abs(low - prev_close)
    return max(tr1, tr2, tr3)
```

现有通用数值中使用的是简化版本 `波幅 = mean(abs(high - low), 30日)`，如果需要更精确可以改用TR计算。

---

本文档最后更新: 2026-03-01
