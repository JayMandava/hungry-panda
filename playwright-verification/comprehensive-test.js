const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const SCREENSHOT_DIR = '/home/jeyanth-mandava/hungry-panda/playwright-verification';

// Ensure screenshot directory exists
if (!fs.existsSync(SCREENSHOT_DIR)) {
    fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

// Console log collector
let consoleLogs = [];
let pageErrors = [];

async function collectConsoleLogs(page) {
    page.on('console', msg => {
        const logEntry = `[${msg.type()}] ${msg.text()}`;
        consoleLogs.push(logEntry);
        console.log(`Console: ${logEntry}`);
    });
    
    page.on('pageerror', error => {
        const errorEntry = `[PAGE ERROR] ${error.message}`;
        pageErrors.push(errorEntry);
        console.log(`Page Error: ${errorEntry}`);
    });
}

async function saveTestReport() {
    const report = {
        timestamp: new Date().toISOString(),
        consoleLogs: consoleLogs,
        pageErrors: pageErrors
    };
    
    fs.writeFileSync(
        path.join(SCREENSHOT_DIR, 'test-report.json'),
        JSON.stringify(report, null, 2)
    );
}

// ==================== TEST 1: Dashboard - Generate New Strategy ====================
async function test1_DashboardGenerateStrategy(browser) {
    console.log('\n========================================');
    console.log('TEST 1: Dashboard - Generate New Strategy');
    console.log('========================================\n');
    
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await context.newPage();
    
    // Clear logs for this test
    consoleLogs = [];
    pageErrors = [];
    await collectConsoleLogs(page);
    
    let testResults = {
        testName: 'TEST 1: Dashboard - Generate New Strategy',
        steps: [],
        passed: false
    };
    
    try {
        // Step 1: Navigate to dashboard
        console.log('Step 1: Navigating to http://localhost:8080/');
        await page.goto('http://localhost:8080/', { waitUntil: 'networkidle', timeout: 30000 });
        await page.waitForTimeout(2000);
        testResults.steps.push({ name: 'Navigation', status: 'PASSED' });
        
        // Take initial screenshot
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'test1-01-initial.png'), fullPage: true });
        console.log('✓ Screenshot saved: test1-01-initial.png');
        
        // Step 2: Find and click "Generate New Strategy" button
        console.log('\nStep 2: Looking for "Generate New Strategy" or "Create Strategy" button...');
        
        // Try multiple selectors for the button
        const buttonSelectors = [
            'button:has-text("Generate New Strategy")',
            'button:has-text("Create Strategy")',
            'button:has-text("Generate Strategy")',
            'a:has-text("Generate New Strategy")',
            'a:has-text("Create Strategy")',
            '[data-testid="generate-strategy"]',
            '.generate-strategy-btn',
            '#generate-strategy-btn'
        ];
        
        let buttonFound = false;
        let buttonInfo = null;
        
        for (const selector of buttonSelectors) {
            try {
                const button = await page.locator(selector).first();
                const count = await button.count();
                if (count > 0) {
                    const isVisible = await button.isVisible();
                    const text = await button.textContent();
                    console.log(`✓ Found button with selector: ${selector}`);
                    console.log(`  Text: "${text?.trim()}"`);
                    console.log(`  Visible: ${isVisible}`);
                    
                    // Get button details before clicking
                    const box = await button.boundingBox();
                    buttonInfo = { selector, text: text?.trim(), visible: isVisible, box };
                    
                    if (isVisible) {
                        console.log('\nStep 3: CLICKING the button...');
                        await button.click();
                        buttonFound = true;
                        testResults.steps.push({ name: 'Button Found and Clicked', status: 'PASSED', details: buttonInfo });
                        break;
                    }
                }
            } catch (e) {
                // Continue to next selector
            }
        }
        
        if (!buttonFound) {
            // Dump page content for debugging
            const pageContent = await page.content();
            fs.writeFileSync(path.join(SCREENSHOT_DIR, 'test1-page-content.html'), pageContent);
            console.log('✗ Button not found. Page content saved to test1-page-content.html');
            testResults.steps.push({ name: 'Button Click', status: 'FAILED', error: 'Button not found' });
        }
        
        // Step 4: Wait and check for modal
        console.log('\nStep 4: Waiting 2 seconds after click...');
        await page.waitForTimeout(2000);
        
        // Take screenshot after click
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'test1-02-after-click.png'), fullPage: true });
        console.log('✓ Screenshot saved: test1-02-after-click.png');
        
        // Step 5: Check for modal/dialog
        console.log('\nStep 5: Checking for modal/dialog appearance...');
        
        const modalSelectors = [
            '.modal',
            '.modal-overlay',
            '.dialog',
            '.popup',
            '[role="dialog"]',
            '.strategy-modal',
            '.create-strategy-modal',
            '.fixed.inset-0', // Common overlay pattern
            '.bg-black.bg-opacity-50',
            '.bg-black\/50'
        ];
        
        let modalFound = false;
        let modalDetails = null;
        
        for (const selector of modalSelectors) {
            try {
                const element = await page.locator(selector).first();
                const count = await element.count();
                if (count > 0) {
                    const isVisible = await element.isVisible();
                    const computedStyle = await element.evaluate(el => ({
                        display: window.getComputedStyle(el).display,
                        opacity: window.getComputedStyle(el).opacity,
                        visibility: window.getComputedStyle(el).visibility,
                        zIndex: window.getComputedStyle(el).zIndex
                    }));
                    
                    console.log(`✓ Found element with selector: ${selector}`);
                    console.log(`  Visible: ${isVisible}`);
                    console.log(`  Computed style:`, computedStyle);
                    
                    modalDetails = { selector, visible: isVisible, computedStyle };
                    
                    if (isVisible && computedStyle.opacity !== '0' && computedStyle.display !== 'none') {
                        modalFound = true;
                    }
                }
            } catch (e) {
                // Continue
            }
        }
        
        testResults.steps.push({ 
            name: 'Modal Detection', 
            status: modalFound ? 'PASSED' : 'FAILED', 
            details: modalDetails,
            modalFound: modalFound
        });
        
        // Step 6: Check console for errors
        console.log('\nStep 6: Checking browser console for errors...');
        const errors = consoleLogs.filter(log => log.includes('error') || log.includes('Error'));
        console.log(`  Console errors found: ${errors.length}`);
        errors.forEach(err => console.log(`    ${err}`));
        testResults.steps.push({ name: 'Console Error Check', status: errors.length === 0 ? 'PASSED' : 'FAILED', errors: errors });
        
        // Step 7: Final screenshot
        console.log('\nStep 7: Taking final screenshot...');
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'test1-03-final.png'), fullPage: true });
        console.log('✓ Screenshot saved: test1-03-final.png');
        
        testResults.passed = buttonFound && modalFound && errors.length === 0;
        
    } catch (error) {
        console.error('Test 1 Error:', error.message);
        testResults.steps.push({ name: 'Test Execution', status: 'FAILED', error: error.message });
        testResults.passed = false;
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'test1-error.png'), fullPage: true });
    }
    
    await context.close();
    
    // Save test results
    fs.writeFileSync(
        path.join(SCREENSHOT_DIR, 'test1-results.json'),
        JSON.stringify(testResults, null, 2)
    );
    
    console.log('\n--- TEST 1 COMPLETE ---');
    console.log(`Result: ${testResults.passed ? '✓ PASSED' : '✗ FAILED'}`);
    
    return testResults;
}

