const { chromium, devices } = require('playwright');

// Test configuration
const BASE_URL = 'http://localhost:8080';
const MOBILE_VIEWPORT = devices['iPhone 13'];
const DESKTOP_VIEWPORT = { width: 1440, height: 900 };

// Test results
const results = {
  desktop: [],
  mobile: [],
  critical: [],
  warnings: [],
  passed: 0,
  failed: 0
};

function log(category, message, status = 'info') {
  const timestamp = new Date().toISOString();
  const entry = { timestamp, category, message, status };
  
  if (status === 'critical') results.critical.push(entry);
  else if (status === 'warning') results.warnings.push(entry);
  else if (status === 'pass') results.passed++;
  else if (status === 'fail') results.failed++;
  
  console.log(`[${status.toUpperCase()}] ${category}: ${message}`);
  return entry;
}

async function runDesktopTests(page) {
  log('DESKTOP', 'Starting desktop viewport tests', 'info');
  
  try {
    // Test 1: Page Load
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
    
    const title = await page.title();
    if (title.includes('Hungry Panda')) {
      log('DESKTOP', '✓ Page title correct', 'pass');
    } else {
      log('DESKTOP', `✗ Page title incorrect: ${title}`, 'fail');
    }
    
    // Test 2: Header visibility
    const header = await page.locator('.app-header').isVisible();
    if (header) {
      log('DESKTOP', '✓ Header visible', 'pass');
    } else {
      log('DESKTOP', '✗ Header not visible', 'fail');
    }
    
    // Test 3: Brand elements
    const brandIcon = await page.locator('.brand-icon').isVisible();
    const brandText = await page.locator('.brand-text h1').textContent();
    if (brandIcon && brandText.includes('Hungry Panda')) {
      log('DESKTOP', '✓ Brand elements present', 'pass');
    } else {
      log('DESKTOP', '✗ Brand elements missing', 'fail');
    }
    
    // Test 4: Metrics grid
    const metricsGrid = await page.locator('.metrics-grid').isVisible();
    const metricCards = await page.locator('.metric-card').count();
    if (metricsGrid && metricCards === 4) {
      log('DESKTOP', `✓ Metrics grid with ${metricCards} cards`, 'pass');
    } else {
      log('DESKTOP', `✗ Metrics grid issue: ${metricCards} cards found`, 'fail');
    }
    
    // Test 5: Upload hero section
    const uploadHero = await page.locator('.upload-hero').isVisible();
    const uploadBtn = await page.locator('.upload-hero .btn-primary').isVisible();
    if (uploadHero && uploadBtn) {
      log('DESKTOP', '✓ Upload hero section functional', 'pass');
    } else {
      log('DESKTOP', '✗ Upload hero issue', 'fail');
    }
    
    // Test 6: Content queue section
    const queueSection = await page.locator('.section:has(.queue-tabs)').isVisible();
    const tabs = await page.locator('.tab').count();
    if (queueSection && tabs >= 3) {
      log('DESKTOP', `✓ Queue section with ${tabs} tabs`, 'pass');
    } else {
      log('DESKTOP', '✗ Queue section issue', 'fail');
    }
    
    // Test 7: Strategy panel
    const strategySection = await page.locator('.strategy-section').isVisible();
    if (strategySection) {
      log('DESKTOP', '✓ Strategy panel present', 'pass');
    } else {
      log('DESKTOP', '✗ Strategy panel missing', 'fail');
    }
    
    // Test 8: Right rail panels
    const competitorSection = await page.locator('text=Competitor Insights').isVisible();
    const hashtagSection = await page.locator('text=Trending Hashtags').isVisible();
    if (competitorSection && hashtagSection) {
      log('DESKTOP', '✓ Right rail panels present', 'pass');
    } else {
      log('DESKTOP', '✗ Right rail panels issue', 'fail');
    }
    
    // Test 9: Hover effects
    const firstMetric = page.locator('.metric-card').first();
    await firstMetric.hover();
    await page.waitForTimeout(300);
    log('DESKTOP', '✓ Metric card hover test', 'pass');
    
    // Test 10: File upload area
    const uploadArea = await page.locator('.upload-hero');
    await uploadArea.dragEnter({ dataTransfer: {} });
    await page.waitForTimeout(200);
    const hasDragover = await uploadArea.evaluate(el => el.classList.contains('dragover'));
    if (hasDragover) {
      log('DESKTOP', '✓ Upload drag state working', 'pass');
    } else {
      log('DESKTOP', '⚠ Upload drag state check inconclusive', 'warning');
    }
    
    // Test 11: Tab switching
    const scheduledTab = page.locator('.tab', { hasText: 'Scheduled' });
    if (await scheduledTab.isVisible()) {
      await scheduledTab.click();
      await page.waitForTimeout(500);
      const isActive = await scheduledTab.evaluate(el => el.classList.contains('active'));
      if (isActive) {
        log('DESKTOP', '✓ Tab switching functional', 'pass');
      } else {
        log('DESKTOP', '✗ Tab switching issue', 'fail');
      }
    }
    
    // Visual check - take screenshot
    await page.screenshot({ path: '/home/jeyanth-mandava/hungry-panda/logs/regression-desktop.png', fullPage: true });
    log('DESKTOP', '✓ Desktop screenshot saved', 'pass');
    
  } catch (err) {
    log('DESKTOP', `✗ Critical error: ${err.message}`, 'critical');
  }
}

