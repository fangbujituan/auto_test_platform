"""
选择器评分常量（Codegen 风格）

JS 端和 Python 端共享同一套评分体系。
分数越低 = 选择器质量越高。

移植自 Playwright selectorGenerator.ts 的评分体系。

整合自 ai-server/tools/middleware/selector_scores.py
"""

# 文本评分范围
TEXT_SCORE_RANGE = 10

# 精确匹配惩罚（非精确匹配会有额外惩罚）
EXACT_PENALTY = TEXT_SCORE_RANGE / 2

# === 优质选择器（分数低 = 好）===

TEST_ID = 1                    # data-testid — 最优选择器
OTHER_TEST_ID = 2              # data-test, data-test-id 等
IFRAME_BY_ATTRIBUTE = 10       # iframe 通过属性定位

# 惩罚区间起始值（高于此值的选择器会被长度惩罚）
BEGIN_PENALIZED = 50

ROLE_WITH_NAME = 100           # getByRole + name（语义化，推荐）
ARIA_LABEL = 110               # aria-label 属性（JS 端已有）
PLACEHOLDER = 120              # placeholder 属性
LABEL = 140                    # label 关联
ALT_TEXT = 160                 # alt 文本（图片）
TEXT = 180                     # 文本内容
TITLE = 200                    # title 属性
TEXT_REGEX = 250               # 文本正则匹配

# === 精确匹配版本（加分 = 更差）===
ROLE_WITH_NAME_EXACT = ROLE_WITH_NAME + EXACT_PENALTY
PLACEHOLDER_EXACT = PLACEHOLDER + EXACT_PENALTY
LABEL_EXACT = LABEL + EXACT_PENALTY
ALT_TEXT_EXACT = ALT_TEXT + EXACT_PENALTY
TEXT_EXACT = TEXT + EXACT_PENALTY
TITLE_EXACT = TITLE + EXACT_PENALTY

# 惩罚区间结束值
END_PENALIZED = 300

# === 一般选择器（分数高 = 较差）===

CSS_ID = 500                   # CSS ID 选择器（可能是动态生成的）
ROLE_WITHOUT_NAME = 510        # role 但没有 name
CSS_NAME = 515                 # CSS [name="xxx"] 选择器
CSS_INPUT_TYPE = 520           # CSS input[type="xxx"]
CSS_TAG_NAME = 530             # CSS 标签名

# === 差的选择器（分数很高 = 不推荐）===

NTH = 10000                    # nth 索引选择器（非常不稳定）
CSS_FALLBACK = 10000000        # CSS 回退选择器（最后的手段）

# 文本期望的分数阈值
SCORE_THRESHOLD_FOR_TEXT_EXPECT = 1000


# 导出为 dict（用于 JS 端注入）
SELECTOR_SCORES = {
    'TEST_ID': TEST_ID,
    'OTHER_TEST_ID': OTHER_TEST_ID,
    'IFRAME_BY_ATTRIBUTE': IFRAME_BY_ATTRIBUTE,
    'BEGIN_PENALIZED': BEGIN_PENALIZED,
    'ROLE_WITH_NAME': ROLE_WITH_NAME,
    'ARIA_LABEL': ARIA_LABEL,
    'PLACEHOLDER': PLACEHOLDER,
    'LABEL': LABEL,
    'ALT_TEXT': ALT_TEXT,
    'TEXT': TEXT,
    'TITLE': TITLE,
    'TEXT_REGEX': TEXT_REGEX,
    'END_PENALIZED': END_PENALIZED,
    'CSS_ID': CSS_ID,
    'ROLE_WITHOUT_NAME': ROLE_WITHOUT_NAME,
    'CSS_NAME': CSS_NAME,
    'CSS_INPUT_TYPE': CSS_INPUT_TYPE,
    'CSS_TAG_NAME': CSS_TAG_NAME,
    'NTH': NTH,
    'CSS_FALLBACK': CSS_FALLBACK,
}
