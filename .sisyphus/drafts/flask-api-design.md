# Flask API + 数据库集成详细方案

> **生成时间**: 2026-03-29
> **模块**: Day 6 任务 T26-T29

---

## 1. 现有系统分析

### 1.1 现有Flask结构

```python
# dashboard/app.py

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'Astock3.duckdb')

# 现有API:
# - GET /                  - 首页
# - GET /api/positions     - 持仓列表
# - GET /api/history       - 历史交易
# - GET /api/backtest      - 回测结果
# - ...
```

### 1.2 现有数据库表

```
DuckDB: data/Astock3.duckdb

现有表:
- stock_info        - 股票基础信息
- daily_price       - 日线数据
- factor_data       - 因子数据
- positions         - 持仓记录
- backtest_run      - 回测运行
- backtest_trades   - 回测交易
- backtest_daily_pnl - 回测每日盈亏
```

---

## 2. 新增数据库设计

### 2.1 分析结果表

```sql
-- agent_analysis 表: 存储AI分析结果
CREATE TABLE IF NOT EXISTS agent_analysis (
    id              VARCHAR(20) PRIMARY KEY,      -- 分析ID, 格式: ag_YYYYMMDDHHMMSS_XXXX
    symbol          VARCHAR(10) NOT NULL,        -- 股票代码
    stock_name      VARCHAR(50),                 -- 股票名称
    trade_date      DATE NOT NULL,              -- 分析日期
    
    -- 分析结果
    final_decision  VARCHAR(10) NOT NULL,       -- BUY/HOLD/SELL
    confidence      FLOAT,                       -- 置信度 0-1
    risk_level      VARCHAR(10),                 -- LOW/MEDIUM/HIGH
    
    -- 交易信号
    action          VARCHAR(10),                 -- BUY/SELL/HOLD
    entry_price     FLOAT,                      -- 入场价格
    stop_loss       FLOAT,                      -- 止损价格
    take_profit     FLOAT,                      -- 止盈价格
    position_size   FLOAT,                      -- 仓位 0-1
    
    -- 详细报告 (JSON格式)
    reports         JSON,                       -- 各分析师报告
    bull_points     JSON,                       -- 看涨论点
    bear_points     JSON,                       -- 看跌论点
    risk_assessment JSON,                       -- 风险评估
    
    -- 执行信息
    provider        VARCHAR(20),                 -- LLM提供商
    model           VARCHAR(50),                 -- LLM模型
    token_usage     JSON,                       -- Token使用统计
    execution_time  FLOAT,                      -- 执行时间(秒)
    
    -- 元数据
    created_at      TIMESTAMP DEFAULT NOW(),
    status          VARCHAR(20) DEFAULT 'completed'  -- pending/completed/failed
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_agent_analysis_symbol ON agent_analysis(symbol);
CREATE INDEX IF NOT EXISTS idx_agent_analysis_date ON agent_analysis(trade_date);
CREATE INDEX IF NOT EXISTS idx_agent_analysis_decision ON agent_analysis(final_decision);
```

### 2.2 Token使用表 (可选)

```sql
-- agent_token_usage 表: Token使用记录
CREATE TABLE IF NOT EXISTS agent_token_usage (
    id              VARCHAR(20) PRIMARY KEY,
    date            DATE NOT NULL,
    provider        VARCHAR(20),                 -- deepseek/minimax/dashscope
    model           VARCHAR(50),
    prompt_tokens   BIGINT DEFAULT 0,
    completion_tokens BIGINT DEFAULT 0,
    total_tokens    BIGINT DEFAULT 0,
    request_count   INTEGER DEFAULT 0,
    estimated_cost  FLOAT DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_token_usage_date ON agent_token_usage(date);
```

---

## 3. 适配器设计

### 3.1 ResultAdapter (结果存储)

