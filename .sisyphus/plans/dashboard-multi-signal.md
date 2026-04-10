# Dashboard多策略共振页面开发计划

## TL;DR

> **Quick Summary**: 在dashboard中添加"多策略共振"子页面，显示同时出现2个及以上买入信号的股票
> 
> **Deliverables**:
> - 新增 `/multi-signal-resonance` 路由
> - 时间筛选功能（默认前1天）
> - 显示共振股票列表及信号详情
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: NO

---

## Context

### 功能需求
- 显示每日同时出现多个买入信号的股票
- 帮助识别市场热点板块

### 数据来源
- `daily_signals` 表
- 信号字段: `signal_buy_b1`, `signal_buy_b2`, `signal_buy_blk`, `signal_buy_dl`, `signal_buy_dz30`, `signal_buy_scb`, `signal_buy_blkB2`

### 信号列表
| 信号 | 含义 |
|------|------|
| B1 | B1策略买入 |
| B2 | B2策略买入 |
| BLK | 暴力K买入 |
| DL | 地量买入 |
| DZ30 | 单针30买入 |
| SCB | 沙尘暴买入 |
| BLKB2 | BLK+B2组合买入 |

---

## Work Objectives

### Core Objective
在dashboard中添加"多策略共振"子页面

### Concrete Deliverables
- [ ] 新增 `api_multi_signal_resonance` API路由
- [ ] 新增 `/multi-signal-resonance` 页面路由
- [ ] 时间筛选功能（默认前一天）
- [ ] 显示共振股票表格（代码、名称、信号数、信号列表）

### Definition of Done
- [ ] 页面可访问
- [ ] 时间筛选正常工作
- [ ] 显示所有符合条件的股票

---

## Execution Strategy

```
Wave 1:
├── Task 1: 添加API路由 (api_multi_signal_resonance)
├── Task 2: 添加页面路由和模板
└── Task 3: 测试验证
```

---

## TODOs

- [x] 1. 添加API路由

  **What to do**:
  在 `dashboard/app.py` 中添加 `api_multi_signal_resonance` 函数：
  
  ```python
  @app.route('/api/multi-signal-resonance')
  def api_multi_signal_resonance():
      date = request.args.get('date')
      if not date:
          date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
      
      # 查询多信号共振股票
      result = db.execute("""
          SELECT code, name,
                 signal_buy_b1, signal_buy_b2, signal_buy_blk, signal_buy_dl,
                 signal_buy_dz30, signal_buy_scb, signal_buy_blkB2,
                 close, change_pct
          FROM daily_signals
          WHERE date = ?
          AND (CAST(signal_buy_b1 AS INT) + CAST(signal_buy_b2 AS INT) + 
               CAST(signal_buy_blk AS INT) + CAST(signal_buy_dl AS INT) + 
               CAST(signal_buy_dz30 AS INT) + CAST(signal_buy_scb AS INT) + 
               CAST(signal_buy_blkB2 AS INT)) >= 2
          ORDER BY close DESC
      """, [date]).fetchall()
      
      # 构建响应
      signal_names = ['B1', 'B2', 'BLK', 'DL', 'DZ30', 'SCB', 'BLKB2']
      data = []
      for row in result:
          signals = [signal_names[i] for i, v in enumerate(row[2:9]) if v]
          data.append({
              'code': row[0],
              'name': row[1],
              'signal_count': len(signals),
              'signals': signals,
              'close': row[9],
              'change_pct': row[10]
          })
      
      return jsonify({'date': date, 'stocks': data})
      ```
  
  **Location**: `dashboard/app.py`

  **Must NOT do**:
  - 不修改现有路由
  - 不修改数据库

---

- [x] 2. 添加页面路由

  **What to do**:
  在 `dashboard/app.py` 中添加HTML页面路由：
  
  ```python
  @app.route('/multi-signal-resonance')
  def multi_signal_resonance():
      return '''
      <!DOCTYPE html>
      <html>
      <head>
          <title>多策略共振</title>
          <style>
              /* 简洁样式 */
          </style>
      </head>
      <body>
          <h1>多策略共振</h1>
          <div class="filter">
              <label>选择日期:</label>
              <input type="date" id="datePicker">
              <button onclick="loadData()">查询</button>
          </div>
          <div id="stats"></div>
          <table id="stockTable">
              <thead>
                  <tr>
                      <th>代码</th>
                      <th>名称</th>
                      <th>信号数</th>
                      <th>信号列表</th>
                      <th>收盘价</th>
                      <th>涨跌幅</th>
                  </tr>
              </thead>
              <tbody></tbody>
          </table>
          <script>
              // 获取数据并渲染表格
          </script>
      </body>
      </html>
      '''
  ```

  **Location**: `dashboard/app.py`

  **Must NOT do**:
  - 不复制现有页面样式

---

- [x] 3. 测试验证

  **What to do**:
  验证功能正常：
  1. 访问 `/multi-signal-resonance`
  2. 检查默认日期是否为前一天
  3. 测试日期切换
  4. 验证表格数据显示正确

---

## Success Criteria

### Verification Commands
```bash
# 启动dashboard
cd /Users/mawenhao/Desktop/code/股票策略/dashboard
python app.py

# 测试API
curl "http://127.0.0.1:5000/api/multi-signal-resonance?date=2026-03-27"
```

### Final Checklist
- [ ] 页面可访问
- [ ] 日期筛选器工作
- [ ] 表格显示共振股票
- [ ] 信号列表正确
