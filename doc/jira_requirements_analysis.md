# Billing Audit - JIRA 需求分析

## 概述
从 JIRA 中找到 5 个状态为 Testing、Epic Link 为 "Billing Audit" 的任务。以下是详细的需求分析。

---

## 1. BP-12011 - Billing Full Set Framework

**任务类型**: Story  
**优先级**: Urgent  
**负责人**: Lei Zhang  
**状态**: Testing  

### 背景
Billing Audit Engine 依赖一套结构化的 Billing Full Set，用于判断漏计费、重复计费、配置缺失等问题。需要新增/改造以下子模块页面：
- Service Category Setting Page（新建）
- Charge Category Setting Page（将现有 Billing Category 改造）
- Billing Items Page Enhancement（适配 Billing Full Set mapping）

### 核心目标
1. 建立 Billing Full Set 的三层结构：Service Category → Charge Category → Billing Item
2. 为 Billing Audit Engine 提供标准化的全局可计费项目模型
3. 将现有 Billing Items 适配到 Charge Category
4. 为 Price List 扩展提供基础结构

### 验收标准
1. 系统在 Billing Set Up 模块之下新增 Billing Full Set 子模块，包含 3 个页面：
   - Service Category Setting Page (BP-12010)
   - Charge Category Setting Page (BP-12013)
   - Billing Items Page (BP-12015)
2. Service Category、Charge Category、System Linked Triggers 与 Billing Items 建立 mapping 关系

### 关联任务
- BP-12010: Service Category Setting Page
- BP-12013: Charge Category Setting Page  
- BP-12015: Billing Items Page Enhancements
- BP-12014: Triggers Setting Page (已取消)

---

## 2. BP-12010 - Service Category Setting Page

**任务类型**: New Feature  
**优先级**: Urgent  
**负责人**: Lei Zhang  
**状态**: Testing  

### 背景
Service Category 作为 Billing Full Set 的最高层级主数据，是 Charge Category 与 Billing Items 的基础分类结构，广泛用于计费配置与 Billing Audit。

### 核心功能需求

#### 1. 列表页
**搜索与过滤**:
- Smart Search Box：支持模糊搜索、多关键字（逗号/分号分隔）
- 搜索字段：Service Category ID、Name、Description
- 输入自动出现推荐项，按照字段分组展示
- 其他过滤器：Status、Company（多选）
- Include Inactive Records 选项（默认不勾选）

**列表展示字段**:
- Service Category ID（可点击进入详情页）
- Service Category Name
- Description
- Status（含彩色状态标签）
- Available Companies
- Created By / Created Time
- Updated By / Updated Time

**操作按钮**:
- Add New Category（进入创建页）
- Export（导出符合当前过滤条件的列表数据）

#### 2. 创建页
**基本信息**:
- Category ID：自动生成，只读
- Category Name：必填，文本框
- Description：非必填
- Status：下拉选择（默认 Active）

**Available in Company**:
- 右侧单独区域展示当前 subsidiary 租户所在 Corporation 大租户下的所有 subsidiary 租户
- 支持多选、全选

**页面操作**:
- Cancel、Save Category
- 校验：Category Name 必填、不重复、至少选择一个公司

#### 3. 详情页
**Basic Information**: 字段和编辑规则和创建页一致

**Associated Charge Categories**:
- 自动显示所有 mapping 到当前 Service Category 的 Charge Category
- 字段：ID、Name、Status
- 仅展示，不支持在此页面编辑映射关系

**Change Log**:
- 记录字段：Date、User、Action（Create / Update）、Details

### 验收标准
1. 列表页可根据 Smart Search、Status、Company、Include Inactive Records 正确过滤数据
2. Smart Search 支持多关键字、模糊搜索、推荐项，并能按字段分组显示建议
3. Include Inactive Records 开关默认关闭，勾选后显示所有 active + inactive 数据
4. 列表页字段展示完整，点击 Category ID 可进入详情页
5. 创建页可成功创建 Service Category，校验规则均生效
6. 详情页可成功编辑字段，变更后写入 Change Log
7. Associated Charge Categories 区域数据正确，且为只读
8. Export 功能按当前过滤条件导出数据
9. UI、交互行为符合 BNP Billing Setup 样式规范

---

## 3. BP-12013 - Charge Category Setting Page