```python
# agent_integration/adapters/result_adapter.py

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from database.db_manager import DatabaseManager

class ResultAdapter:
    """分析结果存储适配器"""
    
    TABLE_NAME = 'agent_analysis'
    
    def __init__(self):
        self._db = DatabaseManager.get_instance()
    
    def _generate_id(self) -> str:
        """生成分析ID: ag_YYYYMMDDHHMMSS_XXXX"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_suffix = str(uuid.uuid4())[:4]
        return f"ag_{timestamp}_{random_suffix}"
    
    def save_analysis_result(
        self,
        symbol: str,
        stock_name: str,
        trade_date: str,
        result: Dict,
        provider: str = None,
        model: str = None
    ) -> str:
        """
        保存分析结果到DuckDB
        
        Args:
            symbol: 股票代码
            stock_name: 股票名称
            trade_date: 分析日期
            result: 分析结果字典
            provider: LLM提供商
            model: LLM模型
            
        Returns:
            str: 分析ID
        """
        analysis_id = self._generate_id()
        
        # 提取数据
        final_decision = result.get('final_decision', 'HOLD')
        confidence = result.get('confidence', 0.0)
        risk_level = result.get('risk_level', 'MEDIUM')
        
        # 交易信号
        trading_signal = result.get('trading_signal', {})
        action = trading_signal.get('action', 'HOLD')
        entry_price = trading_signal.get('entry_price')
        stop_loss = trading_signal.get('stop_loss')
        take_profit = trading_signal.get('take_profit')
        position_size = trading_signal.get('position_size')
        
        # 详细报告
        reports = result.get('reports', {})
        bull_points = result.get('bull_points', [])
        bear_points = result.get('bear_points', [])
        risk_assessment = result.get('risk_assessment', {})
        
        # Token使用
        token_usage = result.get('token_usage', {})
        
        # 执行时间
        execution_time = result.get('execution_time', 0.0)
        
        # 构建SQL
        sql = f"""
        INSERT INTO {self.TABLE_NAME} (
            id, symbol, stock_name, trade_date,
            final_decision, confidence, risk_level,
            action, entry_price, stop_loss, take_profit, position_size,
            reports, bull_points, bear_points, risk_assessment,
            provider, model, token_usage, execution_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = [
            analysis_id,
            symbol,
            stock_name,
            trade_date,
            final_decision,
            confidence,
            risk_level,
            action,
            entry_price,
            stop_loss,
            take_profit,
            position_size,
            json.dumps(reports, ensure_ascii=False),
            json.dumps(bull_points, ensure_ascii=False),
            json.dumps(bear_points, ensure_ascii=False),
            json.dumps(risk_assessment, ensure_ascii=False),
            provider,
            model,
            json.dumps(token_usage, ensure_ascii=False),
            execution_time
        ]
        
        self._db.execute(sql, params)
        
        return analysis_id
    
    def load_analysis_result(self, analysis_id: str) -> Optional[Dict]:
        """加载分析结果"""
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE id = ?"
        row = self._db.execute(sql, [analysis_id]).fetchone()
        
        if not row:
            return None
        
        return self._row_to_dict(row)
    
    def get_analysis_history(
        self,
        symbol: str = None,
        start_date: str = None,
        end_date: str = None,
        decision: str = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        获取分析历史
        
        Args:
            symbol: 股票代码过滤
            start_date: 开始日期
            end_date: 结束日期
            decision: 决策过滤 (BUY/HOLD/SELL)
            limit: 返回数量
            
        Returns:
            List[Dict]: 分析结果列表
        """
        conditions = []
        params = []
        
        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol)
        
        if start_date:
            conditions.append("trade_date >= ?")
            params.append(start_date)
        
        if end_date:
            conditions.append("trade_date <= ?")
            params.append(end_date)
        
        if decision:
            conditions.append("final_decision = ?")
            params.append(decision)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        sql = f"""
        SELECT * FROM {self.TABLE_NAME}
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
        """
        params.append(limit)
        
        rows = self._db.execute(sql, params).fetchall()
        
        return [self._row_to_dict(row) for row in rows]
    
    def _row_to_dict(self, row) -> Dict:
        """将数据库行转换为字典"""
        columns = [
            'id', 'symbol', 'stock_name', 'trade_date',
            'final_decision', 'confidence', 'risk_level',
            'action', 'entry_price', 'stop_loss', 'take_profit', 'position_size',
            'reports', 'bull_points', 'bear_points', 'risk_assessment',
            'provider', 'model', 'token_usage', 'execution_time',
            'created_at', 'status'
        ]
        
        result = {}
        for i, col in enumerate(columns):
            value = row[i]
            if col in ('reports', 'bull_points', 'bear_points', 'risk_assessment', 'token_usage'):
                if value and isinstance(value, str):
                    try:
                        result[col] = json.loads(value)
                    except:
                        result[col] = value
                else:
                    result[col] = value
            elif col in ('entry_price', 'stop_loss', 'take_profit', 'position_size', 'confidence', 'execution_time'):
                result[col] = float(value) if value else None
            else:
                result[col] = value
        
        return result
```

