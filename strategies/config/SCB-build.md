# SCB地量+暴力K综合策略（极地沙尘暴）

本文档分析 `tiangongSCB.txt`（通达信公式）中的所有条件指标。

---

## 一、策略概述

### 1.1 策略名称

**极地沙尘暴** = 地量 + 暴力K 综合策略

### 1.2 策略理念

```
核心思想：既要求地量低吸，又要求暴力K确认

地量信号：成交量萎缩到近期极低水平（可能见底）
暴力K信号：出现放量暴力拉升K线（确认启动）
SCB综合：过去5天内出现地量信号，且今日出现暴力K确认
```

### 1.3 策略参数

| 参数 | 值 | 说明 |
|------|-----|------|
| X | 30 | 地量阈值 |
| M1 | 14 | MA14参数 |
| M2 | 28 | MA28参数 |
| M3 | 57 | MA57参数 |
| M4 | 114 | MA114参数 |

---

## 二、通达信公式原文

```tongda
5.地量+暴力K（极地沙尘暴）

X:=30
M1:=14;M2:=28;M3:=57;M4:=114;

知行短期趋势线:=EMA(EMA(C,10),10),COLORFFFFFF,LINETHICK1;
知行多空线:=(MA(CLOSE,M1)+MA(CLOSE,M2)+MA(CLOSE,M3)+MA(CLOSE,M4))/4;

涨停价:=IF(NAMELIKE('ST'),ZTPRICE(REF(C,1),0.05),
        IF(CODELIKE('300') OR CODELIKE('688') OR CODELIKE('301'),ZTPRICE(REF(C,1),0.2),
        ZTPRICE(REF(C,1),0.1)));

涨停板:=C>=涨停价 AND C>O;

跌停价:=IF(NAMELIKE('ST'),DTPRICE(REF(C,1),0.05),  
        IF(CODELIKE('300') OR CODELIKE('688') OR CODELIKE('301'),DTPRICE(REF(C,1),0.2),  
        DTPRICE(REF(C,1),0.1))); 

跌停板:=C<=跌停价 AND C<O;

一字涨停:=(O=C) AND (C=H) AND (C=涨停价);
一字跌停:=(O=C) AND (C=L) AND (C=跌停价);

VOL_MA60:=MA(VOL,60);

K线长度:=HIGH-LOW;
上影线:=HIGH-MAX(C,O);
下影线:=MIN(C,O)-LOW;
实体 := O - C;

地量1:=IF(涨停板 OR 一字涨停 OR 跌停板 OR 一字跌停, 0, IF(V*0.9<=LLV(V,20),20,IF(V*0.9<=LLV(V,19),19,...)));
地量2:=IF(涨停板 OR 一字涨停 OR 跌停板 OR 一字跌停, 0, IF(V*0.9<=LLV(V,30),30,IF(V*0.9<=LLV(V,29),29,...)));
地量3:=IF(涨停板 OR 一字涨停 OR 跌停板 OR 一字跌停, 0, IF(V*0.9<=LLV(V,40),40,IF(V*0.9<=LLV(V,39),39,...)));
地量4:=IF(涨停板 OR 一字涨停 OR 跌停板 OR 一字跌停, 0, IF(V*0.9<=LLV(V,50),50,IF(V*0.9<=LLV(V,49),49,...)));

地量:=IF(地量4>=41,地量4,IF(地量3>=31,地量3,IF(地量2>=21,地量2,IF(地量1>=10,地量1,0))));

非ST股:=NOT(NAMELIKE('ST')) AND NOT(NAMELIKE('*ST')); 
前60日非阴:=REF(C,HHVBARS(VOL,60))>=REF(O,HHVBARS(VOL,60));

波幅:=MA(TR,30);
涨跌幅:=(C-REF(C,1))/REF(C,1)*100;
波动率:=波幅/REF(C,1)*100;

大长阳:=C>O AND 涨跌幅>波动率*1.5 AND 涨跌幅>2;
大长阴:=C<O AND ABS(涨跌幅)>波动率*1.1 AND ABS(涨跌幅)>2;

参考成交量:=IF(REF(VOL,1)<=VOL/8,REF(VOL,2),REF(VOL,1));

关键K:=CLOSE>REF(CLOSE,1) AND VOL>参考成交量*1.8 AND 大长阳 AND VOL>MA(VOL,40);

暴力K := C > REF(C, 1) AND VOL > 参考成交量 * 1.8 AND 涨跌幅 > 4 AND 上影线 <= K线长度 / 4 
    AND (REF(C, 1) - REF(O, 15)) / REF(O, 15) *100  < 4 
    AND (REF(C, 1) - REF(O, 9)) / REF(O, 9)  *100 < 4 
    AND (REF(C, 1) - REF(O, 4)) / REF(O, 4) * 100 < 4;

异动80:=IF(EXIST(VOL>MA(VOL,60)*2 AND (C>O),80),1,0);

选股1:=REF(地量>=X AND 非ST股 AND FINANCE(42)>100 AND VOL>0 AND 前60日非阴 AND (COUNT(关键K,60)>=1 OR COUNT(暴力K,60)>=1) AND 异动80,1);
选股2:=REF(地量>=X AND 非ST股 AND FINANCE(42)>100 AND VOL>0 AND 前60日非阴 AND (COUNT(关键K,60)>=1 OR COUNT(暴力K,60)>=1) AND 异动80,2);
选股3:=REF(地量>=X AND 非ST股 AND FINANCE(42)>100 AND VOL>0 AND 前60日非阴 AND (COUNT(关键K,60)>=1 OR COUNT(暴力K,60)>=1) AND 异动80,3);
选股4:=REF(地量>=X AND 非ST股 AND FINANCE(42)>100 AND VOL>0 AND 前60日非阴 AND (COUNT(关键K,60)>=1 OR COUNT(暴力K,60)>=1) AND 异动80,4);
选股5:=REF(地量>=X AND 非ST股 AND FINANCE(42)>100 AND VOL>0 AND 前60日非阴 AND (COUNT(关键K,60)>=1 OR COUNT(暴力K,60)>=1) AND 异动80,5);

选股: (选股1 OR 选股2 OR 选股3 OR 选股4 OR 选股5) AND 暴力K AND 知行多空线 > REF(知行多空线,60);
```

