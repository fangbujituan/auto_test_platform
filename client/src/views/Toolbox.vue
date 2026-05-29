<template>
  <div class="toolbox-wrapper">
    <!-- 公共表头 -->
    <AppHeader />
    
    <div class="toolbox-container">
      <div class="toolbox-header">
        <h1>工具箱</h1>
        <p>测试小工具</p>
      </div>

      <div class="tools-grid">
        <!-- 测试用例生成工具卡片 -->
        <div class="tool-card" @click="openTestCaseGenerator">
          <div class="card-icon">📋</div>
          <div class="card-content">
            <h3>测试用例生成器</h3>
            <p>根据参数定义自动生成测试用例</p>
          </div>
        </div>

        <!-- Excel数据库比对工具卡片 -->
        <div class="tool-card" @click="openExcelDBComparator">
          <div class="card-icon">📊</div>
          <div class="card-content">
            <h3>Excel数据库比对</h3>
            <p>比对Excel文件与数据库数据的差异</p>
          </div>
        </div>

        <!-- 哈希密码破解工具卡片 -->
        <div class="tool-card" @click="openHashTool">
          <div class="card-icon">🔐</div>
          <div class="card-content">
            <h3>哈希密码破解</h3>
            <p>哈希密码转换为明文</p>
          </div>
        </div>
      </div>

      <!-- 测试用例生成器对话框 -->
      <el-dialog
        v-model="generatorDialogVisible"
        title="测试用例生成器"
        width="90%"
        :close-on-click-modal="false"
      >
        <div class="generator-container">
          <el-tabs v-model="activeTab">
            <!-- 表单标签页 -->
            <el-tab-pane label="参数配置" name="form">
              <div class="form-section">
                <el-form
                  ref="formRef"
                  :model="formData"
                  label-width="150px"
                  :rules="formRules"
                >
                  <el-form-item label="工具名称" prop="toolName">
                    <el-input
                      v-model="formData.toolName"
                      placeholder="如：user_register"
                    />
                  </el-form-item>

                  <el-form-item label="基准参数 (JSON)" prop="baseParams">
                    <el-input
                      v-model="formData.baseParams"
                      type="textarea"
                      :rows="8"
                      placeholder='{"username": "testuser", "email": "test@example.com"}'
                      spellcheck="false"
                    />
                  </el-form-item>

                  <el-form-item label="字段约束 (JSON)" prop="constraints">
                    <el-input
                      v-model="formData.constraints"
                      type="textarea"
                      :rows="12"
                      placeholder="[{&quot;field_name&quot;: &quot;username&quot;, &quot;field_type&quot;: &quot;string&quot;, &quot;required&quot;: true}]"
                      spellcheck="false"
                    />
                  </el-form-item>

                  <el-form-item label="生成选项">
                    <el-checkbox v-model="formData.includePositive">正向用例</el-checkbox>
                    <el-checkbox v-model="formData.includeNegative">负向用例</el-checkbox>
                    <el-checkbox v-model="formData.includeBoundary">边界值用例</el-checkbox>
                    <el-checkbox v-model="formData.includeCombination">组合用例</el-checkbox>
                  </el-form-item>

                  <el-form-item>
                    <el-button type="primary" @click="submitForm" :loading="loading">
                      生成用例
                    </el-button>
                    <el-button @click="resetForm">重置</el-button>
                    <el-button @click="loadTemplate">加载示例</el-button>
                  </el-form-item>
                </el-form>
              </div>
            </el-tab-pane>

            <!-- 结果标签页 -->
            <el-tab-pane label="生成结果" name="result">
              <div class="result-section" v-if="generationResult">
                <el-alert
                  :title="generationResult.success ? '✅ 生成成功' : '❌ 生成失败'"
                  :type="generationResult.success ? 'success' : 'error'"
                  :closable="false"
                  style="margin-bottom: 20px"
                />

                <div class="statistics" v-if="generationResult.success">
                  <el-row :gutter="20">
                    <el-col :xs="12" :sm="6">
                      <div class="stat-card">
                        <div class="stat-value">{{ generationResult.stats.total }}</div>
                        <div class="stat-label">总用例数</div>
                      </div>
                    </el-col>
                    <el-col :xs="12" :sm="6">
                      <div class="stat-card">
                        <div class="stat-value">{{ generationResult.stats.positive }}</div>
                        <div class="stat-label">正向用例</div>
                      </div>
                    </el-col>
                    <el-col :xs="12" :sm="6">
                      <div class="stat-card">
                        <div class="stat-value">{{ generationResult.stats.negative }}</div>
                        <div class="stat-label">负向用例</div>
                      </div>
                    </el-col>
                    <el-col :xs="12" :sm="6">
                      <div class="stat-card">
                        <div class="stat-value">{{ generationResult.stats.boundary }}</div>
                        <div class="stat-label">边界值用例</div>
                      </div>
                    </el-col>
                    <el-col :xs="12" :sm="6">
                      <div class="stat-card">
                        <div class="stat-value">{{ generationResult.stats.combination }}</div>
                        <div class="stat-label">组合用例</div>
                      </div>
                    </el-col>
                  </el-row>
                </div>

                <div class="file-info" v-if="generationResult.success">
                  <h4>📁 生成的文件</h4>
                  <el-tree
                    :data="generationResult.files"
                    node-key="id"
                    :props="{ children: 'children', label: 'label' }"
                    default-expand-all
                  />
                </div>

                <div class="error-info" v-if="!generationResult.success">
                  <el-alert
                    :title="generationResult.error"
                    type="error"
                    :closable="false"
                  />
                </div>
              </div>

              <div v-else class="empty-result">
                <el-empty description="暂无结果，请先生成用例" />
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </el-dialog>

      <!-- Excel数据库比对对话框 -->
      <el-dialog
        v-model="comparatorDialogVisible"
        title="Excel数据库比对"
        width="90%"
        :close-on-click-modal="false"
      >
        <div class="comparator-container">
          <el-tabs v-model="comparatorActiveTab">
            <!-- 配置标签页 -->
            <el-tab-pane label="比对配置" name="config">
              <div class="form-section">
                <el-form
                  ref="comparatorFormRef"
                  :model="comparatorForm"
                  label-width="150px"
                  :rules="comparatorRules"
                >
                  <el-form-item label="Excel文件" prop="file">
                    <el-upload
                      ref="uploadRef"
                      :auto-upload="false"
                      :limit="1"
                      accept=".xlsx,.xls"
                      :on-change="handleFileChange"
                      :on-remove="handleFileRemove"
                    >
                      <template #trigger>
                        <el-button type="primary">选择文件</el-button>
                      </template>
                      <template #tip>
                        <div class="el-upload__tip">
                          仅支持 .xlsx 或 .xls 格式
                        </div>
                      </template>
                    </el-upload>
                  </el-form-item>

                  <el-form-item label="工作表名称">
                    <el-input
                      v-model="comparatorForm.sheetName"
                      placeholder="留空则读取第一个工作表"
                    />
                  </el-form-item>

                  <el-form-item label="SQL查询语句" prop="sql">
                    <el-input
                      v-model="comparatorForm.sql"
                      type="textarea"
                      :rows="5"
                      placeholder="SELECT id, username, email, age FROM users WHERE status = 1"
                      spellcheck="false"
                    />
                  </el-form-item>

                  <el-form-item label="字段映射关系" prop="mappings">
                    <div class="mappings-editor">
                      <div class="mapping-header">
                        <span class="col-excel">Excel列名</span>
                        <span class="col-db">数据库列名</span>
                        <span class="col-key">主键</span>
                        <span class="col-compare">比对</span>
                        <span class="col-action">操作</span>
                      </div>
                      <div
                        v-for="(mapping, index) in comparatorForm.mappings"
                        :key="index"
                        class="mapping-row"
                      >
                        <el-input
                          v-model="mapping.excel_column"
                          placeholder="Excel列名"
                          class="col-excel"
                        />
                        <el-input
                          v-model="mapping.db_column"
                          placeholder="数据库列名"
                          class="col-db"
                        />
                        <el-checkbox
                          v-model="mapping.is_key"
                          class="col-key"
                        />
                        <el-checkbox
                          v-model="mapping.compare"
                          class="col-compare"
                        />
                        <el-button
                          type="danger"
                          :icon="Delete"
                          circle
                          size="small"
                          @click="removeMapping(index)"
                          class="col-action"
                        />
                      </div>
                      <el-button
                        type="primary"
                        :icon="Plus"
                        @click="addMapping"
                        style="margin-top: 10px"
                      >
                        添加映射
                      </el-button>
                    </div>
                  </el-form-item>

                  <el-form-item>
                    <el-button
                      type="primary"
                      @click="submitCompare"
                      :loading="comparatorLoading"
                    >
                      开始比对
                    </el-button>
                    <el-button @click="resetComparator">重置</el-button>
                    <el-button @click="loadComparatorTemplate">加载示例</el-button>
                  </el-form-item>
                </el-form>
              </div>
            </el-tab-pane>

            <!-- 结果标签页 -->
            <el-tab-pane label="比对结果" name="result">
              <div class="result-section" v-if="compareResult">
                <el-alert
                  :title="compareResult.success ? '✅ 比对完成' : '❌ 比对失败'"
                  :type="compareResult.success ? 'success' : 'error'"
                  :closable="false"
                  style="margin-bottom: 20px"
                />

                <div class="statistics" v-if="compareResult.success">
                  <el-row :gutter="20">
                    <el-col :xs="12" :sm="4">
                      <div class="stat-card">
                        <div class="stat-value">{{ compareResult.report.summary.total_excel_rows }}</div>
                        <div class="stat-label">Excel行数</div>
                      </div>
                    </el-col>
                    <el-col :xs="12" :sm="4">
                      <div class="stat-card">
                        <div class="stat-value">{{ compareResult.report.summary.total_db_rows }}</div>
                        <div class="stat-label">数据库行数</div>
                      </div>
                    </el-col>
                    <el-col :xs="12" :sm="4">
                      <div class="stat-card stat-success">
                        <div class="stat-value">{{ compareResult.report.summary.matched_count }}</div>
                        <div class="stat-label">匹配</div>
                      </div>
                    </el-col>
                    <el-col :xs="12" :sm="4">
                      <div class="stat-card stat-warning">
                        <div class="stat-value">{{ compareResult.report.summary.mismatched_count }}</div>
                        <div class="stat-label">不匹配</div>
                      </div>
                    </el-col>
                    <el-col :xs="12" :sm="4">
                      <div class="stat-card stat-info">
                        <div class="stat-value">{{ compareResult.report.summary.excel_only_count }}</div>
                        <div class="stat-label">仅Excel有</div>
                      </div>
                    </el-col>
                    <el-col :xs="12" :sm="4">
                      <div class="stat-card stat-danger">
                        <div class="stat-value">{{ compareResult.report.summary.db_only_count }}</div>
                        <div class="stat-label">仅数据库有</div>
                      </div>
                    </el-col>
                  </el-row>
                  <div class="match-rate">
                    匹配率: {{ compareResult.report.summary.match_rate }}
                  </div>
                </div>

                <!-- 详情表格 -->
                <div class="details-section" v-if="compareResult.success">
                  <h4>比对详情</h4>
                  <el-table
                    :data="filteredDetails"
                    style="width: 100%"
                    max-height="400"
                    stripe
                  >
                    <el-table-column label="主键值" min-width="150">
                      <template #default="{ row }">
                        <span v-for="(val, key) in row.key_values" :key="key">
                          {{ key }}: {{ val }}
                        </span>
                      </template>
                    </el-table-column>
                    <el-table-column label="结果" width="120">
                      <template #default="{ row }">
                        <el-tag :type="getResultTagType(row.result)">
                          {{ getResultLabel(row.result) }}
                        </el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column label="差异详情" min-width="300">
                      <template #default="{ row }">
                        <div v-if="row.differences && row.differences.length > 0">
                          <div v-for="(diff, idx) in row.differences" :key="idx" class="diff-item">
                            <span class="diff-field">{{ diff.field }}:</span>
                            <span class="diff-excel">Excel={{ diff.excel_value }}</span>
                            <span class="diff-db">DB={{ diff.db_value }}</span>
                          </div>
                        </div>
                        <span v-else class="no-diff">-</span>
                      </template>
                    </el-table-column>
                  </el-table>

                  <div class="filter-section">
                    <el-radio-group v-model="detailFilter" size="small">
                      <el-radio-button label="all">全部</el-radio-button>
                      <el-radio-button label="match">匹配</el-radio-button>
                      <el-radio-button label="mismatch">不匹配</el-radio-button>
                      <el-radio-button label="excel_only">仅Excel</el-radio-button>
                      <el-radio-button label="db_only">仅数据库</el-radio-button>
                    </el-radio-group>
                  </div>
                </div>

                <div class="error-info" v-if="!compareResult.success">
                  <el-alert
                    :title="compareResult.error"
                    type="error"
                    :closable="false"
                  />
                </div>
              </div>

              <div v-else class="empty-result">
                <el-empty description="暂无结果，请先执行比对" />
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </el-dialog>

      <!-- 哈希密码破解对话框 -->
      <el-dialog
        v-model="hashDialogVisible"
        title="哈希密码破解"
        width="600px"
        :close-on-click-modal="false"
      >
        <div class="hash-section">
          <el-input
            v-model="hashForm.hash"
            type="textarea"
            :rows="4"
            placeholder="请粘贴数据库中的密码哈希值"
            style="margin-bottom: 16px"
          />
          <el-button type="primary" @click="doCrack" :loading="crackLoading">
            转换
          </el-button>
          <div v-if="crackResult" style="margin-top: 16px">
            <el-alert
              v-if="crackResult.found"
              type="success"
              :closable="false"
              show-icon
            >
              <template #title>
                明文密码：<span style="font-weight:700;font-size:16px">{{ crackResult.password }}</span>
              </template>
            </el-alert>
            <el-alert
              v-else
              title="未匹配到明文，该密码不在内置字典中"
              type="warning"
              :closable="false"
              show-icon
            />
          </div>
        </div>
      </el-dialog>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Delete, Plus } from '@element-plus/icons-vue'
