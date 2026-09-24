<template>
  <div class="strtostr-wrapper">
    <div class="strtostr-container">
      <header class="strtostr-header">
        <div class="header-actions">
          <button class="btn btn-header" @click="compareTexts">对比文本</button>
          <button class="btn btn-header" @click="clearTexts">清空文本</button>
          <button
            class="btn btn-header"
            :style="{ display: showSortBtn ? '' : 'none' }"
            @click="sortJson"
          >JSON 自动排序</button>
        </div>
        <h1 class="strtostr-title">
          文本对比工具
          <span class="help-icon" :data-tip="helpTip">❓</span>
        </h1>
        <div class="header-sync">
          <input type="checkbox" id="syncScroll" v-model="syncEnabled" />
          <label for="syncScroll">同步滚动</label>
        </div>
      </header>

      <div class="tool-container">
        <div class="diff-container" ref="diffContainerRef">
          <!-- 原始文本编辑器 -->
          <div class="editor-container" ref="editorOriginalRef">
            <div class="diff-header">
              <div>原始文本</div>
              <span class="mode-status" ref="switchOriginalRef"></span>
            </div>
            <div class="editor-body">
              <div class="editor-gutter-overlay" ref="gutterOverlayOriginalRef"></div>
              <textarea
                ref="originalTextRef"
                class="editor-textarea"
                placeholder="在此输入原始文本..."
                v-model="originalText"
                @scroll="onOriginalScroll"
                @input="onOriginalInput"
                @paste="onOriginalPaste"
                @blur="onOriginalBlur"
              ></textarea>
              <div class="code-view" ref="codeViewOriginalRef" @dblclick="onOriginalDblclick">
                <div class="code-gutter" ref="gutterOriginalRef"></div>
                <div class="code-content" ref="contentOriginalRef"></div>
              </div>
            </div>
          </div>

          <!-- 修改文本编辑器 -->
          <div class="editor-container" ref="editorModifiedRef">
            <div class="diff-header">
              <div>修改文本</div>
              <span class="mode-status" ref="switchModifiedRef"></span>
            </div>
            <div class="editor-body">
              <div class="editor-gutter-overlay" ref="gutterOverlayModifiedRef"></div>
              <textarea
                ref="modifiedTextRef"
                class="editor-textarea"
                placeholder="在此输入修改后的文本..."
                v-model="modifiedText"
                @scroll="onModifiedScroll"
                @input="onModifiedInput"
                @paste="onModifiedPaste"
                @blur="onModifiedBlur"
              ></textarea>
              <div class="code-view" ref="codeViewModifiedRef" @dblclick="onModifiedDblclick">
                <div class="code-gutter" ref="gutterModifiedRef"></div>
                <div class="code-content" ref="contentModifiedRef"></div>
              </div>
            </div>
          </div>
        </div>

        <div class="h-resizer" ref="hResizerRef" title="上下拖动调整编辑区高度"></div>

        <div class="diff-header">
          <div>对比结果</div>
        </div>
        <div class="diff-content">
          <div class="result-container">
            <div ref="diffResultRef" class="diff-result"></div>
          </div>
        </div>

        <div class="instructions">
          <h3>使用说明</h3>
          <ul>
            <li>在左侧输入原始文本，右侧输入修改后的文本</li>
            <li>输入框左侧有固定的<span class="highlight">行号列</span>，便于定位具体行</li>
            <li>若文本是合法 JSON（对象或数组）：
              <ul style="margin-left:16px; margin-top:2px;">
                <li>粘贴或失焦会自动按 2 空格缩进格式化</li>
                <li>自动切到<span class="highlight">JSON 视图</span>，行号列上的 ▼ 点击可折叠对应块，▶ 点击可展开</li>
                <li>在 JSON 视图中<span class="highlight">双击任意位置</span>即可进入编辑模式，光标会定位到双击的行和列，失焦后自动格式化并返回 JSON 视图</li>
              </ul>
            </li>
            <li>点击<span class="highlight">对比文本</span>按钮显示差异，顶部会弹出 Toast 提示本次差异数量</li>
            <li><span class="highlight" style="background:#d4edda;">绿色高亮</span>表示新增内容</li>
            <li><span class="highlight" style="background:#f8d7da;">红色高亮</span>表示删除内容</li>
            <li><span class="highlight" style="background:#fff3cd;">黄色高亮</span>表示修改内容</li>
            <li>启用<span class="highlight">同步滚动</span>可使原始文本、修改文本和对比结果三者按百分比同步滚动</li>
            <li>拖动编辑区与对比结果之间的<span class="highlight">分隔条</span>可上下调整两区高度</li>
            <li>点击<span class="highlight">清空文本</span>可重置所有输入区域</li>
            <li>点击「对比文本」后，若两侧文本均为合法 JSON，会出现<span class="highlight">JSON 自动排序</span>按钮</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <div v-if="toast.visible" class="toast" :class="{ show: toast.visible }" :style="{ background: toast.type === 'error' ? 'rgba(220, 53, 69, 0.95)' : 'rgba(40, 167, 69, 0.95)' }">
      {{ toast.message }}
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'

