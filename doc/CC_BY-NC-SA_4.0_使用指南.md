# CC BY-NC-SA 4.0 使用指南

## 目录

- [什么是 CC BY-NC-SA 4.0](#什么是-cc-by-nc-sa-40)
- [核心要素](#核心要素)
- [如何使用 CC 许可证](#如何使用-cc-许可证)
- [违反案例](#违反案例)
- [常见问题](#常见问题)

---

## 什么是 CC BY-NC-SA 4.0

**CC BY-NC-SA 4.0** 是 Creative Commons（知识共享）组织提供的一种开放许可协议，全称为：

**Attribution-NonCommercial-ShareAlike 4.0 International**  
（署名-非商业性使用-相同方式共享 4.0 国际版）

### 许可证特点

这是一个**免费、开放、标准化**的法律工具，允许创作者：
- 保留版权的同时分享作品
- 明确授权他人使用的条件
- 防止未经授权的商业利用
- 全球范围内法律认可

### 适用范围

适用于各类创意作品：
- 文字作品（文章、书籍、教程）
- 音乐作品（歌曲、配乐）
- 视觉作品（照片、插画、视频）
- 软件代码（文档、教程项目）

---

## 核心要素

### BY - 署名（Attribution）

**要求：**
- 必须注明原作者姓名
- 提供许可证链接
- 说明是否对作品进行了修改

**示例：**
```
本作品由 [作者名] 创作，采用 CC BY-NC-SA 4.0 许可。
原作品链接：[URL]
```

### NC - 非商业性使用（NonCommercial）

**禁止：**
- 用于商业目的
- 从作品中直接或间接获利
- 付费课程、商业培训中使用

**允许：**
- 个人学习使用
- 教育机构非营利教学
- 非营利组织使用

### SA - 相同方式共享（ShareAlike）

**要求：**
- 衍生作品必须使用相同许可证
- 保持开放共享精神
- 不能添加额外限制

---

## 如何使用 CC 许可证

### 重要提示

**CC 许可证不需要申请！** 它是免费、开放的法律工具，任何创作者都可以直接使用。

### 步骤 1：选择合适的许可证

访问 CC 官方选择器：[https://creativecommons.org/chooser/](https://creativecommons.org/chooser/)

回答以下问题：
1. 允许他人用于商业目的吗？→ **选 No**（NC）
2. 允许他人修改你的作品吗？→ **选 Yes**
3. 如果允许修改，要求相同许可吗？→ **选 Yes**（SA）

选择器会自动生成许可证代码和图标。

### 步骤 2：应用到不同类型作品

---

### 著作（文章、书籍、教程）

#### 网站/博客

在页面底部添加：

```html
<p xmlns:cc="http://creativecommons.org/ns#">
  本作品采用 
  <a href="http://creativecommons.org/licenses/by-nc-sa/4.0/" 
     target="_blank" rel="license noopener noreferrer">
    CC BY-NC-SA 4.0
    <img src="https://mirrors.creativecommons.org/presskit/icons/cc.svg" 
         style="height:22px!important;margin-left:3px;vertical-align:text-bottom;">
    <img src="https://mirrors.creativecommons.org/presskit/icons/by.svg" 
         style="height:22px!important;margin-left:3px;vertical-align:text-bottom;">
    <img src="https://mirrors.creativecommons.org/presskit/icons/nc.svg" 
         style="height:22px!important;margin-left:3px;vertical-align:text-bottom;">
    <img src="https://mirrors.creativecommons.org/presskit/icons/sa.svg" 
         style="height:22px!important;margin-left:3px;vertical-align:text-bottom;">
  </a> 许可协议进行许可。
</p>
```

#### Markdown 文档

在文档开头或结尾添加：

```markdown
## 许可证

本作品采用 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) 许可协议进行许可。

[![CC BY-NC-SA 4.0](https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
```

#### PDF 文档

在首页或末页添加：

```
版权声明

本作品采用知识共享署名-非商业性使用-相同方式共享 4.0 国际许可协议进行许可。
访问 http://creativecommons.org/licenses/by-nc-sa/4.0/ 查看该许可协议。

© 2026 [作者名]
```

---

### 音乐作品

#### 音频文件元数据

在音频文件的元数据中添加：
- **Copyright**: CC BY-NC-SA 4.0
- **License**: https://creativecommons.org/licenses/by-nc-sa/4.0/
- **Artist**: [你的名字]

#### 音乐平台

**SoundCloud**
1. 上传音乐时选择 "Edit Info"
2. 在 "License" 下拉菜单中选择 "CC BY-NC-SA 4.0"

**Bandcamp**
在专辑/曲目描述中添加：
```
Licensed under CC BY-NC-SA 4.0
https://creativecommons.org/licenses/by-nc-sa/4.0/
```

#### 专辑封面/说明

在专辑封面背面或说明书中注明：
```
本专辑所有曲目采用 CC BY-NC-SA 4.0 许可
允许非商业性分享和改编，需注明出处并以相同方式共享
```

---

### 图片/摄影作品

#### 图片文件 EXIF 信息

使用图片编辑软件添加：
- **Copyright**: CC BY-NC-SA 4.0 - [你的名字]
- **Rights**: https://creativecommons.org/licenses/by-nc-sa/4.0/

#### Flickr

1. 上传照片后点击 "Edit"
2. 在 "License" 选项中选择 "Attribution-NonCommercial-ShareAlike"

#### Instagram/社交媒体

在图片描述中添加：
```
📷 © [你的名字] | CC BY-NC-SA 4.0
可非商业使用，需注明出处
```

#### 图片水印

在图片上添加文字水印：
```
© [你的名字] | CC BY-NC-SA 4.0
```

---

### 代码/软件项目

#### GitHub 项目

**方法 1：创建 LICENSE 文件**

在项目根目录创建 `LICENSE` 或 `LICENSE.txt` 文件，内容为完整的 CC BY-NC-SA 4.0 许可证文本。

访问：https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.txt

**方法 2：在 README.md 中声明**

```markdown
## License

This project is licensed under the [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) License.

[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
```

#### 代码文件头部注释

在每个源代码文件顶部添加：

```python
# Copyright (c) 2026 [你的名字]
# Licensed under CC BY-NC-SA 4.0
# https://creativecommons.org/licenses/by-nc-sa/4.0/
```

```javascript
/**
 * Copyright (c) 2026 [你的名字]
 * Licensed under CC BY-NC-SA 4.0
 * https://creativecommons.org/licenses/by-nc-sa/4.0/
 */
```

#### 注意事项

对于软件代码，CC 许可证**主要适用于教程、文档、示例代码**。

如果是生产级软件，建议使用专门的软件许可证（如 MIT、GPL、Apache 2.0）。

---

### 步骤 3：无需注册或审批

- ✅ 不需要向 CC 组织申请
- ✅ 不需要付费
- ✅ 不需要等待批准
- ✅ 立即生效

只需在作品上标注许可证信息即可。

---

## 违反案例

以下是真实的 CC 许可证侵权诉讼案例，展示了违反许可证的法律后果。

---

### 案例 1：比利时音乐侵权案（2010）

**案件名称：** Lichôdmapwa v. L'asbl Festival de Theatre de Spa

**案情背景：**
- 2004 年，比利时乐队 Lichôdmapwa 以 **CC BY-NC-ND 2.5** 许可发布歌曲 "Abatchouck"
- 某剧院在商业广告中使用了歌曲的 20 秒片段
- 广告在国家电台播放

**违反条款：**
1. ❌ **未署名**（BY）：没有注明原作者
2. ❌ **商业使用**（NC）：用于商业广告
3. ❌ **修改作品**（ND）：只使用了部分片段

**被告辩护：**
- 声称不知道 CC 许可证的存在
- 声称因为乐队不是比利时版权协会（SABAM）成员，不应获得赔偿

**法院判决：**
- ✅ 认定构成**版权侵权**
- ✅ 驳回"不知情"辩护：被告作为专业机构应该了解许可证
- ✅ 驳回 SABAM 辩护：选择 CC 许可不影响版权保护
- 💰 判赔 **4,500 欧元**（每违反一项条款罚 1,500 欧元）

**重要意义：**
- 违反 CC 许可证 = 版权侵权
- "不知情"不是免责理由
- 使用 CC 许可不会削弱版权保护

**来源：** [CC Legal Database](https://legaldb.creativecommons.org/cases/1/)

---

### 案例 2：以色列照片侵权案（2011）

**案件名称：** Avi Re'uveni v. Mapa Inc.

**案情背景：**
- 摄影师在 Flickr 上以 **CC BY-NC-ND** 许可发布照片
- 被告从网上下载照片，制作成拼贴画
- 被告在市场上**出售**这些拼贴画

**违反条款：**
1. ❌ **未署名**（BY）：没有注明摄影师
2. ❌ **商业使用**（NC）：出售拼贴画获利
3. ❌ **修改作品**（ND）：制作成拼贴画

**被告辩护：**
- 声称从另一个网站下载，该网站没有版权或 CC 许可信息
- 声称不知道照片受版权保护

**法院判决：**
- ✅ 认定构成**版权侵权**
- ✅ 被告无权使用受版权保护的照片
- ✅ 需承担赔偿责任
- 法院虽未详细讨论 CC 许可，但未质疑其有效性

**重要意义：**
- 即使从第三方网站获取，仍需承担侵权责任
- 不知道许可证存在不能免责
- CC 许可在以色列法院首次获得认可

**来源：** [Creative Commons Blog](https://creativecommons.org/weblog/entry/26115)

---

### 案例 3：Great Minds v. FedEx（2017-2020）

**案件名称：** Great Minds v. FedEx Office and Print Services, Inc.

**案情背景：**
- 教育机构 Great Minds 以 **CC BY-NC-SA 4.0** 发布数学教材
- 学区（非商业用户）委托 FedEx 打印店打印这些教材
- Great Minds 起诉 FedEx 进行商业使用

**争议焦点：**
- 非商业用户（学区）委托商业打印店打印是否违反"非商业"条款？

**法院判决：**
- ✅ **FedEx 胜诉**
- 学区有权使用教材，委托打印店代为打印**不违反**"非商业"条款
- 打印店作为代理人执行非商业用户的权利
- 许可证未明确禁止使用商业服务商协助

**重要意义：**
- 明确了"非商业使用"的边界
- 非商业用户可以委托商业服务商协助实现非商业目的
- 许可证条款需要明确，不能过度解读

**来源：** [Techdirt](https://www.techdirt.com/2020/01/09/appeals-court-makes-right-call-regarding-non-commercial-creative-commons-licenses/)

---

### 案例 4：德国摄影师系列诉讼（2022）

**案件名称：** 多起 CC 许可照片侵权案

**案情背景：**
- 德国摄影师以 **CC BY** 许可发布照片（允许商业使用）
- 多家美国公司使用照片但**未正确署名**
- 2022 年 2-4 月，摄影师在美国联邦法院提起 9 起诉讼

**违反条款：**
- ❌ **未署名**（BY）：这是唯一的要求，但被违反

**判决结果：**
- 多起案件达成和解
- 被告需支付赔偿金（具体金额未公开）

**重要意义：**
- 即使是最宽松的 CC BY 许可，**署名是强制要求**
- 不署名就是侵权，必须承担法律责任
- "署名"是所有 CC 许可的核心要求

**来源：** [Internet & Technology Law Blog](https://www.internetandtechnologylaw.com/creative-commons-photography-trap/)

---

### 案例 5：荷兰 Curry 案（2006）

**案件名称：** Adam Curry v. Weekend Magazine

**案情背景：**
- 荷兰 DJ Adam Curry 在 Flickr 上以 **CC BY-NC-SA** 发布家庭照片
- 荷兰杂志 Weekend 未经许可在封面使用照片
- 杂志进行商业销售

**违反条款：**
- ❌ **商业使用**（NC）：用于商业杂志

**判决结果：**
- ✅ 认定构成侵权
- 💰 判赔 **€1,000 欧元**
- 法院首次在荷兰确认 CC 许可的法律效力

**重要意义：**
- CC 许可在欧洲法院获得认可
- 商业媒体不能随意使用 NC 许可的作品

---

### 案例统计与总结

#### CC 官方数据

- 全球**数亿作品**使用 CC 许可
- 诉讼案件**极少**（证明许可被广泛理解和遵守）
- **至今无一法院质疑 CC 许可的有效性**

#### 典型赔偿金额

| 案件 | 赔偿金额 | 违反条款 |
|------|---------|---------|
| 比利时音乐案 | €4,500 | BY + NC + ND |
| 以色列照片案 | 未公开 | BY + NC + ND |
| 荷兰 Curry 案 | €1,000 | NC |
| 德国摄影师案 | 和解（未公开） | BY |

#### 常见违规行为

1. **未署名**（最常见）
2. **商业使用 NC 许可作品**
3. **修改 ND 许可作品**
4. **不使用相同许可分享衍生作品**（违反 SA）

#### 法律后果

- ✅ 构成版权侵权
- ✅ 需支付经济赔偿
- ✅ 可能被要求停止侵权
- ✅ 承担诉讼费用
- ✅ "不知情"不能免责

---

## 常见问题

### Q1: CC 许可证需要付费吗？

**A:** 完全免费。CC 许可证是开放的法律工具，任何人都可以免费使用，无需注册或申请。

---

### Q2: 使用 CC 许可证后还能改变主意吗？

**A:** 不能。CC 许可证是**不可撤销**的。一旦应用，你不能收回已经授予的权限。但你可以：
- 停止以 CC 许可发布新作品
- 对未来版本使用不同许可
- 已发布的版本仍受原许可约束

---

### Q3: 什么算"商业使用"？

**商业使用包括：**
- ❌ 付费课程、培训
- ❌ 出售包含作品的产品
- ❌ 用于广告宣传
- ❌ 从作品中直接或间接获利

**非商业使用包括：**
- ✅ 个人学习
- ✅ 教育机构非营利教学
- ✅ 非营利组织使用
- ✅ 学术研究

**灰色地带：**
- 带广告的个人博客（通常被认为是非商业）
- 非营利组织的筹款活动（需具体分析）

---

### Q4: 如何正确署名？

**最佳实践：**
```
作品名称：[作品标题]
作者：[作者名]
来源：[原始链接]
许可：CC BY-NC-SA 4.0 (https://creativecommons.org/licenses/by-nc-sa/4.0/)
修改：[说明你做了哪些修改，如果有的话]
```

**简化版：**
```
© [作者名] | CC BY-NC-SA 4.0
```

---

### Q5: 发现有人侵权怎么办？

**步骤 1：友好沟通**
- 发送邮件说明情况
- 要求停止侵权或正确署名
- 大多数情况可以友好解决

**步骤 2：正式通知**
- 发送正式的停止侵权通知（Cease and Desist Letter）
- 说明违反的具体条款
- 要求在指定时间内纠正

**步骤 3：法律途径**
- 咨询知识产权律师
- 提起版权侵权诉讼
- 要求经济赔偿和禁令救济

---

### Q6: CC 许可证适合软件代码吗？

**部分适合：**
- ✅ 教程代码
- ✅ 示例项目
- ✅ 文档和说明

**不太适合：**
- ❌ 生产级软件库
- ❌ 需要专利保护的代码
- ❌ 需要明确责任条款的项目

**建议：**
对于软件项目，考虑使用专门的软件许可证：
- MIT License（宽松）
- Apache 2.0（包含专利授权）
- GPL（强制开源）

---

### Q7: 可以同时使用多个许可证吗？

**可以（双重许可）：**
```
本作品采用以下许可之一：
- CC BY-NC-SA 4.0（非商业使用）
- 商业许可（联系作者获取）
```

这样可以：
- 允许非商业用户免费使用
- 向商业用户出售商业许可

---

### Q8: 如何监控作品使用情况？

**工具推荐：**
- **Google 图片搜索**：反向搜索图片
- **TinEye**：图片追踪工具
- **Copyscape**：文本抄袭检测
- **YouTube Content ID**：视频内容识别

**定期检查：**
- 搜索作品标题
- 搜索作者名
- 使用专业监控服务

---

### Q9: CC 许可证在中国有效吗？

**有效。** CC 许可证基于国际版权公约（伯尔尼公约），在包括中国在内的全球 180+ 国家有效。

中国法院也认可 CC 许可证的法律效力。

---

### Q10: 如何选择合适的 CC 许可证？

**决策树：**

```
允许商业使用？
├─ 是 → 允许修改？
│   ├─ 是 → 要求相同许可？
│   │   ├─ 是 → CC BY-SA
│   │   └─ 否 → CC BY
│   └─ 否 → CC BY-ND
└─ 否 → 允许修改？
    ├─ 是 → 要求相同许可？
    │   ├─ 是 → CC BY-NC-SA ⭐（本文档使用）
    │   └─ 否 → CC BY-NC
    └─ 否 → CC BY-NC-ND
```

**最宽松：** CC BY（只要求署名）  
**最严格：** CC BY-NC-ND（不能商用，不能修改）  
**平衡选择：** CC BY-NC-SA（教育项目常用）

---

## 相关资源

### 官方资源

- **CC 官网**：https://creativecommons.org/
- **许可证选择器**：https://creativecommons.org/chooser/
- **法律数据库**：https://legaldb.creativecommons.org/
- **常见问题**：https://creativecommons.org/faq/

### 中文资源

- **CC 中国大陆**：https://creativecommons.net.cn/
- **CC 台湾**：https://creativecommons.tw/

### 工具

- **许可证徽章生成器**：https://licensebuttons.net/
- **CC 搜索引擎**：https://search.creativecommons.org/

---

## 结语

CC BY-NC-SA 4.0 是一个强大的法律工具，它让你可以：

✅ 自由分享你的创作  
✅ 保护你的版权  
✅ 防止商业滥用  
✅ 促进知识传播  

记住：
- 使用 CC 许可不会削弱你的版权
- 违反许可条款就是侵权
- 全球法院都认可 CC 许可的有效性

---

**本文档本身也采用 CC BY-NC-SA 4.0 许可。**

[![CC BY-NC-SA 4.0](https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png)](https://creativecommons.org/licenses/by-nc-sa/4.0/)

最后更新：2026 年 1 月 29 日
