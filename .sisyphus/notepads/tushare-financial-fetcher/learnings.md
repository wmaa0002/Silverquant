# Tushare Financial Fetcher Implementation

## Date: 2026-04-06

## Task
Implemented `TushareIncomeFetcher`, `TushareBalanceSheetFetcher`, `TushareCashFlowFetcher` classes

## Key Decisions

1. **Field Mapping**: Used `FIELD_MAPPING` dict to map Tushare API fields to database schema fields (dwd_income, dwd_balancesheet, dwd_cashflow)

2. **report_type filtering**: Only fetch reported data (1=annual, 2=interim, 3=quarterly, 4=cumulative), excluded TTM data

3. **Interface design**: Each fetcher has:
   - `fetch_by_stock(ts_code)`: Single stock fetch
   - `fetch_all(start_date, end_date)`: Batch fetch by date range

## Schema Mappings

### dwd_income (利润表)
- basic_eps, diluted_eps, total_revenue, revenue, total_profit, profit
- income_tax, n_income, n_income_attr_p, total_cogs, operate_profit
- invest_income, non_op_income, asset_impair_loss, net_profit_with_non_recurring

### dwd_balancesheet (资产负债表)
- total_assets, total_liab, total_hldr_eqy_excl_min_int, hldr_eqy_excl_min_int
- minority_int, total_liab_ht_holder, notes_payable, accounts_payable
- advance_receipts, total_current_assets, total_non_current_assets
- fixed_assets, cip, total_current_liab, total_non_current_liab
- lt_borrow, bonds_payable

### dwd_cashflow (现金流量表)
- net_profit, fin_exp, c_fr_oper_a, c_fr_oper_a_op_ttp, c_inf_fr_oper_a
- c_paid_goods_sold, c_paid_to_for_employees, c_paid_taxes, other_cash_fr_oper_a
- n_cashflow_act, c_fr_oper_b, c_fr_inv_a, c_to_inv_a, c_fr_fin_a, c_to_fin_a
- n_cash_in_fin_a, n_cash_in_op_b, n_cash_out_inv_b, n_cash_out_fin_b
- n_cash_in_op_c, n_cash_out_inv_c, n_cash_out_fin_c, end_cash, cap_crisis_shrg

## Files Created
- `data/fetchers/tushare_adapter/financial.py` - Main implementation

## Notes
- All fetchers inherit from `TushareBaseFetcher` which provides token management, rate limiting, retry mechanism
- Data source is marked as 'tushare' in each record
