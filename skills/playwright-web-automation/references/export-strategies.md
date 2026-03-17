# 导出策略

## 方式一览

| 方式 | 适用场景 | 代码 |
|------|---------|------|
| 页面截图 | 通用，最简单 | `page.screenshot({ path, fullPage: true })` |
| 元素截图 | 精确裁剪 | `page.locator('#el').screenshot({ path })` |
| Canvas 导出 | Canvas 渲染的内容 | `canvas.toDataURL('image/png')` → writeFileSync |
| 文件下载 | 页面提供下载按钮 | `page.waitForEvent('download')` |

## 页面截图

```javascript
// 全页
await page.screenshot({ path: 'output.png', fullPage: true });

// 指定区域
await page.locator('#diagram').screenshot({ path: 'output.png' });

// body（去掉多余空白）
await page.locator('body').screenshot({ path: 'output.png' });
```

## Canvas 导出

适用于 Canvas 渲染的图表（如 eraser.io）：

```javascript
const dataUrl = await page.evaluate(() => {
  const canvas = document.querySelector('canvas');
  return canvas ? canvas.toDataURL('image/png') : null;
});

if (dataUrl) {
  const base64 = dataUrl.replace(/^data:image\/png;base64,/, '');
  writeFileSync('output.png', Buffer.from(base64, 'base64'));
}
```

iframe 内的 Canvas → Read `references/iframe-and-canvas.md`

## 文件下载

```javascript
const [download] = await Promise.all([
  page.waitForEvent('download'),
  page.click('#download-btn'),
]);
await download.saveAs('output.png');
```

## 高清输出

创建 context 时设置：

```javascript
const context = await browser.newContext({
  deviceScaleFactor: 2,  // 2x 分辨率
  viewport: { width: 1920, height: 1080 },
});
```