// ==================== TEST 2: Reels - Generate Reel ====================
async function test2_ReelsGenerateReel(browser) {
    console.log('\n========================================');
    console.log('TEST 2: Reels - Generate Reel');
    console.log('========================================\n');
    
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await context.newPage();
    
    // Clear logs for this test
    consoleLogs = [];
    pageErrors = [];
    await collectConsoleLogs(page);
    
    let testResults = {
        testName: 'TEST 2: Reels - Generate Reel',
        steps: [],
        passed: false
    };
    
    try {
        // Step 1: Navigate to reels page
        console.log('Step 1: Navigating to http://localhost:8080/reels.html');
        await page.goto('http://localhost:8080/reels.html', { waitUntil: 'networkidle', timeout: 30000 });
        await page.waitForTimeout(2000);
        testResults.steps.push({ name: 'Navigation', status: 'PASSED' });
        
        // Take initial screenshot
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'test2-01-initial.png'), fullPage: true });
        console.log('✓ Screenshot saved: test2-01-initial.png');
        
        // Step 2: Find and click on a project card
        console.log('\nStep 2: Looking for project card to click...');
        
        const projectCardSelectors = [
            '.project-card',
            '.reel-card',
            '.project-item',
            '[data-project]',
            '.card',
            '.project',
            '.reel-project'
        ];
        
        let projectCardFound = false;
        let projectCardInfo = null;
        
        for (const selector of projectCardSelectors) {
            try {
                const cards = await page.locator(selector);
                const count = await cards.count();
                console.log(`  Selector "${selector}": ${count} elements found`);
                
                if (count > 0) {
                    const firstCard = cards.first();
                    const isVisible = await firstCard.isVisible();
                    
                    if (isVisible) {
                        console.log(`✓ Found visible project card with: ${selector}`);
                        const box = await firstCard.boundingBox();
                        projectCardInfo = { selector, box, count };
                        
                        console.log('\nStep 3: CLICKING project card...');
                        await firstCard.click();
                        projectCardFound = true;
                        testResults.steps.push({ name: 'Project Card Click', status: 'PASSED', details: projectCardInfo });
                        break;
                    }
                }
            } catch (e) {
                // Continue
            }
        }
        
        if (!projectCardFound) {
            console.log('✗ No project card found. Checking page content...');
            const content = await page.content();
            fs.writeFileSync(path.join(SCREENSHOT_DIR, 'test2-page-content.html'), content);
            testResults.steps.push({ name: 'Project Card Click', status: 'FAILED', error: 'No project card found' });
        }
        
        // Step 4: Wait for project detail to load
        console.log('\nStep 4: Waiting for project detail to load...');
        await page.waitForTimeout(2000);
        
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'test2-02-project-detail.png'), fullPage: true });
        console.log('✓ Screenshot saved: test2-02-project-detail.png');
        
        // Step 5: Find and click "Generate Reel" button
        console.log('\nStep 5: Looking for "Generate Reel" button...');
        
        const generateReelSelectors = [
            'button:has-text("Generate Reel")',
            'button:has-text("Generate")',
            'a:has-text("Generate Reel")',
            '.generate-reel-btn',
            '#generate-reel',
            '[data-action="generate-reel"]'
        ];
        
        let generateButtonFound = false;
        let generateButtonInfo = null;
        
        for (const selector of generateReelSelectors) {
            try {
                const button = await page.locator(selector).first();
                const count = await button.count();
                if (count > 0) {
                    const isVisible = await button.isVisible();
                    const text = await button.textContent();
                    console.log(`✓ Found button: "${text?.trim()}" with selector: ${selector}`);
                    
                    if (isVisible) {
                        const box = await button.boundingBox();
                        generateButtonInfo = { selector, text: text?.trim(), box };
                        
                        console.log('\nStep 6: CLICKING Generate Reel button...');
                        await button.click();
                        generateButtonFound = true;
                        testResults.steps.push({ name: 'Generate Reel Button Click', status: 'PASSED', details: generateButtonInfo });
                        break;
                    }
                }
            } catch (e) {
                // Continue
            }
        }
        
        if (!generateButtonFound) {
            testResults.steps.push({ name: 'Generate Reel Button Click', status: 'FAILED', error: 'Button not found' });
        }
        
        // Step 7: Wait after click
        console.log('\nStep 7: Waiting 2 seconds after click...');
        await page.waitForTimeout(2000);
        
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'test2-03-after-generate-click.png'), fullPage: true });
        console.log('✓ Screenshot saved: test2-03-after-generate-click.png');
        
        // Step 8: Check for ticker modal with panda
        console.log('\nStep 8: Checking for Ticker Modal with 🐼 panda...');
        
        const tickerModalSelectors = [
            '.ticker-modal',
            '[data-modal="ticker"]',
            '.modal:has(.panda)',
            '.modal:has-text("🐼")',
            '.modal-overlay',
            '.fixed.inset-0'
        ];
        
        let tickerModalFound = false;
        let tickerModalDetails = null;
        let pandaFound = false;
        
        for (const selector of tickerModalSelectors) {
            try {
                const element = await page.locator(selector).first();
                const count = await element.count();
                if (count > 0) {
                    const isVisible = await element.isVisible();
                    const computedStyle = await element.evaluate(el => ({
                        display: window.getComputedStyle(el).display,
                        opacity: window.getComputedStyle(el).opacity,
                        visibility: window.getComputedStyle(el).visibility,
                        zIndex: window.getComputedStyle(el).zIndex
                    }));
                    
                    // Check for panda emoji or image
                    const hasPanda = await element.evaluate(el => 
                        el.textContent.includes('🐼') || 
                        el.innerHTML.includes('panda') ||
                        el.querySelector('[class*="panda"]') !== null
                    );
                    
                    console.log(`✓ Found element: ${selector}`);
                    console.log(`  Visible: ${isVisible}`);
                    console.log(`  Computed style:`, computedStyle);
                    console.log(`  Has 🐼 panda: ${hasPanda}`);
                    
                    tickerModalDetails = { selector, visible: isVisible, computedStyle, hasPanda };
                    
                    if (isVisible && computedStyle.opacity !== '0') {
                        tickerModalFound = true;
                        if (hasPanda) pandaFound = true;
                    }
                }
            } catch (e) {
                // Continue
            }
        }
        
        testResults.steps.push({ 
            name: 'Ticker Modal Detection', 
            status: tickerModalFound ? 'PASSED' : 'FAILED', 
            details: tickerModalDetails,
            modalFound: tickerModalFound,
            pandaFound: pandaFound
        });
        
        // Step 9: Check console for [TickerModal] logs
        console.log('\nStep 9: Checking console for [TickerModal] logs...');
        const tickerLogs = consoleLogs.filter(log => log.includes('[TickerModal]'));
        console.log(`  [TickerModal] logs found: ${tickerLogs.length}`);
        tickerLogs.forEach(log => console.log(`    ${log}`));
        testResults.steps.push({ name: 'TickerModal Logs', status: tickerLogs.length > 0 ? 'PASSED' : 'WARNING', logs: tickerLogs });
        
        // Step 10: Check for console errors
        console.log('\nStep 10: Checking browser console for errors...');
        const errors = consoleLogs.filter(log => log.includes('error') || log.includes('Error'));
        console.log(`  Console errors found: ${errors.length}`);
        errors.forEach(err => console.log(`    ${err}`));
        testResults.steps.push({ name: 'Console Error Check', status: errors.length === 0 ? 'PASSED' : 'FAILED', errors: errors });
        
        // Final screenshot
        console.log('\nStep 11: Taking final screenshot...');
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'test2-04-final.png'), fullPage: true });
        console.log('✓ Screenshot saved: test2-04-final.png');
        
        testResults.passed = generateButtonFound && tickerModalFound && errors.length === 0;
        
    } catch (error) {
        console.error('Test 2 Error:', error.message);
        testResults.steps.push({ name: 'Test Execution', status: 'FAILED', error: error.message });
        testResults.passed = false;
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'test2-error.png'), fullPage: true });
    }
    
    await context.close();
    
    // Save test results
    fs.writeFileSync(
        path.join(SCREENSHOT_DIR, 'test2-results.json'),
        JSON.stringify(testResults, null, 2)
    );
    
    console.log('\n--- TEST 2 COMPLETE ---');
    console.log(`Result: ${testResults.passed ? '✓ PASSED' : '✗ FAILED'}`);
    
    return testResults;
}

