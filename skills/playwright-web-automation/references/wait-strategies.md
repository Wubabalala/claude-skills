# 等待策略速查

| 场景 | 方法 | 示例 |
|------|------|------|
| 页面加载完 | `waitUntil` | `goto(url, { waitUntil: 'networkidle' })` |
| 元素出现 | `waitFor` | `locator('#el').waitFor({ timeout: 30000 })` |
| 元素消失 | `waitFor detached` | `locator('#splash').waitFor({ state: 'detached' })` |
| 文本出现 | `getByText` + `waitFor` | `frame.getByText('Complete').waitFor()` |
| 网络请求完成 | `waitForResponse` | `page.waitForResponse(r => r.url().includes('/api'))` |
| 下载完成 | `waitForEvent` | `page.waitForEvent('download')` |
| 固定延时（最后手段） | `sleep` | `await new Promise(r => setTimeout(r, 2000))` |

## 原则

1. **优先用条件等待**（waitFor/waitForResponse），不用固定 sleep
2. 固定 sleep 只用于"两步操作之间留缓冲"，通常 2000ms 够用
3. iframe 内等待用 `frame.locator(...).waitFor()`，不是 `page.waitFor`
4. 轮询模式：`for` 循环 + `isVisible({ timeout: 1000 }).catch(() => false)`