---

## 三、核心指标拆解

### 3.1 趋势线指标

| 指标 | 公式 | 说明 |
|------|------|------|
| 知行短期趋势线 | `EMA(EMA(C,10),10)` | 双重EMA形成的短期趋势线 |
| 知行多空线 | `(MA14 + MA28 + MA57 + MA114) / 4` | 多空平衡线 |

### 3.2 涨跌停指标

| 指标 | 公式 | 说明 |
|------|------|------|
| 涨停价(ST) | `ZTPRICE(REF(C,1),0.05)` | ST股5% |
| 涨停价(创业板/科创板) | `ZTPRICE(REF(C,1),0.2)` | 20% |
| 涨停价(普通) | `ZTPRICE(REF(C,1),0.1)` | 10% |
| 涨停板 | `C>=涨停价 AND C>O` | 涨停状态 |
| 跌停板 | `C<=跌停价 AND C<O` | 跌停状态 |
| 一字涨停 | `(O=C) AND (C=H) AND (C=涨停价)` | 一字板 |
| 一字跌停 | `(O=C) AND (C=L) AND (C=跌停价)` | 一字跌停 |

### 3.3 K线形态指标

| 指标 | 公式 | 说明 |
|------|------|------|
| K线长度 | `HIGH-LOW` | K线整体长度 |
| 上影线 | `HIGH-MAX(C,O)` | 上影线长度 |
| 下影线 | `MIN(C,O)-LOW` | 下影线长度 |
| 实体 | `O-C` | K线实体 |

### 3.4 地量指标

| 指标 | 公式 | 等级 |
|------|------|------|
| 地量1 | `V*0.9<=LLV(V,10~20)` | 10~20 |
| 地量2 | `V*0.9<=LLV(V,21~30)` | 21~30 |
| 地量3 | `V*0.9<=LLV(V,31~40)` | 31~40 |
| 地量4 | `V*0.9<=LLV(V,41~50)` | 41~50 |
| **综合地量** | `MAX(地量4, 地量3, 地量2, 地量1)` | 取最高 |

**地量阈值**：X = 30（默认）

### 3.5 暴力K指标

```
暴力K = 条件1 AND 条件2 AND 条件3 AND 条件4 AND 条件5 AND 条件6 AND 条件7

条件1: C > REF(C, 1)              # 收盘价高于昨日
条件2: VOL > 参考成交量 * 1.8      # 成交量放大1.8倍
条件3: 涨跌幅 > 4                  # 涨幅大于4%
条件4: 上影线 <= K线长度 / 4       # 上影线不超过25%
条件5: (REF(C,1)-REF(O,15))/REF(O,15)*100 < 4   # 前15日涨幅<4%
条件6: (REF(C,1)-REF(O,9))/REF(O,9)*100 < 4     # 前9日涨幅<4%
条件7: (REF(C,1)-REF(O,4))/REF(O,4)*100 < 4      # 前4日涨幅<4%
```

**注意**：SCB公式中的暴力K与BLK公式略有不同：
- 上影线阈值：SCB用 `/4`（25%），BLK用 `/3.5`（28.6%）
- 增加了前15日涨幅限制

### 3.6 其他技术指标

