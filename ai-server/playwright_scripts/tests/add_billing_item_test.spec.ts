import { test, expect } from '@playwright/test';

/* 自动化测试：增加Billing Items，填写必填项并保存 */

test('add_billing_item_test', async ({ page }) => {
  await page.goto('https://bnp-test.item.pub/Vue/#/billing/billing-setup/billing-full-set/billing-items/form-data');
  await page.waitForLoadState('networkidle');
  await expect(page).toHaveURL(//Vue/);
  await page.waitForTimeout(30000);
  // ⚠️ TODO: 需要手动确认选择器 - 元素描述: 
  await page.getByRole('textbox').filter({ hasText: /.*/ }).first().fill('TEST-AUTO-1743071150316');  // 
  // ⚠️ TODO: 需要手动确认选择器 - 元素描述: 
  await page.getByRole('textbox').filter({ hasText: /.*/ }).first().fill('Test Billing Item Auto 1743071150316');  // 
  // 获取页面快照
  await page.locator('.el-form-item').filter({ hasText: '*Status' }).locator('[cursor=pointer], .el-select, [role="combobox"]').first().click();  // Status下拉框
  await page.getByText('Active选项', { exact: true }).click();  // Active选项
  // 获取页面快照
  await page.locator('.el-form-item').filter({ hasText: '*Status' }).locator('[cursor=pointer], .el-select, [role="combobox"]').first().click();  // Status下拉框
  await page.getByText('Active选项', { exact: true }).click();  // Active选项
  // 获取页面快照
  // 查找包含特定文本的元素
  // 获取页面快照
  // 查找包含特定文本的元素
  await page.getByText('Status字段的图标', { exact: true }).click();  // Status字段的图标
  await page.getByText('Active选项', { exact: true }).click();  // Active选项
  // 查找包含特定文本的元素
  // 获取页面快照
  await page.getByRole('option', { name: 'Inactive' }).click();  // Active选项
  // 获取页面快照
  await page.getByText('*Billing Category', { exact: true }).click();  // Billing Category下拉框
  await page.getByText('ACCESSORIAL选项', { exact: true }).click();  // ACCESSORIAL选项
  // 获取页面快照
  await page.getByText('*Charge Category', { exact: true }).click();  // Charge Category下拉框
  await page.getByText('Offloading选项', { exact: true }).click();  // Offloading选项
  // 获取页面快照
  await page.getByText('*Rate Type', { exact: true }).click();  // Rate Type下拉框
  await page.getByText('Unit Price选项', { exact: true }).click();  // Unit Price选项
  await page.getByRole('button', { name: 'Save Item' }).click();  // Save Item按钮
  await page.waitForLoadState('networkidle');  // 等待提交完成
  // 断言：验证操作结果
  await expect(page.getByText(/成功|success|saved|completed/i)).toBeVisible({ timeout: 10000 });
  await page.waitForTimeout(3000);
  // 获取页面快照
  await page.goto('https://bnp-test.item.pub/Vue/#/billing/billing-setup/billing-full-set/billing-items');
  await page.waitForLoadState('networkidle');
  await expect(page).toHaveURL(//Vue/);
  await page.waitForTimeout(30000);
});