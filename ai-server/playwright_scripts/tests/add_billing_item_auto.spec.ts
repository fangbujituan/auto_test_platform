import { test, expect } from '@playwright/test';

test('add_billing_item_test', async ({ page }) => {
  const timestamp = Date.now();
  const chargeCode = `TEST-AUTO-${timestamp}`;
  const itemName = `Test Billing Item Auto ${timestamp}`;

  // 导航到页面
  await page.goto('https://bnp-test.item.pub/Vue/#/billing/billing-setup/billing-full-set/billing-items/form-data');
  await page.waitForLoadState('networkidle', { timeout: 30000 });
  await page.waitForTimeout(30000);  // 公司网络缓慢，页面加载需要30秒

  // 填写 Charge Code
  await page.getByLabel('*Charge Code').fill(chargeCode);
  
  // 填写 Item Name
  await page.getByLabel('*Item Name').fill(itemName);
  
  // 选择 Status - Active
  await page.locator('.el-form-item').filter({ hasText: '*Status' }).locator('.el-select').click();
  await page.waitForTimeout(3000);
  await page.getByText('Active').first().click();
  await page.waitForTimeout(3000);
  
  // 选择 Billing Category - ACCESSORIAL
  await page.getByLabel('*Billing Category').click();
  await page.waitForTimeout(5000);
  await page.getByText('ACCESSORIAL').click();
  await page.waitForTimeout(3000);
  
  // 选择 Charge Category - Offloading
  await page.getByLabel('*Charge Category').click();
  await page.waitForTimeout(5000);
  await page.getByText('Offloading').click();
  await page.waitForTimeout(3000);
  
  // 选择 Rate Type - Unit Price
  await page.getByLabel('*Rate Type').click();
  await page.waitForTimeout(5000);
  await page.getByText('Unit Price').click();
  await page.waitForTimeout(3000);
  
  // 点击 Save Item 按钮
  await page.getByRole('button', { name: 'Save Item' }).click();
  await page.waitForTimeout(5000);
  
  // 验证保存成功提示
  await expect(page.getByText('Successfully saved!')).toBeVisible({ timeout: 10000 });
  
  // 导航到列表页验证
  await page.goto('https://bnp-test.item.pub/Vue/#/billing/billing-setup/billing-full-set/billing-items');
  await page.waitForLoadState('networkidle', { timeout: 30000 });
  await page.waitForTimeout(30000);
  
  // 验证新增记录存在
  await expect(page.getByText(chargeCode)).toBeVisible({ timeout: 10000 });
  
  console.log('✅ 测试通过：成功新增 Billing Item');
  console.log(`   Charge Code: ${chargeCode}`);
  console.log(`   Item Name: ${itemName}`);
});