const helpTip = `快速比较两个文本的差异，支持左右并排显示，高亮显示添加、删除和修改的内容。

· 输入框左侧固定行号，便于定位
· JSON 自动按 2 空格缩进格式化，支持行号列上的折叠 / 展开
· 在 JSON 视图中双击任意位置进入编辑模式，光标即定位到双击处，失焦自动返回
· 对比后两侧均为 JSON 时，可点「JSON 自动排序」按 key 字母排序
· 拖动编辑区与对比结果之间的分隔条可调整高度
· 点击「对比文本」顶部会提示差异统计（3 秒后消失）`

// ========== DOM Refs ==========
const diffContainerRef = ref(null)
const hResizerRef = ref(null)
const diffResultRef = ref(null)

const editorOriginalRef = ref(null)
const originalTextRef = ref(null)
const gutterOverlayOriginalRef = ref(null)
const codeViewOriginalRef = ref(null)
const gutterOriginalRef = ref(null)
const contentOriginalRef = ref(null)
const switchOriginalRef = ref(null)

const editorModifiedRef = ref(null)
const modifiedTextRef = ref(null)
const gutterOverlayModifiedRef = ref(null)
const codeViewModifiedRef = ref(null)
const gutterModifiedRef = ref(null)
const contentModifiedRef = ref(null)
const switchModifiedRef = ref(null)

// ========== State ==========
const originalText = ref(`function calculateSum(a, b) {
    return a + b;
}

// 测试调用
console.log(calculateSum(5, 10));

const user = {
    name: "Alice",
    age: 28,
    occupation: "Software Engineer"
};

console.log("用户信息:", user);`)

const modifiedText = ref(`function calculateSum(a, b) {
    // 添加参数验证
    if (typeof a !== 'number' || typeof b !== 'number') {
        throw new Error('参数必须是数字');
    }
    return a + b;
}

// 测试调用
console.log(calculateSum(5, 10));

const user = {
    name: "Alice Smith",
    age: 29,
    occupation: "Senior Software Engineer",
    email: "alice@example.com"
};

console.log("用户详细信息:", user);`)

const syncEnabled = ref(true)
const showSortBtn = ref(false)

const toast = ref({ visible: false, message: '', type: 'success' })
let toastTimer = null

// ========== Editor APIs (set on mount) ==========
let editorOriginal = null
let editorModified = null

// ========== Toast ==========
function showToast(message, type = 'success') {
  toast.value = { visible: true, message, type }
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toast.value.visible = false
  }, 3000)
}

