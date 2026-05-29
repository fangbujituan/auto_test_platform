<template>
  <div style="padding: 20px;">
    <h2>测试目录树</h2>
    <el-button @click="loadData">加载数据</el-button>
    
    <div style="margin-top: 20px;">
      <h3>原始数据：</h3>
      <pre>{{ JSON.stringify(treeData, null, 2) }}</pre>
    </div>
    
    <div style="margin-top: 20px;">
      <h3>树形展示：</h3>
      <el-tree
        :data="treeData"
        :props="{ children: 'children', label: 'name' }"
        node-key="id"
      >
        <template #default="{ node, data }">
          <span>{{ data.type }} - {{ data.name }}</span>
        </template>
      </el-tree>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { getFolderTree } from '../api/folder'

const treeData = ref([])

const loadData = async () => {
  try {
    const res = await getFolderTree(5) // 使用项目ID 5
    console.log('API响应:', res)
    treeData.value = res.data || []
  } catch (error) {
    console.error('加载失败:', error)
  }
}
</script>
