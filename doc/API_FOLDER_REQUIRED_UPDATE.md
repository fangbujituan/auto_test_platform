# API接口目录必填字段更新

## 更新时间
2026-01-22

## 更新内容

### 功能说明
修改了API接口新增功能，使目录选择成为必填字段，并根据不同的触发方式设置默认值。

### 具体改动

#### 1. 表单字段调整
- 在接口名称后添加"所属目录"字段
- 使用 `el-tree-select` 组件实现目录选择
- 目录字段设置为必填项

#### 2. 触发方式区分

**方式一：点击顶部"新建接口"按钮**
- 目录字段为空
- 用户必须手动选择目录
- 不选择目录无法提交表单

**方式二：点击目录后面的"新建接口"按钮**
- 目录字段默认选中当前目录
- 用户可以修改选择其他目录
- 目录字段仍然是必填的

#### 3. 代码修改位置

**文件：** `client/src/views/ProjectDetail.vue`

**修改点：**

1. 添加目录选择器配置
```javascript
// 目录树选择器配置
const folderTreeOptions = ref([])
const folderTreeProps = {
  children: 'children',
  label: 'name',
  value: 'raw_id',
  disabled: (data) => data.type !== 'folder'  // 只能选择目录
}
```

2. 添加表单验证规则
```javascript
folder_id: [
  { required: true, message: '请选择所属目录', trigger: 'change' }
]
```

3. 构建目录选择器选项
```javascript
// 构建目录选择器选项（过滤掉非目录节点）
const buildFolderOptions = (nodes) => {
  const result = []
  for (const node of nodes) {
    if (node.type === 'folder') {
      const folderNode = {
        raw_id: node.raw_id,
        name: node.name,
        type: node.type,
        children: node.children ? buildFolderOptions(node.children) : []
      }
      result.push(folderNode)
    }
  }
  return result
}
```

4. 在表单中添加目录选择字段
```vue
<el-form-item label="所属目录" prop="folder_id">
  <el-tree-select
    v-model="form.folder_id"
    :data="folderTreeOptions"
    :props="folderTreeProps"
    placeholder="请选择所属目录"
    check-strictly
    :render-after-expand="false"
    style="width: 100%;"
  />
</el-form-item>
```

### 用户体验改进

1. **明确的目录归属**：每个接口必须明确归属到某个目录
2. **智能默认值**：从目录创建接口时自动选中当前目录
3. **灵活调整**：即使有默认值，用户仍可修改目录选择
4. **清晰提示**：必填验证提示用户选择目录

### 后端支持

后端API已经支持 `folder_id` 字段：
- 创建接口时接收 `folder_id` 参数
- 更新接口时可以修改 `folder_id`
- 查询接口时返回 `folder_id` 信息

### 测试建议

1. 测试顶部"新建接口"按钮，验证目录必填
2. 测试目录后的"新建接口"按钮，验证默认值
3. 测试修改默认目录选择
4. 测试不选择目录时的验证提示
5. 测试接口创建后的目录归属显示

## 相关文件

- `client/src/views/ProjectDetail.vue` - 主要修改文件
- `app/routes/api.py` - 后端API支持
- `app/models/api.py` - 数据模型