import AppHeader from '../components/AppHeader.vue'
import { generateTestCases, compareExcelDB, crackHash } from '../api/toolbox'

// ========== 测试用例生成器相关 ==========
const generatorDialogVisible = ref(false)
const activeTab = ref('form')
const loading = ref(false)
const formRef = ref(null)

const formData = ref({
  toolName: '',
  baseParams: '',
  constraints: '',
  includePositive: true,
  includeNegative: true,
  includeBoundary: true,
  includeCombination: true
})

const generationResult = ref(null)

const formRules = {
  toolName: [
    { required: true, message: '请输入工具名称', trigger: 'blur' }
  ],
  baseParams: [
    { required: true, message: '请输入基准参数', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        try {
          JSON.parse(value)
          callback()
        } catch (e) {
          callback(new Error('基准参数必须是有效的 JSON 格式'))
        }
      },
      trigger: 'blur'
    }
  ],
  constraints: [
    { required: true, message: '请输入字段约束', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        try {
          JSON.parse(value)
          callback()
        } catch (e) {
          callback(new Error('字段约束必须是有效的 JSON 格式'))
        }
      },
      trigger: 'blur'
    }
  ]
}

const openTestCaseGenerator = () => {
  generatorDialogVisible.value = true
}

const submitForm = async () => {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
    loading.value = true

    const payload = {
      tool_name: formData.value.toolName,
      base_params: JSON.parse(formData.value.baseParams),
      constraints: JSON.parse(formData.value.constraints),
      include_positive: formData.value.includePositive,
      include_negative: formData.value.includeNegative,
      include_boundary: formData.value.includeBoundary,
      include_combination: formData.value.includeCombination
    }

    const response = await generateTestCases(payload)

    generationResult.value = {
      success: true,
      stats: response.stats,
      files: [
        {
          id: 1,
          label: '📂 app/test_data/',
          children: response.files.map((file, index) => ({
            id: index + 2,
            label: `📄 ${file}`
          }))
        }
      ]
    }

    activeTab.value = 'result'
    ElMessage.success('用例生成成功！')
  } catch (error) {
    if (error.response?.data?.error) {
      generationResult.value = {
        success: false,
        error: error.response.data.error
      }
      activeTab.value = 'result'
    } else {
      ElMessage.error(error.message || '生成失败，请检查参数格式')
    }
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  formRef.value?.resetFields()
  generationResult.value = null
}