| 指标 | 公式 | 说明 |
|------|------|------|
| VOL_MA60 | `MA(VOL,60)` | 成交量60日均线 |
| 波幅 | `MA(TR,30)` | 30日平均真实波幅 |
| 涨跌幅 | `(C-REF(C,1))/REF(C,1)*100` | 涨幅百分比 |
| 波动率 | `波幅/REF(C,1)*100` | 波动率百分比 |
| 大长阳 | `C>O AND 涨跌幅>波动率*1.5 AND 涨跌幅>2` | 放量长阳 |
| 大长阴 | `C<O AND ABS(涨跌幅)>波动率*1.1 AND ABS(涨跌幅)>2` | 放量长阴 |
| 参考成交量 | `IF(REF(VOL,1)<=VOL/8,REF(VOL,2),REF(VOL,1))` | 对比参考量 |
| 关键K | `CLOSE>REF(CLOSE,1) AND VOL>参考成交量*1.8 AND 大长阳 AND VOL>MA(VOL,40)` | 关键突破K |
| 异动80 | `EXIST(VOL>MA(VOL,60)*2 AND C>O, 80)` | 80日内有异动 |
| 前60日非阴 | `REF(C,HHVBARS(VOL,60))>=REF(O,HHVBARS(VOL,60))` | 60日最大量当天非阴 |

---

## 四、选股条件详解

### 4.1 地量基础条件

```
地量基础条件:
  地量 >= X (X=30)
  AND 非ST股
  AND FINANCE(42) > 100    {流通市值>1亿}
  AND VOL > 0
  AND 前60日非阴
  AND (COUNT(关键K,60)>=1 OR COUNT(暴力K,60)>=1)
  AND 异动80
```

### 4.2 选股1-5定义

| 选股 | 含义 |
|------|------|
| 选股1 | 1天前满足地量基础条件 |
| 选股2 | 2天前满足地量基础条件 |
| 选股3 | 3天前满足地量基础条件 |
| 选股4 | 4天前满足地量基础条件 |
| 选股5 | 5天前满足地量基础条件 |

### 4.3 最终选股条件

```
选股 = (选股1 OR 选股2 OR 选股3 OR 选股4 OR 选股5) 
     AND 暴力K 
     AND 知行多空线 > REF(知行多空线,60)
```

**解读**：
1. 过去5天内出现过地量信号
2. 今日满足暴力K条件
3. 知行多空线高于60日前的多空线（多头发散）

---

## 五、与BLK/DL公式对比

### 5.1 暴力K条件对比

| 条件项 | BLK公式 | SCB公式 | 差异 |
|--------|---------|---------|------|
| 上影线限制 | `<= K线长度/3.5` (28.6%) | `<= K线长度/4` (25%) | SCB更严格 |
| 前15日涨幅 | 无 | `< 4%` | SCB新增 |
| 前9日涨幅 | `< 4%` | `< 4%` | 一致 |
| 前4日涨幅 | `< 4%` | `< 4%` | 一致 |

### 5.2 选股逻辑对比

| 项目 | BLK/DL | SCB |
|------|---------|-----|
| 信号类型 | 当日信号 | 过去5天信号+当日确认 |
| 地量要求 | 当日地量>=X | 1-5日前出现过地量>=X |
| 暴力K要求 | 当日暴力K | 当日暴力K |
| 多空线要求 | 无 | 知行多空线>60日前多空线 |

---

## 六、Python实现参考

### 6.1 暴力K计算（SCB版本）

```python
def calculate_blk_score_scb(close, prev_close, open_price, high, low, volume, 
                            reference_volume, vol_ma60, close_arr, open_arr):
    """
    SCB版暴力K计算
    与BLK版本的区别：
    1. 上影线阈值用 /4 而不是 /3.5
    2. 增加前15日涨幅限制
    """
    # 条件1: 收盘>昨日
    cond1 = close > prev_close
    
    # 条件2: 放量1.8倍
    cond2 = volume > reference_volume * 1.8
    
    # 条件3: 涨幅>4%
    涨幅 = (close - prev_close) / prev_close * 100
    cond3 = 涨幅 > 4
    
    # 条件4: 上影线<=25% (SCB用/4，BLK用/3.5)
    K线长度 = high - low
    上影线 = high - max(close, open_price)
    cond4 = 上影线 <= K线长度 / 4
    
    # 条件5: 前15日涨幅<4% (SCB特有)
    if len(close_arr) >= 16 and len(open_arr) >= 16:
        prev_close_15 = close_arr[-2]  # 昨日收盘
        open_15 = open_arr[-15]        # 15日前开盘
        if open_15 != 0:
            前15日涨幅 = (prev_close_15 - open_15) / open_15 * 100
            cond5 = 前15日涨幅 < 4
        else:
            cond5 = True
    else:
        cond5 = True
    
    # 条件6: 前9日涨幅<4%
    if len(close_arr) >= 10 and len(open_arr) >= 10:
        prev_close_9 = close_arr[-2]
        open_9 = open_arr[-9]
        if open_9 != 0:
            前9日涨幅 = (prev_close_9 - open_9) / open_9 * 100
            cond6 = 前9日涨幅 < 4
        else:
            cond6 = True
    else:
        cond6 = True
    
    # 条件7: 前4日涨幅<4%
    if len(close_arr) >= 5 and len(open_arr) >= 5:
        prev_close_4 = close_arr[-2]
        open_4 = open_arr[-4]
        if open_4 != 0:
            前4日涨幅 = (prev_close_4 - open_4) / open_4 * 100
            cond7 = 前4日涨幅 < 4
        else:
            cond7 = True
    else:
        cond7 = True
    
    # 条件8: 量能支撑
    cond8 = volume > vol_ma60
    
    return cond1 and cond2 and cond3 and cond4 and cond5 and cond6 and cond7 and cond8
```

