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
  console.log(`✅ 已填写 Charge Code: ${chargeCode}`);
  
  // 填写 Item Name
  await page.locator('input[placeholder="Enter item name"]').fill(itemName);
  console.log(`✅ 已填写 Item Name: ${itemName}`);
  
  // 选择 Status - 使用 JavaScript 直接设置
  await page.evaluate(() => {
    const formItems = [...document.querySelectorAll('.el-form-item')];
    for (let item of formItems) {
      const label = item.querySelector('.el-form-item__label');
      if (label && label.textContent.includes('Status')) {
        const input = item.querySelector('input');
        if (input) {
          input.value = 'Active';
          input.dispatchEvent(new Event('input', { bubbles: true }));
          input.dispatchEvent(new Event('change', { bubbles: true }));
          return;
        }
      }
    }
  });
  console.log('✅ 已设置 Status: Active');
  await page.waitForTimeout(2000);
  
  // 选择 Billing Category - ACCESSORIAL
  await page.locator('.el-form-item').filter({ hasText: 'Billing Category' }).locator('input').click();
  await page.waitForTimeout(5000);
  await page.locator('.el-select-dropdown__item').getByText('ACCESSORIAL').click();
  console.log('✅ 已选择 Billing Category: ACCESSORIAL');
  await page.waitForTimeout(3000);
  
  // 选择 Charge Category - Offloading
  await page.locator('.el-form-item').filter({ hasText: 'Charge Category' }).locator('input').click();
  await page.waitForTimeout(5000);
  await page.locator('.el-select-dropdown__item').getByText('Offloading').click();
  console.log('✅ 已选择 Charge Category: Offloading');
  await page.waitForTimeout(3000);
  
  // 选择 Rate Type - Unit Price
  await page.locator('.el-form-item').filter({ hasText: 'Rate Type' }).locator('input').click();
  await page.waitForTimeout(5000);
  await page.locator('.el-select-dropdown__item').getByText('Unit Price').click();
  console.log('✅ 已选择 Rate Type: Unit Price');
  await page.waitForTimeout(3000);
  
  // 点击 Save Item 按钮
  await page.getByRole('button', { name: 'Save Item' }).click();
  console.log('✅ 已点击 Save Item 按钮');
  await page.waitForTimeout(5000);
  
  // 验证保存成功提示
  await expect(page.getByText('Successfully saved!')).toBeVisible({ timeout: 10000 });
  console.log('✅ 保存成功提示已显示');
  
  // 导航到列表页验证
  await page.goto('https://b-test.item.pub/Vue/#/billing/billing-setup/billing-full-set/billing-items');
  await page.waitForLoadState('networkidle', { timeout: 60000 });
  await page.waitForTimeout(30000);
  
  // 验证新增记录存在
  await expect(page.getByText(chargeCode)).toBeVisible({ timeout: 10000 });
  
  console.log('✅ 测试通过：成功新增 Billing Item');
  console.log(`   Charge Code: ${chargeCode}`);
  console.log(`   Item Name: ${itemName}`);
});
