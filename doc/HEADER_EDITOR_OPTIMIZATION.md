# Header 编辑器优化指南

## 优化概述

接口详情页的 Header 参数编辑已优化为键值对列表方式，提升了用户体验。

## 主要改进

### 1. 编辑方式升级
- **之前**：JSON 格式文本编辑，需要手动编写 JSON 语法
- **现在**：表格形式的键值对编辑，更直观易用

### 2. 新增功能
- 参数键（Key）：输入框编辑
- 参数值（Value）：支持多行输入
- 参数类型（Type）：下拉选择（string、number、boolean、array、object）
- 说明（Description）：参数说明文本
- 快速操作：添加行、删除行、清空所有

### 3. 后端兼容性
- 前端以列表方式编辑，调用接口时自动转换为 JSON 格式
- 后端无需任何改动，继续接收 JSON 格式的 header 参数

## 技术实现

### 新增组件
**文件**：`client/src/components/KeyValueEditor.vue`

**功能**：
- 维护行数据列表（key、value、type、description）
- 通过 v-model 与父组件双向绑定
- 自动将列表转换为 JSON 对象发送给后端
- 支持类型转换（string、number、boolean、array、object）

### 集成位置
**文件**：`client/src/views/ProjectDetail.vue`

**变更**：
- 导入 KeyValueEditor 组件
- 将 Headers 标签页的 JsonEditor 替换为 KeyValueEditor
- 其他功能（发送请求、保存接口）无需改动

## 使用流程

1. **打开接口详情页**
   - 在接口管理中选择一个接口

2. **编辑 Header 参数**
   - 点击"Headers"标签页
   - 点击"添加"按钮新增参数行
   - 填写参数键、参数值、参数类型、说明
   - 支持删除单行或清空所有参数

3. **发送请求**
   - 点击"发送"按钮
   - 前端自动将列表格式转换为 JSON 格式
   - 后端接收标准 JSON 格式的 header

4. **保存接口**
   - 点击"保存"按钮
   - 接口配置保存到数据库

## 示例

### 编辑界面
| 参数键 | 参数值 | 参数类型 | 说明 |
|--------|--------|---------|------|
| Content-Type | application/json | string | 请求内容类型 |
| Authorization | Bearer token123 | string | 认证令牌 |
| X-Custom-Header | 123 | number | 自定义数字头 |

### 转换后的 JSON（发送给后端）
```json
{
  "Content-Type": "application/json",
  "Authorization": "Bearer token123",
  "X-Custom-Header": 123
}
```

## 类型转换规则

| 参数类型 | 转换方式 | 示例 |
|---------|---------|------|
| string | 保持字符串 | "hello" |
| number | parseFloat() | 123 → 123 |
| boolean | 字符串 'true'/'false' 转布尔值 | "true" → true |
| array | JSON.parse() | "[1,2,3]" → [1,2,3] |
| object | JSON.parse() | '{"a":1}' → {a:1} |

## 后续优化方向

1. 支持从 JSON 导入参数
2. 支持参数模板保存和快速应用
3. 支持参数验证规则
4. 支持参数加密存储