// ========== HTML escape ==========
function escapeHtml(text) {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

// ========== JSON detection ==========
function isJsonText(text) {
  const t = (text || '').trim()
  if (t.length < 2) return false
  try {
    JSON.parse(t)
    return true
  } catch (e) {
    return false
  }
}

function isLegalJson(text) {
  const t = (text || '').trim()
  if (t.length < 2) return false
  const f = t.charAt(0), l = t.charAt(t.length - 1)
  if (!((f === '{' && l === '}') || (f === '[' && l === ']'))) return false
  try {
    JSON.parse(t)
    return true
  } catch (e) {
    return false
  }
}

// ========== JSON deep sort ==========
function sortJsonDeep(value) {
  if (Array.isArray(value)) {
    return value.map(sortJsonDeep)
  }
  if (value && typeof value === 'object') {
    const out = {}
    Object.keys(value).sort((a, b) => {
      return a.localeCompare(b, 'zh-Hans-CN', { sensitivity: 'base', numeric: true })
    }).forEach((k) => {
      out[k] = sortJsonDeep(value[k])
    })
    return out
  }
  return value
}

// ========== Text comparison ==========
function compareTexts(silent = false) {
  const text1 = originalTextRef.value.value.split('\n')
  const text2 = modifiedTextRef.value.value.split('\n')

  let resultHTML = ''
  let lineNum = 1
  let addedCount = 0, removedCount = 0, modifiedCount = 0

  const maxLength = Math.max(text1.length, text2.length)

  for (let i = 0; i < maxLength; i++) {
    const line1 = text1[i] || ''
    const line2 = text2[i] || ''

    if (line1 === line2) {
      resultHTML += `<div class="line"><span class="line-number">${lineNum++}</span>${escapeHtml(line1)}</div>`
    } else if (line2 === '') {
      removedCount++
      resultHTML += `<div class="line removed"><span class="line-number">${lineNum++}</span>${escapeHtml(line1)}</div>`
    } else if (line1 === '') {
      addedCount++
      resultHTML += `<div class="line added"><span class="line-number">${lineNum++}</span>${escapeHtml(line2)}</div>`
    } else {
      modifiedCount++
      resultHTML += `<div class="line modified"><span class="line-number">${lineNum++}</span>`
      const maxLineLength = Math.max(line1.length, line2.length)
      let charResult = ''
      for (let j = 0; j < maxLineLength; j++) {
        const char1 = line1[j] || ''
        const char2 = line2[j] || ''
        if (char1 === char2) {
          charResult += escapeHtml(char1)
        } else if (char1 === '') {
          charResult += `<span class="added">${escapeHtml(char2)}</span>`
        } else if (char2 === '') {
          charResult += `<span class="removed">${escapeHtml(char1)}</span>`
        } else {
          charResult += `<span class="modified">${escapeHtml(char2)}</span>`
        }
      }
      resultHTML += charResult + '</div>'
    }
  }

  diffResultRef.value.innerHTML = resultHTML

  // Show sort button only when both sides are valid JSON
  showSortBtn.value = isJsonText(originalTextRef.value.value) && isJsonText(modifiedTextRef.value.value)

  if (silent) return
  const totalDiff = addedCount + removedCount + modifiedCount
  if (totalDiff === 0) {
    showToast('两段文本完全一致 ✅', 'success')
  } else {
    showToast(
      `对比完成：新增 ${addedCount} 行 · 删除 ${removedCount} 行 · 修改 ${modifiedCount} 行`,
      'success'
    )
  }
}

// ========== Clear texts ==========
function clearTexts() {
  originalText.value = ''
  modifiedText.value = ''
  diffResultRef.value.innerHTML = ''
  showSortBtn.value = false
  if (editorOriginal) {
    editorOriginal.clearFolded()
    editorOriginal.refresh()
  }
  if (editorModified) {
    editorModified.clearFolded()
    editorModified.refresh()
  }
}

// ========== Sort JSON ==========
function sortJson() {
  ;[[originalTextRef.value, editorOriginal], [modifiedTextRef.value, editorModified]].forEach((pair) => {
    const ta = pair[0], api = pair[1]
    try {
      const parsed = JSON.parse(ta.value)
      const sorted = JSON.stringify(sortJsonDeep(parsed), null, 2)
      ta.value = sorted
      // Update the v-model bound value
      if (ta === originalTextRef.value) originalText.value = sorted
      else modifiedText.value = sorted
      api.clearFolded()
      api.refresh()
    } catch (e) { /* skip non-JSON */ }
  })
  compareTexts(true)
  showToast('已按 key 字母顺序排序对象（数组保持原序）并重新对比', 'success')
}

// ========== JSON syntax highlighting ==========
const TOK_STR = 'tok-str'
const TOK_KEY = 'tok-key'
const TOK_NUM = 'tok-num'
const TOK_BOOL = 'tok-bool'
const TOK_NULL = 'tok-null'
const TOK_BRAC = 'tok-brac'
const TOK_PUNC = 'tok-punc'
const TOK_UNKNOWN = 'tok-unk'

function highlightJson(text) {
  const n = text.length
  const lineHtmls = []
  const lineBuf = []
  let i = 0
  const containerStack = []

  function pushLine() {
    lineHtmls.push(lineBuf.join(''))
    lineBuf.length = 0
  }

  while (i < n) {
    const ch = text[i]

    if (ch === ' ' || ch === '\t') {
      const wsStart = i
      while (i < n && (text[i] === ' ' || text[i] === '\t')) i++
      lineBuf.push(text.slice(wsStart, i))
      continue
    }
    if (ch === '\n') {
      pushLine()
      i++
      continue
    }

    if (ch === '{') {
      containerStack.push(true)
      lineBuf.push('<span class="' + TOK_BRAC + '">{</span>')
      i++
      continue
    }
    if (ch === '[') {
      containerStack.push(false)
      lineBuf.push('<span class="' + TOK_BRAC + '">[</span>')
      i++
      continue
    }
    if (ch === '}') {
      if (containerStack.length) containerStack.pop()
      lineBuf.push('<span class="' + TOK_BRAC + '">}</span>')
      i++
      continue
    }
    if (ch === ']') {
      if (containerStack.length) containerStack.pop()
      lineBuf.push('<span class="' + TOK_BRAC + '">]</span>')
      i++
      continue
    }
    if (ch === ',') {
      lineBuf.push('<span class="' + TOK_PUNC + '">,</span>')
      i++
      continue
    }

    if (ch === '"') {
      const strStart = i
      i++
      while (i < n && text[i] !== '"') {
        if (text[i] === '\\' && i + 1 < n) i += 2
        else i++
      }
      i++
      const rawStr = text.slice(strStart, i)
      let isKey = false
      if (containerStack.length && containerStack[containerStack.length - 1]) {
        let j = i
        while (j < n && (text[j] === ' ' || text[j] === '\t' || text[j] === '\n' || text[j] === '\r')) j++
        if (j < n && text[j] === ':') isKey = true
      }
      lineBuf.push('<span class="' + (isKey ? TOK_KEY : TOK_STR) + '">' + escapeHtml(rawStr) + '</span>')
      continue
    }

    if ((ch >= '0' && ch <= '9') || ch === '-') {
      const numStart = i
      if (ch === '-') i++
      while (i < n && text[i] >= '0' && text[i] <= '9') i++
      if (i < n && text[i] === '.') {
        i++
        while (i < n && text[i] >= '0' && text[i] <= '9') i++
      }
      if (i < n && (text[i] === 'e' || text[i] === 'E')) {
        i++
        if (i < n && (text[i] === '+' || text[i] === '-')) i++
        while (i < n && text[i] >= '0' && text[i] <= '9') i++
      }
      lineBuf.push('<span class="' + TOK_NUM + '">' + escapeHtml(text.slice(numStart, i)) + '</span>')
      continue
    }

    if (ch === 't' && text.substr(i, 4) === 'true') {
      lineBuf.push('<span class="' + TOK_BOOL + '">true</span>')
      i += 4
      continue
    }
    if (ch === 'f' && text.substr(i, 5) === 'false') {
      lineBuf.push('<span class="' + TOK_BOOL + '">false</span>')
      i += 5
      continue
    }
    if (ch === 'n' && text.substr(i, 4) === 'null') {
      lineBuf.push('<span class="' + TOK_NULL + '">null</span>')
      i += 4
      continue
    }

    if (ch === ':') {
      lineBuf.push('<span class="' + TOK_PUNC + '">:</span>')
      i++
      continue
    }

    lineBuf.push('<span class="' + TOK_UNKNOWN + '">' + escapeHtml(ch) + '</span>')
    i++
  }
  pushLine()
  return lineHtmls
}

// ========== JSON structure scan (fold ranges, depths, guides) ==========
function scanJsonStructure(text) {
  const lineStart = [0]
  for (let i = 0; i < text.length; i++) {
    if (text.charCodeAt(i) === 10) lineStart.push(i + 1)
  }
  function posToLine(pos) {
    let lo = 0, hi = lineStart.length - 1
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1
      if (lineStart[mid] <= pos) lo = mid
      else hi = mid - 1
    }
    return lo
  }

  const folds = new Map()
  const stack = []
  let inStr = false, quote = '', esc = false
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (inStr) {
      if (esc) esc = false
      else if (ch === '\\') esc = true
      else if (ch === quote) inStr = false
    } else {
      if (ch === '"') { inStr = true; quote = ch }
      else if (ch === '{' || ch === '[') stack.push({ ch, pos: i })
      else if (ch === '}' || ch === ']') {
        const open = stack.pop()
        if (open) {
          const sLine = posToLine(open.pos)
          const eLine = posToLine(i)
          if (sLine < eLine) {
            folds.set(sLine, {
              end: eLine,
              close: open.ch === '{' ? '}' : ']'
            })
          }
        }
      }
    }
  }

  const lines = text.split('\n')
  const indents = lines.map((line) => {
    let n = 0
    for (let i = 0; i < line.length; i++) {
      const c = line.charCodeAt(i)
      if (c === 32 || c === 9) n++
      else break
    }
    return n
  })

  const n = lines.length
  const depths = new Array(n)
  const guides = new Array(n)

  let curDepth = 0
  for (let i = 0; i < n; i++) {
    depths[i] = curDepth
    guides[i] = new Array(curDepth).fill(true)

    const line = lines[i]
    let inStr2 = false, quote2 = '', esc2 = false
    let decrDepth = 0
    let firstNonSpaceIdx = -1
    for (let j = 0; j < line.length; j++) {
      const ch = line[j]
      if (inStr2) {
        if (esc2) esc2 = false
        else if (ch === '\\') esc2 = true
        else if (ch === quote2) inStr2 = false
      } else {
        if (ch === '"') { inStr2 = true; quote2 = ch; if (firstNonSpaceIdx === -1) firstNonSpaceIdx = j }
        else if (ch === '{' || ch === '[') { if (firstNonSpaceIdx === -1) firstNonSpaceIdx = j; curDepth++ }
        else if (ch === '}' || ch === ']') { if (firstNonSpaceIdx === -1) firstNonSpaceIdx = j; if (curDepth > 0) { curDepth--; decrDepth++ } }
        else if (firstNonSpaceIdx === -1 && ch !== ' ' && ch !== '\t') firstNonSpaceIdx = j
      }
    }

    if (firstNonSpaceIdx !== -1) {
      const fc = line[firstNonSpaceIdx]
      if (fc === '}' || fc === ']') {
        const closeCount = Math.min(decrDepth, guides[i].length)
        for (let k = guides[i].length - closeCount; k < guides[i].length; k++) {
          guides[i][k] = false
        }
      }
    }
  }

  return { foldMap: folds, indents, lines, depths, guides }
}

