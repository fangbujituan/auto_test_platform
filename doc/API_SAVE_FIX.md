# 接口保存字段修复说明

## 问题描述

在接口详情页面修改 Query Params、Headers、Body 这三个字段后，点击保存按钮，数据没有正确入库。

## 问题原因分析

经过排查，发现了以下问题：

### 1. 后端目录树接口缺少字段

**文件**: `app/routes/api_folder.py`

在 `get_folder_tree` 接口中，构建接口节点时，**没有包含** `headers`、`params`、`body`、`body_type`、`response_example` 等关键字段。

```python
# 修复前 - 缺少关键字段
api_node = {
    'id': f'api_{api.id}',
    'raw_id': api.id,
    'name': api.name,
    'description': api.description,
    'type': 'api',
    'method': api.method,
    'path': api.path,
    'base_url': api.base_url,
    'folder_id': api.folder_id,
    'category': api.category,
    'status': api.status,
    'created_at': api.created_at.strftime("%Y-%m-%d %H:%M:%S"),
    'updated_at': api.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
    'children': []
}
```

### 2. JsonEditor 组件只在失焦时更新

**文件**: `client/src/components/JsonEditor.vue`

JsonEditor 组件原本只在 `blur` 事件（失焦）时才会更新 `modelValue`。如果用户编辑后直接点击保存按钮，数据可能还没有更新到父组件。

### 3. 数据引用问题

在 `watch(currentApi)` 中，直接使用 `newApi.headers || {}` 可能导致引用问题，需要使用深拷贝。

## 修复方案

### 1. 后端修复 - 添加缺失字段

在 `app/routes/api_folder.py` 的 `get_folder_tree` 接口中，为接口节点添加完整字段：

```python
# 修复后 - 包含所有字段
api_node = {
    'id': f'api_{api.id}',
    'raw_id': api.id,
    'name': api.name,
    'description': api.description,
    'type': 'api',
    'method': api.method,
    'path': api.path,
    'base_url': api.base_url,
    'folder_id': api.folder_id,
    'category': api.category,
    'status': api.status,
    'headers': api.headers or {},          # ✓ 新增
    'params': api.params or {},            # ✓ 新增
    'body': api.body or {},                # ✓ 新增
    'body_type': api.body_type or 'json', # ✓ 新增
    'response_example': api.response_example or {}, # ✓ 新增
    'created_at': api.created_at.strftime("%Y-%m-%d %H:%M:%S"),
    'updated_at': api.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
    'children': []
}
```

**修改位置**：
- 目录下的接口节点（第 138-158 行）
- 未分类接口节点（第 185-205 行）

### 2. 前端修复 - JsonEditor 实时更新

在 `client/src/components/JsonEditor.vue` 中，添加 `input` 事件的防抖处理：

```javascript
// 输入时延迟验证（防抖）
const handleInput = () => {
  if (inputTimer) {
    clearTimeout(inputTimer)
  }
  
  inputTimer = setTimeout(() => {
    tryParseAndEmit()
  }, 500) // 500ms 延迟
}
```

这样用户在输入时，会在停止输入 500ms 后自动更新数据，不需要等待失焦。

### 3. 前端修复 - 数据深拷贝

在 `client/src/views/ProjectDetail.vue` 的 `watch(currentApi)` 中，使用深拷贝：

```javascript
watch(currentApi, (newApi) => {
  if (newApi) {
    editableApi.value = {
      method: newApi.method || 'GET',
      fullUrl: (newApi.base_url || '') + (newApi.path || ''),
      description: newApi.description || '',
      headers: JSON.parse(JSON.stringify(newApi.headers || {})),  // 深拷贝
      params: JSON.parse(JSON.stringify(newApi.params || {})),    // 深拷贝
      body: JSON.parse(JSON.stringify(newApi.body || {})),        // 深拷贝
      body_type: newApi.body_type || 'json'
    }
    // ...
  }
}, { immediate: true })
```

### 4. 前端修复 - 添加调试日志

在 `saveApiChanges` 函数中添加调试日志，方便排查问题：

```javascript
console.log('保存接口数据:', updateData)
console.log('headers:', JSON.stringify(updateData.headers))
console.log('params:', JSON.stringify(updateData.params))
console.log('body:', JSON.stringify(updateData.body))
```

### 5. 前端修复 - 保存后刷新数据

保存成功后，重新加载树并更新当前接口数据：

```javascript
await updateApi(projectId.value, currentApi.value.raw_id, updateData)
ElMessage.success('保存成功')

// 重新加载树以获取最新数据
await loadTree()

// 更新当前接口数据
if (currentApi.value) {
  const updatedNode = findNodeById(treeData.value, currentApi.value.raw_id)
  if (updatedNode) {
    currentApi.value = updatedNode
  }
}
```

## 测试验证

运行测试脚本验证修复：

```bash
python tests/test_api_save_fix.py
```

测试内容：
1. 更新接口的 headers、params、body 字段
2. 提交到数据库
3. 重新查询验证数据是否正确保存
4. 验证 to_dict() 方法返回的数据是否正确

## 使用说明

修复后的使用流程：

1. 在左侧目录树中选择一个接口
2. 右侧自动显示接口详情，包含完整的 headers、params、body 数据
3. 在请求参数页签中修改 Query Params、Headers、Body
4. 修改会在停止输入 500ms 后自动更新到内存
5. 点击"保存"按钮，数据会正确保存到数据库
6. 保存成功后，页面会自动刷新显示最新数据

## 相关文件

- `app/routes/api_folder.py` - 后端目录树接口
- `client/src/components/JsonEditor.vue` - JSON 编辑器组件
- `client/src/views/ProjectDetail.vue` - 接口详情页面
- `tests/test_api_save_fix.py` - 测试脚本

## 注意事项

1. JsonEditor 组件现在支持实时更新（500ms 防抖），但仍然保留失焦时的立即更新
2. 所有 JSON 字段都使用深拷贝，避免引用问题
3. 保存后会自动刷新数据，确保显示的是最新状态
4. 控制台会输出调试日志，方便排查问题
