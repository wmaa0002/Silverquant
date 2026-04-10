# Equity Curve Optimization Learnings

## Task Summary
Modified `api_equity_curve` function in `dashboard/app.py` to use `portfolio_daily` table directly instead of `portfolio_daily_strategy` GROUP BY.

## Key Changes Made

### 1. SQL Query Change
- **Old**: `SELECT date, SUM(position_value) as total_position_value, SUM(total_pnl) FROM portfolio_daily_strategy GROUP BY date`
- **New**: `SELECT date, total_value, init_cash, position_ratio, closed_pnl, available_cash, (total_pnl - closed_pnl) AS position_pnl FROM portfolio_daily ORDER BY date`

### 2. Data Extraction
- `values` now uses `total_value` field directly (not aggregated position_value)
- `initial_value` read from first row's `init_cash` (previously hardcoded 500000)

### 3. New Arrays Added
- `position_ratio_list` - from `position_ratio` column
- `closed_pnl_list` - from `closed_pnl` column
- `available_cash_list` - from `available_cash` column
- `position_pnl_list` - computed as `total_pnl - closed_pnl`

### 4. JSON Response (9 fields total)
- `dates`, `values`, `benchmark`, `total_return`, `annotations`
- `position_ratio`, `closed_pnl`, `available_cash`, `position_pnl` (NEW)

## Preserved Logic
- Mock fallback branch (lines 218-234) unchanged
- Benchmark fetching logic unchanged
- Max drawdown calculation unchanged
- Annotations logic unchanged

## Notes
- Used existing `round(v, 2)` convention for float values
- Used NULL handling pattern `if field else 0` for new arrays
- Flask app imports successfully after changes

---

## Task 2: Enhanced Tooltip for Equity Chart (2026-03-28)

### Changes Made
Modified `dashboard/templates/index.html` lines 564-604 to add `callbacks.label` in the `api_equity_curve` chart tooltip.

### Tooltip Configuration Added
```javascript
callbacks: {
    label: function(context) {
        var label = context.label || '';
        var formattedValue = context.formattedValue || '';
        var index = context.dataIndex;
        var positionPnl = data.position_pnl[index];
        var closedPnl = data.closed_pnl[index];
        var posRatio = data.position_ratio[index];
        var availCash = data.available_cash[index];
        var totalPnl = data.total_pnl[index];
        
        // Color coding: positive=#10b981, negative=#ef4444, zero=#94a3b8
        var colorFor = function(val) {
            if (val > 0) return '#10b981';
            if (val < 0) return '#ef4444';
            return '#94a3b8';
        };
        
        // QA logging
        console.log('TOOLTIP_DATA:', label, formattedValue, positionPnl, closedPnl, posRatio, availCash, totalPnl);
        
        return [
            '日期: ' + label,
            '总资产: ' + formattedValue + ' 万元',
            '持仓盈亏: ' + positionPnl + ' (' + colorFor(positionPnl) + ')',
            '已卖盈亏: ' + closedPnl + ' (' + colorFor(closedPnl) + ')',
            '仓位比例: ' + (posRatio * 100).toFixed(2) + '%',
            '可用资金: ' + availCash + ' 万元',
            '总盈亏: ' + totalPnl + ' (' + colorFor(totalPnl) + ')'
        ];
    }
}
```

### 7 Fields Displayed
1. **日期** - x-axis label (date)
2. **总资产** - formattedValue with '万元' suffix
3. **持仓盈亏** - position_pnl with color code in parentheses
4. **已卖盈亏** - closed_pnl with color code in parentheses
5. **仓位比例** - position_ratio as percentage (multiplied by 100, 2 decimal places)
6. **可用资金** - available_cash with '万元' suffix
7. **总盈亏** - total_pnl with color code in parentheses

### Color Coding Rules
- Positive values: `#10b981` (green)
- Negative values: `#ef4444` (red)
- Zero values: `#94a3b8` (gray)

### QA Debugging
Added `console.log('TOOLTIP_DATA:', ...)` at line 591 for tooltip data validation.

### Preserved
- 2-dataset structure (策略收益 + 基准) unchanged
- annotation plugin config unchanged
- legend config unchanged
