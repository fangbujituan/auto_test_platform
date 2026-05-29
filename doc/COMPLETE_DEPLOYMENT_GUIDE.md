# 测试用例管理模块完整部署指南

## 概述

本指南将帮助你完成测试用例管理模块的完整部署，包括后端和前端。

## 前置条件

- Python 3.8+
- Node.js 14+
- 已有运行的项目数据库
- 已有用户和项目数据

## 后端部署

### 1. 数据库迁移

运行迁移脚本创建新表：

```bash
python migrate_add_test_case_module.py
```

预期输出：
```
开始创建测试用例管理相关表...
✓ 模块表 (modules) 创建成功
✓ 测试用例管理表 (test_case_management) 创建成功
✓ 用例-API绑定表 (test_case_api_bindings) 创建成功

迁移完成！
```

### 2. 权限初始化

运行权限初始化脚本：

```bash
python init_test_case_permissions.py
```

预期输出：
```
开始初始化测试用例管理权限...
✓ 创建权限: 创建模块 (module:create)
✓ 创建权限: 查看模块 (module:read)
✓ 创建权限: 更新模块 (module:update)
✓ 创建权限: 删除模块 (module:delete)
✓ 创建权限: 创建测试用例 (test_case:create)
✓ 创建权限: 查看测试用例 (test_case:read)
✓ 创建权限: 更新测试用例 (test_case:update)
✓ 创建权限: 删除测试用例 (test_case:delete)

✓ 已将所有权限添加到管理员角色

权限初始化完成！
```

### 3. 测试后端功能（可选）

运行演示脚本验证功能：

```bash
python test_case_module_demo.py
```

这将创建示例数据并显示统计信息。

### 4. 启动后端服务

```bash
python run.py
```

确认服务启动成功，默认端口：12048

## 前端部署

### 1. 安装依赖（如果还没安装）

```bash
cd client
npm install
```

### 2. 启动前端开发服务器

```bash
npm run dev
```

默认端口：5173

### 3. 访问应用

打开浏览器访问：`http://localhost:5173`

## 功能验证

### 1. 登录系统

使用管理员账号登录系统

### 2. 进入项目

1. 点击"项目列表"
2. 选择一个项目进入

### 3. 访问测试用例管理

在项目详情页，点击左侧菜单的"测试用例"

### 4. 创建模块

1. 点击左侧栏顶部的"+"按钮
2. 填写模块信息：
   - 模块编号：MOD-USER
   - 模块名称：用户模块
   - 模块描述：用户相关功能
3. 点击确定

### 5. 创建测试用例

1. 点击中间栏的"新建用例"按钮
2. 填写用例信息：
   - 用例标题：正常登录测试
   - 所属模块：选择刚创建的模块
   - 优先级：P0
   - 用例类型：功能
   - 用例状态：已评审
   - 测试步骤：
     ```
     1. 打开登录页面
     2. 输入正确的用户名和密码
     3. 点击登录按钮
     ```
   - 预期结果：登录成功，跳转到首页
3. 点击确定

### 6. 查看用例详情

1. 在中间栏点击刚创建的用例
2. 右侧栏会显示用例的完整信息
3. 注意用例编号是自动生成的（如：TC-1-0001）

## API测试

### 使用curl测试

#### 1. 创建模块

```bash
curl -X POST http://localhost:12048/api/modules \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token" \
  -H "X-Username: admin" \
  -d '{
    "module_no": "MOD-TEST",
    "name": "测试模块",
    "description": "API测试用的模块",
    "project_id": 1
  }'
```

#### 2. 获取模块树

```bash
curl -X GET "http://localhost:12048/api/modules/tree?project_id=1" \
  -H "Authorization: Bearer your_token" \
  -H "X-Username: admin"
```

#### 3. 创建测试用例

```bash
curl -X POST http://localhost:12048/api/test-cases \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token" \
  -H "X-Username: admin" \
  -d '{
    "title": "API测试用例",
    "description": "通过API创建的测试用例",
    "project_id": 1,
    "module_id": 1,
    "priority": "P1",
    "case_type": "功能",
    "case_status": "草稿"
  }'
```

#### 4. 获取测试用例列表

```bash
curl -X GET "http://localhost:12048/api/test-cases?project_id=1" \
  -H "Authorization: Bearer your_token" \
  -H "X-Username: admin"
```

#### 5. 获取统计信息

```bash
curl -X GET "http://localhost:12048/api/test-cases/statistics?project_id=1" \
  -H "Authorization: Bearer your_token" \
  -H "X-Username: admin"
```

## 常见问题

### Q1: 数据库迁移失败

**问题**：运行迁移脚本时报错

**解决方案**：
1. 检查数据库连接配置
2. 确认数据库用户有创建表的权限
3. 查看错误信息，可能是表已存在

### Q2: 权限初始化失败

**问题**：找不到admin角色

**解决方案**：
1. 先运行 `python init_permission.py` 初始化基础权限
2. 确保数据库中有admin角色

### Q3: 前端无法访问后端API

**问题**：前端请求后端API时出现跨域错误

**解决方案**：
1. 确认后端已启用CORS（已在flask_app.py中配置）
2. 检查前端的API基础URL配置
3. 确认后端服务正在运行

### Q4: 创建模块时提示"模块编号已存在"

**问题**：模块编号重复

**解决方案**：
1. 模块编号在项目内必须唯一
2. 使用不同的模块编号
3. 或者删除已存在的模块

### Q5: 删除模块时提示"该模块下有测试用例"

**问题**：模块下有用例无法删除

**解决方案**：
1. 先删除该模块下的所有测试用例
2. 或者将用例移动到其他模块
3. 然后再删除模块

## 文件清单

### 后端文件
- `app/models/module.py` - 模块模型
- `app/models/test_case.py` - 测试用例模型
- `app/routes/module.py` - 模块API
- `app/routes/test_case.py` - 测试用例API
- `app/utils/permission.py` - 权限装饰器（已更新）
- `migrate_add_test_case_module.py` - 数据库迁移脚本
- `init_test_case_permissions.py` - 权限初始化脚本
- `test_case_module_demo.py` - 功能演示脚本

### 前端文件
- `client/src/views/TestCaseManagement.vue` - 测试用例管理页面
- `client/src/api/module.js` - 模块API
- `client/src/api/testCase.js` - 测试用例API
- `client/src/router/index.js` - 路由配置（已更新）

### 文档文件
- `TEST_CASE_MODULE_GUIDE.md` - 后端使用指南
- `TEST_CASE_API_EXAMPLES.md` - API示例
- `TEST_CASE_MODULE_SUMMARY.md` - 开发总结
- `FRONTEND_TEST_CASE_GUIDE.md` - 前端使用指南
- `COMPLETE_DEPLOYMENT_GUIDE.md` - 完整部署指南（本文档）

## 下一步

部署完成后，你可以：

1. 创建项目的模块结构
2. 为每个模块添加测试用例
3. 查看统计信息了解测试覆盖情况
4. 后续可以为用例绑定API接口（功能待开发）

## 技术支持

如有问题，请参考：
- 后端API文档：`TEST_CASE_API_EXAMPLES.md`
- 前端使用指南：`FRONTEND_TEST_CASE_GUIDE.md`
- 开发总结：`TEST_CASE_MODULE_SUMMARY.md`

## 版本信息

- 版本：v1.0.0
- 发布日期：2026-01-19
- 开发者：yandc