**任务类型**: Improvement  
**优先级**: Urgent  
**负责人**: Lei Zhang  
**状态**: Testing  

### 背景
现有 Billing Category 页面仅提供基础字段，无法满足 Billing Full Set 的需求。需将 Billing Category 完整升级为 Charge Category 页面。

### 核心功能需求

#### 1. 列表页
**搜索与过滤**:
- Smart Search：支持模糊搜索、多关键字
- 搜索字段：Charge Category ID、Name、Description、Service Category、Billing Logic Mode、System-Linked Triggers
- 其他过滤器：Status、Service Category、Billing Logic Mode、System-Linked Triggers、Billable、UOM、Company（全部多选且可搜索）
- Include Inactive Records（默认不勾选）

**列表字段**（按顺序显示）:
- Charge Category ID（可点击进入详情页）
- Charge Category Name
- Description
- Service Category
- Billing Logic Mode
- System-Linked Triggers
- Default Billable（Yes/No）
- Default UOM
- Default Price
- Accounting Item
- GL Account
- Available Companies
- Status（彩色标签）
- Created By / Created Time
- Updated By / Updated Time

**操作按钮**:
- Add New Category → 进入创建页
- Export → 导出符合当前过滤条件的数据

#### 2. 创建页
**Basic Information**:
- Category ID：系统自动生成，只读
- Status：下拉（默认 Active）
- Charge Category Name：必填，不可重复
- Description：选填

**Configuration & Mapping**（新增模块）:
- Service Category Mapping：下拉选择（必填），选项来自激活状态的 Service Categories
- Billing Logic Mode：下拉选择，选项包括 Material Line、Accessorial Charge Line、Direct Billing Approved、General Task Closed 和 BNP-Auto Billing Logic
- System-Linked Triggers：只读，初始状态显示 "System Generated"
  - 若 Billing Logic Mode ≠ BNP Auto Billing Logic → 等于所选 Billing Logic Mode 名称
  - 若 Billing Logic Mode = BNP Auto Billing Logic → 显示 "System Generated"，实际 triggers 由后端配置
- Default Billable：Yes / No（默认 Yes）
- Default UOM：下拉选择
- Default Price：数字输入框
- Accounting Item：下拉，选填
- GL Account：下拉，选填

**Available in Company**:
- 不可编辑
- 直接继承"所选 Service Category → Available in Company"
- 若未选择 Service Category，则显示提示："No companies available. Select a service category first."

#### 3. 详情页
**Basic Information**: 字段与创建页一致，可编辑除 Category ID 外所有字段

**Configuration & Mapping**: 字段与创建页一致，均可编辑

**Available in Company**: 不可编辑，随 Service Category 动态继承

**Change Log**（新增）:
- 字段：Date、User、Action（Create / Update）、Details
- 系统需自动记录每次变更

#### 4. 重命名 & 导航调整
- 旧菜单 Billing Category 改为 Charge Categories
- Charge Categories 并入 Billing Full Set 子模块
- 与 Service Categories、Billing Items 同级

### 验收标准
1. 列表页所有过滤器均可正确过滤数据
2. Smart Search 支持多关键字，推荐项按照字段分组显示
3. Include Inactive Records 默认关闭，可正确切换显示范围
4. 创建页可成功保存，且校验：Charge Category Name 必填且唯一、Service Category 必填
5. 详情页修改后能写入 Change Log
6. Billing Logic Mode 与 System-Linked Triggers 映射逻辑正确
7. Available Companies 正确继承 Service Category
8. Export 输出字段与列表一致
9. Charge Category 的配置可被下游 Price List、Billing Items、Billing Audit Engine 正确使用

---

## 4. BP-12015 - Billing Items Page Enhancements

**任务类型**: Improvement  
**优先级**: Urgent  
**负责人**: Lei Zhang  
**状态**: Testing  

### 背景
现有 Billing Items 页面在筛选能力、字段展示及与 Charge Category 的映射逻辑方面存在不足，无法与 Billing Full Set Framework 的数据结构保持一致。

### 核心功能需求

#### 1. 列表页
**搜索与过滤**:
- Smart Search（支持推荐项）：
  - 支持模糊搜索、多关键字（逗号/分号）
  - 搜索字段：Item ID、Charge Code、Item Name、Description
  - 输入后需按字段分组显示推荐项