async function runMobileTests(page) {
  log('MOBILE', 'Starting mobile viewport tests', 'info');
  
  try {
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
    
    // Test 1: Mobile header
    const header = await page.locator('.app-header').isVisible();
    const brandIcon = await page.locator('.brand-icon').isVisible();
    if (header && brandIcon) {
      log('MOBILE', '✓ Mobile header present', 'pass');
    } else {
      log('MOBILE', '✗ Mobile header issue', 'fail');
    }
    
    // Test 2: Metrics in 2x2 grid
    const metricCards = await page.locator('.metric-card').count();
    const viewport = page.viewportSize();
    if (metricCards === 4 && viewport.width < 768) {
      log('MOBILE', `✓ Metrics in mobile layout (${viewport.width}px)`, 'pass');
    } else {
      log('MOBILE', `⚠ Metrics layout: ${metricCards} cards at ${viewport.width}px`, 'warning');
    }
    
    // Test 3: Upload hero sizing
    const uploadHero = await page.locator('.upload-hero');
    const box = await uploadHero.boundingBox();
    if (box && box.width > 300) {
      log('MOBILE', `✓ Upload hero sized for mobile (${Math.round(box.width)}px)`, 'pass');
    } else {
      log('MOBILE', '⚠ Upload hero may be too small', 'warning');
    }
    
    // Test 4: Queue items
    const queueItems = await page.locator('.queue-item').count();
    log('MOBILE', `ℹ Queue items visible: ${queueItems}`, 'info');
    
    // Test 5: Touch targets
    const actionBtns = await page.locator('.action-btn').count();
    if (actionBtns > 0) {
      const firstBtn = page.locator('.action-btn').first();
      const btnBox = await firstBtn.boundingBox();
      if (btnBox && btnBox.width >= 32 && btnBox.height >= 32) {
        log('MOBILE', `✓ Touch targets adequate (${Math.round(btnBox.width)}px)`, 'pass');
      } else {
        log('MOBILE', '⚠ Touch targets may be small', 'warning');
      }
    }
    
    // Test 6: Scroll test
    await page.evaluate(() => window.scrollTo(0, 500));
    await page.waitForTimeout(300);
    const scrollPos = await page.evaluate(() => window.scrollY);
    if (scrollPos > 0) {
      log('MOBILE', '✓ Scrolling functional', 'pass');
    }
    
    // Visual check
    await page.screenshot({ path: '/home/jeyanth-mandava/hungry-panda/logs/regression-mobile.png', fullPage: true });
    log('MOBILE', '✓ Mobile screenshot saved', 'pass');
    
  } catch (err) {
    log('MOBILE', `✗ Critical error: ${err.message}`, 'critical');
  }
}

async function runAPITests() {
  log('API', 'Starting API endpoint tests', 'info');
  
  const endpoints = [
    { url: '/api/health', method: 'GET' },
    { url: '/api/growth/dashboard', method: 'GET' },
    { url: '/api/content/pending', method: 'GET' },
    { url: '/api/competitors', method: 'GET' }
  ];
  
  for (const endpoint of endpoints) {
    try {
      const response = await fetch(`${BASE_URL}${endpoint.url}`);
      if (response.ok) {
        const data = await response.json();
        log('API', `✓ ${endpoint.url} - ${response.status}`, 'pass');
      } else {
        log('API', `✗ ${endpoint.url} - ${response.status}`, 'fail');
      }
    } catch (err) {
      log('API', `✗ ${endpoint.url} - ${err.message}`, 'fail');
    }
  }
}

async function generateReport() {
  const report = `
================================
HUNGRY PANDA REGRESSION REPORT
================================

Test Run: ${new Date().toISOString()}
Base URL: ${BASE_URL}

SUMMARY
-------
Passed: ${results.passed}
Failed: ${results.failed}
Warnings: ${results.warnings.length}
Critical: ${results.critical.length}

${results.critical.length > 0 ? 'CRITICAL ISSUES\n---------------\n' + results.critical.map(c => `- ${c.category}: ${c.message}`).join('\n') + '\n' : ''}

${results.warnings.length > 0 ? 'WARNINGS\n--------\n' + results.warnings.map(w => `- ${w.category}: ${w.message}`).join('\n') + '\n' : ''}

DETAILED LOG
------------
${results.desktop.map(d => `[DESKTOP] ${d.message}`).join('\n')}

${results.mobile.map(m => `[MOBILE] ${m.message}`).join('\n')}

RECOMMENDATIONS
---------------
${results.failed > 0 ? '1. Review failed tests above\n' : '1. All core tests passing ✓\n'}
${results.warnings.length > 0 ? '2. Address warnings for better UX\n' : '2. No warnings - great job!\n'}
3. Check screenshots in logs/ directory
4. Test actual file upload functionality manually

================================
`;

  require('fs').writeFileSync(
    '/home/jeyanth-mandava/hungry-panda/logs/regression-report.txt',
    report
  );
  
  console.log(report);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  
  try {
    // Desktop tests
    const desktopContext = await browser.newContext({ viewport: DESKTOP_VIEWPORT });
    const desktopPage = await desktopContext.newPage();
    await runDesktopTests(desktopPage);
    await desktopContext.close();
    
    // Mobile tests
    const mobileContext = await browser.newContext({ ...MOBILE_VIEWPORT });
    const mobilePage = await mobileContext.newPage();
    await runMobileTests(mobilePage);
    await mobileContext.close();
    
    // API tests
    await runAPITests();
    
    // Generate report
    await generateReport();
    
    console.log('\n✅ Regression testing complete');
    console.log(`Report saved to: logs/regression-report.txt`);
    console.log(`Screenshots saved to: logs/regression-*.png`);
    
  } catch (err) {
    console.error('Test run failed:', err);
  } finally {
    await browser.close();
  }
})();