const loadTemplate = () => {
  formData.value = {
    toolName: 'user_register',
    baseParams: JSON.stringify({
      username: 'testuser123',
      password: 'Pass@123456',
      email: 'test@example.com',
      phone: '13800138000',
      age: 25,
      agree_terms: true
    }, null, 2),
    constraints: JSON.stringify([
      {
        field_name: 'username',
        field_type: 'string',
        required: true,
        min_length: 3,
        max_length: 20,
        unique: true
      },
      {
        field_name: 'password',
        field_type: 'string',
        required: true,
        min_length: 6,
        max_length: 50
      },
      {
        field_name: 'email',
        field_type: 'email',
        required: true,
        unique: true
      },
      {
        field_name: 'phone',
        field_type: 'phone',
        required: false,
        min_length: 11,
        max_length: 11
      },
      {
        field_name: 'age',
        field_type: 'integer',
        required: false,
        min_value: 1,
        max_value: 150
      },
      {
        field_name: 'agree_terms',
        field_type: 'boolean',
        required: true
      }
    ], null, 2),
    includePositive: true,
    includeNegative: true,
    includeBoundary: true,
    includeCombination: true
  }
  ElMessage.success('示例已加载')
}

// ========== Excel数据库比对相关 ==========
const comparatorDialogVisible = ref(false)
const comparatorActiveTab = ref('config')
const comparatorLoading = ref(false)
const comparatorFormRef = ref(null)
const uploadRef = ref(null)