### 3.2 ConfigAdapter (配置适配)

```python
# agent_integration/adapters/config_adapter.py

import os
from typing import Optional
from config.settings import Settings

class ConfigAdapter:
    """
    配置适配器 - 对接Settings到TradingAgents
    """
    
    # LLM配置
    @classmethod
    def get_llm_provider(cls) -> str:
        """获取LLM提供商"""
        return getattr(Settings, 'LLM_PROVIDER', None) or os.environ.get('LLM_PROVIDER', 'minimax')
    
    @classmethod
    def get_llm_model(cls) -> str:
        """获取LLM模型"""
        return getattr(Settings, 'LLM_MODEL', None) or os.environ.get('LLM_MODEL', 'M2.1')
    
    @classmethod
    def get_llm_api_key(cls, provider: str = None) -> Optional[str]:
        """获取LLM API Key"""
        provider = provider or cls.get_llm_provider()
        
        # 按优先级查找
        env_vars = {
            'minimax': ['MINIMAX_API_KEY', 'MINIMAX_KEY'],
            'deepseek': ['DEEPSEEK_API_KEY', 'DEEPSEEK_KEY'],
            'dashscope': ['DASHSCOPE_API_KEY', 'DASHSCOPE_KEY'],
            'qianfan': ['QIANFAN_API_KEY'],
            'zhipu': ['ZHIPU_API_KEY', 'ZHIPUAI_API_KEY'],
            'google': ['GOOGLE_API_KEY'],
        }
        
        for env_var in env_vars.get(provider, []):
            api_key = os.environ.get(env_var)
            if api_key:
                return api_key
        
        return None
    
    @classmethod
    def get_minimax_group_id(cls) -> Optional[str]:
        """获取MiniMax Group ID"""
        return os.environ.get('MINIMAX_GROUP_ID')
    
    # 数据源配置
    @classmethod
    def get_data_source(cls) -> str:
        """获取数据源"""
        return getattr(Settings, 'DATA_SOURCE', None) or 'akshare'
    
    # 分析师配置
    @classmethod
    def get_selected_analysts(cls) -> list:
        """获取选中的分析师"""
        return getattr(Settings, 'SELECTED_ANALYSTS', ['market', 'news', 'fundamentals'])
    
    # 数据库配置
    @classmethod
    def get_database_path(cls) -> str:
        """获取数据库路径"""
        return Settings.DATABASE_PATH if hasattr(Settings, 'DATABASE_PATH') else 'data/Astock3.duckdb'
```

---

## 4. Flask API设计

### 4.1 API蓝图

