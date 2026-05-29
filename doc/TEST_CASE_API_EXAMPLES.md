# 测试用例管理API示例

## 前置条件

所有API请求需要在请求头中包含认证信息：
```
Authorization: Bearer <token>
X-Username: <username>
```

## 模块管理API示例

### 1. 创建顶层模块

```bash
curl -X POST http://localhost:12048/api/modules \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token" \
  -H "X-Username: admin" \
  -d '{
    "module_no": "MOD-USER",
    "name": "用户模块",
    "description": "用户相关功能模块",
    "project_id": 1
  }'
```

### 2. 创建子模块

```bash
curl -X POST http://localhost:12048/api/modules \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token" \
  -H "X-Username: admin" \
  -d '{
    "module_no": "MOD-USER-LOGIN",
    "name": "登录子模块",
    "description": "用户登录功能",
    "project_id": 1,
    "parent_id": 1
  }'
```

### 3. 获取模块树

```bash
curl -X GET "http://localhost:12048/api/modules/tree?project_id=1" \
  -H "Authorization: Bearer your_token" \
  -H "X-Username: admin"
```

响应示例：
```json
[
  {
    "id": 1,
    "module_no": "MOD-USER",
    "name": "用户模块",
    "description": "用户相关功能模块",
    "project_id": 1,
    "parent_id": null,
    "status": 1,
    "sort_order": 0,
    "created_at": "2026-01-19 10:00:00",
    "updated_at": "2026-01-19 10:00:00",
    "children": [
      {
        "id": 2,
        "module_no": "MOD-USER-LOGIN",
        "name": "登录子模块",
        "description": "用户登录功能",
        "project_id": 1,
        "parent_id": 1,
        "status": 1,
        "sort_order": 0,
        "created_at": "2026-01-19 10:01:00",
        "updated_at": "2026-01-19 10:01:00",
        "children": []
      }
    ]
  }
]
```

### 4. 更新模块

```bash
curl -X PUT http://localhost:12048/api/modules/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token" \
  -H "X-Username: admin" \
  -d '{
    "name": "用户管理模块",
    "description": "更新后的描述"
  }'
```

### 5. 删除模块

```bash
curl -X DELETE http://localhost:12048/api/modules/1 \
  -H "Authorization: Bearer your_token" \
  -H "X-Username: admin"
```

## 测试用例管理API示例

### 1. 创建测试用例

```bash
curl -X POST http://localhost:12048/api/test-cases \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token" \
  -H "X-Username: admin" \
  -d '{
    "title": "正常登录测试",
    "description": "测试用户使用正确的用户名和密码登录",
    "precondition": "用户已注册",
    "steps": "1. 打开登录页面\n2. 输入正确的用户名和密码\n3. 点击登录按钮",
    "expected_result": "登录成功，跳转到首页",
    "project_id": 1,
    "module_id": 2,
    "priority": "P0",
    "case_type": "功能",
    "case_status": "已评审",
    "api_ids": [1, 2]
  }'
```

响应示例：
```json
{
  "id": 1,
  "case_no": "TC-1-0001",
  "title": "正常登录测试",
  "description": "测试用户使用正确的用户名和密码登录",
  "precondition": "用户已注册",
  "steps": "1. 打开登录页面\n2. 输入正确的用户名和密码\n3. 点击登录按钮",
  "expected_result": "登录成功，跳转到首页",
  "project_id": 1,
  "module_id": 2,
  "priority": "P0",
  "case_type": "功能",
  "case_status": "已评审",
  "status": 1,
  "created_at": "2026-01-19 10:05:00",
  "updated_at": "2026-01-19 10:05:00",
  "api_ids": [1, 2]
}
```

### 2. 获取测试用例列表

```bash
curl -X GET "http://localhost:12048/api/test-cases?project_id=1&module_id=2&page=1&per_page=20" \
  -H "Authorization: Bearer your_token" \
  -H "X-Username: admin"
```

响应示例：
```json
{
  "items": [
    {
      "id": 1,
      "case_no": "TC-1-0001",
      "title": "正常登录测试",
      "description": "测试用户使用正确的用户名和密码登录",
      "project_id": 1,
      "module_id": 2,
      "priority": "P0",
      "case_type": "功能",
      "case_status": "已评审",
      "status": 1,
      "api_ids": [1, 2]
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20,
  "pages": 1
}
```

### 3. 获取测试用例详情

```bash
curl -X GET http://localhost:12048/api/test-cases/1 \
  -H "Authorization: Bearer your_token" \
  -H "X-Username: admin"
```

### 4. 更新测试用例

```bash
curl -X PUT http://localhost:12048/api/test-cases/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token" \
  -H "X-Username: admin" \
  -d '{
    "title": "更新后的标题",
    "case_status": "已评审",
    "api_ids": [1, 2, 3]
  }'
```

### 5. 删除测试用例

```bash
curl -X DELETE http://localhost:12048/api/test-cases/1 \
  -H "Authorization: Bearer your_token" \
  -H "X-Username: admin"
```

### 6. 获取统计信息

```bash
curl -X GET "http://localhost:12048/api/test-cases/statistics?project_id=1&module_id=2" \
  -H "Authorization: Bearer your_token" \
  -H "X-Username: admin"
```

响应示例：
```json
{
  "total_cases": 10,
  "automated_cases": 6,
  "automation_rate": 60.0,
  "priority_stats": {
    "P0": 3,
    "P1": 4,
    "P2": 2,
    "P3": 1
  },
  "status_stats": {
    "草稿": 2,
    "已评审": 7,
    "已废弃": 1
  },
  "type_stats": {
    "功能": 8,
    "性能": 1,
    "安全": 1
  }
}
```

## 使用Postman测试

1. 导入以下环境变量：
   - `base_url`: http://localhost:12048
   - `token`: your_token_here
   - `username`: admin

2. 在请求头中设置：
   - `Authorization`: Bearer {{token}}
   - `X-Username`: {{username}}
   - `Content-Type`: application/json

3. 按照上述示例创建请求并测试

## 常见问题

### Q: 创建测试用例时提示"模块不存在"
A: 请先创建模块，确保module_id对应的模块存在且属于指定的项目。

### Q: 删除模块时提示"该模块下有测试用例，无法删除"
A: 需要先删除该模块下的所有测试用例，或将用例移动到其他模块。

### Q: 用例编号是如何生成的？
A: 用例编号格式为 TC-项目ID-序号，例如 TC-1-0001，系统会自动递增序号。

### Q: 如何统计自动化覆盖率？
A: 自动化覆盖率 = (绑定了API的用例数 / 总用例数) × 100%