const comparatorForm = ref({
  file: null,
  sheetName: '',
  sql: '',
  mappings: [
    { excel_column: '', db_column: '', is_key: false, compare: true }
  ]
})

const compareResult = ref(null)
const detailFilter = ref('all')

const comparatorRules = {
  sql: [
    { required: true, message: '请输入SQL查询语句', trigger: 'blur' }
  ]
}

const openExcelDBComparator = () => {
  comparatorDialogVisible.value = true
}

const handleFileChange = (file) => {
  comparatorForm.value.file = file.raw
}

const handleFileRemove = () => {
  comparatorForm.value.file = null
}

const addMapping = () => {
  comparatorForm.value.mappings.push({
    excel_column: '',
    db_column: '',
    is_key: false,
    compare: true
  })
}

const removeMapping = (index) => {
  if (comparatorForm.value.mappings.length > 1) {
    comparatorForm.value.mappings.splice(index, 1)
  } else {
    ElMessage.warning('至少保留一个映射')
  }
}

const submitCompare = async () => {
  if (!comparatorForm.value.file) {
    ElMessage.error('请选择Excel文件')
    return
  }

  if (!comparatorForm.value.sql.trim()) {
    ElMessage.error('请输入SQL查询语句')
    return
  }

  // 验证映射
  const validMappings = comparatorForm.value.mappings.filter(
    m => m.excel_column && m.db_column
  )
  if (validMappings.length === 0) {
    ElMessage.error('请至少配置一个有效的字段映射')
    return
  }

  const hasKey = validMappings.some(m => m.is_key)
  if (!hasKey) {
    ElMessage.error('请至少指定一个主键字段')
    return
  }

  try {
    comparatorLoading.value = true

    const formDataObj = new FormData()
    formDataObj.append('file', comparatorForm.value.file)
    formDataObj.append('sql', comparatorForm.value.sql)
    formDataObj.append('mappings', JSON.stringify(validMappings))
    if (comparatorForm.value.sheetName) {
      formDataObj.append('sheet_name', comparatorForm.value.sheetName)
    }

    const response = await compareExcelDB(formDataObj)

    compareResult.value = {
      success: true,
      report: response.data.report
    }

    comparatorActiveTab.value = 'result'
    ElMessage.success('比对完成！')
  } catch (error) {
    if (error.response?.data?.error) {
      compareResult.value = {
        success: false,
        error: error.response.data.error
      }
      comparatorActiveTab.value = 'result'
    } else {
      ElMessage.error(error.message || '比对失败')
    }
  } finally {
    comparatorLoading.value = false
  }
}

