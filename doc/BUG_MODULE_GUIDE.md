# Bug管理模块使用指南

## 概述

Bug管理模块是一个完整的缺陷跟踪系统，与API接口管理处于同一层级，支持Bug的全生命周期管理。

## 功能特性

### 核心功能
- ✅ Bug增删改查
- ✅ Bug状态管理（待处理、处理中、已解决、已关闭、重新打开）
- ✅ 优先级和严重程度分类
- ✅ 人员分配（报告人、指派人、解决人）
- ✅ 关联API接口和测试用例
- ✅ Bug统计分析
- ✅ 多条件查询过滤

### Bug状态
- `open` - 待处理
- `in_progress` - 处理中
- `resolved` - 已解决
- `closed` - 已关闭
- `reopened` - 重新打开

### 优先级
- `low` - 低
- `medium` - 中
- `high` - 高
- `critical` - 紧急

### 严重程度
- `trivial` - 轻微
- `minor` - 次要
- `normal` - 一般
- `major` - 严重
- `critical` - 致命

### 解决方案类型
- `fixed` - 已修复
- `wont_fix` - 不修复
- `duplicate` - 重复
- `cannot_reproduce` - 无法复现
- `by_design` - 按设计

## 数据库表结构

### bugs表字段

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| title | String(200) | Bug标题 |
| description | Text | Bug描述 |
| project_id | Integer | 所属项目ID |
| status | String(20) | 状态 |
| priority | String(20) | 优先级 |
| severity | String(20) | 严重程度 |
| category | String(50) | Bug分类 |
| module | String(100) | 所属模块 |
| tags | JSON | 标签列表 |
| reporter_id | Integer | 报告人ID |
| assignee_id | Integer | 指派人ID |
| environment | String(100) | 测试环境 |
| version | String(50) | 发现版本 |
| steps_to_reproduce | Text | 复现步骤 |
| expected_result | Text | 预期结果 |
| actual_result | Text | 实际结果 |
| attachments | JSON | 附件列表 |
| related_apis | JSON | 关联API ID列表 |
| related_test_cases | JSON | 关联测试用例ID列表 |
| resolution | String(50) | 解决方案 |
| resolution_note | Text | 解决说明 |
| resolved_at | DateTime | 解决时间 |
| resolved_by | Integer | 解决人ID |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

## API接口

### 基础路径
```
/api/projects/<project_id>/bugs
```

### 1. 获取Bug列表
```http
GET /api/projects/{project_id}/bugs
```

**查询参数：**
- `status` - 按状态过滤
- `priority` - 按优先级过滤
- `severity` - 按严重程度过滤
- `assignee_id` - 按指派人过滤
- `reporter_id` - 按报告人过滤
- `keyword` - 关键词搜索（标题、描述、模块）

**响应示例：**
```json
{
  "code": 0,
  "data": [
    {
      "id": 1,
      "title": "登录页面无法正常显示",
      "status": "open",
      "priority": "high",
      "severity": "major",
      "reporter_id": 1,
      "assignee_id": 1,
      "created_at": "2026-01-22 10:00:00"
    }
  ]
}
```

### 2. 获取Bug详情
```http
GET /api/projects/{project_id}/bugs/{bug_id}
```

### 3. 创建Bug
```http
POST /api/projects/{project_id}/bugs
```

**请求体：**
```json
{
  "title": "Bug标题",
  "description": "详细描述",
  "status": "open",
  "priority": "high",
  "severity": "major",
  "category": "UI",
  "module": "用户认证",
  "tags": ["前端", "登录"],
  "assignee_id": 2,
  "environment": "Chrome 120, Windows 11",
  "version": "v1.0.0",
  "steps_to_reproduce": "1. 步骤1\n2. 步骤2",
  "expected_result": "预期结果",
  "actual_result": "实际结果",
  "related_apis": [1, 2],
  "related_test_cases": [3, 4]
}
```

### 4. 更新Bug
```http
PUT /api/projects/{project_id}/bugs/{bug_id}
```

**请求体：**（所有字段可选）
```json
{
  "title": "更新后的标题",
  "status": "in_progress",
  "priority": "critical",
  "assignee_id": 3
}
```

### 5. 删除Bug
```http
DELETE /api/projects/{project_id}/bugs/{bug_id}
```

### 6. 解决Bug
```http
POST /api/projects/{project_id}/bugs/{bug_id}/resolve
```

**请求体：**
```json
{
  "resolution": "fixed",
  "resolution_note": "问题已修复并测试通过"
}
```

### 7. 重新打开Bug
```http
POST /api/projects/{project_id}/bugs/{bug_id}/reopen
```

### 8. 获取统计信息
```http
GET /api/projects/{project_id}/bugs/statistics
```

