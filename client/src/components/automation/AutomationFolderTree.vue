<template>
  <div class="automation-folder-tree">
    <!-- 顶部搜索 + 新增 -->
    <div class="panel-header">
      <el-input
        v-model="keyword"
        placeholder="搜索任务/目录"
        clearable
        size="small"
        spellcheck="false"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-dropdown trigger="click" placement="bottom-start" @command="onAddCommand">
        <el-button type="primary" size="small" class="add-btn">
          <el-icon><Plus /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="folder">
              <el-icon><Folder /></el-icon>新建目录
            </el-dropdown-item>
            <el-dropdown-item command="automation">
              <el-icon><VideoPlay /></el-icon>添加自动化
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <!-- 树 -->
    <div v-loading="loading" class="tree-container">
      <el-tree
        ref="treeRef"
        :data="treeData"
        :props="treeProps"
        node-key="id"
        :expand-on-click-node="false"
        :highlight-current="true"
        :default-expand-all="false"
        :filter-node-method="filterNode"
        :indent="16"
        @node-click="onNodeClick"
      >
        <template #default="{ node, data }">
          <div class="tree-node">
            <div class="node-content">
              <el-icon v-if="data.type === 'folder'" class="node-icon folder-icon">
                <FolderOpened v-if="node.expanded" />
                <Folder v-else />
              </el-icon>
              <el-icon v-else-if="data.type === 'automation'" class="node-icon task-icon">
                <VideoPlay />
              </el-icon>
              <span class="node-label" :title="data.description || data.name">
                {{ data.name }}
              </span>
              <span v-if="data.type === 'folder' && data.children?.length" class="node-count">
                ({{ data.children.length }})
              </span>
              <el-tag v-if="data.type === 'automation' && data.status === 0" size="small" type="info">禁用</el-tag>
            </div>

            <div class="node-actions" @click.stop>
              <el-dropdown
                v-if="data.type === 'folder' && !data.is_virtual"
                trigger="click"
                @command="(cmd) => onFolderAction(cmd, data)"
              >
                <el-icon class="action-icon"><MoreFilled /></el-icon>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="addAutomation">
                      <el-icon><DocumentAdd /></el-icon>在此目录添加自动化
                    </el-dropdown-item>
                    <el-dropdown-item command="addFolder">
                      <el-icon><FolderAdd /></el-icon>新建子目录
                    </el-dropdown-item>
                    <el-dropdown-item command="rename" divided>
                      <el-icon><Edit /></el-icon>重命名
                    </el-dropdown-item>
                    <el-dropdown-item command="delete">
                      <el-icon><Delete /></el-icon>删除目录
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-dropdown
                v-else-if="data.type === 'automation'"
                trigger="click"
                @command="(cmd) => onTaskAction(cmd, data)"
              >
                <el-icon class="action-icon"><MoreFilled /></el-icon>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="execute">
                      <el-icon><VideoPlay /></el-icon>执行
                    </el-dropdown-item>
                    <el-dropdown-item command="history">
                      <el-icon><Clock /></el-icon>查看历史
                    </el-dropdown-item>
                    <el-dropdown-item command="delete" divided>
                      <el-icon><Delete /></el-icon>删除
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
        </template>
      </el-tree>

      <el-empty v-if="!loading && treeData.length === 0" description="暂无自动化任务" :image-size="80" />
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

import {
  Search, Plus, Folder, FolderOpened, FolderAdd, VideoPlay,
  MoreFilled, DocumentAdd, Edit, Delete, Clock
} from '@element-plus/icons-vue'

const props = defineProps({
  treeData: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits([
  'select-task', 'add-folder', 'add-automation',
  'folder-action', 'task-action'
])

const treeRef = ref(null)
const keyword = ref('')

const treeProps = {
  children: 'children',
  label: 'name'
}

const filterNode = (value, data) => {
  if (!value) return true
  const v = String(value).toLowerCase()
  return (data.name || '').toLowerCase().includes(v)
}

watch(keyword, (val) => {
  treeRef.value?.filter(val)
})

const onNodeClick = (data) => {
  if (data.type === 'automation') {
    emit('select-task', data)
  }
}

const onAddCommand = (cmd) => {
  if (cmd === 'folder') emit('add-folder', null)
  else if (cmd === 'automation') emit('add-automation', null)
}

const onFolderAction = (cmd, data) => {
  if (cmd === 'addFolder') emit('add-folder', data)
  else if (cmd === 'addAutomation') emit('add-automation', data)
  else emit('folder-action', { command: cmd, data })
}

const onTaskAction = (cmd, data) => {
  emit('task-action', { command: cmd, data })
}

defineExpose({
  setCurrentKey: (key) => treeRef.value?.setCurrentKey(key)
})
</script>

<style scoped>
.automation-folder-tree {
  width: 320px;
  min-width: 280px;
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color-light);
}
.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--el-border-color-light);
}
.add-btn {
  flex: none;
}
.tree-container {
  flex: 1;
  overflow: auto;
  padding: 8px 6px;
}
.tree-node {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex: 1;
  padding-right: 6px;
}
.node-content {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}
.node-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 13px;
}
.node-count {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.node-icon {
  font-size: 15px;
}
.folder-icon { color: #f0a020; }
.task-icon { color: var(--el-color-primary); }
.node-actions {
  opacity: 0;
  transition: opacity 0.15s;
}
.tree-node:hover .node-actions {
  opacity: 1;
}
.action-icon {
  cursor: pointer;
  padding: 4px;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}
.action-icon:hover {
  color: var(--el-color-primary);
}
</style>
