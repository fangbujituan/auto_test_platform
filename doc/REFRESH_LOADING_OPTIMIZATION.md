# 模块切换刷新优化

## 优化内容

将项目管理页面中三个模块（接口管理、Bug管理、测试用例）的切换刷新提示，从简单的消息提示优化为统一的加载动画组件。

## 实现方案

### 1. 创建统一的加载组件

**文件**: `client/src/components/RefreshLoading.vue`

**特性**:
- 全屏半透明遮罩层，带毛玻璃效果
- 三环旋转加载动画，使用不同颜色（蓝、绿、橙）
- 可自定义加载文本
- 平滑的淡入淡出过渡动画
- 从下往上滑入效果

### 2. 三个模块页面集成

#### 接口管理 (ProjectDetail.vue)
- 添加 `refreshing` 状态变量
- 导入 `RefreshLoading` 组件
- 在模板中添加加载组件: `<refresh-loading :visible="refreshing" text="正在刷新接口数据..." />`
- 修改 `handleModuleChange` 为异步函数，使用 `Promise.all` 并行加载数据

#### Bug管理 (BugManagementNew.vue)
- 添加 `refreshing` 状态变量
- 导入 `RefreshLoading` 组件
- 在模板中添加加载组件: `<refresh-loading :visible="refreshing" text="正在刷新Bug数据..." />`
- 修改 `handleModuleChange` 为异步函数，使用 `Promise.all` 并行加载数据

#### 测试用例管理 (TestCaseManagement2.vue)
- 添加 `refreshing` 状态变量
- 导入 `RefreshLoading` 组件
- 在模板中添加加载组件: `<refresh-loading :visible="refreshing" text="正在刷新测试用例数据..." />`
- 修改 `handleModuleChange` 为异步函数，使用 `Promise.all` 并行加载数据

## 用户体验提升

### 优化前
- 点击切换后立即显示消息提示 "已刷新XXX数据"
- 用户无法感知数据加载过程
- 可能在数据未加载完成时就看到提示

### 优化后
- 点击切换后显示优雅的全屏加载动画
- 清晰的加载状态提示
- 数据加载完成后自动关闭，体验流畅
- 视觉效果更专业

## 技术细节

### 加载动画实现
```css
- 三个旋转环使用不同的动画延迟
- 使用 cubic-bezier 缓动函数实现流畅旋转
- backdrop-filter 实现毛玻璃背景效果
```

### 异步加载优化
```javascript
// 使用 Promise.all 并行加载多个数据源
refreshing.value = true
try {
  await Promise.all([loadTree(), loadFolders()])
} finally {
  refreshing.value = false
}
```

## 效果展示

1. **接口管理**: 显示 "正在刷新接口数据..."
2. **Bug管理**: 显示 "正在刷新Bug数据..."
3. **测试用例管理**: 显示 "正在刷新测试用例数据..."

每个模块都有独立的提示文本，让用户清楚知道当前正在加载什么内容。