### 6.2 SCB综合选股

```python
def check_scb_signal(dl_score, blk_signal, 知行多空线, 知行多空线_60日前, X=30):
    """
    SCB综合选股信号
    
    条件:
    1. 过去5天内出现过地量>=X
    2. 今日满足暴力K
    3. 知行多空线 > 60日前多空线
    """
    # 检查过去5天的地量信号
    has_dl_in_5days = any(dl_score_history[-5:] >= X)
    
    # 多头发散
    多头信号 = 知行多空线 > 知行多空线_60日前
    
    return has_dl_in_5days and blk_signal and 多头信号
```

---

## 七、指标状态对照表

### 7.1 趋势线指标

| 指标 | 状态 | 说明 |
|------|------|------|
| 知行短期趋势线 | ✅ 已实现 | EMA(EMA(C,10),10) |
| 知行多空线 | ✅ 已实现 | (MA14+MA28+MA57+MA114)/4 |

### 7.2 涨跌停指标

| 指标 | 状态 | 说明 |
|------|------|------|
| 涨停价 | ✅ 已实现 | 根据板块计算 |
| 跌停价 | ✅ 已实现 | 根据板块计算 |
| 涨停板 | ✅ 已实现 | C>=涨停价 AND C>O |
| 跌停板 | ✅ 已实现 | C<=跌停价 AND C<O |
| 一字涨停 | ✅ 已实现 | O=C AND C=H AND C=涨停价 |
| 一字跌停 | ✅ 已实现 | O=C AND C=L AND C=跌停价 |

### 7.3 K线形态

| 指标 | 状态 | 说明 |
|------|------|------|
| K线长度 | ✅ 已实现 | HIGH-LOW |
| 上影线 | ✅ 已实现 | HIGH-MAX(C,O) |
| 下影线 | ✅ 已实现 | MIN(C,O)-LOW |
| 实体 | ✅ 已实现 | O-C |

### 7.4 地量指标

| 指标 | 状态 | 说明 |
|------|------|------|
| 地量1 | ✅ 已实现 | V*0.9<=LLV(V,10~20) |
| 地量2 | ✅ 已实现 | V*0.9<=LLV(V,21~30) |
| 地量3 | ✅ 已实现 | V*0.9<=LLV(V,31~40) |
| 地量4 | ✅ 已实现 | V*0.9<=LLV(V,41~50) |
| 综合地量 | ✅ 已实现 | 优先级判定 |

### 7.5 暴力K指标

| 指标 | 状态 | 说明 |
|------|------|------|
| 收盘>昨日 | ✅ 已实现 | C>REF(C,1) |
| 放量1.8倍 | ✅ 已实现 | VOL>参考成交量*1.8 |
| 涨幅>4% | ✅ 已实现 | 涨跌幅>4 |
| 上影线<=25% | ✅ 已实现 | SCB版本(/4) |
| 前15日涨幅<4% | ⚠️ 需补充 | SCB特有 |
| 前9日涨幅<4% | ✅ 已实现 | |
| 前4日涨幅<4% | ✅ 已实现 | |
| VOL_MA60 | ✅ 已实现 | |

### 7.6 筛选条件

| 指标 | 状态 | 说明 |
|------|------|------|
| 非ST股 | ✅ 已实现 | NOT(NAMELIKE('ST')) |
| 前60日非阴 | ⚠️ 需补充 | HHVBARS(VOL,60)当天非阴 |
| 异动80 | ⚠️ 需补充 | 80日内有异动 |
| COUNT(关键K/暴力K,60) | ⚠️ 需补充 | 60日内出现过 |

---

## 八、策略参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| X | 30 | 地量阈值 |
| min_data_days | 60 | 最小数据天数 |

### 卖出条件

与天宫B1策略相同（S1分数系统）：
- S1 > 10：清仓
- S1 > 5：半仓
- 跌破知行多空线：卖出

---

本文档最后更新: 2026-03-02
