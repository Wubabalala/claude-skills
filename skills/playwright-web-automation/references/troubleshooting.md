# 常见问题排错

| 问题 | 原因 | 解决 |
|------|------|------|
| `playwright` 命令不存在 | 未安装 | `npm install playwright && npx playwright install chromium` |
| 浏览器启动失败 | Chromium 未下载 | `npx playwright install chromium` |
| iframe 内元素找不到 | 未进入 contentFrame | `page.locator('iframe').contentFrame()` |
| Clipboard API 被禁 | 跨域 iframe Permissions Policy | 改用 `canvas.toDataURL()` 导出 |
| 截图模糊 | 默认 1x DPR | `deviceScaleFactor: 2` |
| 点击无反应 | 元素被遮挡或未加载 | 加 `waitFor()` 或 `{ force: true }` |
| 登录态丢失 | Context 隔离 | `storageState` 保存/加载（见下方） |
| Windows 路径报错 | 反斜杠 | 统一用正斜杠 `/` |
| 页面检测自动化 | `navigator.webdriver` | `launch({ headless: false })` |

## 登录态持久化

```javascript
// 首次登录后保存
await context.storageState({ path: 'auth.json' });

// 后续复用
const context = await browser.newContext({ storageState: 'auth.json' });
```

> 注意：`auth.json` 含 cookie 和 localStorage，不要提交到 git。
