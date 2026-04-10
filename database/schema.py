"""
数据库表结构定义
多因子数据存储 + 回测结果多维度分析支持
"""

# DEPRECATED: Use dwd_stock_info table instead
CREATE_STOCK_INFO_TABLE = """
CREATE TABLE IF NOT EXISTS stock_info (
    code VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    industry VARCHAR,
    industry_sw2 VARCHAR,
    market_cap FLOAT,
    circulating_cap FLOAT,
    listing_date DATE,
    market_type VARCHAR,
    is_st BOOLEAN DEFAULT FALSE,
    is_delisted BOOLEAN DEFAULT FALSE,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# DEPRECATED: Use dwd_daily_price table instead
# daily_price table removed - use dwd_daily_price directly
# DEPRECATED: Minute price storage pending migration
CREATE_MINUTE_PRICE_TABLE = """
CREATE TABLE IF NOT EXISTS minute_price (
    datetime TIMESTAMP,
    code VARCHAR,
    open FLOAT,
    high FLOAT,
    low FLOAT,
    close FLOAT,
    volume BIGINT,
    amount FLOAT,
    freq VARCHAR,
    PRIMARY KEY (datetime, code, freq)
);
"""

CREATE_FACTOR_DATA_TABLE = """
CREATE TABLE IF NOT EXISTS factor_data (
    date DATE,
    code VARCHAR,
    
    -- 估值因子
    pe_ttm FLOAT,
    pb FLOAT,
    ps_ttm FLOAT,
    pcf_ttm FLOAT,
    dividend_yield FLOAT,
    
    -- 质量因子
    roe FLOAT,
    roa FLOAT,
    gross_margin FLOAT,
    net_margin FLOAT,
    debt_to_asset FLOAT,
    
    -- 成长因子
    revenue_growth_yoy FLOAT,
    profit_growth_yoy FLOAT,
    revenue_growth_qoq FLOAT,
    profit_growth_qoq FLOAT,
    
    -- 技术因子
    macd_dif FLOAT,
    macd_dea FLOAT,
    macd_histogram FLOAT,
    kdj_k FLOAT,
    kdj_d FLOAT,
    kdj_j FLOAT,
    rsi_6 FLOAT,
    rsi_12 FLOAT,
    rsi_24 FLOAT,
    boll_upper FLOAT,
    boll_mid FLOAT,
    boll_lower FLOAT,
    ma_5 FLOAT,
    ma_10 FLOAT,
    ma_20 FLOAT,
    ma_60 FLOAT,
    volatility_20d FLOAT,
    turnover_20d FLOAT,
    
    -- 情绪因子
    volume_ratio FLOAT,
    price_momentum_20d FLOAT,
    price_momentum_60d FLOAT,
    
    -- 自定义因子
    custom_factor_1 FLOAT,
    custom_factor_2 FLOAT,
    custom_factor_3 FLOAT,
    custom_factor_4 FLOAT,
    custom_factor_5 FLOAT,
    
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date, code)
);
"""

CREATE_INDUSTRY_CLASSIFICATION_TABLE = """
CREATE TABLE IF NOT EXISTS industry_classification (
    code VARCHAR PRIMARY KEY,
    name VARCHAR,
    industry_sw1 VARCHAR,
    industry_sw2 VARCHAR,
    industry_sw3 VARCHAR,
    industry_citic1 VARCHAR,
    industry_citic2 VARCHAR,
    industry_zjw VARCHAR,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_MARKET_CAP_GROUP_TABLE = """
CREATE TABLE IF NOT EXISTS market_cap_group (
    date DATE,
    code VARCHAR,
    market_cap FLOAT,
    circulating_cap FLOAT,
    market_cap_rank INT,
    cap_group VARCHAR,
    cap_group_detail VARCHAR,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date, code)
);
"""

CREATE_BACKTEST_RUN_TABLE = """
CREATE TABLE IF NOT EXISTS backtest_run (
    run_id VARCHAR PRIMARY KEY,
    strategy_name VARCHAR NOT NULL,
    strategy_params JSON,
    start_date DATE,
    end_date DATE,
    universe VARCHAR,
    benchmark VARCHAR,
    initial_capital FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR DEFAULT 'running',
    error_message VARCHAR
);
"""

CREATE_BACKTEST_TRADES_TABLE = """
CREATE TABLE IF NOT EXISTS backtest_trades (
    id BIGINT,
    run_id VARCHAR,
    date DATE,
    datetime TIMESTAMP,
    code VARCHAR,
    name VARCHAR,
    industry VARCHAR,
    market_cap_group VARCHAR,
    action VARCHAR,
    price FLOAT,
    volume INTEGER,
    amount FLOAT,
    commission FLOAT,
    tax FLOAT,
    total_cost FLOAT,
    signal_type VARCHAR,
    PRIMARY KEY (run_id, id)
);
"""

CREATE_BACKTEST_DAILY_PNL_TABLE = """
CREATE TABLE IF NOT EXISTS backtest_daily_pnl (
    run_id VARCHAR,
    date DATE,
    total_value FLOAT,
    cash FLOAT,
    market_value FLOAT,
    daily_pnl FLOAT,
    daily_return FLOAT,
    cumulative_return FLOAT,
    benchmark_return FLOAT,
    excess_return FLOAT,
    drawdown FLOAT,
    positions JSON,
    PRIMARY KEY (run_id, date)
);
"""

CREATE_BACKTEST_PERFORMANCE_TABLE = """
CREATE TABLE IF NOT EXISTS backtest_performance (
    run_id VARCHAR PRIMARY KEY,
    
    -- 收益指标
    total_return FLOAT,
    annualized_return FLOAT,
    benchmark_return FLOAT,
    excess_return FLOAT,
    
    -- 风险指标
    volatility FLOAT,
    max_drawdown FLOAT,
    max_drawdown_duration INT,
    var_95 FLOAT,
    
    -- 风险调整收益
    sharpe_ratio FLOAT,
    sortino_ratio FLOAT,
    calmar_ratio FLOAT,
    information_ratio FLOAT,
    
    -- 交易统计
    total_trades INT,
    winning_trades INT,
    losing_trades INT,
    win_rate FLOAT,
    avg_profit FLOAT,
    avg_loss FLOAT,
    profit_loss_ratio FLOAT,
    
    -- 多维度分析结果
    industry_analysis JSON,
    cap_group_analysis JSON,
    monthly_returns JSON,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_FACTOR_IC_TABLE = """
CREATE TABLE IF NOT EXISTS factor_ic (
    date DATE,
    factor_name VARCHAR,
    ic FLOAT,
    ic_rank FLOAT,
    ir FLOAT,
    ic_positive_ratio FLOAT,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date, factor_name)
);
"""

CREATE_FACTOR_RETURN_TABLE = """
CREATE TABLE IF NOT EXISTS factor_return (
    date DATE,
    factor_name VARCHAR,
    long_return FLOAT,
    short_return FLOAT,
    long_short_return FLOAT,
    quantile_returns JSON,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date, factor_name)
);
"""

# ============== 量化信号系统表 ==============

CREATE_STRATEGIES_TABLE = """
CREATE TABLE IF NOT EXISTS strategies (
    id INTEGER PRIMARY KEY,
    name VARCHAR,
    signal_type VARCHAR,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_DAILY_SIGNALS_TABLE = """
CREATE TABLE IF NOT EXISTS daily_signals (
    date DATE,
    code VARCHAR,
    name VARCHAR,
    
    -- OHLC数据
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume BIGINT,
    amount DOUBLE,
    prev_close DOUBLE,
    change_pct DOUBLE,
    涨停价 DOUBLE,
    跌停价 DOUBLE,
    涨停 BOOLEAN,
    跌停 BOOLEAN,
    一字涨停 BOOLEAN,
    
    -- 买入分数
    score_b1 DOUBLE,
    score_b2 DOUBLE,
    score_blk DOUBLE,
    score_dl DOUBLE,
    score_dz30 DOUBLE,
    score_scb DOUBLE,
    
    -- 买入信号
    signal_buy_b1 BOOLEAN,
    signal_buy_b2 BOOLEAN,
    signal_buy_blk BOOLEAN,
    signal_buy_dl BOOLEAN,
    signal_buy_dz30 BOOLEAN,
    signal_buy_scb BOOLEAN,
    signal_buy_blkB2 BOOLEAN,

    -- 策略卖出信号
    signal_sell_b1 BOOLEAN,
    signal_sell_b2 BOOLEAN,
    signal_sell_blk BOOLEAN,
    signal_sell_dl BOOLEAN,
    signal_sell_dz30 BOOLEAN,
    signal_sell_scb BOOLEAN,
    signal_sell_blkB2 BOOLEAN,
    
    -- 卖出分数
    score_s1 DOUBLE,
    
    -- 分数卖出信号
    signal_s1_full BOOLEAN,
    signal_s1_half BOOLEAN,
    signal_跌破多空线 BOOLEAN,
    signal_止损 BOOLEAN,
    
    -- 技术指标
    indicators JSON,
    
    PRIMARY KEY (date, code)
);
"""

CREATE_POSITIONS_TABLE = """
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY,
    code VARCHAR,
    name VARCHAR,
    strategy VARCHAR,
    
    -- 买入信息
    buy_date DATE,
    shares INTEGER,
    buy_price DOUBLE,
    buy_change_pct DOUBLE,
    
    -- 买入时关键指标
    buy_score_b1 DOUBLE,
    buy_score_b2 DOUBLE,
    buy_dif DOUBLE,
    buy_j_value DOUBLE,
    buy_知行短期趋势线 DOUBLE,
    buy_知行多空线 DOUBLE,
    
    -- 当前信息
    current_price DOUBLE,
    current_score_s1 DOUBLE,
    current_跌破多空线 BOOLEAN,
    
    -- 止损参数
    stop_loss_pct DOUBLE DEFAULT 0.03,
    
    -- 状态
    status VARCHAR DEFAULT 'holding',
    sell_date DATE,
    sell_price DOUBLE,
    sell_reason VARCHAR,
    profit_loss DOUBLE,
    profit_pct DOUBLE,
    
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_PORTFOLIO_DAILY_TABLE = """
CREATE TABLE IF NOT EXISTS portfolio_daily (
    id              INTEGER PRIMARY KEY,
    date            DATE NOT NULL UNIQUE,          -- 日期
    
    -- 资金基础
    init_cash       DECIMAL(12,2) NOT NULL,        -- 初始资金
    position_cost   DECIMAL(12,2) NOT NULL,        -- 持仓成本（买入价*数量*手续费）
    position_value  DECIMAL(12,2) NOT NULL,        -- 持仓市值（现价*数量）
    
    -- 盈亏计算
    position_pnl    DECIMAL(12,2) NOT NULL,       -- 持仓盈亏 = position_value - position_cost
    closed_pnl      DECIMAL(12,2) NOT NULL DEFAULT 0,  -- 已卖出盈亏（历史累计）
    total_pnl       DECIMAL(12,2) NOT NULL,        -- 总盈亏 = position_pnl + closed_pnl
    
    -- 资金余额
    available_cash  DECIMAL(12,2) NOT NULL,        -- 可用资金 = init_cash - position_cost + closed_pnl
    
    -- 仓位
    position_ratio  DECIMAL(5,2) NOT NULL,         -- 仓位比例 = position_value / init_cash * 100
    
    -- 附加信息
    notes           VARCHAR(500),                   -- 备注（可选）
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_portfolio_date ON portfolio_daily(date);
"""

# ============== 数据流水线表 ==============

CREATE_TABLE_DATA_PIPELINE_RUN = """
CREATE TABLE IF NOT EXISTS data_pipeline_run (
    id              INTEGER PRIMARY KEY,
    pipeline_id     VARCHAR,          -- 流水线ID (如 "daily_20260323")
    pipeline_name   VARCHAR,           -- 流水线名称 (如 "daily", "weekly")
    step_name       VARCHAR,           -- 步骤名: "stock_info", "daily_price", "signals", "trade"
    step_order      INT,              -- 步骤序号: 1, 2, 3, 4
    
    -- 时间戳
    created_at      TIMESTAMP,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    duration_sec    FLOAT,
    
    -- 运行参数
    params          JSON,             -- {"start_date": "20260323", "end_date": "..."}
    
    -- 状态
    status          VARCHAR,          -- pending, running, success, failed, skipped
    
    -- 结果
    records_count   INT,              -- 处理的记录数
    error_message   TEXT,
    
    -- 前置条件检查
    depends_on      VARCHAR,          -- 依赖的step_name
    dependency_met  BOOLEAN,          -- 依赖是否满足
    
    UNIQUE(pipeline_id, step_name)
);
"""

CREATE_TABLE_STEP_UPDATE_LOG = """
CREATE TABLE IF NOT EXISTS step_update_log (
    id                  INTEGER PRIMARY KEY,
    pipeline_id         VARCHAR,       -- 流水线ID
    step_name           VARCHAR,       -- 步骤名
    update_type         VARCHAR,       -- 'full', 'incremental', 'daily'
    
    -- 时间
    update_time         TIMESTAMP,     -- 检测时间
    start_time          TIMESTAMP,     -- 更新开始时间
    end_time            TIMESTAMP,     -- 更新结束时间
    duration_sec        FLOAT,         -- 更新耗时（秒）
    
    -- 数量统计
    expected_count      INT,           -- 预期数量
    actual_count        INT,           -- 实际入库数量
    
    -- 状态
    is_success          BOOLEAN,       -- 是否成功
    error_message       TEXT,
    error_details       JSON,          -- 错误详情（堆栈等）
    
    -- 步骤特定字段
    step_details        JSON,          -- 步骤特定详情
    
    -- 公共检查结果
    validation_results  JSON,          -- 验证检查结果
    
    check_time          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ============== 指数数据表 ==============

# DEPRECATED: Use dwd_trade_calendar for date tracking
CREATE_INDEX_INFO_TABLE = """
CREATE TABLE IF NOT EXISTS index_info (
    ts_code VARCHAR PRIMARY KEY,      -- TS指数代码
    name VARCHAR,                      -- 简称
    fullname VARCHAR,                  -- 指数全称
    market VARCHAR,                     -- 市场
    publisher VARCHAR,                  -- 发布方
    index_type VARCHAR,                 -- 指数风格
    category VARCHAR,                   -- 指数类别
    base_date VARCHAR,                  -- 基期
    base_point FLOAT,                   -- 基点
    list_date VARCHAR,                  -- 发布日期
    weight_rule VARCHAR,                -- 加权方式
    description VARCHAR,                 -- 描述
    exp_date VARCHAR                   -- 终止日期
);
"""

# DEPRECATED: Use dwd_index_daily table instead
CREATE_INDEX_DAILY_TABLE = """
CREATE TABLE IF NOT EXISTS index_daily (
    trade_date DATE,
    ts_code VARCHAR,
    close FLOAT,                       -- 收盘点位
    open FLOAT,                         -- 开盘点位
    high FLOAT,                         -- 最高点位
    low FLOAT,                          -- 最低点位
    pre_close FLOAT,                     -- 昨日收盘点
    change_amount FLOAT,                 -- 涨跌点
    pct_chg FLOAT,                       -- 涨跌幅(%)
    vol FLOAT,                           -- 成交量(手)
    amount FLOAT,                        -- 成交额(千元)
    PRIMARY KEY (trade_date, ts_code)
);
"""

# ============== DWD层数据表（统一数据仓库 Detail层） ==============

CREATE_DWD_DAILY_PRICE_TABLE = """
CREATE TABLE IF NOT EXISTS dwd_daily_price (
    trade_date DATE,
    ts_code VARCHAR,
    open FLOAT,
    high FLOAT,
    low FLOAT,
    close FLOAT,
    vol BIGINT,
    amount DOUBLE,
    pct_chg DOUBLE,
    data_source VARCHAR DEFAULT 'tushare',
    PRIMARY KEY (trade_date, ts_code)
);
"""

CREATE_DWD_DAILY_BASIC_TABLE = """
CREATE TABLE IF NOT EXISTS dwd_daily_basic (
    trade_date DATE,
    ts_code VARCHAR,
    close DOUBLE,
    pe_ttm DOUBLE,
    pe DOUBLE,
    ps_ttm DOUBLE,
    ps DOUBLE,
    pcf DOUBLE,
    pb DOUBLE,
    total_mv DOUBLE,
    circ_mv DOUBLE,
    amount DOUBLE,
    turn_rate DOUBLE,
    data_source VARCHAR DEFAULT 'tushare',
    PRIMARY KEY (trade_date, ts_code)
);
"""

CREATE_DWD_ADJ_FACTOR_TABLE = """
CREATE TABLE IF NOT EXISTS dwd_adj_factor (
    ts_code VARCHAR,
    trade_date DATE,
    adj_factor DOUBLE,
    data_source VARCHAR DEFAULT 'tushare',
    PRIMARY KEY (ts_code, trade_date)
);
"""

CREATE_DWD_DAILY_PRICE_QFQ_TABLE = """
CREATE TABLE IF NOT EXISTS dwd_daily_price_qfq (
    ts_code VARCHAR,
    trade_date DATE,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    vol BIGINT,
    amount DOUBLE,
    pct_chg DOUBLE,
    adj_factor DOUBLE,
    data_source VARCHAR DEFAULT 'tushare',
    PRIMARY KEY (trade_date, ts_code)
);
"""

CREATE_DWD_DAILY_PRICE_HFQ_TABLE = """
CREATE TABLE IF NOT EXISTS dwd_daily_price_hfq (
    ts_code VARCHAR,
    trade_date DATE,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    vol BIGINT,
    amount DOUBLE,
    pct_chg DOUBLE,
    adj_factor DOUBLE,
    data_source VARCHAR DEFAULT 'tushare',
    PRIMARY KEY (trade_date, ts_code)
);
"""

CREATE_DWD_INCOME_TABLE = """
CREATE TABLE IF NOT EXISTS dwd_income (
    ts_code VARCHAR,
    ann_date DATE,
    f_ann_date DATE,
    end_date DATE,
    report_type VARCHAR,
    comp_type VARCHAR,
    basic_eps DOUBLE,
    diluted_eps DOUBLE,
    total_revenue DOUBLE,
    revenue DOUBLE,
    total_profit DOUBLE,
    profit DOUBLE,
    income_tax DOUBLE,
    n_income DOUBLE,
    n_income_attr_p DOUBLE,
    total_cogs DOUBLE,
    operate_profit DOUBLE,
    invest_income DOUBLE,
    non_op_income DOUBLE,
    asset_impair_loss DOUBLE,
    net_profit_with_non_recurring DOUBLE,
    data_source VARCHAR DEFAULT 'tushare',
    PRIMARY KEY (ts_code, ann_date, end_date, report_type)
);
"""

CREATE_DWD_BALANCESHEET_TABLE = """
CREATE TABLE IF NOT EXISTS dwd_balancesheet (
    ts_code VARCHAR,
    ann_date DATE,
    f_ann_date DATE,
    end_date DATE,
    report_type VARCHAR,
    comp_type VARCHAR,
    total_assets DOUBLE,
    total_liab DOUBLE,
    total_hldr_eqy_excl_min_int DOUBLE,
    hldr_eqy_excl_min_int DOUBLE,
    minority_int DOUBLE,
    total_liab_ht_holder DOUBLE,
    notes_payable DOUBLE,
    accounts_payable DOUBLE,
    advance_receipts DOUBLE,
    total_current_assets DOUBLE,
    total_non_current_assets DOUBLE,
    fixed_assets DOUBLE,
    cip DOUBLE,
    total_current_liab DOUBLE,
    total_non_current_liab DOUBLE,
    lt_borrow DOUBLE,
    bonds_payable DOUBLE,
    data_source VARCHAR DEFAULT 'tushare',
    PRIMARY KEY (ts_code, ann_date, end_date, report_type)
);
"""

CREATE_DWD_CASHFLOW_TABLE = """
CREATE TABLE IF NOT EXISTS dwd_cashflow (
    ts_code VARCHAR,
    ann_date DATE,
    f_ann_date DATE,
    end_date DATE,
    report_type VARCHAR,
    comp_type VARCHAR,
    net_profit DOUBLE,
    fin_exp DOUBLE,
    c_fr_oper_a DOUBLE,
    c_fr_oper_a_op_ttp DOUBLE,
    c_inf_fr_oper_a DOUBLE,
    c_paid_goods_sold DOUBLE,
    c_paid_to_for_employees DOUBLE,
    c_paid_taxes DOUBLE,
    other_cash_fr_oper_a DOUBLE,
    n_cashflow_act DOUBLE,
    c_fr_oper_b DOUBLE,
    c_fr_inv_a DOUBLE,
    c_to_inv_a DOUBLE,
    c_fr_fin_a DOUBLE,
    c_to_fin_a DOUBLE,
    n_cash_in_fin_a DOUBLE,
    n_cash_in_op_b DOUBLE,
    n_cash_out_inv_b DOUBLE,
    n_cash_out_fin_b DOUBLE,
    n_cash_in_op_c DOUBLE,
    n_cash_out_inv_c DOUBLE,
    n_cash_out_fin_c DOUBLE,
    end_cash DOUBLE,
    cap_crisis_shrg DOUBLE,
    data_source VARCHAR DEFAULT 'tushare',
    PRIMARY KEY (ts_code, ann_date, end_date, report_type)
);
"""

CREATE_DWD_INDEX_DAILY_TABLE = """
CREATE TABLE IF NOT EXISTS dwd_index_daily (
    index_code VARCHAR,
    trade_date DATE,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    pre_close DOUBLE,
    change DOUBLE,
    pct_change DOUBLE,
    vol BIGINT,
    amount DOUBLE,
    data_source VARCHAR DEFAULT 'tushare',
    PRIMARY KEY (index_code, trade_date)
);
"""

CREATE_DWD_STOCK_INFO_TABLE = """
CREATE TABLE IF NOT EXISTS dwd_stock_info (
    ts_code VARCHAR PRIMARY KEY,
    symbol VARCHAR,
    name VARCHAR,
    area VARCHAR,
    industry VARCHAR,
    market VARCHAR,
    list_date DATE,
    is_hs VARCHAR,
    act_name VARCHAR,
    data_source VARCHAR DEFAULT 'tushare'
);
"""

CREATE_DWD_TRADE_CALENDAR_TABLE = """
CREATE TABLE IF NOT EXISTS dwd_trade_calendar (
    trade_date DATE,
    exchange VARCHAR,
    is_open BOOLEAN,
    PRIMARY KEY (trade_date, exchange)
);
"""

# ============== 运营监控表 ==============

CREATE_AGENT_ANALYSIS_RESULTS_TABLE = """
CREATE TABLE IF NOT EXISTS agent_analysis_results (
    run_id VARCHAR,
    symbol VARCHAR,
    trade_date VARCHAR,
    result_json VARCHAR,
    created_at TIMESTAMP
);
"""

CREATE_PIPELINE_MONITOR_FLAG_TABLE = """
CREATE TABLE IF NOT EXISTS pipeline_monitor_flag (
    id INTEGER,
    date VARCHAR,
    completed BOOLEAN,
    completed_at TIMESTAMP
);
"""

CREATE_TRADE_AUDIT_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS trade_audit_log (
    id INTEGER,
    audit_date DATE,
    check_item VARCHAR,
    check_type VARCHAR,
    severity VARCHAR,
    status VARCHAR,
    detail VARCHAR,
    fix_action VARCHAR,
    before_val VARCHAR,
    after_val VARCHAR,
    auditor VARCHAR,
    created_at TIMESTAMP
);
"""

CREATE_PORTFOLIO_DAILY_STRATEGY_TABLE = """
CREATE TABLE IF NOT EXISTS portfolio_daily_strategy (
    id INTEGER,
    date DATE,
    strategy VARCHAR,
    position_cost DECIMAL(12,2),
    position_value DECIMAL(12,2),
    position_pnl DECIMAL(12,2),
    closed_pnl DECIMAL(12,2),
    total_pnl DECIMAL(12,2),
    trade_count INTEGER,
    notes VARCHAR,
    created_at TIMESTAMP
);
"""

# ============== VIEW层（向后兼容） ==============
# VIEWs map old table names to new dwd_* tables for backward compatibility

CREATE_VIEW_DAILY_BASIC = """
CREATE OR REPLACE VIEW daily_basic AS
SELECT
    trade_date,
    ts_code,
    close,
    pe_ttm,
    pe,
    ps_ttm,
    ps,
    pcf,
    pb,
    total_mv,
    circ_mv,
    amount,
    turn_rate,
    data_source
FROM dwd_daily_basic;
"""

CREATE_VIEW_INDEX_DAILY = """
CREATE OR REPLACE VIEW index_daily AS
SELECT
    trade_date,
    index_code AS ts_code,
    open,
    high,
    low,
    close,
    vol,
    amount,
    pct_change,
    data_source
FROM dwd_index_daily;
"""

CREATE_VIEW_STOCK_INFO = """
CREATE OR REPLACE VIEW stock_info AS
SELECT
    ts_code AS code,
    symbol,
    name,
    area,
    industry,
    market,
    list_date AS listing_date,
    is_hs,
    act_name AS act_name,
    data_source
FROM dwd_stock_info;
"""

# 所有表的创建语句列表
ALL_TABLES = [
    CREATE_STOCK_INFO_TABLE,
    CREATE_MINUTE_PRICE_TABLE,
    CREATE_FACTOR_DATA_TABLE,
    CREATE_INDUSTRY_CLASSIFICATION_TABLE,
    CREATE_MARKET_CAP_GROUP_TABLE,
    CREATE_BACKTEST_RUN_TABLE,
    CREATE_BACKTEST_TRADES_TABLE,
    CREATE_BACKTEST_DAILY_PNL_TABLE,
    CREATE_BACKTEST_PERFORMANCE_TABLE,
    CREATE_FACTOR_IC_TABLE,
    CREATE_FACTOR_RETURN_TABLE,
    CREATE_STRATEGIES_TABLE,
    CREATE_DAILY_SIGNALS_TABLE,
    CREATE_POSITIONS_TABLE,
    CREATE_PORTFOLIO_DAILY_TABLE,
    CREATE_TABLE_DATA_PIPELINE_RUN,
    CREATE_TABLE_STEP_UPDATE_LOG,
    CREATE_INDEX_INFO_TABLE,
    CREATE_INDEX_DAILY_TABLE,
    CREATE_DWD_DAILY_PRICE_TABLE,
    CREATE_DWD_DAILY_BASIC_TABLE,
    CREATE_DWD_ADJ_FACTOR_TABLE,
    CREATE_DWD_INCOME_TABLE,
    CREATE_DWD_BALANCESHEET_TABLE,
    CREATE_DWD_CASHFLOW_TABLE,
    CREATE_DWD_INDEX_DAILY_TABLE,
    CREATE_DWD_STOCK_INFO_TABLE,
    CREATE_DWD_TRADE_CALENDAR_TABLE,
    CREATE_DWD_DAILY_PRICE_QFQ_TABLE,
    CREATE_DWD_DAILY_PRICE_HFQ_TABLE,
    # 运营监控表
    CREATE_AGENT_ANALYSIS_RESULTS_TABLE,
    CREATE_PIPELINE_MONITOR_FLAG_TABLE,
    CREATE_TRADE_AUDIT_LOG_TABLE,
    CREATE_PORTFOLIO_DAILY_STRATEGY_TABLE,
    # VIEWs - 已禁用，与现有 TABLE 冲突
    # CREATE_VIEW_DAILY_BASIC,
    # CREATE_VIEW_INDEX_DAILY,
    # CREATE_VIEW_STOCK_INFO,
]


def create_tables(conn):
    """创建所有数据库表"""
    cursor = conn.cursor()
    for table_sql in ALL_TABLES:
        cursor.execute(table_sql)
    conn.commit()
    print("所有数据表创建成功")


def drop_tables(conn):
    """删除所有数据库表（危险操作！）"""
    cursor = conn.cursor()
    tables = [
        'stock_info', 'daily_price', 'minute_price', 'factor_data',
        'industry_classification', 'market_cap_group',
        'backtest_run', 'backtest_trades', 'backtest_daily_pnl', 'backtest_performance',
        'factor_ic', 'factor_return',
        'strategies', 'daily_signals', 'positions'
    ]
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()
    print("所有数据表已删除")
