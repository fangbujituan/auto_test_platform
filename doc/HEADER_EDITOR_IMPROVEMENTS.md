# Header 编辑器优化总结

## 优化清单

### 1. ✅ 拼写检查禁用
**问题**：输入框内有红色波浪线（英文拼写检查）
**解决**：为所有输入框添加 `spellcheck="false"` 属性
- 参数键输入框
- 参数值输入框
- 说明输入框

### 2. ✅ 新增行追加到底部
**问题**：点击添加后，新的 header 在顶部
**解决**：移除表格的默认排序配置
- 删除 `:default-sort` 属性
- 新增行现在会追加到表格底部

### 3. ✅ 单行显示（不自动换行）
**问题**：参数值和说明字段自动换行展示
**解决**：将输入框类型改为单行
- 参数值：从 `type="textarea"` 改为普通 `el-input`
- 说明：从 `type="textarea"` 改为普通 `el-input`
- 移除 `:rows="1"` 属性

### 4. ✅ 删除单条记录
**问题**：点击删除按钮，全部清除
**解决**：确保删除逻辑正确
- 删除按钮调用 `deleteRow($index)` 只删除指定行
- 清空按钮调用 `clearAll()` 清空所有行
- 两个按钮功能分离，互不影响

### 5. ✅ Ctrl+S 快捷键保存
**问题**：需要点击保存按钮才能保存
**解决**：添加全局快捷键监听
- 按下 `Ctrl+S`（Windows/Linux）或 `Cmd+S`（Mac）
- 自动触发 `saveApiChanges()` 函数
- 组件卸载时自动清理事件监听

### 6. ✅ 保存后刷新详情页面
**问题**：保存后 header 顺序颠倒
**解决**：重置 KeyValueEditor 的初始化状态
- 保存成功后调用 `resetInitialization()` 方法
- 刷新时重新加载数据，保持原有顺序
- 添加 loading 效果提示用户

## 技术实现细节

### KeyValueEditor.vue 改动
```vue
<!-- 移除排序 -->
<el-table :data="rows" stripe border size="small" class="kv-table">

<!-- 参数值：单行输入 -->
<el-input
  v-model="row.value"
  placeholder="参数值"
  size="small"
  spellcheck="false"
  @input="updateModel"
/>

<!-- 说明：单行输入 -->
<el-input
  v-model="row.description"
  placeholder="参数说明"
  size="small"
  spellcheck="false"
  @input="updateModel"
/>
```

```javascript
// 重置初始化状态（用于刷新后重新加载数据）
const resetInitialization = () => {
  isInitialized = false
}

// 暴露方法给父组件
defineExpose({
  resetInitialization
})
```

### ProjectDetail.vue 改动
```javascript
// 导入 onUnmounted
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'

// 添加 ref
const keyValueEditorRef = ref(null)

// 快捷键处理
const handleKeyDown = (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === 's') {
    event.preventDefault()
    if (currentApi.value) {
      saveApiChanges()
    }
  }
}

// 保存接口修改
const saveApiChanges = async () => {
  testingApi.value = true  // 显示 loading
  try {
    // ... 保存逻辑 ...
    
    // 重置 KeyValueEditor 的初始化状态
    if (keyValueEditorRef.value) {
      keyValueEditorRef.value.resetInitialization()
    }
    
    // 重新加载树
    await loadTree()
  } finally {
    testingApi.value = false  // 隐藏 loading
  }
}

// 挂载时添加监听
onMounted(() => {
  loadTree()
  loadCategories()
  window.addEventListener('keydown', handleKeyDown)
})

// 卸载时移除监听
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})
```

## 使用体验提升

| 功能 | 改进前 | 改进后 |
|------|--------|--------|
| 拼写检查 | 红色波浪线干扰 | 干净整洁 |
| 新增行位置 | 顶部（需要滚动） | 底部（直观） |
| 输入框显示 | 自动换行（占用空间） | 单行显示（紧凑） |
| 删除操作 | 容易误删全部 | 精确删除单条 |
| 保存方式 | 必须点击按钮 | 快捷键 Ctrl+S |
| 保存反馈 | 无 loading 提示 | 有 loading 效果 |
| 刷新后顺序 | 顺序颠倒 | 保持原有顺序 |

## 快捷键说明

- **Windows/Linux**：`Ctrl+S`
- **Mac**：`Cmd+S`
- 仅在选中接口时有效
- 自动保存接口配置到数据库
- 保存时显示 loading 效果
