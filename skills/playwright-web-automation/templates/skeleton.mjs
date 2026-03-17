/**
 * Playwright Automation Skeleton
 * Usage: node skeleton.mjs
 *
 * 两种使用方式：
 * A) 录制式: npx playwright codegen <URL> → 粘贴到操作区域 → 参数化
 * B) 直接编写: 在操作区域写代码，或用 setContent 加载 HTML
 */

import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
import { resolve } from 'path';
import { writeFileSync } from 'fs';

// ============================================
// 配置区 — 修改这里
// ============================================
const TARGET_URL = 'https://example.com';  // 路径 B 渲染模式可留空，用 setContent
const OUTPUT_PATH = resolve('output.png');
const HEADLESS = true;                     // true: 后台运行（渲染/批量）; false: 调试/录制
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

// ============================================
// 主流程
// ============================================
(async () => {
  const browser = await chromium.launch({ headless: HEADLESS });
  const context = await browser.newContext({
    deviceScaleFactor: 2,
    viewport: { width: 1920, height: 1080 },
  });
  const page = await context.newPage();

  try {
    // ============================================
    // 路径 A: 打开 URL
    // ============================================
    // await page.goto(TARGET_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
    // await sleep(2000);

    // ============================================
    // 路径 B: 直接加载 HTML（渲染图表等）
    // ============================================
    // const html = `<!DOCTYPE html><html>...</html>`;
    // await page.setContent(html, { waitUntil: 'networkidle', timeout: 30000 });
    // await page.waitForSelector('svg', { timeout: 15000 });

    // ============================================
    // 操作区域 — 粘贴录制代码 或 直接编写
    // ============================================

    // ============================================
    // 导出区域 — 选择导出方式
    // ============================================

    // 截图（最常用）
    // await page.locator('body').screenshot({ path: OUTPUT_PATH });

    // 元素截图
    // await page.locator('#diagram').screenshot({ path: OUTPUT_PATH });

    // Canvas 导出
    // const dataUrl = await page.evaluate(() => {
    //   return document.querySelector('canvas')?.toDataURL('image/png');
    // });
    // if (dataUrl) {
    //   const base64 = dataUrl.replace(/^data:image\/png;base64,/, '');
    //   writeFileSync(OUTPUT_PATH, Buffer.from(base64, 'base64'));
    // }

    // 文件下载
    // const [download] = await Promise.all([
    //   page.waitForEvent('download'),
    //   page.click('#download-btn'),
    // ]);
    // await download.saveAs(OUTPUT_PATH);

    console.log('Done!');
  } finally {
    await browser.close();
  }
})();
