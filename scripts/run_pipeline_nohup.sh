#!/bin/bash
# 数据流水线 nohup wrapper script
# 确保在后台稳定运行

cd /Users/mawenhao/Desktop/code/股票策略

# 使用 nohup 运行流水线，日志输出到专门的文件
nohup /opt/anaconda3/bin/python3.11 scripts/workflow_scheduler.py --pipeline daily --run >> logs/pipeline_nohup.log 2>&1 &

echo "Pipeline started with PID: $!"
echo "Start time: $(date '+%Y-%m-%d %H:%M:%S')" >> logs/pipeline_nohup.log