// ========== Editor factory ==========
function createEditor({ containerEl, textarea, overlay, codeView, gutterEl, contentEl, switchBtn }) {
  let foldedLines = new Set()
  let mode = 'edit'
  let isJson = false

  function updateSwitchLabel() {
    if (!isJson) {
      switchBtn.textContent = ''
      switchBtn.style.visibility = 'hidden'
      return
    }
    switchBtn.style.visibility = 'visible'
    switchBtn.textContent = mode === 'json' ? 'JSON 视图' : '编辑模式'
    switchBtn.classList.toggle('status-json', mode === 'json')
    switchBtn.classList.toggle('status-edit', mode !== 'json')
  }

  function renderOverlay() {
    const lines = textarea.value.split('\n')
    let html = ''
    for (let i = 0; i < lines.length; i++) {
      html += '<span class="ln">' + (i + 1) + '</span>'
    }
    overlay.innerHTML = html
    overlay.scrollTop = textarea.scrollTop
  }

  function ensureGutterInner() {
    let inner = gutterEl.querySelector(':scope > .gutter-inner')
    if (!inner) {
      inner = document.createElement('div')
      inner.className = 'gutter-inner'
      gutterEl.appendChild(inner)
    }
    return inner
  }

  function syncGutterScroll() {
    const inner = ensureGutterInner()
    inner.style.transform = 'translateY(' + (-contentEl.scrollTop) + 'px)'
  }

  function renderJsonView() {
    const text = textarea.value
    const { foldMap, lines, depths, guides } = scanJsonStructure(text)
    const totalLines = lines.length
    const savedScrollTop = contentEl.scrollTop
    const highlightedLines = highlightJson(text)

    const hidden = new Set()
    foldedLines.forEach((s) => {
      const info = foldMap.get(s)
      if (!info) return
      for (let i = s + 1; i <= info.end; i++) hidden.add(i)
    })

    const gutterParts = []
    const contentParts = []
    for (let i = 0; i < totalLines; i++) {
      if (hidden.has(i)) continue

      const foldInfo = foldMap.get(i)
      const isFolded = foldedLines.has(i)
      let btnHtml = ''
      if (foldInfo) {
        btnHtml = '<span class="fold-btn" data-fold="' + i + '" title="点击' + (isFolded ? '展开' : '折叠') + '">'
          + (isFolded ? '▶' : '▼') + '</span>'
      } else {
        btnHtml = '<span class="fold-btn placeholder"></span>'
      }

      gutterParts.push('<div class="row">' + btnHtml
        + '<span class="gutter-num">' + (i + 1) + '</span></div>')

      const depth = depths[i]
      const guideFlags = guides[i]
      let guidesHtml = ''
      for (let g = 0; g < depth; g++) {
        guidesHtml += '<span class="indent-guide'
          + (guideFlags[g] ? ' guide-on' : ' guide-off')
          + '"></span>'
      }

      let lineText = highlightedLines[i] !== undefined ? highlightedLines[i] : escapeHtml(lines[i])
      if (isFolded && foldInfo) {
        const count = foldInfo.end - i
        lineText += '<i class="fold-placeholder"> ⋯ ' + count + ' lines ' + foldInfo.close + ' </i>'
      }
      contentParts.push('<div class="row" data-line="' + i + '">'
        + '<span class="indent-guides">' + guidesHtml + '</span>'
        + lineText + '</div>')
    }

    const gutterInner = ensureGutterInner()
    gutterInner.innerHTML = gutterParts.join('')
    contentEl.innerHTML = contentParts.join('')

    Array.prototype.forEach.call(gutterInner.querySelectorAll('[data-fold]'), (btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation()
        const lineIdx = parseInt(btn.getAttribute('data-fold'), 10)
        if (foldedLines.has(lineIdx)) foldedLines.delete(lineIdx)
        else foldedLines.add(lineIdx)
        renderJsonView()
      })
    })

    contentEl.onscroll = () => {
      syncGutterScroll()
    }
    contentEl.scrollTop = savedScrollTop
    syncGutterScroll()
  }

  function trySwitchToJsonView() {
    if (!isLegalJson(textarea.value)) { isJson = false; updateSwitchLabel(); return }
    isJson = true
    mode = 'json'
    const pct = getScrollPercent(getCurrentScrollEl())

    try {
      textarea.style.display = 'none'
      overlay.style.display = 'none'
      codeView.style.display = 'flex'
      renderJsonView()
      setScrollPercent(getCurrentScrollEl(), pct)
      updateSwitchLabel()
      rebuildScrollTargets()
    } catch (err) {
      console.warn('JSON 视图渲染失败，已回退到编辑模式:', err)
      codeView.style.display = 'none'
      overlay.style.display = 'block'
      textarea.style.display = 'block'
      isJson = false
      mode = 'edit'
      renderOverlay()
      updateSwitchLabel()
      rebuildScrollTargets()
      showToast('JSON 视图渲染失败，已切换到编辑模式', 'error')
    }
  }

  function switchToEdit(caretPos) {
    mode = 'edit'
    codeView.style.display = 'none'
    overlay.style.display = 'block'
    textarea.style.display = 'block'
    renderOverlay()
    updateSwitchLabel()
    rebuildScrollTargets()
    textarea.focus()
    if (caretPos) {
      const lines = textarea.value.split('\n')
      let offset = 0
      for (let i = 0; i < caretPos.line && i < lines.length; i++) {
        offset += lines[i].length + 1
      }
      const targetLine = lines[Math.min(caretPos.line, lines.length - 1)] || ''
      offset += Math.min(caretPos.col, targetLine.length)
      textarea.setSelectionRange(offset, offset)
      const lineH = parseFloat(getComputedStyle(textarea).lineHeight) || 21
      textarea.scrollTop = Math.max(0, caretPos.line * lineH - textarea.clientHeight / 2)
    }
  }

  function formatJsonIfNeeded() {
    const raw = textarea.value
    const trimmed = (raw || '').trim()
    if (!trimmed) { isJson = false; updateSwitchLabel(); return false }
    const first = trimmed.charAt(0), last = trimmed.charAt(trimmed.length - 1)
    if (!((first === '{' && last === '}') || (first === '[' && last === ']'))) {
      isJson = false
      updateSwitchLabel()
      return false
    }
    try {
      const parsed = JSON.parse(trimmed)
      const formatted = JSON.stringify(parsed, null, 2)
      const changed = formatted !== trimmed && formatted !== raw
      if (changed) {
        textarea.value = formatted
        // sync v-model
        if (textarea === originalTextRef.value) originalText.value = formatted
        else if (textarea === modifiedTextRef.value) modifiedText.value = formatted
      }
      isJson = true
      return true
    } catch (e) {
      isJson = false
      updateSwitchLabel()
      return false
    }
  }

  function refresh() {
    const ok = formatJsonIfNeeded()
    if (ok) {
      if (mode !== 'json') trySwitchToJsonView()
      else renderJsonView()
    } else {
      if (mode !== 'edit') switchToEdit()
      else renderOverlay()
    }
  }

  function clearFolded() { foldedLines.clear() }

  function getCurrentScrollEl() {
    return mode === 'json' ? contentEl : textarea
  }

  function handleDblclick(e) {
    if (mode !== 'json' || e.target.closest('.fold-btn')) return

    let line = 0, col = 0
    const contentRow = e.target.closest ? e.target.closest('.code-content [data-line]') : null
    if (contentRow) {
      line = parseInt(contentRow.getAttribute('data-line'), 10) || 0
      const lineTextNode = contentRow.firstChild
      const lineLen = (lineTextNode && lineTextNode.nodeType === 3) ? lineTextNode.textContent.length : 0

      if (e.target.closest('.fold-placeholder')) {
        col = lineLen
      } else {
        let pos = null
        if (document.caretRangeFromPoint) {
          pos = document.caretRangeFromPoint(e.clientX, e.clientY)
        } else if (document.caretPositionFromPoint) {
          const p = document.caretPositionFromPoint(e.clientX, e.clientY)
          if (p) pos = { startContainer: p.offsetNode, startOffset: p.offset }
        }
        const inFold = pos && pos.startContainer.parentElement
          && pos.startContainer.parentElement.closest('.fold-placeholder')
        if (pos && contentRow.contains(pos.startContainer)
          && pos.startContainer.nodeType === 3 && !inFold) {
          col = pos.startOffset
        } else {
          col = lineLen
        }
      }
    } else {
      const gutterRow = e.target.closest ? e.target.closest('.code-gutter .row') : null
      if (gutterRow) {
        const inner = ensureGutterInner()
        const idx = Array.prototype.indexOf.call(inner.children, gutterRow)
        const mapped = contentEl.children[idx]
        if (mapped && mapped.hasAttribute('data-line')) {
          line = parseInt(mapped.getAttribute('data-line'), 10) || 0
        }
      }
      col = 0
    }

    switchToEdit({ line, col })
    const sel = window.getSelection()
    if (sel && sel.removeAllRanges) sel.removeAllRanges()
  }

  // Initial render
  renderOverlay()
  formatJsonIfNeeded()
  updateSwitchLabel()
  if (isJson) trySwitchToJsonView()

  return {
    refresh,
    clearFolded,
    getCurrentScrollEl,
    switchToEdit,
    trySwitchToJsonView,
    formatJsonIfNeeded,
    handleDblclick,
    renderOverlay,
    get mode() { return mode },
    get isJson() { return isJson }
  }
}