const resetComparator = () => {
  comparatorForm.value = {
    file: null,
    sheetName: '',
    sql: '',
    mappings: [
      { excel_column: '', db_column: '', is_key: false, compare: true }
    ]
  }
  uploadRef.value?.clearFiles()
  compareResult.value = null
  detailFilter.value = 'all'
}

const loadComparatorTemplate = () => {
  comparatorForm.value.sql = 'SELECT id, username, email, age FROM users WHERE status = 1'
  comparatorForm.value.mappings = [
    { excel_column: 'ID', db_column: 'id', is_key: true, compare: false },
    { excel_column: '用户名', db_column: 'username', is_key: false, compare: true },
    { excel_column: '邮箱', db_column: 'email', is_key: false, compare: true },
    { excel_column: '年龄', db_column: 'age', is_key: false, compare: true }
  ]
  ElMessage.success('示例已加载，请选择Excel文件')
}

const filteredDetails = computed(() => {
  if (!compareResult.value?.report?.details) return []
  if (detailFilter.value === 'all') {
    return compareResult.value.report.details
  }
  return compareResult.value.report.details.filter(
    d => d.result === detailFilter.value
  )
})

const getResultTagType = (result) => {
  const types = {
    match: 'success',
    mismatch: 'warning',
    excel_only: 'info',
    db_only: 'danger'
  }
  return types[result] || 'info'
}

