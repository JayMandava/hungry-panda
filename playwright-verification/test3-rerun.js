const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const SCREENSHOT_DIR = '/home/jeyanth-mandava/hungry-panda/playwright-verification';

async function test3ContentLoading() {
    console.log('\n========================================');
    console.log('TEST 3: Verify Content Loading (Re-run)');
    console.log('========================================\n');
    
    const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await context.newPage();
    
    const consoleLogs = [];
    page.on('console', msg => {
        consoleLogs.push(`[${msg.type()}] ${msg.text()}`);
    });
    
    const testResults = {
        testName: 'TEST 3: Verify Content Loading',
        checks: [],
        passed: true
    };
    
    try {
        // Check 1: Content Queue
        console.log('Check 1: Content Queue Loading State');
        await page.goto('http://localhost:8080/', { waitUntil: 'domcontentloaded', timeout: 15000 });
        await page.waitForTimeout(3000);
        
        // Check for various loading indicators
        const loadingSelectors = [
            'text=Loading',
            'text=loading',
            '.loading',
            '.spinner',
            '[data-loading]'
        ];
        
        let loadingElements = [];
        for (const selector of loadingSelectors) {
            try {
                const elements = await page.locator(selector);
                const count = await elements.count();
                if (count > 0) {
                    for (let i = 0; i < Math.min(count, 3); i++) {
                        const el = elements.nth(i);
                        if (await el.isVisible()) {
                            const text = await el.textContent();
                            loadingElements.push({ selector, text: text?.substring(0, 50) });
                        }
                    }
                }
            } catch (e) {}
        }
        
        console.log(`  Loading indicators found: ${loadingElements.length}`);
        loadingElements.forEach(e => console.log(`    - ${e.selector}: "${e.text}"`));
        
        // Check content sections
        const sections = [
            { name: 'Content Queue', selectors: ['.content-queue', '.queue-section', '.queue'] },
            { name: 'Insights', selectors: ['.insights', '.insights-section', '.stats'] },
            { name: 'Strategy Status', selectors: ['.strategy-status', '.status-card'] },
            { name: 'Recent Content', selectors: ['.recent-content', '.content-list'] }
        ];
        
        for (const section of sections) {
            let found = false;
            let content = '';
            for (const selector of section.selectors) {
                try {
                    const el = await page.locator(selector).first();
                    if (await el.count() > 0 && await el.isVisible()) {
                        found = true;
                        content = await el.textContent();
                        break;
                    }
                } catch (e) {}
            }
            const status = found ? (content.toLowerCase().includes('loading') ? 'LOADING' : 'LOADED') : 'NOT_FOUND';
            console.log(`  ${section.name}: ${status}`);
            testResults.checks.push({ section: section.name, status, found });
        }
        
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'test3-01-dashboard.png'), fullPage: true });
        console.log('✓ Screenshot: test3-01-dashboard.png\n');
        
        // Check 2: Reels page
        console.log('Check 2: Reels Page Content');
        await page.goto('http://localhost:8080/reels.html', { waitUntil: 'domcontentloaded', timeout: 15000 });
        await page.waitForTimeout(3000);
        
        const reelsSections = [
            { name: 'Projects List', selectors: ['.projects-list', '.reels-list', '.project-grid'] },
            { name: 'Project Cards', selectors: ['.project-card', '.reel-card', '.card'] },
            { name: 'New Project Button', selectors: ['button:has-text("New")', 'button:has-text("Create")', '.new-project-btn'] }
        ];
        
        for (const section of reelsSections) {
            let found = false;
            let count = 0;
            for (const selector of section.selectors) {
                try {
                    const els = await page.locator(selector);
                    const c = await els.count();
                    if (c > 0) {
                        found = true;
                        count = c;
                        break;
                    }
                } catch (e) {}
            }
            console.log(`  ${section.name}: ${found ? 'FOUND' : 'NOT_FOUND'} (${count} items)`);
            testResults.checks.push({ section: section.name, status: found ? 'FOUND' : 'NOT_FOUND', count });
        }
        
        await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'test3-02-reels.png'), fullPage: true });
        console.log('✓ Screenshot: test3-02-reels.png\n');
        
        // Check for console errors
        const errors = consoleLogs.filter(log => log.includes('error') || log.includes('Error'));
        console.log(`Console errors: ${errors.length}`);
        errors.forEach(e => console.log(`  ${e}`));
        
        testResults.consoleErrors = errors;
        testResults.passed = errors.length === 0;
        
    } catch (error) {
        console.error('Test 3 Error:', error.message);
        testResults.error = error.message;
        testResults.passed = false;
    }
    
    await browser.close();
    
    fs.writeFileSync(
        path.join(SCREENSHOT_DIR, 'test3-results.json'),
        JSON.stringify(testResults, null, 2)
    );
    
    console.log('\n--- TEST 3 COMPLETE ---');
    console.log(`Result: ${testResults.passed ? '✓ PASSED' : '✗ FAILED'}`);
    
    return testResults;
}

test3ContentLoading().catch(console.error);