```python
# agent_integration/api/agent_api.py

from flask import Blueprint, request, jsonify, current_app
from functools import wraps
import time

agent_bp = Blueprint('agent', __name__, url_prefix='/api/agent')

# 导入组件
from agent_integration import TradingAgentsGraph
from agent_integration.adapters.result_adapter import ResultAdapter
from agent_integration.adapters.config_adapter import ConfigAdapter
from agent_integration.dataflows.adapters.stock_adapter import StockDataAdapter

# 全局实例
_result_adapter = None
_stock_adapter = None

def get_result_adapter():
    global _result_adapter
    if _result_adapter is None:
        _result_adapter = ResultAdapter()
    return _result_adapter

def get_stock_adapter():
    global _stock_adapter
    if _stock_adapter is None:
        _stock_adapter = StockDataAdapter()
    return _stock_adapter

# ==================== 错误处理 ====================

class APIError(Exception):
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code

@agent_bp.errorhandler(APIError)
def handle_api_error(error):
    return jsonify({
        'success': False,
        'error': error.message
    }), error.status_code

# ==================== 中间件 ====================

@agent_bp.before_request
def before_request():
    """请求前置处理"""
    request.start_time = time.time()

@agent_bp.after_request
def after_request(response):
    """请求后置处理"""
    if hasattr(request, 'start_time'):
        elapsed = time.time() - request.start_time
        response.headers['X-Process-Time'] = f"{elapsed:.3f}s"
    return response

# ==================== API端点 ====================

@agent_bp.route('/analyze', methods=['POST'])
def analyze():
    """
    股票AI分析接口
    
    POST /api/agent/analyze
    Content-Type: application/json
    
    Request:
    {
        "symbol": "600519",       # 股票代码 (必需)
        "trade_date": "2024-05-10",  # 分析日期 (可选, 默认今天)
        "analysts": ["market", "news", "fundamentals"]  # 分析师列表 (可选)
    }
    
    Response:
    {
        "success": true,
        "analysis_id": "ag_20240510123045_abc1",
        "symbol": "600519",
        "stock_name": "贵州茅台",
        "final_decision": "BUY",
        "confidence": 0.75,
        "risk_level": "MEDIUM",
        "trading_signal": {
            "action": "BUY",
            "entry_price": 1700.0,
            "stop_loss": 1600.0,
            "take_profit": 1850.0,
            "position_size": 0.3
        },
        "reports": {...},
        "execution_time": 45.2,
        "token_usage": {...}
    }
    """
    # 1. 解析请求
    data = request.get_json() or {}
    
    symbol = data.get('symbol')
    if not symbol:
        raise APIError("symbol is required")
    
    trade_date = data.get('trade_date') or datetime.now().strftime('%Y-%m-%d')
    analysts = data.get('analysts') or ConfigAdapter.get_selected_analysts()
    
    # 2. 获取股票信息
    stock_adapter = get_stock_adapter()
    stock_info = stock_adapter.get_stock_info(symbol)
    stock_name = stock_info.get('name', symbol)
    
    # 3. 获取LLM配置
    provider = ConfigAdapter.get_llm_provider()
    model = ConfigAdapter.get_llm_model()
    
    # 4. 创建分析图
    llm_kwargs = {'model': model}
    api_key = ConfigAdapter.get_llm_api_key(provider)
    if api_key:
        llm_kwargs['api_key'] = api_key
    
    if provider == 'minimax':
        group_id = ConfigAdapter.get_minimax_group_id()
        if group_id:
            llm_kwargs['group_id'] = group_id
    
    # 5. 执行分析
    start_time = time.time()
    
    try:
        graph = TradingAgentsGraph(
            provider=provider,
            selected_analysts=analysts,
            debug=False
        )
        
        result = graph.propagate(symbol, trade_date)
        
    except Exception as e:
        current_app.logger.error(f"分析失败: {e}")
        raise APIError(f"分析失败: {str(e)}", status_code=500)
    
    execution_time = time.time() - start_time
    
    # 6. 保存结果
    result_adapter = get_result_adapter()
    
    # 补充执行信息
    result['execution_time'] = execution_time
    result['token_usage'] = graph.get_token_usage() if hasattr(graph, 'get_token_usage') else {}
    
    analysis_id = result_adapter.save_analysis_result(
        symbol=symbol,
        stock_name=stock_name,
        trade_date=trade_date,
        result=result,
        provider=provider,
        model=model
    )
    
    # 7. 返回响应
    return jsonify({
        'success': True,
        'analysis_id': analysis_id,
        'symbol': symbol,
        'stock_name': stock_name,
        'trade_date': trade_date,
        'final_decision': result.get('final_decision'),
        'confidence': result.get('confidence'),
        'risk_level': result.get('risk_level'),
        'trading_signal': result.get('trading_signal'),
        'reports': result.get('reports'),
        'bull_points': result.get('bull_points'),
        'bear_points': result.get('bear_points'),
        'risk_assessment': result.get('risk_assessment'),
        'execution_time': execution_time,
        'provider': provider,
        'model': model,
        'token_usage': result.get('token_usage', {})
    })


@agent_bp.route('/analyze/async', methods=['POST'])
def analyze_async():
    """
    异步股票AI分析接口 (不等待结果)
    
    POST /api/agent/analyze/async
    Content-Type: application/json
    
    Request:
    {
        "symbol": "600519"
    }
    
    Response:
    {
        "success": true,
        "task_id": "task_abc123",
        "status": "pending"
    }
    """
    # 异步实现使用Celery或线程池
    # 这里返回task_id供后续查询
    pass


@agent_bp.route('/history', methods=['GET'])
def get_history():
    """
    获取分析历史
    
    GET /api/agent/history
    Query Parameters:
        - symbol: 股票代码 (可选)
        - start_date: 开始日期 (可选)
        - end_date: 结束日期 (可选)
        - decision: 决策过滤 BUY/HOLD/SELL (可选)
        - limit: 返回数量 (默认50)
    
    Response:
    {
        "success": true,
        "count": 10,
        "data": [
            {
                "analysis_id": "ag_20240510123045_abc1",
                "symbol": "600519",
                "stock_name": "贵州茅台",
                "trade_date": "2024-05-10",
                "final_decision": "BUY",
                "confidence": 0.75,
                ...
            },
            ...
        ]
    }
    """
    symbol = request.args.get('symbol')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    decision = request.args.get('decision')
    limit = int(request.args.get('limit', 50))
    
    result_adapter = get_result_adapter()
    history = result_adapter.get_analysis_history(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        decision=decision,
        limit=limit
    )
    
    return jsonify({
        'success': True,
        'count': len(history),
        'data': history
    })


@agent_bp.route('/result/<analysis_id>', methods=['GET'])
def get_result(analysis_id):
    """
    获取单个分析结果
    
    GET /api/agent/result/<analysis_id>
    
    Response:
    {
        "success": true,
        "data": {...}
    }
    """
    result_adapter = get_result_adapter()
    result = result_adapter.load_analysis_result(analysis_id)
    
    if not result:
        raise APIError("分析结果不存在", status_code=404)
    
    return jsonify({
        'success': True,
        'data': result
    })


@agent_bp.route('/stats', methods=['GET'])
def get_stats():
    """
    获取分析统计
    
    GET /api/agent/stats
    Query Parameters:
        - start_date: 开始日期 (可选)
        - end_date: 结束日期 (可选)
    
    Response:
    {
        "success": true,
        "stats": {
            "total_count": 100,
            "buy_count": 30,
            "hold_count": 50,
            "sell_count": 20,
            "avg_confidence": 0.68,
            "avg_execution_time": 42.5,
            "token_usage": {
                "total": 1000000,
                "cost_estimate": 0.50
            }
        }
    }
    """
    # 实现统计查询
    pass


@agent_bp.route('/config', methods=['GET'])
def get_config():
    """
    获取当前配置
    
    GET /api/agent/config
    
    Response:
    {
        "success": true,
        "config": {
            "llm_provider": "minimax",
            "llm_model": "M2.1",
            "selected_analysts": ["market", "news", "fundamentals"],
            "data_source": "akshare"
        }
    }
    """
    return jsonify({
        'success': True,
        'config': {
            'llm_provider': ConfigAdapter.get_llm_provider(),
            'llm_model': ConfigAdapter.get_llm_model(),
            'selected_analysts': ConfigAdapter.get_selected_analysts(),
            'data_source': ConfigAdapter.get_data_source()
        }
    })


@agent_bp.route('/health', methods=['GET'])
def health_check():
    """
    健康检查
    
    GET /api/agent/health
    
    Response:
    {
        "success": true,
        "status": "healthy",
        "components": {
            "database": "ok",
            "llm": "ok"
        }
    }
    """
    # 检查数据库连接
    db_status = "ok"
    try:
        result_adapter = get_result_adapter()
        result_adapter.get_analysis_history(limit=1)
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    # 检查LLM连接
    llm_status = "ok"
    try:
        from agent_integration.llm_adapters import create_llm_by_provider
        provider = ConfigAdapter.get_llm_provider()
        model = ConfigAdapter.get_llm_model()
        api_key = ConfigAdapter.get_llm_api_key(provider)
        llm = create_llm_by_provider(provider, model, api_key=api_key)
        # 简单测试
    except Exception as e:
        llm_status = f"error: {str(e)}"
    
    overall_status = "healthy" if db_status == "ok" and llm_status == "ok" else "degraded"
    
    return jsonify({
        'success': True,
        'status': overall_status,
        'components': {
            'database': db_status,
            'llm': llm_status
        }
    })
```