const getResultLabel = (result) => {
  const labels = {
    match: '匹配',
    mismatch: '不匹配',
    excel_only: '仅Excel',
    db_only: '仅数据库'
  }
  return labels[result] || result
}

// ========== 哈希密码破解相关 ==========
const hashDialogVisible = ref(false)
const crackLoading = ref(false)

const hashForm = ref({ hash: '' })
const crackResult = ref(null)

const openHashTool = () => {
  hashDialogVisible.value = true
  crackResult.value = null
}

const doCrack = async () => {
  if (!hashForm.value.hash.trim()) {
    ElMessage.warning('请输入哈希值')
    return
  }
  try {
    crackLoading.value = true
    const res = await crackHash({ hash: hashForm.value.hash.trim() })
    crackResult.value = res.data || res
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '转换失败')
  } finally {
    crackLoading.value = false
  }
}
</script>


<style scoped>
.toolbox-wrapper {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: var(--el-bg-color-page);
}

.toolbox-container {
  flex: 1;
  padding: 30px 20px;
}

.toolbox-header {
  margin-bottom: 40px;
}

.toolbox-header h1 {
  font-size: 24px;
  margin: 0 0 8px 0;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.toolbox-header p {
  font-size: 14px;
  color: var(--el-text-color-placeholder);
  margin: 0;
}

.tools-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  max-width: 1200px;
}

