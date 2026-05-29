import { test, expect } from '@playwright/test';

test('add_billing_item', async ({ page }) => {
  // 使用时间戳生成唯一的测试数据
  const timestamp = Date.now();
  const chargeCode = `TEST-AUTO-${timestamp}`;
  const itemName = `Test Billing Item Auto ${timestamp}`;

  // 导航到新增页面
  await page.goto('https://bnp-test.item.pub/Vue/#/billing/billing-setup/billing-full-set/billing-items/form-data');
  await page.waitForLoadState('networkidle', { timeout: 30000 });
  await page.waitForTimeout(30000);

  // 填写 Charge Code
  await page.getByPlaceholder('Enter charge code').fill(chargeCode);
  await page.waitForTimeout(1000);

  // 填写 Item Name
  await page.getByPlaceholder('Enter item name').fill(itemName);
  await page.waitForTimeout(1000);

  // 选择 Status - Active
  await page.evaluate(() => {
    const labels = document.querySelectorAll('.el-form-item__label');
    for (let label of labels) {
      if (label.textContent.includes('Status')) {
        const formItem = label.closest('.el-form-item');
        const selectTrigger = formItem?.querySelector('.el-select');
        if (selectTrigger) {
          selectTrigger.click();
        }
      }
    }
  });
  await page.waitForTimeout(2000);
  
  await page.evaluate(() => {
    const options = document.querySelectorAll('.el-select-dropdown__item');
    for (let option of options) {
      if (option.textContent.trim() === 'Active') {
        option.click();
        break;
      }
    }
  });
  await page.waitForTimeout(2000);

  // 选择 Billing Category - STORAGE INCOME
  await page.locator('.el-form-item').filter({ hasText: 'Billing Category' }).locator('[role="combobox"]').click();
  await page.waitForTimeout(2000);
  await page.locator('.el-select-dropdown__item').filter({ hasText: /^STORAGE INCOME$/ }).click();
  await page.waitForTimeout(2000);

  // 选择 Charge Category - Offloading
  await page.locator('.el-form-item').filter({ hasText: 'Charge Category' }).locator('[role="combobox"]').click();
  await page.waitForTimeout(2000);
  await page.locator('.el-select-dropdown__item').filter({ hasText: /^Offloading$/ }).click();
  await page.waitForTimeout(2000);

  // 选择 Rate Type - Unit Price
  await page.locator('.el-form-item').filter({ hasText: 'Rate Type' }).locator('[role="combobox"]').click();
  await page.waitForTimeout(2000);
  await page.locator('.el-select-dropdown__item').lter({ hasText: /^Unit Price$/ }).click();
  await page.waitForTimeout(2000);

  // 点击 Save Item 按钮
  await page.getByRole('button', { name: 'Save Item' }).click();
  await page.waitForTimeout(5000);

  // 等待保存成功提示
  await expect(page.getByText('Successfully saved!')).toBeVisible({ timeout: 10000 });
  await page.waitForTimeout(3000);

  // 导航到列表页验证
  await page.goto('https://bnp-test.item.pub/Vue/#/billing/billing-setup/billing-full-set/billing-items');
  await page.waitForLoadState('networkidle', { timeout: 30000 });
  await page.waitForTimeout(30000);

  // 搜索刚创建的记录
  await page.getByPlaceholder('Search by ID,code,name,description,or customer').fill(chargeCode);
  await page.getByPlaceholder('Search by ID,code,name,description,or customer').press('Enter');
  await page.waitForTimeout(10000);

  // 验证记录存在
  await expect(page.getByText(chargeCode)).toBeVisible({ timeout: 10000 });
  await expect(page.getByText(itemName)).toBeVisible({ timeout: 10000 });

  console.log(`✅ 测试通过：成功创建 Billing Item - ${chargeCode}`);
});