---

## 5. 集成到现有Flask App

### 5.1 方式一: 注册蓝图

```python
# dashboard/app.py

from agent_integration.api.agent_api import agent_bp

def create_app():
    app = Flask(__name__)
    
    # 注册现有路由
    from dashboard import routes
    
    # 注册Agent API蓝图
    app.register_blueprint(agent_bp)
    
    return app

# 或在现有app.py中添加:
# from agent_integration.api.agent_api import agent_bp
# app.register_blueprint(agent_bp)
```

### 5.2 方式二: 独立运行

```python
# agent_integration/api/run.py

from flask import Flask
from agent_integration.api.agent_api import agent_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(agent_bp)
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5002, debug=True)
```

---

## 6. 数据库初始化

```python
# agent_integration/adapters/init_db.py

from database.db_manager import DatabaseManager

def init_agent_tables():
    """初始化Agent相关表"""
    db = DatabaseManager.get_instance()
    
    # agent_analysis 表
    db.execute("""
    CREATE TABLE IF NOT EXISTS agent_analysis (
        id              VARCHAR(20) PRIMARY KEY,
        symbol          VARCHAR(10) NOT NULL,
        stock_name      VARCHAR(50),
        trade_date      DATE NOT NULL,
        final_decision  VARCHAR(10) NOT NULL,
        confidence      FLOAT,
        risk_level      VARCHAR(10),
        action          VARCHAR(10),
        entry_price     FLOAT,
        stop_loss       FLOAT,
        take_profit     FLOAT,
        position_size   FLOAT,
        reports         JSON,
        bull_points     JSON,
        bear_points     JSON,
        risk_assessment JSON,
        provider        VARCHAR(20),
        model           VARCHAR(50),
        token_usage     JSON,
        execution_time  FLOAT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status          VARCHAR(20) DEFAULT 'completed'
    )
    """)
    
    # agent_token_usage 表
    db.execute("""
    CREATE TABLE IF NOT EXISTS agent_token_usage (
        id              VARCHAR(20) PRIMARY KEY,
        date            DATE NOT NULL,
        provider        VARCHAR(20),
        model           VARCHAR(50),
        prompt_tokens   BIGINT DEFAULT 0,
        completion_tokens BIGINT DEFAULT 0,
        total_tokens    BIGINT DEFAULT 0,
        request_count   INTEGER DEFAULT 0,
        estimated_cost  FLOAT DEFAULT 0,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 创建索引
    db.execute("CREATE INDEX IF NOT EXISTS idx_agent_analysis_symbol ON agent_analysis(symbol)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_agent_analysis_date ON agent_analysis(trade_date)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_agent_analysis_decision ON agent_analysis(final_decision)")
    
    print("Agent表初始化完成")

if __name__ == '__main__':
    init_agent_tables()
```