- 其他过滤器（全部多选且可搜索）：
  - Status（Active / Inactive / All）
  - Type、Rate Type、UOM
  - Service Category、Charge Category
  - System-Linked Triggers
  - Applicable Customers
- Include Inactive Records：默认不勾选，仅展示 Active；勾选后展示 Active + Inactive

**新增列**（放置顺序如截图所示）:
- Description
- Service Category
- Charge Category
- System-Linked Triggers
- Created By、Create Time
- Updated By、Update Time

**其他调整**:
- 将现有的 customer 列名改为 'Applicable Customers'
- Export 文件同步增加新增列

#### 2. 创建页
- 将 Billing Category 字段更名为 Charge Category，取数来源为 Charge Categories 页面（升级后的 Billing Categories 页面）激活状态，且当前租户可用的 Charge Category
- 新增 Service Category 字段，只读，自动显示 charge category 所映射的值
- 将 Trigger Point 字段更名为 System-Linked Triggers，只读，自动显示 charge category 所映射 System-Linked Triggers 的值。如果 Auto Billing for WMS 没有勾选，此字段留空

#### 3. 详情页
与创建页改动一致

#### 4. WMS 同步逻辑不变
现有 Billing Items 中的 Trigger Point 字段包含四个会触发 Billing Item 同步至 WMS 的值。在本次升级中，这四个值将由 Charge Category → System-Linked Triggers 自动带出，注意要保持相同的同步逻辑与弹窗提醒。

**新旧值映射关系**:
| 旧 Trigger Point | 新 System-Linked Triggers |
|-----------------|---------------------------|
| Material | Material Line |
| Accessorial | Accessorial Charge Line |
| Direct Billing Approved | Direct Billing Approved |
| General Task Closed | General Task Closed |

### 验收标准
1. Billing Items 列表页搜索框支持 Smart Search、模糊搜索、多关键字输入，并正确返回结果
2. 所有新增过滤条件均能正确筛选数据
3. 列表页成功展示新增字段，顺序与需求一致；原 "Customer" 列名成功更名为 "Applicable Customers"
4. Export 文件包含新增字段，与列表显示一致
5. 创建页与详情页：Billing Category 成功更名为 Charge Category，并仅展示当前租户可用、激活状态的 Charge Categories
6. Service Category 与 System-Linked Triggers 均为只读，且能正确根据 Charge Category 自动带出
7. 当 Auto Billing for WMS 未勾选时，System-Linked Triggers 自动清空
8. 新 System-Linked Triggers 的四个触发值与旧 trigger points 对应值的触发同步 WMS 逻辑保持一致
9. 弹窗提醒机制与原先行为一致
10. 所有新增字段写入数据库正常，并在 Price List、Billing Audit 等相关模块可正确引用
11. 现有 Billing Items 数据不受影响，历史记录加载正确
12. 页面加载、保存、编辑流程均正常，无前端或后端报错

---

## 5. BP-12078 - Price List Improvement for Billing Audit

**任务类型**: Improvement  
**优先级**: Urgent  
**负责人**: Lei Zhang  
**状态**: Testing  

### 背景
现有 Price List 页面仅支持逐条添加 Billing Items，无法与升级后的 Billing Audit Framework 保持一致，也无法体现客户对 Charge Category 的计费策略（Billable / Non-Billable）。

### 核心功能需求

#### 1. 新增 Charge Category Billing Overview 区域
**位置**: 插入在 Price List Information 与 Pricing Items 之间

**展示结构**（分为两块）:
- **A. Billable**: 显示所有满足以下条件的 Charge Category：
  - 当前租户可用
  - 激活状态
  - Default Billable = Yes
  
- **B. Non-Billable**: 显示所有满足：
  - 当前租户可用
  - 激活状态
  - Default Billable = No
  - 如某 category 被用户设为 Non-Billable，后方需展示 reason

**分组展示**:
- Billable 区域和 Non-Billable 区域统一按 Service Category（Inbound / Outbound / Storage 等）分组呈现
- 每个组可单独展开/收起
- 顶部支持 Expand All / Collapse All

#### 2. 编辑 Charge Category Billing Overview
点击 Edit Charge Categories → 右侧抽屉弹窗出现

