# 项目代码统计教程

统计项目的文件数量和代码行数，便于了解项目规模、评估工作量。

## 方法一：Git + PowerShell（无需安装工具）

利用 `git ls-files` 获取版本控制中的文件列表，配合 PowerShell 统计行数。

### 1. 统计总文件数

```powershell
# 排除依赖和生成目录
git ls-files | Where-Object {
  $_ -notmatch 'node_modules|venv|__pycache__|client/dist|\.idea/'
} | Measure-Object
```

### 2. 按扩展名分类统计

```powershell
$files = git ls-files | Where-Object {
  $_ -notmatch 'node_modules|venv|__pycache__|client/dist|\.png$|\.svg$|package-lock\.json$|\.idea/'
}

$totalFiles = $files.Count
$totalLines = 0
$stats = @{}

foreach ($f in $files) {
  if (Test-Path $f) {
    $ext = [System.IO.Path]::GetExtension($f).ToLower()
    if (-not $ext) { $ext = '(no ext)' }
    $lines = (Get-Content $f -ErrorAction SilentlyContinue | Measure-Object).Count
    $totalLines += $lines
    if (-not $stats.ContainsKey($ext)) { $stats[$ext] = @{files=0; lines=0} }
    $stats[$ext].files += 1
    $stats[$ext].lines += $lines
  }
}

Write-Host "=== 项目代码统计 ==="
Write-Host "总文件数: $totalFiles"
Write-Host "总代码行: $totalLines"
Write-Host ""
Write-Host ("{0,-12} {1,8} {2,10}" -f "扩展名", "文件数", "代码行数")
Write-Host ("-" * 32)
$stats.GetEnumerator() | Sort-Object { $_.Value.lines } -Descending | ForEach-Object {
  Write-Host ("{0,-12} {1,8} {2,10}" -f $_.Key, $_.Value.files, $_.Value.lines)
}
```

### 3. 只统计纯代码文件

```powershell
$codeExts = @('.py', '.vue', '.js', '.css', '.html')
$files = git ls-files | Where-Object {
  $_ -notmatch 'node_modules|venv|__pycache__|client/dist|\.idea/'
}
$codeFiles = 0; $codeLines = 0
foreach ($f in $files) {
  $ext = [System.IO.Path]::GetExtension($f).ToLower()
  if ($codeExts -contains $ext -and (Test-Path $f)) {
    $codeFiles++
    $codeLines += (Get-Content $f -ErrorAction SilentlyContinue | Measure-Object).Count
  }
}
Write-Host "纯代码文件: $codeFiles 个, $codeLines 行"
```

## 方法二：cloc（推荐，跨平台专业工具）

[cloc](https://github.com/AlDanial/cloc)（Count Lines of Code）能自动识别语言、区分代码/注释/空行。

### 安装

```bash
# 任选一种
npm install -g cloc
pip install cloc
# macOS
brew install cloc
# Windows Scoop
scoop install cloc
```

### 使用

```bash
# 统计整个项目（自动排除 node_modules、.git 等）
cloc app/ client/src/ tests/

# 按文件列出明细
cloc --by-file app/ client/src/

# 排除特定目录
cloc --exclude-dir=__pycache__,dist,venv .

# 只统计特定语言
cloc --include-lang=Python,Vuejs,JavaScript app/ client/src/

# 输出为 Markdown 表格（方便贴到文档）
cloc --md app/ client/src/ tests/
```

### 示例输出

```
-------------------------------------------------------------------------------
Language                     files          blank        comment           code
-------------------------------------------------------------------------------
Python                         116           1820            980          10960
Vuejs Component                 27            640            120          10797
JavaScript                      23            180             85           1170
Markdown                        64            1200              0          12858
JSON                             6              0              0           1333
CSS                              1             10              5             64
-------------------------------------------------------------------------------
SUM:                           237           3850           1190          37182
-------------------------------------------------------------------------------
```

## 方法三：Linux / macOS / Git Bash

```bash
# 统计文件数
git ls-files | grep -v -E 'node_modules|venv|__pycache__|dist' | wc -l

# 统计代码行数
git ls-files | grep -v -E 'node_modules|venv|__pycache__|dist|\.png|\.svg|package-lock' \
  | xargs wc -l | tail -1

# 按扩展名分组统计
git ls-files | grep -v -E 'node_modules|venv|__pycache__|dist' \
  | sed 's/.*\.//' | sort | uniq -c | sort -rn
```

## 关键原则

| 要点 | 说明 |
|------|------|
| 用 `git ls-files` | 只统计版本控制中的文件，自动排除 .gitignore 的内容 |
| 排除依赖目录 | `node_modules`、`venv`、`__pycache__`、`dist` 不是你写的代码 |
| 排除二进制文件 | `.png`、`.svg`、`package-lock.json` 等统计行数无意义 |
| 区分代码与文档 | 纯代码（.py/.vue/.js）和文档（.md）分开看更有参考价值 |
