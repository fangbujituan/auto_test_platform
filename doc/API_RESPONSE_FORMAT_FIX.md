# API 响应格式修复说明

## 问题描述
点击用例节点时，虽然调用了接口，但详情页面没有显示内容。

## 根本原因
不同的后端 API 返回格式不一致：

### Bug API 返回格式
```json
{
  "code": 0,
  "data": {
    "id": 1,
    "title": "Bug标题",
    ...
  }
}
```

### 测试用例详情 API 返回格式
```json
{
  "id": 1,
  "title": "用例标题",
  ...
}
```
直接返回数据，没有包装在 `data` 字段中。

### 目录树 API 返回格式
```json
{
  "code": 0,
  "data": [...]
}
```

## 解决方案

### 修改前
```javascript
const handleNodeClick = async (data) => {
  if (data.type === 'case') {
    try {
      const res = await getTestCase(data.raw_id)
      currentCase.value = res.data  // ❌ 错误：res.data 是 undefined
      currentFolder.value = null
    } catch (error) {
      console.error('加载用例详情失败:', error)
      ElMessage.error('加载用例详情失败')
    }
  }
}
```

### 修改后
```javascript
const handleNodeClick = async (data) => {
  if (data.type === 'case') {
    try {
      const res = await getTestCase(data.raw_id)
      currentCase.value = res  // ✅ 正确：直接使用 res
      currentFolder.value = null
    } catch (error) {
      console.error('加载用例详情失败:', error)
      ElMessage.error('加载用例详情失败')
    }
  }
}
```

同样修改 `submitCase` 函数：
```javascript
if (currentCase.value && caseForm.value.id === currentCase.value.id) {
  const res = await getTestCase(caseForm.value.id)
  currentCase.value = res  // ✅ 直接使用 res
}
```

## API 响应格式对照表

| API | 路径 | 返回格式 | 前端使用 |
|-----|------|---------|---------|
| 获取Bug详情 | `/projects/{id}/bugs/{id}` | `{code, data}` | `res.data` |
| 获取用例详情 | `/test-cases/{id}` | `{...}` | `res` |
| 获取目录树 | `/test-cases/tree/{id}` | `{code, data}` | `res.data` |
| 获取目录列表 | `/projects/{id}/folders` | `{code, data}` | `res.data` |
| 获取Bug目录树 | `/projects/{id}/bugs/tree` | `{code, data}` | `res.data` |

## 响应拦截器说明

`client/src/api/request.js` 中的响应拦截器：
```javascript
service.interceptors.response.use(
  response => {
    const res = response.data
    
    // 如果响应中有error字段，说明是错误响应
    if (res.error) {
      ElMessage.error(res.error || '请求失败')
      return Promise.reject(new Error(res.error || '请求失败'))
    }
    
    // 如果响应有code字段且不为0，说明是错误
    if (res.code !== undefined && res.code !== 0) {
      ElMessage.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || '请求失败'))
    }
    
    // 直接返回响应数据
    return res  // 返回的是 response.data
  },
  ...
)
```

拦截器返回 `response.data`，所以：
- 如果后端返回 `{code: 0, data: {...}}`，前端得到的 `res` 就是这个对象，需要用 `res.data`
- 如果后端直接返回 `{...}`，前端得到的 `res` 就是这个对象，直接用 `res`

## 建议：统一后端返回格式

为了保持一致性，建议修改测试用例详情 API，使其返回格式与其他 API 一致：

### 修改后端代码
```python
# app/routes/test_case.py
@test_case_bp.route("/<int:case_id>", methods=["GET"])
@require_permission("test_case:read")
def get_test_case(case_id):
    """获取测试用例详情。"""
    test_case = TestCaseManagement.query.get(case_id)
    if not test_case:
        return jsonify({"error": "测试用例不存在"}), 404
    
    # 修改为统一格式
    return jsonify({
        "code": 0,
        "data": test_case.to_dict(include_apis=True)
    })
```

### 如果统一后端格式，前端也需要相应修改
```javascript
const handleNodeClick = async (data) => {
  if (data.type === 'case') {
    try {
      const res = await getTestCase(data.raw_id)
      currentCase.value = res.data  // 使用 res.data
      currentFolder.value = null
    } catch (error) {
      console.error('加载用例详情失败:', error)
      ElMessage.error('加载用例详情失败')
    }
  }
}
```

## 当前状态

✅ 已修改前端代码，适配当前后端返回格式  
⚠️ 后端返回格式不统一，建议后续统一

## 测试验证

1. 点击用例节点
2. 查看浏览器控制台网络请求
3. 验证响应数据格式
4. 确认详情面板正确显示

### 预期结果
- 接口返回 200 状态码
- 响应数据包含完整的用例信息
- 右侧详情面板显示用例详情
- 所有字段正确显示

### 调试方法
如果仍然不显示，在浏览器控制台执行：
```javascript
// 查看 currentCase 的值
console.log('currentCase:', currentCase.value)

// 查看接口响应
// 在 handleNodeClick 中添加
console.log('API Response:', res)
```
