# 数据库迁移说明 - 测试用例表字段修改

## 迁移目的
修改 `test_case_management` 表，使 `module_id` 和 `folder_id` 字段变为可选，支持新的目录管理方式。

## 问题背景

### 原表结构
```sql
CREATE TABLE test_case_management (
    id INT PRIMARY KEY AUTO_INCREMENT,
    project_id INT NOT NULL,
    module_id INT NOT NULL,  -- ❌ 不能为空
    folder_id INT,           -- 可以为空
    ...
);
```

### 问题
- `module_id` 字段设置为 `NOT NULL`，导致创建测试用例时必须提供模块ID
- 前端已改用 `folder_id` 管理目录结构，不再使用 `module_id`
- 创建用例时报错："模块ID不能为空"

## 迁移内容

### 修改的字段
1. **module_id**: `NOT NULL` → `NULL`（可选）
2. **folder_id**: 确保为 `NULL`（可选）

### 迁移脚本
文件：`migrate_test_case_optional_fields.py`

```python
# 修改 module_id 字段为可空
ALTER TABLE test_case_management 
MODIFY COLUMN module_id INT NULL COMMENT '所属模块ID（可选）';

# 确保 folder_id 字段为可空
ALTER TABLE test_case_management 
MODIFY COLUMN folder_id INT NULL COMMENT '所属目录ID（可选）';
```

## 执行迁移

### 运行命令
```bash
python migrate_test_case_optional_fields.py
```

### 执行结果
```
开始迁移测试用例表...
1. 修改 module_id 字段为可空...
2. 确保 folder_id 字段为可空...
✅ 迁移成功完成！

验证表结构...

当前字段信息:
  - module_id: int, Null=YES, Default=None
  - folder_id: int, Null=YES, Default=None
```

## 迁移后的表结构

```sql
CREATE TABLE test_case_management (
    id INT PRIMARY KEY AUTO_INCREMENT,
    case_no VARCHAR(50) NOT NULL UNIQUE,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    precondition TEXT,
    steps TEXT,
    expected_result TEXT,
    
    -- 分类信息
    project_id INT NOT NULL,
    module_id INT NULL COMMENT '所属模块ID（可选）',  -- ✅ 可以为空
    folder_id INT NULL COMMENT '所属目录ID（可选）',  -- ✅ 可以为空
    
    -- 用例属性
    priority VARCHAR(10) DEFAULT 'P2',
    case_type VARCHAR(20) DEFAULT '功能',
    case_status VARCHAR(20) DEFAULT '草稿',
    status INT DEFAULT 1,
    
    created_at DATETIME,
    updated_at DATETIME,
    
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (module_id) REFERENCES modules(id),
    FOREIGN KEY (folder_id) REFERENCES api_folders(id)
);
```

## 模型代码修改

### app/models/test_case.py

**修改前：**
```python
module_id = db.Column(db.Integer, db.ForeignKey("modules.id"), nullable=False)
folder_id = db.Column(db.Integer, db.ForeignKey("api_folders.id"), comment="所属目录ID")
```

**修改后：**
```python
module_id = db.Column(db.Integer, db.ForeignKey("modules.id"), nullable=True, comment="所属模块ID（可选）")
folder_id = db.Column(db.Integer, db.ForeignKey("api_folders.id"), nullable=True, comment="所属目录ID（可选）")
```

## 支持的使用场景

### 1. 只使用 folder_id（推荐）
```json
{
  "title": "测试用例",
  "folder_id": 16,
  "project_id": 5
}
```

### 2. 只使用 module_id（兼容旧方式）
```json
{
  "title": "测试用例",
  "module_id": 3,
  "project_id": 5
}
```

### 3. 同时使用两者（兼容模式）
```json
{
  "title": "测试用例",
  "folder_id": 16,
  "module_id": 3,
  "project_id": 5
}
```

### 4. 都不使用（未分类）
```json
{
  "title": "测试用例",
  "project_id": 5
}
```
用例会显示在"未分类"节点下。

## 数据影响

### 现有数据
- ✅ 现有数据不受影响
- ✅ 已有的 `module_id` 值保持不变
- ✅ 不需要数据迁移

### 新数据
- ✅ 可以只提供 `folder_id`
- ✅ 可以只提供 `module_id`
- ✅ 可以两者都提供
- ✅ 可以两者都不提供

## 验证测试

### 1. 创建用例（只使用 folder_id）
```bash
curl -X POST "http://localhost:12048/api/test-cases" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  --data '{
    "title": "测试用例01",
    "folder_id": 16,
    "project_id": 5
  }'
```
**预期结果：** ✅ 成功创建

### 2. 创建用例（不指定 folder_id 和 module_id）
```bash
curl -X POST "http://localhost:12048/api/test-cases" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  --data '{
    "title": "未分类用例",
    "project_id": 5
  }'
```
**预期结果：** ✅ 成功创建，显示在"未分类"

### 3. 查询表结构
```sql
SHOW COLUMNS FROM test_case_management WHERE Field IN ('module_id', 'folder_id');
```

**预期结果：**
```
+------------+------+------+-----+---------+-------+
| Field      | Type | Null | Key | Default | Extra |
+------------+------+------+-----+---------+-------+
| module_id  | int  | YES  | MUL | NULL    |       |
| folder_id  | int  | YES  | MUL | NULL    |       |
+------------+------+------+-----+---------+-------+
```

## 回滚方案

如果需要回滚（不推荐），可以执行：

```sql
-- 注意：回滚前需要确保所有测试用例都有 module_id
ALTER TABLE test_case_management 
MODIFY COLUMN module_id INT NOT NULL COMMENT '所属模块ID';
```

⚠️ **警告**：回滚前必须确保所有测试用例都有有效的 `module_id`，否则会失败。

## 相关文件

### 迁移脚本
- `migrate_test_case_optional_fields.py` - 数据库迁移脚本

### 修改的代码文件
- `app/models/test_case.py` - 模型定义
- `app/routes/test_case.py` - API 接口（验证逻辑）

### 文档
- `TEST_CASE_CREATE_FIX.md` - API 修复说明
- `TEST_CASE_FOLDER_INTEGRATION.md` - 目录集成说明

## 注意事项

1. **外键约束**：`module_id` 和 `folder_id` 的外键约束仍然存在，如果提供了值，必须是有效的ID
2. **数据一致性**：建议逐步将数据从 `module_id` 迁移到 `folder_id`
3. **权限控制**：确保用户有权限访问指定的目录或模块
4. **级联删除**：删除目录或模块时，需要处理关联的测试用例

## 后续计划

1. ✅ 完成数据库迁移
2. ✅ 修改 API 验证逻辑
3. ✅ 前端使用 folder_id
4. ⏳ 数据迁移：将现有 module_id 数据迁移到 folder_id
5. ⏳ 废弃 module_id：在未来版本中完全移除 module_id 字段

## 总结

✅ 迁移成功完成  
✅ 字段已修改为可选  
✅ 支持多种使用场景  
✅ 向后兼容现有数据  
✅ 前端可以正常创建测试用例
