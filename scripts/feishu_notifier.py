#!/usr/bin/env python3
"""飞书消息通知模块 - 通过stdout输出标记，由上层agent发送"""
import sys, os

def send_feishu_message(message: str, target: str = None):
    """
    输出飞书消息标记，agent会识别并发送
    """
    target = target or "oc_8e87901bd3cc64893318ee16ccb08d57"
    # 输出特殊标记，agent识别后发送
    print("=" * 40)
    print(f"【飞书发送】目标: {target}")
    print("=" * 40)
    print(message)
    print("=" * 40)
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        send_feishu_message(sys.argv[1])