**抽屉内容规则**:
- 按 Service Category → Charge Category 列表呈现
- 字段：
  - Billable：Yes / No 切换开关
  - No Charge Reason：文本输入框；当 Billable = No 必填；若该 Category 原本 Default Billable = No 且 reason 未修改，则显示 "By default setting"

**保存规则**:
- 若有 Billable = No 但 reason 为空 → 阻止保存，提醒用户缺失项
- 保存成功后，主页面同步更新 Billable / Non-Billable 列表

#### 3. Add Item（新增 Billing Items）区域改造
点击 Add Item，右侧抽屉展示：
- 按 Charge Category（新名称）分组展示
- 只展示 Billable 的 Charge Category 下的 Billing Items，Non-Billable 的 charge category 下的 Billing Item 在 Add Item 抽屉中完全不可见
- Billing Item 卡片需要展示的信息：
  - 删除 Item ID
  - 新增 System-Linked Triggers

#### 4. Pricing Items 自动同步 Charge Category Billable 状态
当用户修改 Charge Category Billing Overview 后：
- 如果某 Charge Category 被切换为 Non-Billable：
  - 系统需自动移除 Pricing Items 中属于该 Category 的所有 Billing Items
  - 并弹窗提示："AA billing item(s) were removed because their charge category is now Non-Billable: – BB"
    - AA = 具体被移除的 billing item 数量
    - BB = 具体的 charge category 名称

**移除顺序**:
- 发生在用户点击 Save Changes（编辑抽屉）之后
- 必须先更新 Billable 状态，再同步更新 Pricing Items 区域

#### 5. Pricing Item 列表更新
- Category → 改名为 Charge Category
- 调整位置 → 放置在 Item Name 左侧

#### 6. 默认 price list 模板加载逻辑更新
当用户勾选 "Use Default Price List Template" 时，弹窗出现两个选项：

**OPTION 1 — Overwrite（完全覆盖）**:
- 覆盖内容：
  1. Charge Category Billing Overview：读取模板的 Billable / Reason，完全替换当前客人的设置
  2. Pricing Items：移除所有现有 pricing items，加载模板的所有 Billing Items

**OPTION 2 — Keep My Settings（保留用户设置的 charge category billing overview）**:
- 覆盖策略：
  1. Charge Category Billing Overview：保留用户当前已设置的 Billable / Non-Billable 状态与 No Charge Reason
  2. Pricing Items：移除所有现有 pricing items，仅加载"模板中属于用户所设的 Billable Charge Category 的 Billing Items"，模板中属于 Non-Billable 的不加载

#### 7. 创建新 price list 或更新已有 price list 保存时，新增 Billable charge category & pricing items 校验项
每一个 billable charge category 都至少有一个对应的 billing item 配置在 pricing item 区域中，如有遗漏，系统提醒用户具体那些 billable charge category 的 billing item 还未配置。

提醒文字：
"The following charge categories are marked as Billable but have no billing items configured: [具体列出缺少 billing item 配置的 charge category 名称]"

### 验收标准
1. Billable / Non-Billable 展示符合 Default Billable + 用户编辑结果
2. 编辑抽屉能正确校验 No Charge Reason 并保存
3. Add Item 抽屉只显示 Billable Charge Category 下的 Billing Items，billing items 卡片显示信息更新
4. Pricing Items 受 Billable 状态实时约束：切换为 Non-Billable 时自动移除相关 Items，移除时弹窗提示
5. Pricing Items 列表列名更新
6. 使用模板时两种模式（Overwrite / Keep My Settings）行为完全符合规则
7. 创建新 price list 或更新已有 price list 保存时，新增 Billable charge category & pricing items 校验项

---

## 总结

这 5 个任务构成了完整的 Billing Audit Framework：

1. **BP-12011** 是总体框架，定义了三层结构
2. **BP-12010** 实现了最顶层的 Service Category
3. **BP-12013** 实现了中间层的 Charge Category（从原 Billing Category 升级）
4. **BP-12015** 改造了底层的 Billing Items，使其适配新框架
5. **BP-12078** 改造了 Price List，使其支持基于 Charge Category 的计费策略

所有任务都处于 Testing 状态，负责人均为 Lei Zhang，优先级均为 Urgent，属于同一个 Epic（Billing Audit）。

测试人员：Dechao Yan
开发人员：Jerry Zhang, Lei Zhang
