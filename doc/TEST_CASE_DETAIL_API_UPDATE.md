# 测试用例详情接口调用更新

## 问题
之前点击用例节点时，只是显示树节点中的数据，没有调用接口获取最新的详细信息。

## 解决方案
参考 Bug 管理的实现，在点击用例节点时调用接口获取最新数据。

## 修改内容

### 1. 导入 getTestCase 接口
```javascript
import { 
  getTestCases, 
  getTestCase,  // 新增
  createTestCase, 
  updateTestCase, 
  deleteTestCase as deleteTestCaseApi 
} from '../api/testCase'
```

### 2. 修改 handleNodeClick 函数
**修改前：**
```javascript
const handleNodeClick = (data) => {
  if (data.type === 'case') {
    currentCase.value = data  // 直接使用树节点数据
    currentFolder.value = null
  } else if (data.type === 'folder') {
    currentFolder.value = data
    currentCase.value = null
  }
}
```

**修改后：**
```javascript
const handleNodeClick = async (data) => {
  if (data.type === 'case') {
    try {
      const res = await getTestCase(data.raw_id)  // 调用接口获取最新数据
      currentCase.value = res.data
      currentFolder.value = null
    } catch (error) {
      console.error('加载用例详情失败:', error)
      ElMessage.error('加载用例详情失败')
    }
  } else if (data.type === 'folder') {
    currentFolder.value = data
    currentCase.value = null
  }
}
```

### 3. 修改 submitCase 函数
在编辑用例后，重新加载最新数据而不是简单地合并对象。

**修改前：**
```javascript
if (currentCase.value && caseForm.value.id === currentCase.value.id) {
  // 更新当前用例数据
  Object.assign(currentCase.value, caseForm.value)
}
```

**修改后：**
```javascript
if (currentCase.value && caseForm.value.id === currentCase.value.id) {
  // 重新加载当前用例的最新数据
  const res = await getTestCase(caseForm.value.id)
  currentCase.value = res.data
}
```

## 接口说明

### 前端 API
```javascript
// client/src/api/testCase.js
export function getTestCase(caseId) {
  return request({
    url: `/test-cases/${caseId}`,
    method: 'get'
  })
}
```

### 后端 API
```python
# app/routes/test_case.py
@test_case_bp.route("/<int:case_id>", methods=["GET"])
@require_permission("test_case:read")
def get_test_case(case_id):
    """获取测试用例详情。"""
    test_case = TestCaseManagement.query.get(case_id)
    if not test_case:
        return jsonify({"error": "测试用例不存在"}), 404
    
    return jsonify(test_case.to_dict(include_apis=True))
```

## 优势

### 1. 数据实时性
- ✅ 每次点击用例都获取最新数据
- ✅ 避免显示过期的缓存数据
- ✅ 确保详情面板显示的是数据库中的最新状态

### 2. 数据完整性
- ✅ 获取完整的用例详情（包括关联的 API 信息）
- ✅ 树节点数据可能不包含所有字段，接口返回完整数据
- ✅ 支持 `include_apis=True` 参数，获取关联的 API 列表

### 3. 一致性
- ✅ 与 Bug 管理模块保持一致的交互方式
- ✅ 统一的错误处理机制
- ✅ 相同的用户体验

### 4. 可靠性
- ✅ 编辑后重新加载，确保显示最新数据
- ✅ 错误提示，用户体验更好
- ✅ 异步加载，不阻塞 UI

## 数据流程

### 点击用例节点
```
用户点击用例
    ↓
handleNodeClick(data)
    ↓
调用 getTestCase(data.raw_id)
    ↓
GET /test-cases/{case_id}
    ↓
返回完整的用例数据
    ↓
更新 currentCase.value
    ↓
右侧面板显示详情
```

### 编辑用例
```
用户编辑用例
    ↓
submitCase()
    ↓
调用 updateTestCase(id, data)
    ↓
PUT /test-cases/{case_id}
    ↓
更新成功
    ↓
调用 getTestCase(id) 获取最新数据
    ↓
更新 currentCase.value
    ↓
右侧面板显示最新详情
```

## 返回数据示例

```json
{
  "id": 1,
  "case_no": "TC-001",
  "title": "测试正常登录",
  "description": "验证用户使用正确的用户名和密码能够成功登录",
  "priority": "P1",
  "case_type": "功能",
  "case_status": "已评审",
  "folder_id": 5,
  "module_id": 3,
  "precondition": "用户已注册且账号状态正常",
  "steps": "1. 打开登录页面\n2. 输入用户名\n3. 输入密码\n4. 点击登录按钮",
  "expected_result": "成功登录并跳转到首页",
  "project_id": 1,
  "created_at": "2024-01-20 10:30:00",
  "updated_at": "2024-01-22 15:45:00",
  "api_ids": [10, 11, 12],
  "apis": [
    {
      "id": 10,
      "name": "用户登录接口",
      "method": "POST",
      "path": "/api/auth/login"
    }
  ]
}
```

## 性能考虑

### 优化点
1. **按需加载**：只在点击时才加载详情，不是一次性加载所有用例的详情
2. **缓存策略**：可以考虑添加缓存机制，避免重复点击同一用例时重复请求
3. **加载状态**：可以添加 loading 状态，提升用户体验

### 未来优化建议
```javascript
// 添加加载状态
const detailLoading = ref(false)

const handleNodeClick = async (data) => {
  if (data.type === 'case') {
    detailLoading.value = true
    try {
      const res = await getTestCase(data.raw_id)
      currentCase.value = res.data
      currentFolder.value = null
    } catch (error) {
      console.error('加载用例详情失败:', error)
      ElMessage.error('加载用例详情失败')
    } finally {
      detailLoading.value = false
    }
  }
}
```

## 测试建议

1. **基本功能测试**
   - 点击用例节点，验证详情正确显示
   - 验证接口被正确调用
   - 验证返回数据完整

2. **编辑后刷新测试**
   - 编辑用例信息
   - 保存后验证详情面板显示最新数据
   - 验证树节点也更新了

3. **错误处理测试**
   - 点击不存在的用例（模拟 404）
   - 网络错误情况
   - 验证错误提示正确显示

4. **性能测试**
   - 快速连续点击多个用例
   - 验证请求不会堆积
   - 验证响应时间合理

## 与 Bug 管理的对比

| 特性 | Bug 管理 | 测试用例 | 状态 |
|------|---------|----------|------|
| 点击节点调用接口 | ✅ | ✅ | 已实现 |
| 获取完整详情 | ✅ | ✅ | 已实现 |
| 编辑后刷新 | ✅ | ✅ | 已实现 |
| 错误处理 | ✅ | ✅ | 已实现 |
| 加载状态 | ❌ | ❌ | 可优化 |

现在测试用例管理与 Bug 管理在数据加载方面保持完全一致！
