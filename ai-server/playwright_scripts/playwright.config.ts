import { defineConfig, devices } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

/**
 * Playwright 测试配置
 * 由 AI Agent 自动生成
 */

// 从环境变量读取输出路径，支持动态配置
const htmlOutputFolder = process.env.PLAYWRIGHT_HTML_OUTPUT_FOLDER || '../playwright_reports';
const jsonOutputFile = process.env.PLAYWRIGHT_JSON_OUTPUT_FILE || '../playwright_results/result.json';

// 超时配置（从环境变量读取，支持动态调整）
const actionTimeout = parseInt(process.env.PLAYWRIGHT_ACTION_TIMEOUT || '60000', 10);
const navigationTimeout = parseInt(process.env.PLAYWRIGHT_NAVIGATION_TIMEOUT || '120000', 10);

// 认证状态文件路径（从环境变量读取，支持指定不同登录态）
const authStatePath = process.env.PLAYWRIGHT_AUTH_STATE || '';
const authStateFullPath = authStatePath ? path.resolve(__dirname, authStatePath) : '';

// 检查认证状态文件是否存在
const hasAuthState = authStateFullPath && fs.existsSync(authStateFullPath);
if (authStatePath) {
  console.log(`🔐 认证状态文件: ${authStateFullPath}`);
  console.log(`   状态: ${hasAuthState ? '✅ 存在' : '❌ 不存在'}`);
}

export default defineConfig({
  // 测试目录
  testDir: './tests',
  
  // 完全并行运行测试
  fullyParallel: true,
  
  // CI 上失败时禁止 test.only
  forbidOnly: !!process.env.CI,
  
  // CI 上重试失败测试
  retries: process.env.CI ? 2 : 0,
  
  // CI 上限制并行工作线程
  workers: process.env.CI ? 1 : undefined,
  
  // Reporter 配置（从环境变量读取输出路径）
  reporter: [
    ['html', { outputFolder: htmlOutputFolder }],
    ['json', { outputFile: jsonOutputFile }],
    ['list']
  ],
  
  // 全局测试配置
  use: {
    // 基础 URL
    // baseURL: 'http://localhost:3000',
    
    // 视口大小（窗口尺寸）
    viewport: { width: 1920, height: 1080 },
    
    // 加载认证状态（如果指定且存在）
    // 使用已保存的登录态，跳过登录步骤
    storageState: hasAuthState ? authStateFullPath : undefined,
    
    // 收集失败测试的跟踪信息
    trace: 'on-first-retry',
    
    // 截图配置
    screenshot: 'only-on-failure',
    
    // 视频录制
    video: 'retain-on-failure',
    
    // 超时设置（从环境变量读取）
    actionTimeout: actionTimeout,
    navigationTimeout: navigationTimeout,
  },

  // 配置项目（浏览器）
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    // 带认证状态的配置（可选）
    // 如果需要单独运行带登录态的测试，使用 --project=chromium-auth
    ...(hasAuthState ? [{
      name: 'chromium-auth',
      use: { 
        ...devices['Desktop Chrome'],
        storageState: authStateFullPath,
      },
    }] : []),
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },
    // {
    //   name: 'webkit',
    //   use: { ...devices['Desktop Safari'] },
    // },
  ],

  // 运行本地开发服务器
  // webServer: {
  //   command: 'npm run start',
  //   url: 'http://localhost:3000',
  //   reuseExistingServer: !process.env.CI,
  // },
});
