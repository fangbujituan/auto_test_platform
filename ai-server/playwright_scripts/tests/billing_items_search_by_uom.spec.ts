import { test, expect } from '@playwright/test';

/* 在 Billing Items 页面通过 UOM 筛选条件（选择 Box）进行查询 */

test('billing_items_search_by_uom', async ({ page }) => {
  await page.goto('https://bnp-test.item.pub/vue/#/billing/billing-setup/billing-full-set/billing-items');
  await page.waitForLoadState('networkidle');
  await expect(page).toHaveURL(//vue/);
  await page.waitForTimeout(30000);
  // 获取页面快照
  await page.getByText('UOM', { exact: true }).click();  // UOM下拉框
  await page.getByText('Box选项', { exact: true }).click();  // Box选项
  // 获取页面快照
  await page.getByRole('button', { name: 'Search' }).click();  // Search按钮
});