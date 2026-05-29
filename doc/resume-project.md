# 简历项目描述参考

---

## 项目名称

ATP 接口自动化测试平台

## 项目角色

全栈开发（独立完成前后端设计与开发）

## 技术栈

Vue 3 + Element Plus + Vite | Flask + SQLAlchemy + MySQL | APScheduler | OpenAI/通义千问 API

## 项目描述

独立设计并开发的接口自动化测试平台，支持接口管理、用例编排、自动化执行、缺陷跟踪、AI 辅助生成测试用例等功能，服务于团队日常接口测试工作。

## 核心职责 & 亮点

**接口执行引擎**
- 基于 requests 库封装 HTTP 请求工厂，支持 JSON / Form / Raw 多种请求体类型，内置响应断言（状态码校验 + 响应体递归匹配）
- 实现环境变量替换引擎，支持 `{{变量名}}` 占位符语法，按优先级（环境变量 > 全局变量）递归替换请求各字段
- 设计前置 URL 匹配机制，按模块/服务精确匹配环境域名，实现一套用例多环境执行

**自动化任务编排**
- 设计自动化任务执行引擎，支持用例按顺序编排执行，单用例异常不中断整体流程，执行完成自动汇总通过率
- 实现三种触发方式：手动执行、Cron 定时调度（APScheduler + croniter）、Webhook 回调（可对接 CI/CD 流水线）
- 服务启动时自动从数据库恢复定时任务，保证调度持久化

**接口导入**
- 实现 cURL 命令解析器，支持标准格式及 Windows CMD 转义格式，自动提取 method / url / headers / body
- 实现 Swagger/OpenAPI 2.0 & 3.x 文档批量导入，支持 `$ref` 引用解析、按 tag 自动创建目录分组、远程 URL 拉取

**AI 辅助测试**
- 采用适配器模式对接 OpenAI、通义千问、Ollama 三种 AI 提供商，统一 chat / stream / test_connection 接口
- 实现提示词模板机制，支持场景化 AI 调用（如根据接口文档自动生成测试用例）
- API Key 使用 Fernet 对称加密存储，调用时内存解密，用完即清，保障密钥安全

**权限与架构**
- 设计 RBAC 权限模型（admin / owner / member / viewer 四级角色），通过装饰器实现接口级鉴权
- 后端采用 Flask 应用工厂模式 + Flask-Smorest 蓝图组织 20+ 个 API 模块，自动生成 OpenAPI 3.0 文档
- 前端基于 Vue 3 Composition API + Element Plus 构建，Axios 封装统一请求拦截（Token 注入、错误提示）

---

## 简短版（适合简历项目经历栏，3-5 行）

**ATP 接口自动化测试平台** | 全栈开发 | Vue 3 + Flask + MySQL

独立开发的接口自动化测试平台。封装 HTTP 执行引擎，支持环境变量替换和响应断言；实现自动化任务编排，支持 Cron 定时 / Webhook 触发；集成 cURL 解析和 Swagger 批量导入降低用例录入成本；采用适配器模式对接多家 AI 提供商，实现测试用例智能生成；设计 RBAC 权限模型，Flask-Smorest 自动生成 API 文档。

---

## 面试追问准备

| 可能的追问 | 回答要点 |
|------------|----------|
| 执行引擎怎么做的？ | requests.Session 封装，支持多种 body 类型，响应自动 JSON 解析，递归匹配断言 |
| 环境变量怎么替换？ | 正则匹配 `{{xxx}}`，从数据库加载变量字典，递归替换 str/dict/list，环境变量覆盖全局变量 |
| 定时任务怎么保证不丢？ | APScheduler BackgroundScheduler，服务启动时 `_restore_jobs` 从数据库恢复所有 enabled 的 cron 任务 |
| 防重复执行怎么做的？ | 执行前查询是否有 status=running 的记录，有则抛 DuplicateExecutionError 拒绝 |
| AI 适配器怎么扩展？ | 抽象基类定义 chat/chat_stream/test_connection，新增提供商只需实现子类并注册到 _ADAPTER_MAP |
| cURL 解析难点？ | Windows CMD 的 `^` 转义符处理、多行反斜杠合并、body 类型自动判断（JSON > form > raw） |
| Swagger 导入怎么处理 $ref？ | 递归解析 `#/components/schemas/xxx` 路径，深度限制 5 层防止循环引用 |
| 权限怎么设计的？ | Role-Permission 多对多，装饰器从请求头取 token → 查用户 → 查项目成员 → 查角色权限 |