**响应示例：**
```json
{
  "code": 0,
  "data": {
    "total": 10,
    "by_status": {
      "open": 3,
      "in_progress": 2,
      "resolved": 5
    },
    "by_priority": {
      "low": 2,
      "medium": 4,
      "high": 3,
      "critical": 1
    },
    "by_severity": {
      "minor": 3,
      "normal": 4,
      "major": 2,
      "critical": 1
    }
  }
}
```

## 快速开始

### 1. 初始化Bug模块

```bash
# 创建表并添加示例数据
python init_bug_data.py
```

### 2. 启动服务

```bash
# 启动Flask应用
python run.py
```

### 3. 测试API

```bash
# 运行测试脚本
python test_bug_api.py
```

## 使用示例

### Python示例

```python
import requests

BASE_URL = "http://localhost:12048"
PROJECT_ID = 1
TOKEN = "your_token_here"

headers = {"Authorization": f"Bearer {TOKEN}"}

# 创建Bug
bug_data = {
    "title": "登录失败",
    "description": "用户无法登录系统",
    "priority": "high",
    "severity": "major",
    "status": "open"
}
response = requests.post(
    f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs",
    headers=headers,
    json=bug_data
)
bug = response.json()["data"]
print(f"创建Bug成功，ID: {bug['id']}")

# 更新Bug状态
response = requests.put(
    f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs/{bug['id']}",
    headers=headers,
    json={"status": "in_progress"}
)

# 解决Bug
response = requests.post(
    f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs/{bug['id']}/resolve",
    headers=headers,
    json={
        "resolution": "fixed",
        "resolution_note": "已修复登录逻辑"
    }
)

# 查询高优先级Bug
response = requests.get(
    f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs?priority=high",
    headers=headers
)
high_priority_bugs = response.json()["data"]
```

### JavaScript示例

```javascript
const BASE_URL = 'http://localhost:12048';
const PROJECT_ID = 1;
const TOKEN = 'your_token_here';

const headers = {
  'Authorization': `Bearer ${TOKEN}`,
  'Content-Type': 'application/json'
};

// 创建Bug
async function createBug() {
  const response = await fetch(
    `${BASE_URL}/api/projects/${PROJECT_ID}/bugs`,
    {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({
        title: '登录失败',
        description: '用户无法登录系统',
        priority: 'high',
        severity: 'major'
      })
    }
  );
  const data = await response.json();
  console.log('创建Bug成功:', data.data);
  return data.data.id;
}

// 获取Bug列表
async function getBugs() {
  const response = await fetch(
    `${BASE_URL}/api/projects/${PROJECT_ID}/bugs?status=open`,
    { headers: headers }
  );
  const data = await response.json();
  console.log('Bug列表:', data.data);
}
```

## 权限控制

Bug管理模块使用项目级权限控制：

- `read` - 查看Bug
- `create` - 创建Bug
- `update` - 更新Bug（包括解决、重新打开）
- `delete` - 删除Bug

## 最佳实践

### 1. Bug标题规范
- 简洁明了，描述核心问题
- 包含关键信息（模块、功能）
- 示例：`[登录模块] 用户名验证失败`

### 2. Bug描述规范
- 详细描述问题现象
- 包含环境信息
- 提供复现步骤
- 说明预期和实际结果

### 3. 优先级设置
- `critical` - 系统崩溃、数据丢失
- `high` - 核心功能不可用
- `medium` - 功能部分受影响
- `low` - 界面问题、优化建议

### 4. 状态流转
```
open → in_progress → resolved → closed
         ↓              ↓
         ←── reopened ←──
```

### 5. 关联管理
- 关联相关API接口，便于定位问题
- 关联测试用例，确保回归测试
- 使用标签分类，便于统计分析

## 注意事项

1. **权限检查**：所有操作都需要相应的项目权限
2. **数据验证**：创建和更新时会验证必填字段
3. **状态管理**：解决和重新打开操作会自动更新相关字段
4. **关联数据**：删除Bug不会影响关联的API和测试用例
5. **时间记录**：系统自动记录创建、更新、解决时间

## 故障排查

### 问题1：无法创建Bug
- 检查是否有项目的create权限
- 确认必填字段（title, project_id）已提供
- 验证token是否有效

### 问题2：查询结果为空
- 确认项目ID正确
- 检查过滤条件是否过于严格
- 验证数据库中是否有数据

### 问题3：更新失败
- 确认Bug ID和项目ID匹配
- 检查是否有update权限
- 验证更新字段的数据类型

## 后续扩展

可以考虑添加的功能：
- Bug评论功能
- Bug历史记录
- 邮件通知
- Bug导入导出
- 自定义字段
- Bug看板视图
- 统计报表

## 技术支持

如有问题，请联系：yandc
