"""
Baostock代码格式转换工具

baostock格式: sz.300486, sh.600000
内部格式: 300486.SZ, 600000.SH
"""


def convert_code_to_baostock(code: str) -> str:
    """
    转换内部代码到baostock格式
    
    Examples:
        '300486' → 'sz.300486'
        '300486.SZ' → 'sz.300486'
        '600000.SH' → 'sh.600000'
        'sz.300486' → 'sz.300486' (直接返回)
        'sh.600000' → 'sh.600000' (直接返回)
    """
    # 已经是baostock格式
    if code.startswith('sz.') or code.startswith('sh.'):
        return code
    
    # 去掉.SH/.SZ后缀
    code = code.replace('.SH', '').replace('.SZ', '')
    
    # 判断市场
    if code.startswith('6') or code.startswith('688'):
        return f'sh.{code}'
    else:
        return f'sz.{code}'


def convert_code_from_baostock(code: str) -> str:
    """
    转换baostock代码到内部格式
    
    Examples:
        'sz.300486' → '300486.SZ'
        'sh.600000' → '600000.SH'
    """
    if code.startswith('sz.'):
        return code.replace('sz.', '') + '.SZ'
    elif code.startswith('sh.'):
        return code.replace('sh.', '') + '.SH'
    return code


def is_baostock_format(code: str) -> bool:
    """检查是否为baostock格式"""
    return code.startswith('sz.') or code.startswith('sh.')


# ============ Tushare格式转换 ============

def get_market(code: str) -> str:
    """
    根据股票代码判断市场

    Args:
        code: 6位股票代码

    Returns:
        'SH' (沪市), 'SZ' (深市), 或 'BJ' (北交所)
    """
    if code.startswith(('8', '4')):
        return 'BJ'
    elif code.startswith('6'):
        return 'SH'
    else:
        return 'SZ'


def to_tushare(code: str) -> str:
    """
    内部格式转换为tushare格式

    Args:
        code: 6位股票代码，如 '000001'

    Returns:
        tushare格式代码，如 '000001.SZ'
    """
    market = get_market(code)
    return f"{code}.{market}"


def from_tushare(ts_code: str) -> str:
    """
    tushare格式转换为内部格式

    Args:
        ts_code: tushare格式代码，如 '000001.SZ'

    Returns:
        6位股票代码，如 '000001'
    """
    return ts_code.split('.')[0]