/**
 * DiagramGPT Architecture Diagram Generator
 * 完整示例：自动化 eraser.io/diagramgpt 生成架构图
 *
 * 工作流对应关系：
 *   Step 1 (codegen) → 已完成，录制代码见下方选择器
 *   Step 2 (分析)   → iframe 嵌套，追问式表单，canvas 渲染
 *   Step 3 (参数化) → PROMPT 和 OUTPUT 提取为常量
 *   Step 4 (导出)   → canvas.toDataURL (Clipboard API 跨域被禁)
 *
 * Usage: node diagramgpt.mjs
 */

import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
import { resolve } from 'path';
import { writeFileSync } from 'fs';

// ============================================
// 配置区
// ============================================
const PROMPT = `A board game engine (Shaman: Taiga) with 4 layers:

DATA LAYER:
- cards.js (98 card definitions)
- rules.js (constants, income tables)

ENGINE LAYER:
- GameFlow: main controller, action execution, phase management
- EffectResolver: processes effects (affinity, lv_up, activate_totem)
- EffectChain: generator coroutine driver (yield/resume for player choices)
- PathfinderEffectSystem: 33 pathfinder card effects
- PossessionEffectSystem: 29 possession card effects, passive listeners
- CardByCardResolver: card-by-card picking (explore/draft)
- ScoringEngine: end-game scoring
- GameState: state container with serialization
- TotemRing, EssenceSystem, SeededRNG, ActionLog

ACTION HANDLERS (called by GameFlow):
- ExploreAction, HuntAction, TravelAction, EncounterAction, ReturnToTreeAction
- TerrainEntry: terrain entry effects

UI LAYER:
- main.js, ActionUI, PhaseController, ModalManager
- boardRenderer, cardRenderer, logPanel

CORE PATTERN (generator choice loop):
EffectChain yields needsChoice -> PhaseController -> ModalManager -> player chooses -> submitEffectChoice -> EffectChain resumes`;

const OUTPUT = resolve('output-architecture.png');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

// ============================================
// 主流程
// ============================================
(async () => {
  // --- Step 3: 参数化后的脚本 ---

  console.log('1. Launching browser...');
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    deviceScaleFactor: 2,             // 高分辨率
    viewport: { width: 1920, height: 1080 },
  });
  const page = await context.newPage();

  try {
    console.log('2. Opening DiagramGPT...');
    await page.goto('https://www.eraser.io/diagramgpt', {
      waitUntil: 'domcontentloaded', timeout: 60000,
    });

    // --- 关键：进入 iframe (Step 2 分析得出) ---
    const frame = page.locator('iframe').contentFrame();
    console.log('3. Waiting for iframe content...');
    await frame.getByRole('textbox', { name: 'Describe your diagram using' })
      .waitFor({ timeout: 60000 });
    await sleep(2000);

    // --- 操作区域 (来自 codegen 录制) ---
    console.log('4. Filling prompt...');
    await frame.getByRole('textbox', { name: 'Describe your diagram using' }).click();
    await sleep(2000);
    await frame.getByRole('textbox', { name: 'Describe your diagram using' }).fill(PROMPT);
    await sleep(2000);

    console.log('5. Clicking Generate...');
    await frame.getByRole('button', { name: 'Generate Ctrl ↩' }).click();
    await sleep(5000);

    // --- 自适应追问处理 (eraser.io 会问 2-4 个问题) ---
    console.log('6. Handling follow-up questions...');
    for (let round = 0; round < 8; round++) {
      // 优先找最终生成按钮
      const finalBtn = frame.getByRole('button', { name: 'Generate Diagram Ctrl ↩' });
      if (await finalBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
        console.log('   Found Generate Diagram!');
        await sleep(2000);
        await finalBtn.click();
        break;
      }
      // 单选
      const radio = frame.getByRole('radio').first();
      if (await radio.isVisible({ timeout: 500 }).catch(() => false)) {
        await radio.click(); await sleep(2000); continue;
      }
      // 复选（选前3个）
      const cbs = frame.getByRole('checkbox');
      const cbCount = await cbs.count();
      if (cbCount > 0) {
        for (let j = 0; j < Math.min(3, cbCount); j++) {
          const cb = cbs.nth(j);
          if (await cb.isVisible({ timeout: 500 }).catch(() => false)) await cb.check();
          await sleep(500);
        }
        await sleep(2000); continue;
      }
      // 文本输入
      const input = frame.getByPlaceholder('Enter your response...').first();
      if (await input.isVisible({ timeout: 500 }).catch(() => false)) {
        const val = await input.inputValue();
        if (!val) { await input.fill('No special requirements'); await sleep(1000); }
        await sleep(2000); continue;
      }
      await sleep(3000);
    }

    // --- 等待渲染完成 ---
    console.log('7. Waiting for diagram...');
    for (let i = 0; i < 45; i++) {
      const complete = frame.getByText('Complete', { exact: true });
      if (await complete.isVisible({ timeout: 1000 }).catch(() => false)) {
        console.log('   Complete!');
        await sleep(5000);
        break;
      }
      await sleep(2000);
    }

    // --- Step 4: Canvas 导出 (Clipboard 跨域被禁，改用 toDataURL) ---
    console.log('8. Exporting canvas...');
    const iframeEl = await page.$('iframe');
    const realFrame = await iframeEl.contentFrame();

    const imageData = await realFrame.evaluate(() => {
      const canvas = document.querySelector('canvas');
      if (canvas) return { ok: true, data: canvas.toDataURL('image/png') };
      return { ok: false, canvases: document.querySelectorAll('canvas').length };
    });

    if (imageData.ok) {
      const base64 = imageData.data.replace(/^data:image\/png;base64,/, '');
      writeFileSync(OUTPUT, Buffer.from(base64, 'base64'));
      console.log(`   Saved to ${OUTPUT}`);
    } else {
      console.log('   Canvas not found, taking screenshot fallback...');
      await page.locator('iframe').screenshot({ path: OUTPUT });
    }

    console.log('Done!');
  } finally {
    await browser.close();
  }
})();
