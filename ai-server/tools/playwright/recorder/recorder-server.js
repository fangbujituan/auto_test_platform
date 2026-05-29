/**
 * Playwright Codegen Recorder Server
 * 
 * 提供 WebSocket 接口，让 Python 可以：
 * 1. 启动带录制功能的浏览器
 * 2. 执行操作并自动录制
 * 3. 获取生成的代码
 * 
 * 使用 Playwright 内部 API: context._enableRecorder()
 */

import { chromium } from 'playwright';
import { WebSocketServer } from 'ws';
import fs from 'fs';
import path from 'path';

class RecorderServer {
  constructor(port = 9223) {
    this.port = port;
    this.browser = null;
    this.context = null;
    this.page = null;
    this.recordedActions = [];
    this.outputFile = null;
    this.wss = null;
  }

  /**
   * 启动 WebSocket 服务器
   */
  async start() {
    this.wss = new WebSocketServer({ port: this.port });
    
    this.wss.on('connection', (ws) => {
      console.log(`[RecorderServer] Client connected`);
      
      ws.on('message', async (data) => {
        try {
          const message = JSON.parse(data.toString());
          const response = await this.handleMessage(message);
          ws.send(JSON.stringify(response));
        } catch (error) {
          ws.send(JSON.stringify({ 
            success: false, 
            error: error.message 
          }));
        }
      });
      
      ws.on('close', () => {
        console.log(`[RecorderServer] Client disconnected`);
      });
    });
    
    console.log(`[RecorderServer] Listening on ws://localhost:${this.port}`);
  }

  /**
   * 处理客户端消息
   */
  async handleMessage(message) {
    const { action, params } = message;
    
    switch (action) {
      case 'start':
        return await this.startRecording(params);
      
      case 'navigate':
        return await this.navigate(params.url);
      
      case 'click':
        return await this.click(params.selector, params.coordinates);
      
      case 'fill':
        return await this.fill(params.selector, params.value);
      
      case 'select':
        return await this.select(params.selector, params.value);
      
      case 'hover':
        return await this.hover(params.selector);
      
      case 'press':
        return await this.press(params.key);
      
      case 'waitForSelector':
        return await this.waitForSelector(params.selector);
      
      case 'waitForTimeout':
        return await this.waitForTimeout(params.timeout);
      
      case 'screenshot':
        return await this.screenshot(params.path);
      
      case 'getRecordedCode':
        return await this.getRecordedCode();
      
      case 'getCodegenCode':
        return await this.getCodegenCode();
      
      case 'stop':
        return await this.stopRecording();
      
      case 'getStatus':
        return this.getStatus();
      
      default:
        return { success: false, error: `Unknown action: ${action}` };
    }
  }

  /**
   * 启动带录制功能的浏览器
   */
  async startRecording(params = {}) {
    const {
      url = 'about:blank',
      headless = false,
      viewport = { width: 1920, height: 1080 },
      storageState = null,
      outputFile = null
    } = params;

    try {
      // 启动浏览器
      this.browser = await chromium.launch({ 
        headless,
        args: ['--start-maximized']
      });
      
      // 创建上下文
      const contextOptions = {
        viewport,
        ignoreHTTPErrors: true
      };
      
      // 加载登录态
      if (storageState && fs.existsSync(storageState)) {
        contextOptions.storageState = storageState;
        console.log(`[RecorderServer] Loading storage state: ${storageState}`);
      }
      
      this.context = await this.browser.newContext(contextOptions);
      
      // 🔥 核心：启用录制器
      // 使用 Playwright 内部 API
      this.outputFile = outputFile;
      
      await this.context._enableRecorder({
        mode: 'recording',
        language: 'playwright-test',
        outputFile: outputFile
      });
      
      console.log('[RecorderServer] ✅ Recorder enabled');
      
      // 创建页面
      this.page = await this.context.newPage();
      
      // 导航到 URL
      if (url !== 'about:blank') {
        await this.page.goto(url, { waitUntil: 'networkidle' });
      }
      
      this.recordedActions = [];
      
      return {
        success: true,
        message: 'Recording session started',
        viewport
      };
      
    } catch (error) {
      return {
        success: false,
        error: `Failed to start recording: ${error.message}`
      };
    }
  }

