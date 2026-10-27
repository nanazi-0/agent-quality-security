import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('agent page has no automatically detectable WCAG A/AA violations', async ({ page }, testInfo) => {
  await page.goto('/');
  const result = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  await testInfo.attach('axe-results', {
    body: JSON.stringify(result, null, 2),
    contentType: 'application/json',
  });
  expect(result.violations).toEqual([]);
});
