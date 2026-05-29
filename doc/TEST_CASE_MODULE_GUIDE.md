# 测试用例管理模块使用指南

## 概述

测试用例管理模块用于管理项目的测试用例，支持模块化组织和API绑定，可统计模块覆盖率和自动化覆盖率。

## 数据模型

### 1. 模块 (Module)
- 支持多层级树形结构
- 字段：
  - `module_no`: 模块编号（手动输入，项目内唯一）
  - `name`: 模块名称
  - `description`: 模块描述
  - `project_id`: 所属项目ID
  - `parent_id`: 父模块ID（可为空，表示顶层模块）
  - `sort_order`: 排序
  - `status`: 状态（1启用/0禁用）

### 2. 测试用例 (TestCase)
- 字段：
  - `case_no`: 用例编号（自动生成，格式：TC-项目ID-序号，如 TC-1-0001）
  - `title`: 用例标题
  - `description`: 用例描述
  - `precondition`: 前置条件
  - `steps`: 测试步骤
  - `expected_result`: 预期结果
  - `project_id`: 所属项目ID
  - `module_id`: 所属模块ID
  - `priority`: 优先级（P0/P1/P2/P3）
  - `case_type`: 用例类型（功能/性能/安全等）
  - `case_status`: 用例状态（草稿/已评审/已废弃）
  - `status`: 状态（1启用/0禁用）

### 3. 用例-API绑定 (TestCaseApi)
- 多对多关系，一个用例可以绑定多个API
- 字段：
  - `test_case_id`: 测试用例ID
  - `api_id`: API接口ID
  - `sort_order`: 执行顺序
  - `remark`: 备注

## API接口

### 模块管理 (/api/modules)

#### 1. 创建模块
```http
POST /api/modules
Content-Type: application/json

{
  "module_no": "MOD-001",
  "name": "用户模块",
  "description": "用户相关功能",
  "project_id": 1,
  "parent_id": null,
  "sort_order": 0
}
```

#### 2. 获取模块列表
```http
GET /api/modules?project_id=1&parent_id=0&include_children=false
```
- `project_id`: 项目ID（可选）
- `parent_id`: 父模块ID（可选，0表示顶层模块）
- `include_children`: 是否包含子模块（true/false）

#### 3. 获取模块树
```http
GET /api/modules/tree?project_id=1
```
返回项目的完整模块树结构（只返回顶层模块，包含所有子模块）

#### 4. 获取模块详情
```http
GET /api/modules/1?include_children=true
```

#### 5. 更新模块
```http
PUT /api/modules/1
Content-Type: application/json

{
  "name": "用户管理模块",
  "description": "更新后的描述"
}
```

#### 6. 删除模块
```http
DELETE /api/modules/1
```
注意：有子模块或测试用例的模块无法删除

### 测试用例管理 (/api/test-cases)

#### 1. 创建测试用例
```http
POST /api/test-cases
Content-Type: application/json

{
  "title": "用户登录功能测试",
  "description": "测试用户登录功能是否正常",
  "precondition": "用户已注册",
  "steps": "1. 打开登录页面\n2. 输入用户名密码\n3. 点击登录",
  "expected_result": "登录成功，跳转到首页",
  "project_id": 1,
  "module_id": 1,
  "priority": "P0",
  "case_type": "功能",
  "case_status": "已评审",
  "api_ids": [1, 2]
}
```
注意：`case_no` 会自动生成，无需传入

#### 2. 获取测试用例列表
```http
GET /api/test-cases?project_id=1&module_id=1&priority=P0&page=1&per_page=20
```
- `project_id`: 项目ID（可选）
- `module_id`: 模块ID（可选）
- `priority`: 优先级（可选）
- `case_type`: 用例类型（可选）
- `case_status`: 用例状态（可选）
- `page`: 页码（默认1）
- `per_page`: 每页数量（默认20）

#### 3. 获取测试用例详情
```http
GET /api/test-cases/1
```

#### 4. 更新测试用例
```http
PUT /api/test-cases/1
Content-Type: application/json

{
  "title": "更新后的标题",
  "case_status": "已评审",
  "api_ids": [1, 2, 3]
}
```

#### 5. 删除测试用例
```http
DELETE /api/test-cases/1
```

#### 6. 获取统计信息
```http
GET /api/test-cases/statistics?project_id=1&module_id=1
```
返回：
- 总用例数
- 自动化用例数（绑定了API的用例）
- 自动化覆盖率
- 按优先级统计
- 按状态统计
- 按类型统计

## 部署步骤

### 1. 运行数据库迁移
```bash
python migrate_add_test_case_module.py
```

### 2. 初始化权限
```bash
python init_test_case_permissions.py
```

### 3. 运行演示脚本（可选）
```bash
python test_case_module_demo.py
```

### 4. 重启应用
```bash
python run.py
```

## 使用流程示例

### 1. 创建模块结构
```
项目A
├── 用户模块 (MOD-USER)
│   ├── 登录子模块 (MOD-USER-LOGIN)
│   └── 注册子模块 (MOD-USER-REG)
└── 订单模块 (MOD-ORDER)
```

### 2. 创建测试用例
在"登录子模块"下创建测试用例：
- TC-1-0001: 正常登录测试
- TC-1-0002: 错误密码登录测试
- TC-1-0003: 未注册用户登录测试

### 3. 绑定API接口
为"正常登录测试"绑定API：
- POST /api/auth/login
- GET /api/user/info

### 4. 查看统计
- 模块覆盖率：登录子模块有3个测试用例
- 自动化覆盖率：3个用例中有1个绑定了API，覆盖率33.33%

## 权限说明

需要以下权限才能使用相关功能：
- `module:create`: 创建模块
- `module:read`: 查看模块
- `module:update`: 更新模块
- `module:delete`: 删除模块
- `test_case:create`: 创建测试用例
- `test_case:read`: 查看测试用例
- `test_case:update`: 更新测试用例
- `test_case:delete`: 删除测试用例

管理员角色默认拥有所有权限。

## 注意事项

1. 模块编号需要手动输入，建议使用有意义的编号规则
2. 用例编号自动生成，格式为 TC-项目ID-序号
3. 删除模块前需要先删除其下的子模块和测试用例
4. 一个测试用例可以绑定多个API接口
5. 统计自动化覆盖率时，只要用例绑定了至少一个API就算自动化用例