// ========== Sync scroll ==========
let isSyncingScroll = false
let scrollTargets = []
const scrollHandlerMap = new WeakMap()

function getScrollPercent(el) {
  if (!el) return 0
  const max = el.scrollHeight - el.clientHeight
  return max > 0 ? el.scrollTop / max : 0
}

function setScrollPercent(el, percent) {
  if (!el) return
  const max = el.scrollHeight - el.clientHeight
  el.scrollTop = Math.round(percent * max)
}

function makeScrollHandler(srcEl) {
  return () => {
    if (!syncEnabled.value || isSyncingScroll) return
    isSyncingScroll = true
    const percent = getScrollPercent(srcEl)
    scrollTargets.forEach((other) => {
      if (other !== srcEl) setScrollPercent(other, percent)
    })
    requestAnimationFrame(() => { isSyncingScroll = false })
  }
}

function bindScrollTargets() {
  scrollTargets.forEach((el) => {
    const h = scrollHandlerMap.get(el)
    if (h && el.removeEventListener) el.removeEventListener('scroll', h)
    scrollHandlerMap.delete(el)
  })
  scrollTargets.forEach((el) => {
    if (!el || !el.addEventListener) return
    const h = makeScrollHandler(el)
    el.addEventListener('scroll', h)
    scrollHandlerMap.set(el, h)
  })
}

