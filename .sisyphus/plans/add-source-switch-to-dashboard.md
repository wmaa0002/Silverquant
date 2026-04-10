# 计划: Dashboard 数据更新页面添加数据源开关

## 需求
在 Dashboard 数据更新页面添加数据源切换开关（tushare ↔ baostock），并更新 API 支持数据源参数。

## 修改文件

### 1. data_update_api.py

**修改 run_update_task() 函数签名** (第24行):
```python
# 修改前
def run_update_task(task_id: str, data_type: str, start_date: str = None, end_date: str = None, 
                   ts_code: str = None, index_code: str = None, workers: int = 4):

# 修改后
def run_update_task(task_id: str, data_type: str, start_date: str = None, end_date: str = None, 
                   ts_code: str = None, index_code: str = None, workers: int = 4, source: str = 'tushare'):
```

**修改 fetcher 初始化** (第30行):
```python
# 修改前
fetcher = DWDFetcher()

# 修改后
fetcher = DWDFetcher(source=source)
```

**修改 update_stock_info 调用** (第95行):
```python
# 修改前
result = fetcher.update_stock_info()

# 修改后
result = fetcher.update_stock_info(source=source)
```

**修改 trigger_update() POST 处理** (第252行后添加):
```python
# 在 workers 变量后添加
source = data.get('source', 'tushare')
```

**修改线程启动** (第258行):
```python
# 修改前
thread = threading.Thread(
    target=run_update_task,
    args=(task_id, data_type, start_date, end_date, ts_code, index_code, workers)
)

# 修改后
thread = threading.Thread(
    target=run_update_task,
    args=(task_id, data_type, start_date, end_date, ts_code, index_code, workers, source)
)
```

### 2. data_update.html

**添加开关样式** (在 `<style>` 标签内，`.switch` 相关样式后添加):
```css
.source-switch {
    display: flex;
    align-items: center;
    gap: 12px;
}

.source-switch-label {
    font-size: 14px;
    color: #8b98a5;
    min-width: 60px;
}

.source-switch-label.active {
    color: #1d9bf0;
    font-weight: 600;
}

.switch {
    position: relative;
    width: 56px;
    height: 28px;
    background: #2f3336;
    border-radius: 14px;
    cursor: pointer;
    transition: background 0.3s;
}

.switch::after {
    content: '';
    position: absolute;
    top: 2px;
    left: 2px;
    width: 24px;
    height: 24px;
    background: #e7e9ea;
    border-radius: 50%;
    transition: transform 0.3s;
}

.switch.baostock {
    background: #1d9bf0;
}

.switch.baostock::after {
    transform: translateX(28px);
}
```

**添加开关 HTML** (在卡片标题旁，第557行附近):
```html
<div class="source-switch">
    <span class="source-switch-label active" id="tushareLabel">Tushare</span>
    <div class="switch" id="sourceSwitch" onclick="toggleSource()"></div>
    <span class="source-switch-label" id="baostockLabel">Baostock</span>
</div>
```

**添加 JavaScript 变量和函数** (在 `<script>` 标签内):
```javascript
let currentSource = 'tushare';

function toggleSource() {
    const switchEl = document.getElementById('sourceSwitch');
    const tushareLabel = document.getElementById('tushareLabel');
    const baostockLabel = document.getElementById('baostockLabel');
    
    if (currentSource === 'tushare') {
        currentSource = 'baostock';
        switchEl.classList.add('baostock');
        tushareLabel.classList.remove('active');
        baostockLabel.classList.add('active');
    } else {
        currentSource = 'tushare';
        switchEl.classList.remove('baostock');
        baostockLabel.classList.remove('active');
        tushareLabel.classList.add('active');
    }
}
```

**修改 triggerUpdate() 函数** (在发送请求前添加 source):
```javascript
// 在 const body = { ... } 后添加
body.source = currentSource;
```

## 任务清单

- [ ] 1. 修改 data_update_api.py 的 run_update_task() 函数签名
- [ ] 2. 修改 fetcher 初始化添加 source 参数
- [ ] 3. 修改 update_stock_info() 调用传递 source
- [ ] 4. 修改 trigger_update() POST 解析 source 参数
- [ ] 5. 修改线程启动传递 source 参数
- [ ] 6. 添加 source switch CSS 样式
- [ ] 7. 添加 source switch HTML 元素
- [ ] 8. 添加 toggleSource() JavaScript 函数
- [ ] 9. 修改 triggerUpdate() 发送 source 参数
- [ ] 10. 测试验证

## 验证命令

启动 dashboard 后访问 http://localhost:5000/data-update
1. 检查开关是否显示在"触发数据更新"标题旁
2. 点击开关，验证样式切换
3. 触发更新，检查日志中是否显示数据源
