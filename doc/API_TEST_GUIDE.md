# API测试功能使用指南

## 功能概述

接口测试引擎（RequestFactory）已经完成开发，可以在项目详情页面测试API接口并查看详细的请求/响应信息。

## 使用步骤

### 1. 进入项目详情页面
- 从仪表盘点击项目卡片进入项目详情
- 或直接访问：`http://localhost:5174/projects/{projectId}`

### 2. 选择要测试的接口
- 在中间栏的目录树中点击任意接口
- 右侧面板会显示接口的详细信息

### 3. 执行测试
有两种方式触发测试：

**方式1：右侧详情面板**
- 点击右上角的"测试"按钮

**方式2：树节点操作菜单**
- 在中间栏接口节点上点击"..."按钮
- 选择"测试"选项

### 4. 查看测试结果
测试完成后会弹出对话框，显示：

#### 基本信息
- 测试状态（成功/失败）
- 耗时（秒）
- 执行时间戳

#### 请求信息
- 请求方法（GET/POST/PUT/DELETE/PATCH）
- 请求URL
- Headers（请求头）
- Params（查询参数）
- Body（请求体）

#### 响应信息
- 状态码（带颜色标识）
  - 2xx：绿色（成功）
  - 3xx：蓝色（重定向）
  - 4xx：橙色（客户端错误）
  - 5xx：红色（服务器错误）
- 响应大小
- 编码格式
- Response Body（响应体，自动格式化JSON）
- Response Headers（响应头）

#### 错误信息（如果失败）
- 错误类型
- 错误消息

### 5. 重新测试
- 在测试结果对话框中点击"重新测试"按钮
- 会使用相同的参数再次执行测试

## 技术实现

### 后端：RequestFactory
位置：`app/services/request_factory.py`

功能：
- HTTP请求执行（支持GET/POST/PUT/DELETE/PATCH）
- 自动处理不同的请求体类型（json/form/raw）
- 响应解析（自动识别JSON）
- 错误处理（超时、连接失败、请求异常）
- 性能统计（耗时计算）

### 前端：测试对话框
位置：`client/src/views/ProjectDetail.vue`

功能：
- 调用后端测试接口
- 展示测试结果
- 格式化显示JSON数据
- 状态码颜色标识
- 文件大小格式化

### API接口
```
POST /api/projects/{project_id}/apis/{api_id}/test
```

请求体（可选，用于覆盖接口配置）：
```json
{
  "method": "GET",
  "base_url": "http://localhost:12048",
  "path": "/api/users",
  "headers": {},
  "params": {},
  "body": {},
  "body_type": "json"
}
```

响应：
```json
{
  "code": 0,
  "data": {
    "success": true,
    "duration": 0.123,
    "timestamp": "2026-01-16 22:30:00",
    "request": {
      "method": "GET",
      "url": "http://localhost:12048/api/users",
      "headers": {},
      "params": {},
      "body": {}
    },
    "response": {
      "status_code": 200,
      "status_text": "OK",
      "headers": {},
      "body": {},
      "size": 1024,
      "encoding": "utf-8"
    },
    "error": null
  }
}
```

## 注意事项

1. **URL处理**
   - 如果URL不包含协议，会自动添加`http://`
   - base_url和path会自动拼接

2. **超时设置**
   - 默认超时时间：30秒
   - 可在RequestFactory初始化时修改

3. **请求体类型**
   - `json`：发送JSON格式数据
   - `form`：发送表单数据
   - `raw`：发送原始数据

4. **错误类型**
   - `TimeoutError`：请求超时
   - `ConnectionError`：连接失败
   - `RequestException`：请求异常
   - `UnknownError`：未知错误

## 后续扩展

可以考虑添加以下功能：

1. **断言验证**
   - 状态码断言
   - 响应体字段断言
   - 响应时间断言

2. **环境变量**
   - 支持多环境配置
   - 变量替换

3. **前置/后置脚本**
   - 请求前执行脚本
   - 响应后执行脚本

4. **测试历史**
   - 保存测试记录
   - 查看历史结果

5. **批量测试**
   - 选择多个接口批量测试
   - 生成测试报告
