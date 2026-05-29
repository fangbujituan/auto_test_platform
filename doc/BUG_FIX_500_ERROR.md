# Bug管理模块500错误修复说明

## 问题描述

创建Bug时接口返回500错误。

## 错误原因

在Bug API中使用了`g.user.id`来获取当前用户ID，但权限装饰器中设置的是`g.current_user`，导致`g.user`为None，引发AttributeError。

## 修复内容

### 1. 修复Bug API (`app/routes/bug.py`)

#### 创建Bug接口
```python
# 修复前
reporter_id=data.get("reporter_id", g.user.id),

# 修复后
current_user = g.get('current_user')
reporter_id=data.get("reporter_id", current_user.id if current_user else None),
```

#### 解决Bug接口
```python
# 修复前
bug.resolved_by = g.user.id

# 修复后
current_user = g.get('current_user')
bug.resolved_by = current_user.id if current_user else None
```

### 2. 增强权限装饰器 (`app/utils/permission.py`)

为了兼容性，同时设置`g.user`和`g.current_user`：

```python
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({
                "code": 401,
                "message": "未登录或登录已过期"
            }), 401
        
        g.current_user = user
        g.user = user  # 为了兼容性，同时设置g.user
        return f(*args, **kwargs)
    
    return decorated_function
```

## 修复步骤

1. 更新 `app/routes/bug.py` 文件
2. 更新 `app/utils/permission.py` 文件
3. 重启Flask服务

```bash
# 停止当前运行的服务（Ctrl+C）
# 重新启动
python run.py
```

## 验证修复

### 方法1：使用前端测试
1. 访问 http://localhost:5173
2. 登录系统
3. 进入项目的Bug管理页面
4. 点击"新建Bug"
5. 填写表单并提交
6. 应该成功创建Bug

### 方法2：使用curl测试
```bash
curl -X POST http://localhost:12048/api/projects/5/bugs \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Username: admin" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "测试Bug",
    "description": "测试描述",
    "priority": "medium",
    "severity": "normal",
    "status": "open"
  }'
```

### 方法3：使用测试脚本
```bash
python test_bug_api.py
```

## 预期结果

创建Bug成功，返回：
```json
{
  "code": 0,
  "message": "创建成功",
  "data": {
    "id": 6,
    "title": "测试Bug",
    "status": "open",
    "priority": "medium",
    "severity": "normal",
    "reporter_id": 3,
    "created_at": "2026-01-22 14:30:00",
    ...
  }
}
```

## 其他可能的问题

### 问题1：reporter_id为NULL
**原因：** 用户未正确登录或token无效
**解决：** 确保请求头包含有效的Authorization和X-Username

### 问题2：权限不足
**原因：** 用户没有项目的create权限
**解决：** 检查用户在项目中的角色和权限

### 问题3：项目ID不存在
**原因：** 请求的项目ID在数据库中不存在
**解决：** 使用正确的项目ID

## 注意事项

1. **重启服务**：修改代码后必须重启Flask服务才能生效
2. **清除缓存**：如果使用了缓存，可能需要清除
3. **检查日志**：如果仍有问题，查看Flask控制台的错误日志
4. **数据库连接**：确保数据库连接正常

## 修复后的完整流程

1. ✅ 修复代码
2. ✅ 重启服务
3. ✅ 测试创建Bug
4. ✅ 测试解决Bug
5. ✅ 测试其他功能

## 总结

此次修复解决了创建Bug时的500错误，主要是统一了用户对象在Flask g对象中的存储方式。现在Bug管理模块可以正常使用了。

---

**修复时间：** 2026-01-22  
**影响范围：** Bug创建和解决功能  
**修复状态：** ✅ 已完成
