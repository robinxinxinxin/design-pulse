# 设计前沿监测系统

自动采集 Behance 和站酷（ZCOOL）的最新产品设计动态，专注于消费电子类产品。

## 功能特性

- **双平台采集**：同时监测站酷（产品效果图渲染）和 Behance（头部设计公司）
- **智能筛选**：自动识别消费电子类产品（手机、耳机、智能家居等）
- **去重机制**：基于 URL 去重，避免重复采集
- **网页看板**：可视化展示本周新增项目，支持一键跳转
- **定时任务**：每周一自动运行采集任务
- **手动触发**：支持手动触发采集

## 项目结构

```
design-monitor/
├── crawler/              # 采集器
│   ├── base_crawler.py   # 采集器基类
│   ├── zcool_crawler.py  # 站酷采集器
│   └── behance_crawler.py # Behance 采集器
├── processor/            # 数据处理
│   ├── filter.py         # 品类筛选
│   └── dedup.py          # 去重逻辑
├── db/                   # 数据库
│   └── models.py         # 数据模型
├── api/                  # 后端 API
│   ├── main.py           # FastAPI 主入口
│   └── scheduler.py      # 定时任务
├── dashboard/            # 前端看板
│   └── index.html        # 看板页面
├── data/                 # 数据文件
│   ├── keywords.json     # 关键词配置
│   ├── monitor_list.json # 监测名单
│   └── design_monitor.db # SQLite 数据库
├── run.py                # 启动脚本
└── requirements.txt      # Python 依赖
```

## 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m virtualenv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

### 2. 初始化数据库

```bash
python run.py init
```

### 3. 配置监测名单

编辑 `data/monitor_list.json`，添加 Behance 上的设计公司和设计师主页 URL：

```json
{
  "companies": [
    {
      "name": "公司名称",
      "profile_url": "https://www.behance.net/username",
      "notes": "备注"
    }
  ],
  "individuals": [
    {
      "name": "设计师名称",
      "profile_url": "https://www.behance.net/username",
      "notes": "备注"
    }
  ]
}
```

### 4. 启动系统

#### 方式一：启动 API 服务器（推荐）

```bash
python run.py api
```

访问：
- 看板：http://localhost:8000/
- API 文档：http://localhost:8000/docs

#### 方式二：启动定时任务

```bash
python run.py scheduler
```

每周一早上 9:00 自动运行采集任务。

#### 方式三：手动运行采集

```bash
python run.py crawl
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/projects` | GET | 获取项目列表 |
| `/api/projects/stats` | GET | 获取统计数据 |
| `/api/logs` | GET | 获取采集日志 |
| `/api/crawl/zcool` | POST | 手动触发站酷采集 |
| `/api/crawl/behance` | POST | 手动触发 Behance 采集 |
| `/api/crawl/all` | POST | 手动触发全部采集 |

## 配置说明

### 关键词配置 (`data/keywords.json`)

- `zcool.search_keywords`: 站酷搜索关键词列表
- `category_keywords.include`: 包含关键词（判定为消费电子）
- `category_keywords.exclude`: 排除关键词（过滤掉非产品类内容）

### 品类筛选规则

系统自动根据标题关键词判断是否为消费电子类产品：

**包含关键词**：手机、耳机、智能手表、充电器、键盘、鼠标、显示器、智能家居、机器人、无人机、AR/VR 等

**排除关键词**：UI设计、APP设计、网页设计、包装设计、海报设计、品牌VI、广告设计、建筑设计、室内设计等

## 注意事项

1. **Behance 监测名单**：需要手动配置设计公司和设计师的 Behance 主页 URL
2. **反爬策略**：采集器已内置随机延迟和浏览器伪装，但仍建议控制采集频率
3. **数据存储**：所有数据存储在本地 SQLite 数据库中，路径为 `data/design_monitor.db`

## 后续扩展

- [ ] 接入 AI 分类模型，提高品类判断准确率
- [ ] 添加飞书/邮件通知功能
- [ ] 支持更多设计平台（Pinterest、Dribbble 等）
- [ ] 数据趋势分析和可视化

## License

MIT
