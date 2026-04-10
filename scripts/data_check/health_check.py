"""
多数据源健康检查
检查 tushare、baostock 两个数据源的可用性和响应时间
"""
import sys
import os
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import tushare as ts
import akshare as ak
import baostock as bs

from config.settings import Settings


def check_tushare():
    """检查 tushare 数据源可用性"""
    result = {"available": False, "response_time": None}
    start_time = time.time()
    
    try:
        token = Settings.TUSHARE_TOKEN
        if not token:
            return result
        
        ts.set_token(token)
        pro = ts.pro_api()
        # 调用 stock_basic 接口获取一条数据
        df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,list_date')
        
        response_time = time.time() - start_time
        result["response_time"] = round(response_time, 3)
        
        # 检查响应时间是否超过阈值
        if response_time > Settings.FAILOVER_RESPONSE_TIME_THRESHOLD:
            return result
        
        result["available"] = True
    except Exception as e:
        result["response_time"] = round(time.time() - start_time, 3)
    
    return result


def check_akshare():
    """检查 akshare 数据源可用性"""
    result = {"available": False, "response_time": None}
    start_time = time.time()
    
    try:
        # 调用 stock_info_a_code_name 接口获取一条数据
        df = ak.stock_info_a_code_name()
        
        response_time = time.time() - start_time
        result["response_time"] = round(response_time, 3)
        
        # 检查响应时间是否超过阈值
        if response_time > Settings.FAILOVER_RESPONSE_TIME_THRESHOLD:
            return result
        
        result["available"] = True
    except Exception as e:
        result["response_time"] = round(time.time() - start_time, 3)
    
    return result


def check_baostock():
    """检查 baostock 数据源可用性"""
    result = {"available": False, "response_time": None}
    start_time = time.time()
    
    try:
        # 登录 baostock
        lg = bs.login()
        if lg.error_code != '0':
            return result
        
        # 调用 query_stock_basic 接口获取一条数据
        rs = bs.query_stock_basic(code="sh.600000")
        
        response_time = time.time() - start_time
        result["response_time"] = round(response_time, 3)
        
        # 检查响应时间是否超过阈值
        if response_time > Settings.FAILOVER_RESPONSE_TIME_THRESHOLD:
            bs.logout()
            return result
        
        result["available"] = True
        bs.logout()
    except Exception as e:
        result["response_time"] = round(time.time() - start_time, 3)
        try:
            bs.logout()
        except Exception as e:
            print(f"baostock登出失败: {e}")
    
    return result


def check_all_sources():
    """
    检查所有三个数据源的可用性和响应时间
    
    Returns:
        dict: 包含各数据源检查结果的字典
    """
    results = {
        "tushare": check_tushare(),
        "baostock": check_baostock()
    }
    
    return results


def get_optimal_source(results):
    """
    根据检查结果确定最优数据源
    
    Args:
        results: check_all_sources() 返回的结果字典
    
    Returns:
        str: 最优数据源名称，如果没有可用数据源返回 None
    """
    available_sources = []
    
    for source in Settings.DATA_SOURCE_PRIORITY:
        if source in results and results[source]["available"]:
            available_sources.append(source)
    
    return available_sources[0] if available_sources else None


def main():
    """主函数"""
    print("=" * 60)
    print("多数据源健康检查")
    print("=" * 60)
    
    results = check_all_sources()
    
    print("\n检查结果:")
    for source, result in results.items():
        status = "✅ 可用" if result["available"] else "❌ 不可用"
        rt = f"{result['response_time']}s" if result["response_time"] else "N/A"
        print(f"  {source}: {status} (响应时间: {rt})")
    
    # 确定最优数据源
    optimal = get_optimal_source(results)
    print(f"\n推荐数据源: {optimal if optimal else '无'}")
    
    # 输出 JSON 格式结果
    print("\n" + "=" * 60)
    print("JSON 输出:")
    print("=" * 60)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    
    return results


if __name__ == '__main__':
    main()