  /**
   * 导航到 URL
   */
  async navigate(url) {
    if (!this.page) {
      return { success: false, error: 'No active page' };
    }
    
    try {
      await this.page.goto(url, { waitUntil: 'networkidle' });
      this.recordedActions.push({
        type: 'navigate',
        url,
        timestamp: Date.now()
      });
      
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * 点击元素
   * 支持选择器或坐标点击
   */
  async click(selector, coordinates) {
    if (!this.page) {
      return { success: false, error: 'No active page' };
    }
    
    try {
      if (coordinates) {
        // 坐标点击
        await this.page.mouse.click(coordinates.x, coordinates.y);
        this.recordedActions.push({
          type: 'click',
          coordinates,
          timestamp: Date.now()
        });
      } else if (selector) {
        // 选择器点击
        await this.page.locator(selector).click();
        this.recordedActions.push({
          type: 'click',
          selector,
          timestamp: Date.now()
        });
      }
      
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * 填充输入框
   */
  async fill(selector, value) {
    if (!this.page) {
      return { success: false, error: 'No active page' };
    }
    
    try {
      await this.page.locator(selector).fill(value);
      this.recordedActions.push({
        type: 'fill',
        selector,
        value,
        timestamp: Date.now()
      });
      
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * 下拉选择
   */
  async select(selector, value) {
    if (!this.page) {
      return { success: false, error: 'No active page' };
    }
    
    try {
      await this.page.locator(selector).selectOption(value);
      this.recordedActions.push({
        type: 'select',
        selector,
        value,
        timestamp: Date.now()
      });
      
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * 悬停
   */
  async hover(selector) {
    if (!this.page) {
      return { success: false, error: 'No active page' };
    }
    
    try {
      await this.page.locator(selector).hover();
      this.recordedActions.push({
        type: 'hover',
        selector,
        timestamp: Date.now()
      });
      
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * 按键
   */
  async press(key) {
    if (!this.page) {
      return { success: false, error: 'No active page' };
    }
    
    try {
      await this.page.keyboard.press(key);
      this.recordedActions.push({
        type: 'press',
        key,
        timestamp: Date.now()
      });
      
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * 等待选择器
   */
  async waitForSelector(selector) {
    if (!this.page) {
      return { success: false, error: 'No active page' };
    }
    
    try {
      await this.page.locator(selector).waitFor({ state: 'visible' });
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * 等待时间
   */
  async waitForTimeout(timeout) {
    if (!this.page) {
      return { success: false, error: 'No active page' };
    }
    
    await this.page.waitForTimeout(timeout);
    return { success: true };
  }

  /**
   * 截图
   */
  async screenshot(savePath) {
    if (!this.page) {
      return { success: false, error: 'No active page' };
    }
    
    try {
      const buffer = await this.page.screenshot({ fullPage: false });
      
      if (savePath) {
        fs.writeFileSync(savePath, buffer);
      }
      
      return {
        success: true,
        base64: buffer.toString('base64')
      };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * 获取录制的操作列表（我们记录的）
   */
  async getRecordedCode() {
    return {
      success: true,
      actions: this.recordedActions,
      count: this.recordedActions.length
    };
  }

  /**
   * 获取 Codegen 生成的代码
   * 这是关键：从 Codegen 获取高质量选择器的代码
   */
  async getCodegenCode() {
    try {
      // 如果指定了输出文件，读取它
      if (this.outputFile && fs.existsSync(this.outputFile)) {
        const code = fs.readFileSync(this.outputFile, 'utf-8');
        return {
          success: true,
          code,
          source: 'codegen_file'
        };
      }
      
      // 否则返回我们记录的操作
      // 注意：这不是 Codegen 生成的高质量代码
      // 只是我们的操作记录
      const generatedCode = this.generateCodeFromActions();
      
      return {
        success: true,
        code: generatedCode,
        source: 'action_log',
        warning: 'Codegen output file not found, using action log'
      };
      
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * 从操作记录生成代码（备用方案）
   */
  generateCodeFromActions() {
    const lines = [
      "import { test, expect } from '@playwright/test';",
      "",
      "test('recorded test', async ({ page }) => {"
    ];
    
    for (const action of this.recordedActions) {
      switch (action.type) {
        case 'navigate':
          lines.push(`  await page.goto('${action.url}');`);
          break;
        case 'click':
          if (action.selector) {
            lines.push(`  await page.locator('${action.selector}').click();`);
          }
          break;
        case 'fill':
          lines.push(`  await page.locator('${action.selector}').fill('${action.value}');`);
          break;
        case 'select':
          lines.push(`  await page.locator('${action.selector}').selectOption('${action.value}');`);
          break;
        case 'hover':
          lines.push(`  await page.locator('${action.selector}').hover();`);
          break;
        case 'press':
          lines.push(`  await page.keyboard.press('${action.key}');`);
          break;
      }
    }
    
    lines.push('});');
    return lines.join('\n');
  }

  /**
   * 停止录制，关闭浏览器
   */
  async stopRecording() {
    try {
      // 先获取最终代码
      let finalCode = null;
      if (this.outputFile && fs.existsSync(this.outputFile)) {
        finalCode = fs.readFileSync(this.outputFile, 'utf-8');
      }
      
      // 关闭浏览器
      if (this.browser) {
        await this.browser.close();
      }
      
      this.browser = null;
      this.context = null;
      this.page = null;
      
      return {
        success: true,
        code: finalCode,
        actionsCount: this.recordedActions.length
      };
      
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  /**
   * 获取当前状态
   */
  getStatus() {
    return {
      success: true,
      isRunning: this.browser !== null,
      hasPage: this.page !== null,
      actionsCount: this.recordedActions.length,
      outputFile: this.outputFile
    };
  }
}

// 启动服务器
const server = new RecorderServer(process.env.RECORDER_PORT || 9223);
server.start().catch(console.error);

// 导出供外部使用
export { RecorderServer };