// ==================== TEST 3: Verify Content Loading ====================
async function test3_ContentLoading(browser) {
    console.log('\n========================================');
    console.log('TEST 3: Verify Content Loading');
    console.log('========================================\n');
    
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await context.newPage();
    
    // Clear logs
    consoleLogs = [];
    pageErrors = [];
    await collectConsoleLogs(page);
    
    let testResults = {
        testName: 'TEST 3: Verify Content Loading',
        checks: [],
        passed: true
    };
    
    try {
        // Check 1: Content Queue
        console.log('Check 1: Content Queue Loading State');
        await page.goto('http://localhost:8080/', { waitUntil: 'networkidle', timeout: 30000 });
        await page.waitForTimeout(2000);
        
        const contentQueueSelectors = [
            '.content-queue',
            '.queue-section',
            '[data-section="content-queue"]',
            '.queue-list',
            '.content-list'
        ];
        
        let contentQueueFound = false;
        let contentQueueStatus = 'unknown';
        
        for (const selector of contentQueueSelectors) {
            try {
                const element = await page.locator(selector).first();
                if (await element.count() > 0 && await element.isVisible()) {
                    contentQueueFound = true;
                    const text = await element.textContent();
                    const hasLoading = text.toLowerCase().includes('loading');
                    const hasItems = await element.locator('li, .item, .queue-item').count() > 0;
                    
                    contentQueueStatus = hasLoading ? 'loading' : (hasItems ? 'loaded' : 'empty');
                    console.log(`  Content queue found: ${selector}`);
                    console.log(`  Status: ${contentQueueStatus}`);
                    console.log(`  Has "Loading...": ${hasLoading}`);
                    console.log(`  Has items: ${hasItems}`);
                    
                    testResults.checks.push({
                        name: 'Content Queue',
                        found: true,
                        status: contentQueueStatus,
                        hasLoading: hasLoading,
                        hasItems: hasItems
                    });
                    break;
                }
            } catch (e) {}
        }
        
        if (!contentQueueFound) {
            console.log('  ✗ Content queue section not found');
            testResults.checks.push({ name: 'Content Queue', found: false });
            testResults.passed = false;
        }
        
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'test3-01-content-queue.png'), fullPage: true });
        console.log('✓ Screenshot saved: test3-01-content-queue.png\n');
        
        // Check 2: Insights Section
        console.log('Check 2: Insights Section');
        
        const insightsSelectors = [
            '.insights',
            '.insights-section',
            '[data-section="insights"]',
            '.analytics',
            '.stats'
        ];
        
        let insightsFound = false;
        let insightsStatus = 'unknown';
        
        for (const selector of insightsSelectors) {
            try {
                const element = await page.locator(selector).first();
                if (await element.count() > 0 && await element.isVisible()) {
                    insightsFound = true;
                    const text = await element.textContent();
                    const hasLoading = text.toLowerCase().includes('loading');
                    const hasData = text.length > 50; // Assume data if there's substantial text
                    
                    insightsStatus = hasLoading ? 'loading' : (hasData ? 'loaded' : 'empty');
                    console.log(`  Insights section found: ${selector}`);
                    console.log(`  Status: ${insightsStatus}`);
                    console.log(`  Has "Loading...": ${hasLoading}`);
                    console.log(`  Has data: ${hasData}`);
                    
                    testResults.checks.push({
                        name: 'Insights Section',
                        found: true,
                        status: insightsStatus,
                        hasLoading: hasLoading,
                        hasData: hasData
                    });
                    break;
                }
            } catch (e) {}
        }
        
        if (!insightsFound) {
            console.log('  ✗ Insights section not found');
            testResults.checks.push({ name: 'Insights Section', found: false });
        }
        
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'test3-02-insights.png'), fullPage: true });
        console.log('✓ Screenshot saved: test3-02-insights.png\n');
        
        // Check 3: Reels Projects List
        console.log('Check 3: Reels Projects List');
        await page.goto('http://localhost:8080/reels.html', { waitUntil: 'networkidle', timeout: 30000 });
        await page.waitForTimeout(2000);
        
        const projectsSelectors = [
            '.projects-list',
            '.reels-list',
            '[data-section="projects"]',
            '.project-grid',
            '.reels-grid'
        ];
        
        let projectsFound = false;
        let projectsStatus = 'unknown';
        
        for (const selector of projectsSelectors) {
            try {
                const element = await page.locator(selector).first();
                if (await element.count() > 0 && await element.isVisible()) {
                    projectsFound = true;
                    const text = await element.textContent();
                    const hasLoading = text.toLowerCase().includes('loading');
                    const projectCount = await element.locator('.project-card, .reel-card, .card, .project, .reel').count();
                    
                    projectsStatus = hasLoading ? 'loading' : (projectCount > 0 ? 'loaded' : 'empty');
                    console.log(`  Projects list found: ${selector}`);
                    console.log(`  Status: ${projectsStatus}`);
                    console.log(`  Has "Loading...": ${hasLoading}`);
                    console.log(`  Project count: ${projectCount}`);
                    
                    testResults.checks.push({
                        name: 'Reels Projects List',
                        found: true,
                        status: projectsStatus,
                        hasLoading: hasLoading,
                        projectCount: projectCount
                    });
                    break;
                }
            } catch (e) {}
        }
        
        if (!projectsFound) {
            console.log('  ✗ Projects list not found');
            testResults.checks.push({ name: 'Reels Projects List', found: false });
        }
        
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'test3-03-reels-projects.png'), fullPage: true });
        console.log('✓ Screenshot saved: test3-03-reels-projects.png\n');
        
        // Capture any "stuck loading" states
        const stuckLoading = testResults.checks.filter(c => c.status === 'loading');
        if (stuckLoading.length > 0) {
            console.log('⚠ WARNING: Detected stuck loading states:');
            stuckLoading.forEach(c => console.log(`  - ${c.name}`));
        }
        
        // Check console errors
        const errors = consoleLogs.filter(log => log.includes('error') || log.includes('Error'));
        console.log(`\nConsole errors found: ${errors.length}`);
        errors.forEach(err => console.log(`  ${err}`));
        
        testResults.consoleErrors = errors;
        
    } catch (error) {
        console.error('Test 3 Error:', error.message);
        testResults.checks.push({ name: 'Test Execution', status: 'FAILED', error: error.message });
        testResults.passed = false;
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'test3-error.png'), fullPage: true });
    }
    
    await context.close();
    
    // Save test results
    fs.writeFileSync(
        path.join(SCREENSHOT_DIR, 'test3-results.json'),
        JSON.stringify(testResults, null, 2)
    );
    
    console.log('\n--- TEST 3 COMPLETE ---');
    console.log(`Result: ${testResults.passed ? '✓ PASSED' : '✗ FAILED'}`);
    
    return testResults;
}

