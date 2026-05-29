# API路径修复说明

## 问题描述

前端访问测试用例管理页面时，出现404错误：
```
OPTIONS /api/api/modules/tree?project_id=5 HTTP/1.1" 404
OPTIONS /api/api/test-cases?project_id=5&page=1&per_page=20 HTTP/1.1" 404
```

URL中出现了重复的 `/api/api/`。

## 问题原因

1. **baseURL配置**：`client/src/api/request.js` 中已经配置了 `baseURL: 'http://localhost:12048/api'`
2. **API封装重复**：`module.js` 和 `testCase.js` 中的URL又加了 `/api` 前缀
3. **结果**：最终URL变成了 `/api/api/modules/tree`

## 修复内容

### 1. 修复 module.js

**修改前：**
```javascript
export function getModuleTree(projectId) {
  return request({
    url: '/api/modules/tree',  // ❌ 多余的 /api
    method: 'get',
    params: { project_id: projectId }
  })
}
```

**修改后：**
```javascript
export function getModuleTree(projectId) {
  return request({
    url: '/modules/tree',  // ✅ 正确
    method: 'get',
    params: { project_id: projectId }
  })
}
```

### 2. 修复 testCase.js

**修改前：**
```javascript
export function getTestCases(params = {}) {
  return request({
    url: '/api/test-cases',  // ❌ 多余的 /api
    method: 'get',
    params
  })
}
```

**修改后：**
```javascript
export function getTestCases(params = {}) {
  return request({
    url: '/test-cases',  // ✅ 正确
    method: 'get',
    params
  })
}
```

### 3. 修复响应拦截器

**修改前：**
```javascript
service.interceptors.response.use(
  response => {
    const res = response.data
    if (res.code !== 0) {  // ❌ 后端不返回code字段
      ElMessage.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || '请求失败'))
    }
    return res
  }
)
```

**修改后：**
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
    return res
  }
)
```

### 4. 修复组件中的数据处理

**修改前：**
```javascript
const res = await getModuleTree(projectId.value)
moduleTree.value = res.data || []  // ❌ 后端直接返回数组
```

**修改后：**
```javascript
const res = await getModuleTree(projectId.value)
moduleTree.value = res || []  // ✅ 直接使用响应数据
```

## 验证修复

### 1. 重启前端服务

```bash
# 停止当前服务（Ctrl+C）
# 重新启动
cd client
npm run dev
```

### 2. 清除浏览器缓存

- 打开浏览器开发者工具（F12）
- 右键点击刷新按钮
- 选择"清空缓存并硬性重新加载"

### 3. 检查网络请求

打开浏览器开发者工具的Network标签，应该看到：

**正确的请求：**
```
GET http://localhost:12048/api/modules/tree?project_id=5
GET http://localhost:12048/api/test-cases?project_id=5&page=1&per_page=20
```

**错误的请求（修复前）：**
```
GET http://localhost:12048/api/api/modules/tree?project_id=5  ❌
GET http://localhost:12048/api/api/test-cases?project_id=5    ❌
```

### 4. 检查响应状态

- 状态码应该是 `200 OK`
- 响应数据应该正常显示

## 后端API路径

确认后端API路径正确：

```python
# app/routes/module.py
module_bp = Blueprint("module", __name__, url_prefix="/api/modules")

# app/routes/test_case.py
test_case_bp = Blueprint("test_case", __name__, url_prefix="/api/test-cases")
```

最终URL：
- `/api/modules/tree`
- `/api/test-cases`

## 完整的URL构建流程

1. **baseURL**: `http://localhost:12048/api`
2. **API路径**: `/modules/tree`
3. **最终URL**: `http://localhost:12048/api/modules/tree` ✅

## 其他可能的问题

### CORS问题

如果看到CORS错误，确认后端已启用CORS：

```python
# app/flask_app.py
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # ✅ 已配置
```

### 权限问题

如果返回403错误，检查：
1. 是否已登录
2. 用户是否有相应权限
3. token是否正确传递

### 数据库问题

如果返回500错误，检查：
1. 数据库表是否已创建
2. 权限是否已初始化

## 测试步骤

1. **启动后端**
   ```bash
   python run.py
   ```

2. **启动前端**
   ```bash
   cd client
   npm run dev
   ```

3. **访问页面**
   - 登录系统
   - 进入项目列表
   - 选择项目
   - 点击"测试用例"

4. **检查控制台**
   - 打开浏览器开发者工具（F12）
   - 查看Console标签，不应有错误
   - 查看Network标签，请求应该成功

## 修复文件清单

- ✅ `client/src/api/module.js` - 移除URL中的 `/api` 前缀
- ✅ `client/src/api/testCase.js` - 移除URL中的 `/api` 前缀
- ✅ `client/src/api/request.js` - 修复响应拦截器
- ✅ `client/src/views/TestCaseManagement.vue` - 修复数据处理

## 预期结果

修复后，访问测试用例管理页面应该：
1. ✅ 左侧显示模块树（如果有数据）
2. ✅ 中间显示用例列表（如果有数据）
3. ✅ 右侧显示"请选择一个用例查看详情"
4. ✅ 没有404或其他错误

如果是第一次使用，模块树和用例列表会是空的，这是正常的。