.tool-card {
  background: var(--el-bg-color);
  border-radius: 6px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  border: 1px solid var(--el-border-color-light);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tool-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  border-color: var(--el-color-primary);
}

.card-icon {
  font-size: 36px;
}

.card-content h3 {
  margin: 0;
  font-size: 15px;
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.card-content p {
  margin: 0;
  color: var(--el-text-color-placeholder);
  font-size: 13px;
  line-height: 1.5;
}

.generator-container,
.comparator-container {
  padding: 20px 0;
}

.hash-section {
  padding: 20px;
}

.form-section {
  padding: 20px;
}

.result-section {
  padding: 20px;
}

.empty-result {
  padding: 60px 20px;
  text-align: center;
}

.statistics {
  margin: 30px 0;
}

.stat-card {
  background: var(--el-fill-color-light);
  padding: 16px;
  border-radius: 6px;
  text-align: center;
  border: 1px solid var(--el-border-color-light);
  margin-bottom: 15px;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--el-color-primary);
  margin-bottom: 6px;
}

.stat-label {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.stat-success .stat-value {
  color: var(--el-color-success);
}

.stat-warning .stat-value {
  color: var(--el-color-warning);
}

.stat-info .stat-value {
  color: var(--el-color-info);
}

.stat-danger .stat-value {
  color: var(--el-color-danger);
}

.match-rate {
  text-align: center;
  font-size: 16px;
  color: var(--el-color-primary);
  font-weight: 600;
  margin-top: 10px;
}

.file-info {
  margin-top: 30px;
  padding: 20px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  border: 1px solid var(--el-border-color-light);
}

.file-info h4 {
  margin: 0 0 15px 0;
  color: var(--el-text-color-primary);
  font-size: 13px;
  font-weight: 600;
}

.error-info {
  margin-top: 20px;
}

/* 映射编辑器样式 */
.mappings-editor {
  width: 100%;
}

.mapping-header {
  display: flex;
  gap: 10px;
  padding: 10px 0;
  font-weight: 600;
  font-size: 13px;
  color: var(--el-text-color-regular);
  border-bottom: 1px solid var(--el-border-color-light);
  margin-bottom: 10px;
}

.mapping-row {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}

.col-excel,
.col-db {
  flex: 1;
}

.col-key,
.col-compare {
  width: 60px;
  text-align: center;
}

.col-action {
  width: 40px;
}

/* 详情区域 */
.details-section {
  margin-top: 30px;
}

.details-section h4 {
  margin: 0 0 15px 0;
  color: var(--el-text-color-primary);
  font-size: 14px;
  font-weight: 600;
}

.filter-section {
  margin-top: 15px;
  text-align: right;
}

.diff-item {
  margin-bottom: 4px;
  font-size: 12px;
}

.diff-field {
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-right: 8px;
}

.diff-excel {
  color: var(--el-color-primary);
  margin-right: 8px;
}

.diff-db {
  color: var(--el-color-warning);
}

.no-diff {
  color: var(--el-text-color-placeholder);
}

@media (max-width: 768px) {
  .toolbox-container {
    padding: 20px 10px;
  }

  .toolbox-header h1 {
    font-size: 20px;
  }

  .tools-grid {
    grid-template-columns: 1fr;
  }

  .mapping-header {
    display: none;
  }

  .mapping-row {
    flex-wrap: wrap;
  }

  .col-excel,
  .col-db {
    flex: 1 1 100%;
  }
}
</style>
