# ATP 前端 (Vue 3 + Vite)

自动化测试平台前端，基于 Vue 3 + Element Plus + Vite 构建。

## 技术栈

- Vue 3（Composition API / `<script setup>`）
- Vite 7.x — 构建工具
- Element Plus — UI 组件库
- Vue Router 4 — 路由管理
- Axios — HTTP 客户端
- WangEditor — 富文本编辑器

## 快速开始

```bash
npm install
npm run dev
```

开发服务器运行在 http://localhost:5173

## 构建

```bash
npm run build
npm run preview   # 预览构建产物
```

## 项目结构

```
src/
├── api/            # 后端 API 请求封装
├── components/     # 公共组件（AI 聊天、JSON 编辑器、环境变量面板等）
├── views/          # 页面视图
├── router/         # 路由配置
├── App.vue         # 根组件
└── main.js         # 入口文件
```
