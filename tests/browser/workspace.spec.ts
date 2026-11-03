import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  // Browser tests must never spend model credits.
  await page.route('**/api/status', route => route.fulfill({ json: { ai_available: false, message: '实时 AI 测试中关闭，案例可正常体验。' } }));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: '让每个产品需求，都有用户证据。' })).toBeVisible();
});

test('case navigation, feedback correction, undo, and session restore', async ({ page }) => {
  await page.getByRole('button', { name: '查看问题与证据' }).click();
  await expect(page.getByText('正在查看需求：')).toBeVisible();
  await page.getByRole('button', { name: '校准分类与关联' }).click();
  await page.getByRole('textbox', { name: '校准理由' }).fill('核验后确认该反馈属于功能建议。');
  await page.getByRole('button', { name: '保存校准' }).click();
  await expect(page.getByRole('button', { name: '已确认', exact: true })).toBeDisabled();
  await page.reload();
  await expect(page.getByRole('button', { name: '反馈分析', exact: false }).first()).toBeVisible();
  const data = await page.evaluate(() => JSON.parse(sessionStorage.getItem('feedback-lens-workspace-v1')!));
  expect(data.feedback.some((item: { reviewed: boolean; reason: string }) => item.reviewed && item.reason.includes('核验后确认'))).toBeTruthy();
});

test('RICE recalculates, undo restores, merge retains evidence', async ({ page }) => {
  await page.getByRole('button', { name: '需求决策', exact: false }).first().click();
  await page.getByRole('button', { name: '校准评分' }).click();
  await page.getByRole('spinbutton', { name: 'Effort · 成本人周' }).fill('0.5');
  await page.getByRole('textbox', { name: 'RICE 调整依据' }).fill('缩小方案到引用与失效提示，降低开发成本。');
  await page.getByRole('button', { name: '应用评分并重新排序' }).click();
  const changed = await page.evaluate(() => JSON.parse(sessionStorage.getItem('feedback-lens-workspace-v1')!));
  expect(changed.needs.some((need: { effort: number }) => need.effort === 0.5)).toBeTruthy();
  await page.getByRole('button', { name: '撤销上次修改' }).click();
  const undone = await page.evaluate(() => JSON.parse(sessionStorage.getItem('feedback-lens-workspace-v1')!));
  expect(undone.needs.some((need: { effort: number }) => need.effort === 0.5)).toBeFalsy();
  await page.getByRole('button', { name: '对比与合并' }).click();
  await page.getByRole('textbox', { name: '合并理由' }).fill('用于验证合并时证据完整保留。');
  await page.getByRole('button', { name: '确认合并' }).click();
  const merged = await page.evaluate(() => JSON.parse(sessionStorage.getItem('feedback-lens-workspace-v1')!));
  expect(merged.feedback.length).toBe(65); expect(merged.needs.length).toBe(7);
  expect(merged.needs.reduce((count: number, need: { feedback_ids: string[] }) => count + need.feedback_ids.length, 0)).toBe(65);
  await page.getByRole('button', { name: '撤销上次修改' }).click();
  const restored = await page.evaluate(() => JSON.parse(sessionStorage.getItem('feedback-lens-workspace-v1')!));
  expect(restored.needs.length).toBe(8);
});

test('PRD editing persists, preview cancels safely, citations and Markdown download work', async ({ page }) => {
  await page.getByRole('button', { name: 'PRD 工作台', exact: false }).first().click();
  await expect(page.getByText('模板草稿', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '编辑', exact: true }).click();
  const editor = page.getByRole('textbox', { name: 'PRD Markdown 编辑器' });
  const original = await editor.inputValue();
  await editor.fill(original + '\n\n人工补充：核对来源是否支持结论。');
  await page.getByRole('button', { name: '完成编辑' }).click();
  await page.getByRole('button', { name: '按当前证据更新模板' }).click();
  await page.getByRole('button', { name: '保留原文' }).click();
  await expect(page.getByText('人工补充：核对来源是否支持结论。', { exact: true })).toBeVisible();
  await page.locator('.document-content .citation').first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button', { name: '关闭', exact: true }).click();
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载 Markdown' }).click();
  expect((await downloaded).suggestedFilename()).toMatch(/\.md$/);
  await page.reload();
  await expect(page.getByText('人工补充：核对来源是否支持结论。', { exact: true })).toBeVisible();
});

