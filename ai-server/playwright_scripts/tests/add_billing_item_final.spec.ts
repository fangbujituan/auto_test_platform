import { test, expect } from '@playwright/test';

test('add_billing_item_test', async ({ page }) => {
  // 设置更长的超时时间
  test.setTimeout(180000);  // 3分钟超时
  
  const timestamp = Date.now();
  const chargeCode = `TEST-AUTO-${timestamp}`;
  const itemName = `Test Billing Item Auto ${timestamp}`;

  // 导航到页面
  await page.goto('https://bnp-test.item.pub/Vue/#/billing/billing-setup/billing-full-set/billing-items/form-data');
  await page.waitForLoadState('networkidle', { timeout: 60000 });
  await page.waitForTimeout(30000);  // 公司网络缓慢，页面加载需要30秒

  // 等待表单加载完成
  await page.waitForSelector('input[placeholder="Enter charge code"]', { timeout: 30000 });
  
  // 填写 Charge Code
  await page.locator('input[placeholder="Enter charge code"]').fill(chargeCode);
  
  // 填写 Item Name
  await page.locator('input[placeholder="Enter item name"]').fill(itemName);
  
  // 选择 Status - Active
  const statusFormItem = page.locator('.el-form-item').filter({ hasText: '*Status' });
  await statusFormItem.locator('.el-select').click();
  await page.waitForTimeout(3000);
  await page.locator('.el-select-dropdown__item').filter({ hasText: 'Active' }).first().click();
  await page.waitForTimeout(3000);
  
  // 选择 Billing Category - ACCESSORIAL
  const billingCategorySelect = page.locator('.el-form-item').filter({ hasText: '*Billing Category' }).locator('.el-select');
  await billingCategorySelect.click();
  await page.waitForTimeout(5000);
  await page.locator('.el-select-dropdown__item').filter({ hasText: 'ACCESSORIAL' }).click();
  await page.waitForTimeout(3000);
  
  // 选择 Charge Category - Offloading
  const chargeCategorySelect = page.locator('.el-form-item').filter({ hasText: '*Charge Category' }).locator('.el-select');
  await chargeCategorySelect.click();
  await page.waitForTimeout(5000);
  await page.locator('.el-select-dropdown__item').filter({ hasText: 'Offloading' }).click();
  await page.waitForTimeout(3000);
  
  // 选择 Rate Type - Unit Price
  const rateTypeSelect = page.locator('.el-form-item').filter({ hasText: '*Rate Type' }).locator('.el-select');
  await rateTypeSelect.click();
  await page.waitForTimeout(5000);
  await page.locator('.el-select-dropdown__item').filter({ hasText: 'Unit Price' }).click();
  await page.waitForTimeout(3000);
  
  // 点击 Save Item 按钮
  await page.getByRole('bue: 'Save Item' }).click();
  await page.waitForTimeout(5000);
  
  // 验证保存成功提示
  await expect(page.getByText('Successfully saved!')).toBeVisible({ timeout: 10000 });
  console.log('✅ 保存成功提示已显示');
  
  // 导航到列表页验证
  await page.goto('https://bnp-test.item.pub/Vue/#/billing/billing-setup/billing-full-set/billing-items');
  await page.waitForLoadState('networkidle', { timeout: 60000 });
  await page.waitForTimeout(30000);
  
  // 验证新增记录存在
  await expect(page.getByText(chargeCode)).toBeVisible({ timeout: 10000 });
  
  console.log('✅ 测试通过：成功新增 Billing Item');
  console.log(`   Charge Code: ${chargeCode}`);
  console.log(`   Item Name: ${itemName}`);
});
