# iframe 操作 + Canvas 导出

## iframe 进入

```javascript
// FrameLocator 方式（推荐，配合 getByRole 等）
const frame = page.locator('iframe[src*="app.target.com"]').contentFrame();
await frame.getByRole('textbox', { name: 'Input' }).fill('content');

// Frame 方式（需要 evaluate 时）
const iframeEl = await page.$('iframe');
const realFrame = await iframeEl.contentFrame();
const data = await realFrame.evaluate(() => document.title);
```

嵌套 iframe：`page.locator('iframe').contentFrame().locator('iframe').contentFrame()`

## Canvas 导出（替代 Clipboard）

跨域 iframe 的 Clipboard API 会被 Permissions Policy 阻止。直接从 Canvas 导出：

```javascript
const iframeEl = await page.$('iframe');
const realFrame = await iframeEl.contentFrame();

const dataUrl = await realFrame.evaluate(() => {
  const canvas = document.querySelector('canvas');
  return canvas ? canvas.toDataURL('image/png') : null;
});

if (dataUrl) {
  const base64 = dataUrl.replace(/^data:image\/png;base64,/, '');
  writeFileSync('output.png', Buffer.from(base64, 'base64'));
}
```

## 权限授权

```javascript
const context = await browser.newContext();
// 必须指定 origin，不能省略
await context.grantPermissions(['clipboard-read', 'clipboard-write'], {
  origin: 'https://app.target.com'
});
```

> 注意：`grantPermissions` 无法覆盖 iframe 的 Permissions Policy。跨域 iframe 内的 Clipboard 仍会被禁。

## 高分辨率截图

```javascript
const context = await browser.newContext({
  deviceScaleFactor: 2,  // 2x 分辨率
  viewport: { width: 1920, height: 1080 }
});
```

## 自适应表单填写

页面有动态追问时，轮询处理：

```javascript
for (let round = 0; round < 10; round++) {
  // 优先找最终提交按钮
  const submit = frame.getByRole('button', { name: /Submit|Generate/i });
  if (await submit.isVisible({ timeout: 1000 }).catch(() => false)) {
    await submit.click();
    break;
  }
  // 单选
  const radio = frame.getByRole('radio').first();
  if (await radio.isVisible({ timeout: 500 }).catch(() => false)) {
    await radio.click(); await sleep(2000); continue;
  }
  // 复选（选前3个）
  const cbs = frame.getByRole('checkbox');
  if (await cbs.count() > 0) {
    for (let i = 0; i < Math.min(3, await cbs.count()); i++)
      await cbs.nth(i).check();
    await sleep(2000); continue;
  }
  // 文本输入
  const input = frame.getByPlaceholder(/enter|response/i);
  if (await input.isVisible({ timeout: 500 }).catch(() => false)) {
    await input.fill('No special requirements'); await sleep(2000); continue;
  }
  await sleep(3000);
}
```
