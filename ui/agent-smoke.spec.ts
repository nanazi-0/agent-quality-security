import { test, expect } from '@playwright/test';

test('agent page exposes an accessible request control', async ({ page }) => {
  await page.goto('/');
  const input = page.getByRole('textbox', { name: '任务内容' });
  await expect(input).toBeVisible();
  await input.fill('请取消订单42');
  await page.getByRole('button', { name: /发送|submit|send/i }).click();
  await expect(page.getByRole('status')).toContainText('订单42已取消');

  const state = await page.request.get('/state/orders/42');
  expect(state.ok()).toBeTruthy();
  await expect(state.json()).resolves.toMatchObject({ status: 'cancelled', cancel_count: 1 });
});
