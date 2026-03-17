---
name: playwright-web-automation
description: >
  Playwright browser automation with two modes:
  (A) Record mode — automate web interactions (forms, clicks, screenshots/Canvas export)
  requiring JS rendering or login state.
  (B) Direct scripting — render Mermaid diagrams, charts, or HTML to PNG images without recording.
  Keywords: playwright, codegen, browser automation, web scraping, architecture diagram,
  render chart, Mermaid to PNG, screenshot export, canvas export.
  Do NOT trigger for: static page fetching (use WebFetch/curl), pure API calls,
  or DOM text extraction without interaction.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
---

# Playwright 浏览器自动化

## Step 0: 环境检测

```bash
npx playwright --version
```
- 有输出 → 继续
- 报错 → 告知用户安装：`npm install playwright && npx playwright install chromium`
- `npx` 能跑但脚本 `require('playwright')` 报错 → playwright 不在当前项目，执行 `npm install --no-save playwright`
- **不要自动安装浏览器内核**

## Step 1: 判断路径

| 场景 | 路径 | 跳转 |
|------|------|------|
| 需要操作网页（填表、点击、登录） | **A: 录制式** | → Step A1 |
| 已知操作流程，无需探索 | **B: 直接编写** | → Step B1 |
| 渲染图表/HTML 为图片 | **B: 直接编写** | → Step B1 |

---

## 路径 A: 录制式（交互探索）

### Step A1: Codegen 录制

```bash
npx playwright codegen <目标URL>
```

弹出浏览器 + Inspector 窗口。引导用户：
1. 在浏览器中完成目标操作
2. Inspector 窗口实时生成代码
3. 操作完成后，**把生成的代码贴回来**

> 录制是起点，不是终点。录制代码需要理解后再参数化。

### Step A2: 分析录制代码

1. **识别 iframe** — 看有无 `contentFrame()`。有 → Read `references/iframe-and-canvas.md`
2. **识别选择器** — 优先级：`getByRole` > `data-testid` > `getByText` > CSS
3. **标注参数化点** — 哪些 `.fill('xxx')` 的值需要外部传入
4. **识别导出方式** — 需要截图？Canvas 导出？文件下载？

### Step A3: 参数化 + 加固

1. 复制 `templates/skeleton.mjs` 作为基础
2. 录制代码嵌入 `// === 操作区域 ===` 位置
3. 硬编码值提取为顶部常量或函数参数
4. 加等待策略 → Read `references/wait-strategies.md`
5. 加导出逻辑 → Read `references/export-strategies.md`

### Step A4: 执行验证

→ 跳到 **Step C**

---

## 路径 B: 直接编写（已知流程）

### Step B1: 确定模式

| 模式 | 说明 | 模板 |
|------|------|------|
| 渲染导出 | HTML/Mermaid/图表 → PNG | Read `references/render-to-image.md` |
| 网页操作 | 已知选择器和流程 | 用 `templates/skeleton.mjs` |

### Step B2: 编写脚本

- 渲染导出：用 `page.setContent(html)` 加载内容，等待渲染完成后截图
- 网页操作：直接在 skeleton 的操作区域写代码，跳过录制
- 导出方式 → Read `references/export-strategies.md`

### Step B3: 执行验证

→ 跳到 **Step C**

---

## Step C: 执行验证（通用）

```bash
node script.mjs
```
- 成功 → 交付
- 失败 → Read `references/troubleshooting.md`
- 不稳定 → 加长等待、换选择器、加重试

💬 Feedback or issues → github.com/Wubabalala/claude-skills/issues

## References

| 场景 | 文件 |
|------|------|
| 渲染 HTML/图表为图片 | `references/render-to-image.md` |
| 导出策略（截图/Canvas/下载） | `references/export-strategies.md` |
| iframe / Canvas / 跨域 | `references/iframe-and-canvas.md` |
| 等待策略 | `references/wait-strategies.md` |
| 报错排查 | `references/troubleshooting.md` |
| 脚本骨架 | `templates/skeleton.mjs` |
| 完整示例（DiagramGPT） | `examples/diagramgpt.mjs` |
| 完整示例（Mermaid 渲染） | `examples/mermaid-render.mjs` |