function rebuildScrollTargets() {
  if (!editorOriginal || !editorModified) return
  scrollTargets = [
    editorOriginal.getCurrentScrollEl(),
    editorModified.getCurrentScrollEl(),
    diffResultRef.value
  ]
  bindScrollTargets()
}

// ========== Resizer ==========
let resizing = false
let startY = 0
let startH = 0
const MIN_EDITOR_H = 120
const MIN_RESULT_H = 160

function onResizerMouseDown(e) {
  if (window.innerWidth <= 768) return
  resizing = true
  startY = e.clientY
  startH = diffContainerRef.value.getBoundingClientRect().height
  document.body.style.cursor = 'row-resize'
  document.body.style.userSelect = 'none'
  e.preventDefault()
}

function onMouseMove(e) {
  if (!resizing) return
  const top = diffContainerRef.value.getBoundingClientRect().top
  const maxH = window.innerHeight - top - MIN_RESULT_H
  let h = startH + (e.clientY - startY)
  h = Math.max(MIN_EDITOR_H, Math.min(h, maxH))
  diffContainerRef.value.style.height = h + 'px'
}

function onMouseUp() {
  if (!resizing) return
  resizing = false
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

// ========== Event handlers (bound in template) ==========
function onOriginalScroll() {
  if (gutterOverlayOriginalRef.value) {
    gutterOverlayOriginalRef.value.scrollTop = originalTextRef.value.scrollTop
  }
}

function onOriginalInput() {
  if (editorOriginal) editorOriginal.renderOverlay()
}

function onOriginalPaste() {
  setTimeout(() => {
    if (!editorOriginal) return
    const before = originalTextRef.value.value
    const ok = editorOriginal.formatJsonIfNeeded()
    if (ok) {
      editorOriginal.trySwitchToJsonView()
    } else {
      editorOriginal.renderOverlay()
      if (editorOriginal.mode === 'json') editorOriginal.switchToEdit()
    }
  }, 0)
}

function onOriginalBlur() {
  if (editorOriginal) editorOriginal.refresh()
}

function onOriginalDblclick(e) {
  if (editorOriginal) editorOriginal.handleDblclick(e)
}

function onModifiedScroll() {
  if (gutterOverlayModifiedRef.value) {
    gutterOverlayModifiedRef.value.scrollTop = modifiedTextRef.value.scrollTop
  }
}

function onModifiedInput() {
  if (editorModified) editorModified.renderOverlay()
}

function onModifiedPaste() {
  setTimeout(() => {
    if (!editorModified) return
    const ok = editorModified.formatJsonIfNeeded()
    if (ok) {
      editorModified.trySwitchToJsonView()
    } else {
      editorModified.renderOverlay()
      if (editorModified.mode === 'json') editorModified.switchToEdit()
    }
  }, 0)
}

function onModifiedBlur() {
  if (editorModified) editorModified.refresh()
}

function onModifiedDblclick(e) {
  if (editorModified) editorModified.handleDblclick(e)
}

// ========== Lifecycle ==========
onMounted(() => {
  nextTick(() => {
    editorOriginal = createEditor({
      containerEl: editorOriginalRef.value,
      textarea: originalTextRef.value,
      overlay: gutterOverlayOriginalRef.value,
      codeView: codeViewOriginalRef.value,
      gutterEl: gutterOriginalRef.value,
      contentEl: contentOriginalRef.value,
      switchBtn: switchOriginalRef.value
    })

    editorModified = createEditor({
      containerEl: editorModifiedRef.value,
      textarea: modifiedTextRef.value,
      overlay: gutterOverlayModifiedRef.value,
      codeView: codeViewModifiedRef.value,
      gutterEl: gutterModifiedRef.value,
      contentEl: contentModifiedRef.value,
      switchBtn: switchModifiedRef.value
    })

    rebuildScrollTargets()
    compareTexts(true)
  })

  // Global listeners for resizer
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
  if (toastTimer) clearTimeout(toastTimer)
})
</script>

<style scoped>
.strtostr-wrapper {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.strtostr-container {
  max-width: 100%;
  margin: 0 auto;
  width: 100%;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.strtostr-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
  color: white;
  padding: 4px 8px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 25%, #6B8DD6 50%, #8E2DE2 75%, #4A00E0 100%);
  background-size: 400% 400%;
  animation: gradientShift 18s ease infinite;
  border-radius: 8px 8px 0 0;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
  position: relative;
}

@keyframes gradientShift {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

.header-actions,
.header-sync {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1 1 0;
  min-width: 0;
}

.header-sync {
  justify-content: flex-end;
}

.header-sync label {
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
}

.btn-header {
  padding: 6px 14px;
  font-size: 13px;
  color: #fff;
  background: rgba(255, 255, 255, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.4);
  text-shadow: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.2s ease;
}

.btn-header:hover {
  background: rgba(255, 255, 255, 0.32);
  transform: translateY(-1px);
}

.strtostr-title {
  font-size: 1.3rem;
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.help-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
  font-size: 13px;
  cursor: help;
  position: relative;
  text-shadow: none;
  border: 1px solid rgba(255, 255, 255, 0.4);
  transition: background 0.2s;
}

.help-icon:hover {
  background: rgba(255, 255, 255, 0.35);
}

.help-icon::after {
  content: attr(data-tip);
  position: absolute;
  left: 50%;
  top: calc(100% + 8px);
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.85);
  color: #fff;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: normal;
  line-height: 1.6;
  white-space: pre-wrap;
  text-align: left;
  width: max-content;
  max-width: 360px;
  min-width: 240px;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.15s ease;
  z-index: 100;
  text-shadow: none;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3);
}

.help-icon:hover::after {
  opacity: 1;
}

.tool-container {
  background: white;
  border-radius: 0 0 8px 8px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
  overflow: hidden;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.diff-container {
  display: flex;
  flex: 1;
  min-height: 120px;
  position: relative;
}

.h-resizer {
  height: 7px;
  background: #e9ecef;
  border-top: 1px solid #dee2e6;
  border-bottom: 1px solid #dee2e6;
  cursor: row-resize;
  position: relative;
  flex-shrink: 0;
  z-index: 6;
  transition: background 0.15s;
}

.h-resizer::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 52px;
  height: 3px;
  border-radius: 2px;
  background: #adb5bd;
  transition: background 0.15s;
}

.h-resizer:hover {
  background: #d0ebff;
}

.h-resizer:hover::after {
  background: #4a6ee0;
}

.diff-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #e9ecef;
  padding: 6px 12px;
  font-weight: bold;
  border-bottom: 1px solid #dee2e6;
  font-size: 14px;
}

