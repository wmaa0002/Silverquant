"""
Flask API - Agent分析接口
"""
import sys
import os
from flask import Blueprint, request, jsonify
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_integration.api.analyzer import analyze_stock, health_check, get_analysis_history

agent_bp = Blueprint('agent', __name__, url_prefix='/api/agent')

@agent_bp.route('/analyze', methods=['POST'])
def analyze():
    """分析股票

    POST /api/agent/analyze
    Body: {"symbol": "600519", "trade_date": "2024-05-10"}

    Returns: JSON格式分析结果
    """
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'error': '请求体不能为空'}), 400

    symbol = data.get('symbol')
    trade_date = data.get('trade_date')

    if not symbol:
        return jsonify({'success': False, 'error': '缺少symbol参数'}), 400

    if not trade_date:
        trade_date = datetime.now().strftime('%Y-%m-%d')

    try:
        result = analyze_stock(symbol, trade_date)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@agent_bp.route('/history', methods=['GET'])
def history():
    """获取分析历史

    GET /api/agent/history?symbol=600519&start_date=2024-01-01&end_date=2024-12-31&offset=0&limit=10

    Returns: JSON格式历史记录列表
    """
    symbol = request.args.get('symbol')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    offset = request.args.get('offset', 0, type=int)
    limit = int(request.args.get('limit', 10))

    try:
        results = get_analysis_history(symbol=symbol, start_date=start_date, end_date=end_date, offset=offset, limit=limit)
        return jsonify({'success': True, 'data': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@agent_bp.route('/health', methods=['GET'])
def health():
    """健康检查

    GET /api/agent/health

    Returns: JSON格式健康状态
    """
    try:
        status = health_check()
        return jsonify(status)
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500
