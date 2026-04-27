/**
 * Playwright MCP Test Script for Hungry Panda Web Application
 * Tests the fixes for ticker-modal.js exports and /shared directory mounting
 */

import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

// Test configuration
const BASE_URL = 'http://localhost:8080';
const SCREENSHOT_DIR = '/home/jeyanth-mandava/hungry-panda/test-results';

// Ensure screenshot directory exists
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

// Helper function to take screenshots
async function takeScreenshot(page, name) {
  const screenshotPath = path.join(SCREENSHOT_DIR, `${name}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log(`📸 Screenshot saved: ${screenshotPath}`);
  return screenshotPath;
}

// Helper function to capture console logs
function setupConsoleCapture(page) {
  const consoleLogs = [];
  const errorLogs = [];

  page.on('console', msg => {
    const logEntry = {
      type: msg.type(),
      text: msg.text(),
      location: msg.location(),
      timestamp: new Date().toISOString()
    };
    consoleLogs.push(logEntry);

    if (msg.type() === 'error') {
      errorLogs.push(logEntry);
      console.log(`❌ Console Error: ${msg.text()}`);
    }
  });

  page.on('pageerror', error => {
    const errorEntry = {
      type: 'pageerror',
      text: error.message,
      stack: error.stack,
      timestamp: new Date().toISOString()
    };
    errorLogs.push(errorEntry);
    console.log(`❌ Page Error: ${error.message}`);
  });

  return { consoleLogs, errorLogs };
}

// Test 1: Dashboard page loads
async function testDashboard(page) {
  console.log('\n📋 TEST 1: Dashboard Page Loading');
  console.log('=====================================');

  const { consoleLogs, errorLogs } = setupConsoleCapture(page);

  try {
    // Navigate to dashboard
    console.log(`Navigating to ${BASE_URL}/...`);
    await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 30000 });

    // Wait for page to stabilize
    await page.waitForTimeout(2000);

    // Take screenshot
    await takeScreenshot(page, '01-dashboard-loaded');

    // Check for content queue section
    const contentQueue = await page.locator('.section:has-text("Content Queue"), .section:has-text("Queue"), [class*="queue"]').first();
    const queueVisible = await contentQueue.isVisible().catch(() => false);

    // Check for insights section
    const insightsSection = await page.locator('.strategy-section, [class*="insight"], [class*="strategy"]').first();
    const insightsVisible = await insightsSection.isVisible().catch(() => false);

    // Check for AI Recommendations button
    const aiRecButton = await page.locator('button:has-text("AI Recommendations"), button:has-text("Get AI"), .btn-primary').first();
    const aiRecButtonVisible = await aiRecButton.isVisible().catch(() => false);
    const aiRecButtonEnabled = await aiRecButton.isEnabled().catch(() => false);

    console.log('\n✅ Dashboard Test Results:');
    console.log(`  - Page loaded: YES`);
    console.log(`  - Content queue section visible: ${queueVisible ? 'YES' : 'NO'}`);
    console.log(`  - Insights section visible: ${insightsVisible ? 'YES' : 'NO'}`);
    console.log(`  - AI Recommendations button visible: ${aiRecButtonVisible ? 'YES' : 'NO'}`);
    console.log(`  - AI Recommendations button clickable: ${aiRecButtonEnabled ? 'YES' : 'NO'}`);

    // Check console errors
    const moduleErrors = errorLogs.filter(e =>
      e.text.includes('module') ||
      e.text.includes('import') ||
      e.text.includes('export') ||
      e.text.includes('ticker-modal') ||
      e.text.includes('animations') ||
      e.text.includes('quotes')
    );

    const showTickerErrors = errorLogs.filter(e =>
      e.text.includes('showTicker') ||
      e.text.includes('updateProgress') ||
      e.text.includes('tickerModal')
    );

    console.log(`\n🔍 Console Error Analysis:`);
    console.log(`  - Total errors: ${errorLogs.length}`);
    console.log(`  - Module/import/export errors: ${moduleErrors.length}`);
    console.log(`  - showTicker related errors: ${showTickerErrors.length}`);

    if (moduleErrors.length > 0) {
      console.log('\n  Module errors found:');
      moduleErrors.forEach(e => console.log(`    - ${e.text.substring(0, 100)}...`));
    }

    if (showTickerErrors.length > 0) {
      console.log('\n  showTicker errors found:');
      showTickerErrors.forEach(e => console.log(`    - ${e.text.substring(0, 100)}...`));
    }

    return {
      test: 'Dashboard',
      passed: errorLogs.length === 0 && queueVisible,
      queueVisible,
      insightsVisible,
      aiRecButtonVisible,
      aiRecButtonEnabled,
      errorCount: errorLogs.length,
      moduleErrors: moduleErrors.length,
      showTickerErrors: showTickerErrors.length,
      consoleLogs: consoleLogs.slice(-20), // Last 20 logs
      errorLogs
    };

  } catch (error) {
    console.error(`❌ Dashboard test failed: ${error.message}`);
    await takeScreenshot(page, '01-dashboard-error');
    return {
      test: 'Dashboard',
      passed: false,
      error: error.message
    };
  }
}

// Test 2: Reels page loads
async function testReels(page) {
  console.log('\n📋 TEST 2: Reels Page Loading');
  console.log('=====================================');

  const { consoleLogs, errorLogs } = setupConsoleCapture(page);

  try {
    // Navigate to reels page
    console.log(`Navigating to ${BASE_URL}/reels.html...`);
    await page.goto(`${BASE_URL}/reels.html`, { waitUntil: 'networkidle', timeout: 30000 });

    // Wait for page to stabilize
    await page.waitForTimeout(2000);

    // Take screenshot
    await takeScreenshot(page, '02-reels-loaded');

    // Check for projects list
    const projectsGrid = await page.locator('.projects-grid, [class*="project"], .project-card').first();
    const projectsVisible = await projectsGrid.isVisible().catch(() => false);

    // Check for empty state or loading
    const emptyState = await page.locator('.empty-state, [class*="empty"]').first();
    const emptyStateVisible = await emptyState.isVisible().catch(() => false);

    // Check for create project button
    const createButton = await page.locator('button:has-text("New Project"), button:has-text("Create"), .btn-primary').first();
    const createButtonVisible = await createButton.isVisible().catch(() => false);

    console.log('\n✅ Reels Test Results:');
    console.log(`  - Page loaded: YES`);
    console.log(`  - Projects/Content visible: ${projectsVisible ? 'YES' : 'NO'}`);
    console.log(`  - Empty state visible: ${emptyStateVisible ? 'YES' : 'NO'}`);
    console.log(`  - Create button visible: ${createButtonVisible ? 'YES' : 'NO'}`);

    // Try clicking on a project if available
    let projectClickable = false;
    try {
      const projectCard = await page.locator('.project-card, [class*="project"]').first();
      if (await projectCard.isVisible().catch(() => false)) {
        await projectCard.click();
        await page.waitForTimeout(1000);
        projectClickable = true;
        console.log(`  - Can click on project: YES`);
        await takeScreenshot(page, '03-reels-project-clicked');

        // Check for generate button in detail view
        const generateButton = await page.locator('button:has-text("Generate"), .generate-btn').first();
        const generateButtonVisible = await generateButton.isVisible().catch(() => false);
        console.log(`  - Generate button visible: ${generateButtonVisible ? 'YES' : 'NO'}`);

        // Go back to projects list
        await page.goto(`${BASE_URL}/reels.html`, { waitUntil: 'networkidle' });
        await page.waitForTimeout(1000);
      }
    } catch (e) {
      console.log(`  - Can click on project: NO (no projects or error)`);
    }

    // Check console errors
    const moduleErrors = errorLogs.filter(e =>
      e.text.includes('module') ||
      e.text.includes('import') ||
      e.text.includes('export') ||
      e.text.includes('ticker-modal') ||
      e.text.includes('animations') ||
      e.text.includes('quotes')
    );

    const showTickerErrors = errorLogs.filter(e =>
      e.text.includes('showTicker') ||
      e.text.includes('updateProgress') ||
      e.text.includes('tickerModal')
    );

    console.log(`\n🔍 Console Error Analysis:`);
    console.log(`  - Total errors: ${errorLogs.length}`);
    console.log(`  - Module/import/export errors: ${moduleErrors.length}`);
    console.log(`  - showTicker related errors: ${showTickerErrors.length}`);

    if (moduleErrors.length > 0) {
      console.log('\n  Module errors found:');
      moduleErrors.forEach(e => console.log(`    - ${e.text.substring(0, 100)}...`));
    }

    return {
      test: 'Reels',
      passed: errorLogs.length === 0,
      projectsVisible,
      emptyStateVisible,
      createButtonVisible,
      projectClickable,
      errorCount: errorLogs.length,
      moduleErrors: moduleErrors.length,
      showTickerErrors: showTickerErrors.length,
      consoleLogs: consoleLogs.slice(-20),
      errorLogs
    };

  } catch (error) {
    console.error(`❌ Reels test failed: ${error.message}`);
    await takeScreenshot(page, '02-reels-error');
    return {
      test: 'Reels',
      passed: false,
      error: error.message
    };
  }
}

// Test 3: Check shared files are accessible
async function testSharedFiles(page) {
  console.log('\n📋 TEST 3: Shared Files Accessibility');
  console.log('=====================================');

  const sharedFiles = [
    '/shared/ticker-modal.js',
    '/shared/animations.js',
    '/shared/quotes.js',
    '/shared/liquid-ui.css'
  ];

  const results = [];

  for (const file of sharedFiles) {
    try {
      const response = await page.goto(`${BASE_URL}${file}`, { timeout: 10000 });
      const status = response.status();
      const ok = status === 200;

      console.log(`  ${file}: ${ok ? '✅ 200 OK' : `❌ ${status}`}`);
      results.push({ file, accessible: ok, status });
    } catch (error) {
      console.log(`  ${file}: ❌ Error - ${error.message}`);
      results.push({ file, accessible: false, error: error.message });
    }
  }

  return {
    test: 'Shared Files',
    passed: results.every(r => r.accessible),
    results
  };
}

// Main test runner
async function runTests() {
  console.log('🎭 Hungry Panda - Playwright MCP Test Suite');
  console.log('==============================================');
  console.log(`Testing against: ${BASE_URL}`);
  console.log(`Results will be saved to: ${SCREENSHOT_DIR}`);

  let browser;
  let page;

  try {
    // Launch browser
    console.log('\n🚀 Launching browser...');
    browser = await chromium.launch({ headless: true });
    page = await browser.newPage({
      viewport: { width: 1280, height: 800 }
    });

    // Run all tests
    const dashboardResult = await testDashboard(page);
    const reelsResult = await testReels(page);
    const sharedFilesResult = await testSharedFiles(page);

    // Summary
    console.log('\n\n📊 TEST SUMMARY');
    console.log('=================');

    const allResults = [dashboardResult, reelsResult, sharedFilesResult];

    allResults.forEach(result => {
      const status = result.passed ? '✅ PASS' : '❌ FAIL';
      console.log(`${status}: ${result.test}`);
      if (result.error) {
        console.log(`      Error: ${result.error}`);
      }
    });

    const totalPassed = allResults.filter(r => r.passed).length;
    const totalTests = allResults.length;

    console.log(`\nOverall: ${totalPassed}/${totalTests} tests passed`);

    // Save detailed results
    const resultsPath = path.join(SCREENSHOT_DIR, 'test-results.json');
    fs.writeFileSync(resultsPath, JSON.stringify({
      timestamp: new Date().toISOString(),
      baseUrl: BASE_URL,
      results: allResults,
      summary: {
        total: totalTests,
        passed: totalPassed,
        failed: totalTests - totalPassed
      }
    }, null, 2));

    console.log(`\n📄 Detailed results saved to: ${resultsPath}`);

    return {
      success: totalPassed === totalTests,
      results: allResults
    };

  } catch (error) {
    console.error(`\n❌ Test suite failed: ${error.message}`);
    return {
      success: false,
      error: error.message
    };

  } finally {
    if (browser) {
      await browser.close();
      console.log('\n🔒 Browser closed');
    }
  }
}

// Run tests
runTests().then(result => {
  console.log('\n🏁 Test execution complete');
  process.exit(result.success ? 0 : 1);
}).catch(error => {
  console.error(`\n💥 Fatal error: ${error.message}`);
  process.exit(1);
});