---

## 7. API使用示例

### 7.1 cURL测试

```bash
# 健康检查
curl http://localhost:5001/api/agent/health

# 执行分析
curl -X POST http://localhost:5001/api/agent/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "600519",
    "trade_date": "2024-05-10"
  }'

# 获取分析历史
curl "http://localhost:5001/api/agent/history?symbol=600519&limit=10"

# 获取单个结果
curl http://localhost:5001/api/agent/result/ag_20240510123045_abc1

# 获取统计
curl "http://localhost:5001/api/agent/stats?start_date=2024-01-01&end_date=2024-05-10"
```

### 7.2 Python客户端

```python
import requests

API_BASE = "http://localhost:5001/api/agent"

# 1. 健康检查
resp = requests.get(f"{API_BASE}/health")
print(resp.json())

# 2. 执行分析
resp = requests.post(f"{API_BASE}/analyze", json={
    "symbol": "600519",
    "trade_date": "2024-05-10"
})
result = resp.json()
print(f"决策: {result['final_decision']}, 置信度: {result['confidence']}")
analysis_id = result['analysis_id']

# 3. 等待完成后获取结果
resp = requests.get(f"{API_BASE}/result/{analysis_id}")
print(resp.json())

# 4. 获取历史
resp = requests.get(f"{API_BASE}/history", params={
    "symbol": "600519",
    "decision": "BUY",
    "limit": 10
})
print(f"历史记录: {len(resp.json()['data'])}条")
```

---

## 8. 目录结构

```
agent_integration/
├── adapters/
│   ├── __init__.py
│   ├── config_adapter.py      # 配置适配 (T26)
│   ├── result_adapter.py     # 结果存储 (T27)
│   └── stock_adapter.py      # 股票数据适配
│
├── api/
│   ├── __init__.py
│   ├── agent_api.py          # Flask API (T28)
│   └── run.py                # 独立运行入口
│
├── graph/
│   └── trading_graph.py      # 核心Graph
│
└── llm_adapters/
    └── ...

# 独立运行
python agent_integration/api/run.py  # 端口5002

# 集成到主应用
# 在 dashboard/app.py 中添加:
# from agent_integration.api.agent_api import agent_bp
# app.register_blueprint(agent_bp)
```

---

## 9. 验收标准

- [ ] `ResultAdapter` 可保存和加载分析结果
- [ ] POST `/api/agent/analyze` 返回结构化结果
- [ ] GET `/api/agent/history` 返回分析历史
- [ ] GET `/api/agent/result/<id>` 返回单个结果
- [ ] GET `/api/agent/config` 返回当前配置
- [ ] GET `/api/agent/health` 返回健康状态
- [ ] 分析结果正确存入DuckDB
- [ ] API响应时间 < 60秒 (单股票分析)