// ==================== MAIN EXECUTION ====================
async function runAllTests() {
    console.log('╔══════════════════════════════════════════════════════════╗');
    console.log('║    COMPREHENSIVE PLAYWRIGHT MCP TEST SUITE               ║');
    console.log('║    Target: http://localhost:8080                          ║');
    console.log('╚══════════════════════════════════════════════════════════╝\n');
    
    let browser;
    try {
        console.log('Launching browser...');
        browser = await chromium.launch({ 
            headless: true,
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });
        console.log('✓ Browser launched\n');
        
        // Run all tests
        const test1Results = await test1_DashboardGenerateStrategy(browser);
        const test2Results = await test2_ReelsGenerateReel(browser);
        const test3Results = await test3_ContentLoading(browser);
        
        // Generate final report
        const finalReport = {
            timestamp: new Date().toISOString(),
            target: 'http://localhost:8080',
            summary: {
                totalTests: 3,
                passed: [test1Results, test2Results, test3Results].filter(r => r.passed).length,
                failed: [test1Results, test2Results, test3Results].filter(r => !r.passed).length
            },
            test1: test1Results,
            test2: test2Results,
            test3: test3Results,
            allConsoleLogs: consoleLogs,
            allPageErrors: pageErrors
        };
        
        fs.writeFileSync(
            path.join(SCREENSHOT_DIR, 'FINAL-REPORT.json'),
            JSON.stringify(finalReport, null, 2)
        );
        
        // Print summary
        console.log('\n╔══════════════════════════════════════════════════════════╗');
        console.log('║                    FINAL TEST SUMMARY                    ║');
        console.log('╠══════════════════════════════════════════════════════════╣');
        console.log(`║  Test 1 (Dashboard - Generate Strategy): ${test1Results.passed ? '✓ PASSED' : '✗ FAILED'}`);
        console.log(`║  Test 2 (Reels - Generate Reel):        ${test2Results.passed ? '✓ PASSED' : '✗ FAILED'}`);
        console.log(`║  Test 3 (Content Loading):              ${test3Results.passed ? '✓ PASSED' : '✗ FAILED'}`);
        console.log('╠══════════════════════════════════════════════════════════╣');
        console.log(`║  Total: ${finalReport.summary.passed}/${finalReport.summary.totalTests} tests passed`);
        console.log('╚══════════════════════════════════════════════════════════╝\n');
        
        console.log(`All screenshots and reports saved to: ${SCREENSHOT_DIR}`);
        console.log('Files generated:');
        const files = fs.readdirSync(SCREENSHOT_DIR);
        files.forEach(file => console.log(`  - ${file}`));
        
    } catch (error) {
        console.error('Fatal Error:', error.message);
        process.exit(1);
    } finally {
        if (browser) await browser.close();
    }
}

// Run the tests
runAllTests().catch(console.error);
