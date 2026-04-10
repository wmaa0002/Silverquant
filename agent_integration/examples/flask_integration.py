"""
Flask API集成示例 - flask_integration.py

展示如何在Flask应用中集成agent_integration模块。

用法:
    python flask_integration.py
    
    或在已有的Flask应用中:
    from flask_integration import create_app
    app = create_app()
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def create_app():
    """创建Flask应用并注册蓝图
    
    Returns:
        Flask应用实例
    """
    # 导入base_app（已注册蓝图）
    from dashboard.app import app as base_app
    
    # agent_bp已经在dashboard/app.py中注册
    # 如果需要单独使用这个函数，可以在这里注册
    try:
        from dashboard.agent_api import agent_bp
        if 'agent' not in [rule.endpoint for rule in base_app.url_map.iter_rules()]:
            base_app.register_blueprint(agent_bp)
            print("Agent API蓝图已注册")
        else:
            print("Agent API蓝图已存在")
    except ImportError as e:
        print(f"警告: 无法导入agent_api蓝图: {e}")
    
    return base_app


def main():
    """启动Flask开发服务器"""
    app = create_app()
    
    print("=" * 60)
    print("Flask应用已创建")
    print("=" * 60)
    print("\n可访问以下端点:")
    print("  POST /api/agent/analyze - 分析股票")
    print("  GET  /api/agent/history - 获取历史")
    print("  GET  /api/agent/health - 健康检查")
    print("\n启动服务器: http://0.0.0.0:5001")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5001, debug=True)


if __name__ == '__main__':
    main()
