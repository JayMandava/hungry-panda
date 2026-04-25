const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();

    try {
        console.log('=== COMPREHENSIVE REELS MODAL TEST ===\n');

        await page.goto('http://localhost:8080/reels.html', { waitUntil: 'domcontentloaded' });
        await page.waitForTimeout(2000);

        await page.locator('.project-card').first().click();
        await page.waitForTimeout(2000);

        // Check context input
        const contextInput = await page.locator('#reelContextText');
        console.log('1. Context input visible:', await contextInput.isVisible());

        await contextInput.fill('Crispy dosa with chutney');
        await page.click('#getRecommendationsBtn');

        console.log('\n2. Waiting for API (90s)...');
        await page.waitForTimeout(90000);

        const modal = page.locator('#recommendationModal');
        const visible = await modal.isVisible();
        console.log('\n3. Modal visible:', visible);

        if (visible) {
            // Full content analysis
            const html = await modal.locator('#recommendationModalContent').innerHTML();

            console.log('\n4. STRUCTURE CHECKS:');
            console.log('   - variant-cards:', html.includes('variant-cards') ? '✅' : '❌');
            console.log('   - variant-card:', html.includes('variant-card') ? '✅' : '❌');
            console.log('   - modal-hashtags:', html.includes('modal-hashtags') ? '✅' : '❌');
            console.log('   - hashtag-chip:', html.includes('hashtag-chip') ? '✅' : '❌');
            console.log('   - modal-actions:', html.includes('modal-actions') ? '✅' : '❌');
            console.log('   - btn-primary:', html.includes('btn-primary') ? '✅' : '❌');

            console.log('\n5. ISSUE CHECKS:');
            console.log('   - Has template artifacts ${}:', html.includes('${') ? '❌ YES' : '✅ No');
            console.log('   - Has double ##:', html.includes('##') ? '❌ YES' : '✅ No');

            // Button text
            const schedule = await modal.locator('#modalScheduleBtn').textContent();
            console.log('\n6. Button text: "' + schedule.trim() + '"');

            // Hashtags
            const chips = await modal.locator('.hashtag-chip').all();
            console.log('\n7. Hashtag count:', chips.length);
            if (chips.length > 0) {
                const first = await chips[0].textContent();
                console.log('   First hashtag: "' + first + '"');
            }

            // Check time badge
            const timeBadge = await modal.locator('.time-badge').textContent().catch(() => 'Not found');
            console.log('\n8. Time badge:', timeBadge);

            // Mobile viewport test
            console.log('\n9. Testing mobile viewport...');
        }

        await browser.close();

        // Now launch mobile test
        console.log('\n=== MOBILE TEST ===');
        const mobileBrowser = await chromium.launch({ headless: true });
        const mobilePage = await mobileBrowser.newPage({
            viewport: { width: 390, height: 844 },
            deviceScaleFactor: 2
        });

        await mobilePage.goto('http://localhost:8080/reels.html', { waitUntil: 'domcontentloaded' });
        await mobilePage.waitForTimeout(2000);
        await mobilePage.locator('.project-card').first().click();
        await mobilePage.waitForTimeout(2000);
        await mobilePage.fill('#reelContextText', 'Mobile test');
        await mobilePage.click('#getRecommendationsBtn');
        await mobilePage.waitForTimeout(90000);

        const mobileModal = mobilePage.locator('#recommendationModal');
        const mobileVisible = await mobileModal.isVisible();
        console.log('Mobile modal visible:', mobileVisible);

        if (mobileVisible) {
            const box = await mobileModal.boundingBox();
            console.log('Modal width:', box ? box.width : 'unknown');
            console.log('Fits mobile screen:', (box && box.width <= 400) ? '✅' : '❌');
        }

        await mobileBrowser.close();

        console.log('\n=== TEST COMPLETE ===');

    } catch (err) {
        console.log('ERROR:', err.message);
        console.log(err.stack);
        await browser.close();
    }
})();