.diff-header > div:first-child {
  flex: 1;
  text-align: center;
}

.mode-status {
  font-size: 12px;
  user-select: none;
  padding: 2px 10px;
  border-radius: 10px;
  font-weight: normal;
  border: 1px solid transparent;
  white-space: nowrap;
}

.mode-status.status-json {
  color: #4a6ee0;
  background: rgba(74, 110, 224, 0.12);
  border-color: rgba(74, 110, 224, 0.4);
}

.mode-status.status-edit {
  color: #2f9e44;
  background: rgba(47, 158, 68, 0.12);
  border-color: rgba(47, 158, 68, 0.4);
}

.diff-content {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 200px;
}

.editor-container {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
  position: relative;
  border-right: 1px solid #dee2e6;
}

.editor-body {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.5;
}

textarea.editor-textarea {
  width: 100%;
  flex: 1 1 auto;
  min-width: 0;
  padding: 8px 10px 8px 56px;
  border: none;
  resize: none;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.5;
  outline: none;
  background: #f8f9fa;
  transition: background 0.3s;
  overflow: auto;
}

textarea.editor-textarea:focus {
  background: #fff;
}

.editor-gutter-overlay {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  width: 46px;
  background: #e9ecef;
  border-right: 1px solid #dee2e6;
  overflow: hidden;
  padding: 8px 4px;
  pointer-events: none;
  z-index: 2;
}