test('real CSV import and Excel download use the Python API', async ({ page }) => {
  await page.getByRole('button', { name: '分析我的反馈' }).click();
  await page.getByRole('button', { name: '粘贴反馈', exact: true }).click();
  await page.getByRole('textbox', { name: '粘贴反馈文本' }).fill('希望回答给出可核验的来源。\n导出文件后的格式乱了。\n希望回答给出可核验的来源。');
  await page.getByRole('button', { name: '预览导入与分析' }).click();
  await expect(page.getByText('已完成规则预分析')).toBeVisible();
  await page.getByRole('button', { name: '应用导入结果' }).click();
  const imported = await page.evaluate(() => JSON.parse(sessionStorage.getItem('feedback-lens-workspace-v1')!));
  expect(imported.feedback.length).toBe(2); expect(imported.cleaning.duplicates).toBe(1);
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', { name: '导出 Excel' }).click();
  expect((await downloaded).suggestedFilename()).toMatch(/\.xlsx$/);
});

test('rejecting an association creates an independent need and can be undone', async ({ page }) => {
  await page.getByRole('button', { name: '查看问题与证据' }).click();
  await page.getByRole('button', { name: '不接受当前关联建议' }).click();
  await page.getByRole('textbox', { name: '独立需求标题' }).fill('事实核验入口的独立评估');
  await page.getByRole('textbox', { name: '校准理由' }).fill('该诉求需要独立确认，与原聚合需求的范围不同。');
  await page.getByRole('button', { name: '保存校准' }).click();
  const split = await page.evaluate(() => JSON.parse(sessionStorage.getItem('feedback-lens-workspace-v1')!));
  expect(split.needs.length).toBe(9); expect(split.feedback.length).toBe(65);
  const created = split.needs.find((need: { title: string }) => need.title === '事实核验入口的独立评估');
  expect(created.feedback_ids.length).toBe(1);
  await page.getByRole('button', { name: '撤销上次修改' }).click();
  const restored = await page.evaluate(() => JSON.parse(sessionStorage.getItem('feedback-lens-workspace-v1')!));
  expect(restored.needs.length).toBe(8);
});

test('model failure preserves manual PRD edits and offers template generation', async ({ page }) => {
  await page.route('**/api/status', route => route.fulfill({ json: { ai_available: true, message: 'Mock model for browser test' } }));
  await page.route('**/api/prd', route => route.fulfill({ status: 502, json: { detail: '模型服务暂不可用，当前文档已保留。' } }));
  await page.reload();
  await page.getByRole('button', { name: 'PRD 工作台', exact: false }).first().click();
  await page.getByRole('button', { name: '编辑', exact: true }).click();
  const editor = page.getByRole('textbox', { name: 'PRD Markdown 编辑器' });
  await editor.fill((await editor.inputValue()) + '\n\n模型失败也需要保留的人工意见。');
  await page.getByRole('button', { name: '完成编辑' }).click();
  await page.getByRole('button', { name: 'AI 生成完整 PRD', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('当前文档已保留');
  await expect(page.getByText('模型失败也需要保留的人工意见。', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '按当前证据更新模板' })).toBeEnabled();
});

test('desktop and mobile layouts have no horizontal overflow or console errors', async ({ page }) => {
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  await page.screenshot({ path: 'output/web/overview-desktop.png', fullPage: true });
  for (const width of [1440, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    for (const destination of ['overview', 'feedback', 'needs', 'prd', 'about']) {
      await page.goto('/#' + destination);
      await expect(page.locator('main')).toBeVisible();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
      expect(overflow, `${destination} overflows at ${width}px`).toBeFalsy();
      if (width === 1440) await page.screenshot({ path: `output/web/${destination}-desktop.png`, fullPage: true });
    }
  }
  await page.goto('/'); await page.screenshot({ path: 'output/web/overview-mobile.png', fullPage: true });
  expect(errors).toEqual([]);
});
