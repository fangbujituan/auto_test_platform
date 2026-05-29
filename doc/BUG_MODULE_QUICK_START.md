# Bug管理模块快速开始

## 已完成的工作

✅ **数据库模型** - `app/models/bug.py`
- Bug模型包含完整的字段定义
- 支持状态、优先级、严重程度管理
- 支持关联API和测试用例

✅ **API路由** - `app/routes/bug.py`
- 完整的CRUD操作
- Bug解决和重新打开功能
- 统计信息接口
- 多条件查询过滤

✅ **模块注册**
- 已在 `app/models/__init__.py` 中注册Bug模型
- 已在 `app/flask_app.py` 中注册Bug路由

✅ **数据初始化** - `init_bug_data.py`
- 自动创建bugs表
- 添加5条示例Bug数据
- 包含不同状态、优先级的示例

✅ **测试脚本** - `test_bug_api.py`
- 完整的API测试流程
- 包含所有接口的测试用例

✅ **文档**
- `BUG_MODULE_GUIDE.md` - 完整使用指南
- `BUG_MODULE_QUICK_START.md` - 快速开始文档

## 当前状态

📊 **数据库状态**
- bugs表已创建
- 5条示例Bug数据已添加
- 数据分布：
  - 待处理(open): 3条
  - 处理中(in_progress): 1条
  - 已解决(resolved): 1条
  - 高优先级: 2条
  - 严重级别: 1条

## 快速测试

### 1. 检查数据
```bash
python check_bug_data.py
```

### 2. 启动服务
```bash
python run.py
```

### 3. 测试API（需要先启动服务）
```bash
python test_bug_api.py
```

## API端点列表

基础路径: `/api/projects/<project_id>/bugs`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/bugs` | 获取Bug列表 |
| POST | `/bugs` | 创建Bug |
| GET | `/bugs/<bug_id>` | 获取Bug详情 |
| PUT | `/bugs/<bug_id>` | 更新Bug |
| DELETE | `/bugs/<bug_id>` | 删除Bug |
| POST | `/bugs/<bug_id>/resolve` | 解决Bug |
| POST | `/bugs/<bug_id>/reopen` | 重新打开Bug |
| GET | `/bugs/statistics` | 获取统计信息 |

## 快速示例

### 使用curl测试

```bash
# 1. 登录获取token
curl -X POST http://localhost:12048/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 2. 获取Bug列表（替换YOUR_TOKEN）
curl -X GET http://localhost:12048/api/projects/2/bugs \
  -H "Authorization: Bearer YOUR_TOKEN"

# 3. 创建Bug
curl -X POST http://localhost:12048/api/projects/2/bugs \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "测试Bug",
    "description": "这是一个测试Bug",
    "priority": "high",
    "severity": "major"
  }'

# 4. 获取统计信息
curl -X GET http://localhost:12048/api/projects/2/bugs/statistics \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 使用Python测试

```python
import requests

BASE_URL = "http://localhost:12048"
PROJECT_ID = 2

# 登录
response = requests.post(f"{BASE_URL}/api/auth/login", json={
    "username": "admin",
    "password": "admin123"
})
token = response.json()["data"]["token"]
headers = {"Authorization": f"Bearer {token}"}

# 获取Bug列表
response = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs", headers=headers)
bugs = response.json()["data"]
print(f"共有 {len(bugs)} 条Bug")

# 创建Bug
new_bug = {
    "title": "新Bug",
    "description": "Bug描述",
    "priority": "high",
    "severity": "major"
}
response = requests.post(
    f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs",
    headers=headers,
    json=new_bug
)
bug = response.json()["data"]
print(f"创建成功，Bug ID: {bug['id']}")
```

## 查询过滤示例

```python
# 查询待处理的Bug
response = requests.get(
    f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs?status=open",
    headers=headers
)

# 查询高优先级Bug
response = requests.get(
    f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs?priority=high",
    headers=headers
)

# 查询指派给特定用户的Bug
response = requests.get(
    f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs?assignee_id=3",
    headers=headers
)

# 关键词搜索
response = requests.get(
    f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs?keyword=登录",
    headers=headers
)

# 组合查询
response = requests.get(
    f"{BASE_URL}/api/projects/{PROJECT_ID}/bugs?status=open&priority=high",
    headers=headers
)
```

## 文件清单

### 核心文件
- `app/models/bug.py` - Bug数据模型
- `app/routes/bug.py` - Bug API路由
- `app/models/__init__.py` - 模型注册（已更新）
- `app/flask_app.py` - 应用配置（已更新）

### 工具脚本
- `init_bug_data.py` - 初始化脚本
- `check_bug_data.py` - 数据检查脚本
- `test_bug_api.py` - API测试脚本

### 文档
- `BUG_MODULE_GUIDE.md` - 完整使用指南
- `BUG_MODULE_QUICK_START.md` - 快速开始文档

## 下一步

1. **前端开发**
   - 创建Bug管理页面
   - 实现Bug列表、详情、创建、编辑界面
   - 添加统计图表

2. **功能增强**
   - Bug评论功能
   - Bug历史记录
   - 邮件通知
   - 文件附件上传

3. **权限管理**
   - 配置Bug模块的权限规则
   - 添加到角色权限配置

4. **集成测试**
   - 与API模块集成测试
   - 与测试用例模块集成测试

## 注意事项

1. Bug模块已完全集成到现有系统
2. 使用与API模块相同的权限控制机制
3. 所有API都需要登录认证
4. 项目ID为2（根据当前数据库）

## 技术支持

如有问题，请查看：
- `BUG_MODULE_GUIDE.md` - 详细文档
- 运行 `python check_bug_data.py` 检查数据状态
- 运行 `python test_bug_api.py` 测试API功能
