# 自动生成的测试用例

总计: 52 个用例


## POSITIVE (2个)

| 用例ID | 描述 | 测试点 | 预期结果 |
|--------|------|--------|----------|
| TC_001 | 最小必传参数集 | 验证仅传必传参数时接口正常 | 成功 |
| TC_002 | 全参数正常值 | 验证传入所有参数时接口正常 | 成功 |

## NEGATIVE (26个)

| 用例ID | 描述 | 测试点 | 预期结果 |
|--------|------|--------|----------|
| TC_003 | 缺失必传参数: username | 验证缺少必传参数 username 时返回错误 | 失败: 参数缺失 |
| TC_004 | 必传参数为None: username | 验证必传参数 username 为None时返回错误 | 失败: 参数为空 |
| TC_005 | 必传参数为空字符串: username | 验证必传参数 username 为空字符串时返回错误 | 失败: 参数为空 |
| TC_006 | 缺失必传参数: password | 验证缺少必传参数 password 时返回错误 | 失败: 参数缺失 |
| TC_007 | 必传参数为None: password | 验证必传参数 password 为None时返回错误 | 失败: 参数为空 |
| TC_008 | 必传参数为空字符串: password | 验证必传参数 password 为空字符串时返回错误 | 失败: 参数为空 |
| TC_009 | 缺失必传参数: email | 验证缺少必传参数 email 时返回错误 | 失败: 参数缺失 |
| TC_010 | 必传参数为None: email | 验证必传参数 email 为None时返回错误 | 失败: 参数为空 |
| TC_011 | 缺失必传参数: agree_terms | 验证缺少必传参数 agree_terms 时返回错误 | 失败: 参数缺失 |
| TC_012 | 必传参数为None: agree_terms | 验证必传参数 agree_terms 为None时返回错误 | 失败: 参数为空 |
| TC_029 | username 类型错误: int | 验证 username 传入 int 类型时返回错误 | 失败: 类型错误 |
| TC_030 | username 类型错误: bool | 验证 username 传入 bool 类型时返回错误 | 失败: 类型错误 |
| TC_031 | password 类型错误: int | 验证 password 传入 int 类型时返回错误 | 失败: 类型错误 |
| TC_032 | password 类型错误: bool | 验证 password 传入 bool 类型时返回错误 | 失败: 类型错误 |
| TC_033 | age 类型错误: str | 验证 age 传入 str 类型时返回错误 | 失败: 类型错误 |
| TC_034 | age 类型错误: bool | 验证 age 传入 bool 类型时返回错误 | 失败: 类型错误 |
| TC_035 | gender 类型错误: int | 验证 gender 传入 int 类型时返回错误 | 失败: 类型错误 |
| TC_036 | gender 类型错误: bool | 验证 gender 传入 bool 类型时返回错误 | 失败: 类型错误 |
| TC_037 | nickname 类型错误: int | 验证 nickname 传入 int 类型时返回错误 | 失败: 类型错误 |
| TC_038 | nickname 类型错误: bool | 验证 nickname 传入 bool 类型时返回错误 | 失败: 类型错误 |
| TC_039 | bio 类型错误: int | 验证 bio 传入 int 类型时返回错误 | 失败: 类型错误 |
| TC_040 | bio 类型错误: bool | 验证 bio 传入 bool 类型时返回错误 | 失败: 类型错误 |
| TC_041 | agree_terms 类型错误: str | 验证 agree_terms 传入 str 类型时返回错误 | 失败: 类型错误 |
| TC_042 | agree_terms 类型错误: int | 验证 agree_terms 传入 int 类型时返回错误 | 失败: 类型错误 |
| TC_043 | username 重复值测试 | 验证 username 使用已存在的值时返回错误（需先创建重复数据） | 失败: 字段值已存在 |
| TC_044 | email 重复值测试 | 验证 email 使用已存在的值时返回错误（需先创建重复数据） | 失败: 字段值已存在 |

## BOUNDARY (16个)

| 用例ID | 描述 | 测试点 | 预期结果 |
|--------|------|--------|----------|
| TC_013 | username 长度小于最小值 | 验证 username 长度小于 3 时返回错误 | 失败: 长度不足 |
| TC_014 | username 长度等于最小值 | 验证 username 长度等于 3 时正常 | 成功 |
| TC_015 | username 长度等于最大值 | 验证 username 长度等于 20 时正常 | 成功 |
| TC_016 | username 长度大于最大值 | 验证 username 长度大于 20 时返回错误 | 失败: 长度超限 |
| TC_017 | password 长度小于最小值 | 验证 password 长度小于 6 时返回错误 | 失败: 长度不足 |
| TC_018 | password 长度等于最小值 | 验证 password 长度等于 6 时正常 | 成功 |
| TC_019 | password 长度等于最大值 | 验证 password 长度等于 50 时正常 | 成功 |
| TC_020 | password 长度大于最大值 | 验证 password 长度大于 50 时返回错误 | 失败: 长度超限 |
| TC_021 | age 小于最小值 | 验证 age 小于 1 时返回错误 | 失败: 数值过小 |
| TC_022 | age 等于最小值 | 验证 age 等于 1 时正常 | 成功 |
| TC_023 | age 等于最大值 | 验证 age 等于 150 时正常 | 成功 |
| TC_024 | age 大于最大值 | 验证 age 大于 150 时返回错误 | 失败: 数值过大 |
| TC_025 | nickname 长度等于最大值 | 验证 nickname 长度等于 50 时正常 | 成功 |
| TC_026 | nickname 长度大于最大值 | 验证 nickname 长度大于 50 时返回错误 | 失败: 长度超限 |
| TC_027 | bio 长度等于最大值 | 验证 bio 长度等于 200 时正常 | 成功 |
| TC_028 | bio 长度大于最大值 | 验证 bio 长度大于 200 时返回错误 | 失败: 长度超限 |

## COMBINATION (8个)

| 用例ID | 描述 | 测试点 | 预期结果 |
|--------|------|--------|----------|
| TC_045 | 组合测试: username+password | 验证 username 和 password 的组合场景 | 成功或失败（取决于值） |
| TC_046 | 组合测试: username+password | 验证 username 和 password 的组合场景 | 成功或失败（取决于值） |
| TC_047 | 组合测试: username+password | 验证 username 和 password 的组合场景 | 成功或失败（取决于值） |
| TC_048 | 组合测试: username+password | 验证 username 和 password 的组合场景 | 成功或失败（取决于值） |
| TC_049 | 组合测试: password+agree_terms | 验证 password 和 agree_terms 的组合场景 | 成功或失败（取决于值） |
| TC_050 | 组合测试: password+agree_terms | 验证 password 和 agree_terms 的组合场景 | 成功或失败（取决于值） |
| TC_051 | 组合测试: password+agree_terms | 验证 password 和 agree_terms 的组合场景 | 成功或失败（取决于值） |
| TC_052 | 组合测试: password+agree_terms | 验证 password 和 agree_terms 的组合场景 | 成功或失败（取决于值） |