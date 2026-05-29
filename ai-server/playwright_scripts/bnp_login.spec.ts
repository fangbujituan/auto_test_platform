import { test, expect } from '@playwright/test';

/* BNP系统登录脚本，使用用户名xinghua.ning和密码Test@123进行登录 */

test('bnp_login', async ({ page }) => {
  await page.goto('https://bnp-test.item.pub/');
  await page.locator('input[type="text"], input[type="email"]').first().fill('xinghua.ning');  // 
  await page.locator('input[type="password"]').fill('Test@123');  // 
  await page.getByRole('button', { name: 'Sign in' }).click();  // Sign in 按钮
  // 等待页面跳转完成
  await page.waitForFunction(() => window.location.href.includes('Home.html'));
  
  // 等待 3 秒让用户看到结果
  await page.waitForTimeout(3000);
  
  // 验证登录成功
  console.log('✅ 登录成功！当前 URL:', page.url());
});