.editor-gutter-overlay .ln {
  display: block;
  text-align: right;
  color: #6c757d;
  user-select: none;
  padding: 1px 6px 1px 0;
  white-space: nowrap;
  font-size: 13px;
}

.code-view {
  display: none;
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  flex-direction: row;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.5;
}

.code-gutter {
  flex-shrink: 0;
  width: 64px;
  min-width: 64px;
  background: #e9ecef;
  border-right: 1px solid #dee2e6;
  overflow: hidden;
  user-select: none;
  text-align: right;
  color: #6c757d;
  position: relative;
}

.gutter-inner {
  padding: 8px 0;
  will-change: transform;
}

.code-gutter .row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 1px 2px 1px 0;
  white-space: nowrap;
  height: calc(14px * 1.5 + 2px);
  box-sizing: content-box;
}

.fold-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 18px;
  margin-right: 2px;
  cursor: pointer;
  color: #495057;
  font-size: 10px;
  line-height: 1;
  border-radius: 2px;
  flex-shrink: 0;
}

.fold-btn:hover {
  background: #fff;
  color: #4a6ee0;
}

.fold-btn.placeholder {
  visibility: hidden;
}

.gutter-num {
  min-width: 28px;
  padding-right: 4px;
  display: inline-block;
  font-size: 13px;
}

.code-content {
  flex: 1 1 auto;
  min-width: 0;
  overflow: auto;
  padding: 8px 10px;
  background: #f8f9fa;
  white-space: pre;
  font-size: 14px;
  line-height: 1.5;
  word-break: keep-all;
  word-wrap: normal;
}

.code-content .row {
  padding: 1px 0;
  height: calc(14px * 1.5 + 2px);
  box-sizing: content-box;
  position: relative;
}

.fold-placeholder {
  display: inline-block;
  margin: 0 4px;
  padding: 0 6px;
  color: #868e96;
  background: #dee2e6;
  border-radius: 3px;
  font-style: normal;
  font-size: 12px;
  user-select: none;
}

.indent-guides {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  display: flex;
  height: 100%;
  pointer-events: none;
}

.indent-guide {
  position: relative;
  display: inline-block;
  width: 12px;
  flex-shrink: 0;
  height: 100%;
}

.indent-guide.guide-on::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 1px;
  background: rgba(108, 117, 125, 0.35);
}

.indent-guide.guide-off::after {
  display: none;
}

.code-content { color: #333; }
.tok-key { color: #EE8800; }
.tok-str { color: #178000; }
.tok-num { color: #1a1aa6; }
.tok-bool { color: #1a1aa6; font-weight: 600; }
.tok-null { color: #1a1aa6; font-style: italic; }
.tok-brac { color: #da3633; font-weight: 600; }
.tok-punc { color: #da3633; }
.tok-unk { color: #dc3545; background: rgba(220, 53, 69, 0.08); }

.result-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  position: relative;
}

.diff-result {
  flex: 1;
  padding: 8px 10px;
  overflow: auto;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
  background: #f8f9fa;
  min-height: 200px;
}

.line {
  padding: 1px 0;
}

.added {
  background: #d4edda;
  color: #155724;
}

.removed {
  background: #f8d7da;
  color: #721c24;
  text-decoration: line-through;
}

.modified {
  background: #fff3cd;
  color: #856404;
}

.line-number {
  display: inline-block;
  width: 40px;
  text-align: right;
  padding-right: 10px;
  color: #6c757d;
  user-select: none;
}

.instructions {
  background: #f8f9fa;
  padding: 10px 16px;
  border-top: 1px solid #e9ecef;
  font-size: 13px;
}

.instructions h3 {
  margin-bottom: 6px;
  color: #4a6ee0;
}

.instructions ul {
  padding-left: 20px;
}

.instructions li {
  margin-bottom: 4px;
}

.highlight {
  background: #ffeb3b;
  padding: 1px 4px;
  border-radius: 3px;
}

.toast {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%) translateY(0);
  color: white;
  padding: 10px 24px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
  z-index: 9999;
  transition: all 0.3s ease;
  pointer-events: none;
}

@media (max-width: 768px) {
  .strtostr-header {
    flex-wrap: wrap;
  }

  .diff-container {
    flex-direction: column;
    height: auto;
  }

  .h-resizer {
    display: none;
  }

  .editor-container,
  .result-container {
    height: 40vh;
    border-right: none;
    border-bottom: 1px solid #dee2e6;
  }
}
</style>
