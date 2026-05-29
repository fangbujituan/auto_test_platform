# 测试用例管理模块

> 完整的测试用例管理解决方案，支持模块化组织、用例管理、统计分析

## 🎯 功能特性

- ✅ **模块管理**：支持多层级树形结构的模块组织
- ✅ **用例管理**：完整的测试用例增删改查功能
- ✅ **自动编号**：用例编号自动生成，格式：TC-项目ID-序号
- ✅ **多维筛选**：支持按优先级、类型、状态筛选
- ✅ **统计分析**：自动化覆盖率、多维度统计
- ✅ **权限控制**：基于RBAC的细粒度权限管理
- ✅ **友好界面**：直观的三栏布局，操作简单

## 📦 快速开始

### 方式一：使用快速启动脚本（推荐）

```bash
# Windows系统
quick_start.bat
```

### 方式二：手动启动

```bash
# 1. 数据库迁移
python migrate_add_test_case_module.py

# 2. 权限初始化
python init_test_case_permissions.py

# 3. 启动后端（新终端）
python run.py

# 4. 启动前端（新终端）
cd client
npm run dev
```

### 访问应用

1. 打开浏览器访问：`http://localhost:5173`
2. 登录系统（使用管理员账号）
3. 进入项目详情页
4. 点击左侧菜单的"测试用例"

## 📖 文档导航

### 快速入门
- [完整部署指南](COMPLETE_DEPLOYMENT_GUIDE.md) - 从零开始的完整部署步骤
- [最终总结](FINAL_SUMMARY.md) - 项目概览和开发统计

### 后端文档
- [使用指南](TEST_CASE_MODULE_GUIDE.md) - 数据模型、API接口、使用流程
- [API示例](TEST_CASE_API_EXAMPLES.md) - 详细的API调用示例
- [开发总结](TEST_CASE_MODULE_SUMMARY.md) - 技术架构和核心功能

### 前端文档
- [前端使用指南](FRONTEND_TEST_CASE_GUIDE.md) - 页面布局、功能说明、操作指南

## 🏗️ 技术架构

### 后端
- **框架**：Flask
- **ORM**：SQLAlchemy
- **数据库**：SQLite / MySQL / PostgreSQL
- **权限**：RBAC

### 前端
- **框架**：Vue 3
- **UI库**：Element Plus
- **路由**：Vue Router
- **HTTP**：Axios

## 📊 数据模型

### 模块表 (modules)
```
- id: 主键
- module_no: 模块编号（手动输入）
- name: 模块名称
- parent_id: 父模块ID（支持树形结构）
- project_id: 所属项目
```

### 测试用例表 (test_case_management)
```
- id: 主键
- case_no: 用例编号（自动生成）
- title: 用例标题
- description: 用例描述
- precondition: 前置条件
- steps: 测试步骤
- expected_result: 预期结果
- module_id: 所属模块
- priority: 优先级（P0/P1/P2/P3）
- case_type: 类型（功能/性能/安全）
- case_status: 状态（草稿/已评审/已废弃）
```

### 用例-API绑定表 (test_case_api_bindings)
```
- id: 主键
- test_case_id: 测试用例ID
- api_id: API接口ID
- sort_order: 执行顺序
```

## 🔌 API接口

### 模块管理
```
POST   /api/modules          创建模块
GET    /api/modules          获取模块列表
GET    /api/modules/tree     获取模块树
GET    /api/modules/{id}     获取模块详情
PUT    /api/modules/{id}     更新模块
DELETE /api/modules/{id}     删除模块
```

### 测试用例管理
```
POST   /api/test-cases              创建测试用例
GET    /api/test-cases              获取用例列表
GET    /api/test-cases/{id}         获取用例详情
PUT    /api/test-cases/{id}         更新测试用例
DELETE /api/test-cases/{id}         删除测试用例
GET    /api/test-cases/statistics   获取统计信息
```

## 🎨 界面预览

### 三栏布局
```
┌─────────────┬──────────────┬────────────────────┐
│             │              │                    │
│  模块树     │  用例列表    │    用例详情        │
│             │              │                    │
│  - 用户模块 │  TC-1-0001   │  编号：TC-1-0001   │
│    - 登录   │  正常登录    │  标题：正常登录    │
│    - 注册   │              │  优先级：P0        │
│  - 订单模块 │  TC-1-0002   │  ...               │
│             │  错误密码    │                    │
│             │              │                    │
└─────────────┴──────────────┴────────────────────┘
```

## 📝 使用示例

### 1. 创建模块
```javascript
// 创建顶层模块
{
  "module_no": "MOD-USER",
  "name": "用户模块",
  "description": "用户相关功能",
  "project_id": 1
}

// 创建子模块
{
  "module_no": "MOD-USER-LOGIN",
  "name": "登录子模块",
  "parent_id": 1,
  "project_id": 1
}
```

### 2. 创建测试用例
```javascript
{
  "title": "正常登录测试",
  "description": "测试用户使用正确的用户名和密码登录",
  "precondition": "用户已注册",
  "steps": "1. 打开登录页面\n2. 输入用户名密码\n3. 点击登录",
  "expected_result": "登录成功，跳转到首页",
  "project_id": 1,
  "module_id": 2,
  "priority": "P0",
  "case_type": "功能",
  "case_status": "已评审"
}
```

### 3. 查看统计
```javascript
// 响应示例
{
  "total_cases": 10,
  "automated_cases": 6,
  "automation_rate": 60.0,
  "priority_stats": {
    "P0": 3,
    "P1": 4,
    "P2": 2,
    "P3": 1
  }
}
```

## 🔐 权限说明

需要以下权限才能使用相关功能：

| 权限代码 | 说明 |
|---------|------|
| module:create | 创建模块 |
| module:read | 查看模块 |
| module:update | 更新模块 |
| module:delete | 删除模块 |
| test_case:create | 创建测试用例 |
| test_case:read | 查看测试用例 |
| test_case:update | 更新测试用例 |
| test_case:delete | 删除测试用例 |

管理员角色默认拥有所有权限。

## ❓ 常见问题

### Q: 模块编号规则是什么？
A: 模块编号需要手动输入，建议使用有意义的规则，如：
- MOD-USER（用户模块）
- MOD-ORDER（订单模块）
- MOD-USER-LOGIN（用户登录子模块）

### Q: 用例编号如何生成？
A: 用例编号由系统自动生成，格式为：TC-项目ID-序号
- 例如：TC-1-0001、TC-1-0002
- 保证项目内唯一

### Q: 如何统计自动化覆盖率？
A: 自动化覆盖率 = (绑定了API的用例数 / 总用例数) × 100%

### Q: 删除模块时提示有用例怎么办？
A: 需要先删除该模块下的所有测试用例，或将用例移动到其他模块

## 🚀 后续计划

- [ ] 用例与API绑定功能（前端界面）
- [ ] 用例批量操作
- [ ] 用例导入导出（Excel）
- [ ] 用例版本管理
- [ ] 用例执行记录
- [ ] 统计图表展示
- [ ] 用例复制和移动

## 📄 许可证

本项目为内部使用项目。

## 👨‍💻 开发者

yandc

## 📅 版本历史

### v1.0.0 (2026-01-19)
- ✨ 初始版本发布
- ✅ 完整的模块管理功能
- ✅ 完整的测试用例管理功能
- ✅ 统计分析功能
- ✅ 前后端完整实现

## 🙏 致谢

感谢使用本系统！如有问题或建议，欢迎反馈。
