# 权限系统使用指南

## 概述

本系统实现了基于角色的访问控制（RBAC），支持项目级别的权限管理。

## 权限架构

### 核心概念

- **用户 (User)**: 系统使用者
- **角色 (Role)**: 权限的集合，如管理员、项目负责人、成员等
- **权限 (Permission)**: 具体的操作权限，格式为 `资源:操作`
- **项目成员 (ProjectMember)**: 用户在项目中的角色关联

### 权限粒度

1. **平台级**: 全局管理员（admin角色）
2. **项目级**: 项目内的权限控制（owner、member、viewer角色）

## 默认角色

### 1. admin - 平台管理员
- 拥有所有权限
- 可以访问所有项目

### 2. owner - 项目负责人
- 项目内所有权限
- 管理项目成员
- 删除项目

### 3. member - 项目成员
- 查看、创建、编辑用例
- 执行测试
- 查看结果
- **不能**删除项目和管理成员

### 4. viewer - 只读用户
- 只能查看项目、用例和执行结果
- 不能进行任何修改操作

## 权限列表

### 项目权限
- `project:read` - 查看项目
- `project:create` - 创建项目
- `project:update` - 编辑项目
- `project:delete` - 删除项目
- `project:manage_member` - 管理项目成员

### 用例权限
- `case:read` - 查看用例
- `case:create` - 创建用例
- `case:update` - 编辑用例
- `case:delete` - 删除用例

### 执行权限
- `execute:run` - 执行测试
- `execute:read` - 查看执行结果

## 初始化步骤

### 1. 初始化数据库表
```bash
python run.py
```

### 2. 初始化权限系统
```bash
python -m app.init_permission
```

### 3. 初始化测试用户（可选）
```bash
curl -X POST http://localhost:12048/api/auth/init
```

## API使用示例

### 1. 用户登录
```bash
curl -X POST http://localhost:12048/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### 2. 创建项目（自动成为项目负责人）
```bash
curl -X POST http://localhost:12048/api/projects \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -H "X-Username: admin" \
  -d '{"name": "测试项目", "description": "项目描述"}'
```

### 3. 查看项目成员
```bash
curl -X GET http://localhost:12048/api/project-members/1 \
  -H "Authorization: Bearer {token}" \
  -H "X-Username: admin"
```

### 4. 添加项目成员
```bash
curl -X POST http://localhost:12048/api/project-members \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -H "X-Username: admin" \
  -d '{
    "project_id": 1,
    "user_id": 2,
    "role": "member"
  }'
```

### 5. 更新成员角色
```bash
curl -X PUT http://localhost:12048/api/project-members/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -H "X-Username: admin" \
  -d '{"role": "viewer"}'
```

### 6. 移除项目成员
```bash
curl -X DELETE http://localhost:12048/api/project-members/1 \
  -H "Authorization: Bearer {token}" \
  -H "X-Username: admin"
```

## 权限检查机制

### 装饰器使用

```python
from app.utils.permission import login_required, check_project_permission

@app.route('/api/projects/<int:project_id>', methods=['PUT'])
@login_required
@check_project_permission('update')
def update_project(project_id):
    # 只有拥有 project:update 权限的用户才能访问
    pass
```

### 手动检查

```python
from app.utils.permission import is_project_owner, is_admin

if is_project_owner(user_id, project_id):
    # 项目负责人特殊逻辑
    pass

if is_admin(user_id):
    # 管理员特殊逻辑
    pass
```

## 注意事项

1. **认证简化**: 当前使用简化的token认证，生产环境应使用JWT
2. **项目创建**: 创建项目的用户自动成为项目负责人（owner）
3. **负责人保护**: 不能移除项目负责人
4. **数据隔离**: 用户只能看到自己参与的项目
5. **权限继承**: 管理员拥有所有项目的所有权限

## 后续扩展

- [ ] 实现JWT token认证
- [ ] 添加资源级权限（具体到某个用例）
- [ ] 支持自定义角色
- [ ] 添加权限审计日志
- [ ] 实现权限缓存机制
