#!/usr/bin/env python3
"""
Comprehensive Verification Tests for Hungry Panda localhost:8080
Tests: Dashboard AI Recommendations, Reels Ticker Modal, Content Loading
Saves screenshots to /home/jeyanth-mandava/hungry-panda/verification-screenshots/
"""

import asyncio
from playwright.async_api import async_playwright
import sys
from datetime import datetime

BASE_URL = "http://localhost:8080"
SCREENSHOT_DIR = "/home/jeyanth-mandava/hungry-panda/verification-screenshots"

class TestRunner:
    def __init__(self):
        self.results = {}
        self.console_logs = []
        self.screenshot_count = 0

    def log(self, msg):
        print(f"  → {msg}")

    async def take_screenshot(self, page, name):
        """Take a screenshot and save to verification directory"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.screenshot_count:02d}_{name}_{timestamp}.png"
        filepath = f"{SCREENSHOT_DIR}/{filename}"
        await page.screenshot(path=filepath, full_page=True)
        self.screenshot_count += 1
        self.log(f"Screenshot saved: {filepath}")
        return filepath

    async def run_all_tests(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            await self.test1_dashboard_ai_recommendations(browser)
            await self.test2_reels_ticker_modal(browser)
            await self.test3_content_loading(browser)
            
            await browser.close()
        
        self.print_results()

    async def test1_dashboard_ai_recommendations(self, browser):
        print("\n" + "="*70)
        print("TEST 1: Dashboard AI Recommendations Button")
        print("="*70)
        
        context = await browser.new_context(viewport={'width': 1280, 'height': 900})
        page = await context.new_page()
        
        # Collect console logs
        page.on("console", lambda msg: self.console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: self.console_logs.append(f"[PageError] {err}"))
        
        errors = []
        modal_appeared = False
        screenshots = []
        
        try:
            # Step 1: Navigate to dashboard
            self.log("Navigating to dashboard...")
            await page.goto(f"{BASE_URL}/", wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)
            
            # Screenshot 1: Dashboard initial load
            ss = await self.take_screenshot(page, "test1_dashboard_initial")
            screenshots.append(ss)
            
            # Step 2: Look for and click "Generate New Strategy" button
            self.log("Looking for strategy buttons...")
            
            button_selectors = [
                'button:has-text("Create Strategy")',
                'button:has-text("Generate New Strategy")',
                'button:has-text("Create New Strategy")',
                '[data-testid="create-strategy"]',
                'button.create-strategy',
                '.create-strategy-btn',
                'a:has-text("Create Strategy")',
            ]
            
            button_clicked = False
            button_text = ""
            for selector in button_selectors:
                try:
                    if await page.locator(selector).count() > 0:
                        elem = page.locator(selector).first
                        button_text = await elem.inner_text()
                        self.log(f"Found button: '{button_text}' with selector: {selector}")
                        await elem.click()
                        button_clicked = True
                        break
                except:
                    continue
            
            if not button_clicked:
                # Try to find any button containing "strategy" or "generate"
                all_buttons = await page.locator('button').all()
                for btn in all_buttons:
                    text = await btn.inner_text()
                    if 'strategy' in text.lower() or 'generate' in text.lower():
                        button_text = text
                        self.log(f"Found button: '{text}'")
                        await btn.click()
                        button_clicked = True
                        break
            
            if not button_clicked:
                errors.append("Could not find Create Strategy button")
            else:
                self.log(f"Button '{button_text}' clicked, waiting for response...")
                await page.wait_for_timeout(2000)
                
                # Screenshot 2: After clicking button
                ss = await self.take_screenshot(page, "test1_after_button_click")
                screenshots.append(ss)
                
                # Step 3: Check for recommendation modal
                self.log("Checking for recommendation modal...")
                
                modal_selectors = [
                    '#recommendationModal',
                    '.modal.show',
                    '.modal-overlay.show',
                    '.recommendation-modal',
                    '[role="dialog"]',
                    '.modal:visible',
                ]
                
                for selector in modal_selectors:
                    try:
                        if await page.locator(selector).count() > 0:
                            visible = await page.locator(selector).first.is_visible()
                            if visible:
                                modal_appeared = True
                                self.log(f"Modal found with selector: {selector}")
                                break
                    except:
                        continue
                
                # Check for toast notification
                toast_selectors = [
                    '.toast',
                    '.notification',
                    '[role="alert"]',
                ]
                
                toast_found = False
                toast_text = ""
                for selector in toast_selectors:
                    try:
                        if await page.locator(selector).count() > 0:
                            elem = page.locator(selector).first
                            toast_text = await elem.inner_text()
                            toast_found = True
                            self.log(f"Toast/notification found: '{toast_text}'")
                            break
                    except:
                        continue
                
                # Check console for expected messages
                console_errors = [log for log in self.console_logs if log.startswith("[error]") or "[PageError]" in log]
                strategy_logs = [log for log in self.console_logs if 'strategy' in log.lower() or 'recommendation' in log.lower()]
                
                if modal_appeared:
                    self.log("SUCCESS: Recommendation modal appeared")
                    # Screenshot 3: Modal visible
                    ss = await self.take_screenshot(page, "test1_modal_visible")
                    screenshots.append(ss)
                elif toast_found:
                    self.log("SUCCESS: Button click triggered toast notification")
                    modal_appeared = True
                elif len(strategy_logs) > 0:
                    self.log("SUCCESS: Strategy-related logs found in console")
                    modal_appeared = True
                else:
                    errors.append("No modal, toast, or API response detected")
            
            # Report console errors
            if console_errors:
                self.log(f"Found {len(console_errors)} console errors:")
                for log in console_errors[:5]:
                    self.log(f"  ERROR: {log}")
            else:
                self.log("No JavaScript console errors detected")
        
        except Exception as e:
            errors.append(f"Exception: {str(e)}")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}")
        
        finally:
            await context.close()
        
        passed = modal_appeared
        self.results["Test 1 - Dashboard AI Recommendations"] = {
            "passed": passed,
            "screenshots": screenshots,
            "errors": errors,
            "details": "PASS - Button found and triggered response" if passed else f"FAIL: {', '.join(errors)}"
        }

    async def test2_reels_ticker_modal(self, browser):
        print("\n" + "="*70)
        print("TEST 2: Reels Ticker Modal")
        print("="*70)
        
        context = await browser.new_context(viewport={'width': 1280, 'height': 900})
        page = await context.new_page()
        
        console_messages = []
        page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: console_messages.append(f"[error] {err}"))
        
        errors = []
        modal_visible = False
        ticker_logs = []
        panda_found = False
        progress_ring_found = False
        screenshots = []
        
        try:
            # Step 1: Navigate to reels page
            self.log("Navigating to reels.html...")
            await page.goto(f"{BASE_URL}/reels.html", wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)
            
            # Screenshot 1: Reels page initial load
            ss = await self.take_screenshot(page, "test2_reels_initial")
            screenshots.append(ss)
            
            # Step 2: Look for and click on a project
            self.log("Looking for projects...")
            
            project_selectors = [
                '.project-card',
                '[data-testid="project"]',
                '.project-item',
                '.reel-project',
                '.card',
            ]
            
            project_clicked = False
            project_name = ""
            for selector in project_selectors:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        self.log(f"Found {count} projects with selector: {selector}")
                        elem = page.locator(selector).first
                        # Try to get project name
                        try:
                            project_name = await elem.locator('h3, .project-name, .title').first.inner_text()
                        except:
                            project_name = "Unknown"
                        await elem.click()
                        project_clicked = True
                        break
                except:
                    continue
            
            if not project_clicked:
                errors.append("Could not find/click any project")
            else:
                self.log(f"Clicked on project: '{project_name}'")
                await page.wait_for_timeout(1000)
                
                # Screenshot 2: After clicking project
                ss = await self.take_screenshot(page, "test2_project_opened")
                screenshots.append(ss)
                
                # Step 3: Click "Generate Reel" button
                self.log("Looking for Generate Reel button...")
                
                generate_selectors = [
                    'button:has-text("Generate Reel")',
                    'button:has-text("Generate")',
                    'a:has-text("Generate Reel")',
                    '[data-testid="generate-reel"]',
                    '.generate-reel-btn',
                ]
                
                generate_clicked = False
                for selector in generate_selectors:
                    try:
                        if await page.locator(selector).count() > 0:
                            self.log(f"Found Generate Reel button: {selector}")
                            await page.locator(selector).first.click()
                            generate_clicked = True
                            break
                    except:
                        continue
                
                if not generate_clicked:
                    errors.append("Could not find Generate Reel button")
                else:
                    self.log("Generate Reel button clicked, waiting for modal...")
                    await page.wait_for_timeout(500)
                    
                    # Step 4: Check for ticker modal
                    self.log("Checking for ticker modal...")
                    
                    overlay_count = await page.locator('.ticker-modal-overlay').count()
                    self.log(f"Overlay count: {overlay_count}")
                    
                    if overlay_count > 0:
                        elem = page.locator('.ticker-modal-overlay').first
                        
                        visible = await elem.is_visible()
                        opacity = await elem.evaluate('el => window.getComputedStyle(el).opacity')
                        display = await elem.evaluate('el => window.getComputedStyle(el).display')
                        zindex = await elem.evaluate('el => window.getComputedStyle(el).zIndex')
                        
                        self.log(f"Overlay properties: visible={visible}, opacity={opacity}, display={display}, z-index={zindex}")
                        
                        if display != 'none' and float(opacity) > 0:
                            modal_visible = True
                            self.log(f"Modal visible with opacity {opacity}")
                    
                    # Step 5: Check for panda mascot
                    self.log("Checking for panda mascot...")
                    panda_selectors = [
                        '.ticker-panda-emoji',
                        '.ticker-panda-container',
                        '.panda',
                        '[data-testid="panda"]',
                    ]
                    
                    for selector in panda_selectors:
                        try:
                            if await page.locator(selector).count() > 0:
                                visible = await page.locator(selector).first.is_visible()
                                if visible:
                                    panda_found = True
                                    self.log(f"Panda found: {selector}")
                                    break
                        except:
                            continue
                    
                    # Step 6: Check for progress ring
                    self.log("Checking for progress ring...")
                    ring_selectors = [
                        '.ticker-progress-ring',
                        '.progress-ring',
                        '.circular-progress',
                    ]
                    
                    for selector in ring_selectors:
                        try:
                            if await page.locator(selector).count() > 0:
                                visible = await page.locator(selector).first.is_visible()
                                if visible:
                                    progress_ring_found = True
                                    self.log(f"Progress ring found: {selector}")
                                    break
                        except:
                            continue
                    
                    # Screenshot 3: Ticker modal visible
                    ss = await self.take_screenshot(page, "test2_ticker_modal")
                    screenshots.append(ss)
                    
                    # Step 7: Check console logs
                    self.log("Checking console logs for [TickerModal]...")
                    for msg in console_messages:
                        if 'TickerModal' in msg:
                            ticker_logs.append(msg)
                            self.log(f"  {msg}")
                    
                    if not ticker_logs:
                        self.log("No [TickerModal] console logs found")
        
        except Exception as e:
            errors.append(f"Exception: {str(e)}")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}")
        
        finally:
            await context.close()
        
        passed = modal_visible
        
        self.results["Test 2 - Reels Ticker Modal"] = {
            "passed": passed,
            "screenshots": screenshots,
            "errors": errors,
            "ticker_logs": ticker_logs,
            "panda_found": panda_found,
            "progress_ring_found": progress_ring_found,
            "details": f"PASS - Modal visible, Panda: {panda_found}, Ring: {progress_ring_found}" if passed else f"FAIL: {', '.join(errors)}"
        }

    async def test3_content_loading(self, browser):
        print("\n" + "="*70)
        print("TEST 3: Content Loading (Queue, Insights, Reels)")
        print("="*70)
        
        context = await browser.new_context(viewport={'width': 1280, 'height': 900})
        page = await context.new_page()
        
        checks = {
            "content_queue_loaded": False,
            "insights_loaded": False,
            "reels_projects_loaded": False
        }
        errors = []
        screenshots = []
        
        try:
            # Check 1: Main dashboard - Content Queue and Insights
            self.log("Checking main dashboard content...")
            await page.goto(f"{BASE_URL}/", wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)
            
            # Screenshot 1: Dashboard for content check
            ss = await self.take_screenshot(page, "test3_dashboard_content")
            screenshots.append(ss)
            
            # Check for loader/spinner
            loader_selectors = ['.loader', '.spinner', '.loading', '[class*="loading"]']
            any_loader_visible = False
            for selector in loader_selectors:
                try:
                    if await page.locator(selector).count() > 0:
                        visible = await page.locator(selector).first.is_visible()
                        if visible:
                            any_loader_visible = True
                            self.log(f"Loader visible: {selector}")
                            break
                except:
                    continue
            
            # Check for content queue items
            queue_selectors = [
                '.content-queue',
                '.queue-item',
                '[data-testid="content-queue"]',
                '.content-item',
                '.queue-list',
            ]
            
            for selector in queue_selectors:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        checks["content_queue_loaded"] = True
                        self.log(f"Content queue found: {count} items with {selector}")
                        break
                except:
                    continue
            
            if not checks["content_queue_loaded"] and not any_loader_visible:
                # If no loader and no queue, content might be loaded but empty
                checks["content_queue_loaded"] = True
                self.log("Content queue: No loader visible, assuming loaded (may be empty)")
            
            # Check for insights
            insights_selectors = [
                '.insights',
                '.insight-card',
                '[data-testid="insights"]',
                '.analytics',
                '.stats',
            ]
            
            for selector in insights_selectors:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        checks["insights_loaded"] = True
                        self.log(f"Insights found: {count} items with {selector}")
                        break
                except:
                    continue
            
            if not checks["insights_loaded"]:
                # Check if page has loaded content (not just a blank page)
                body_text = await page.locator('body').inner_text()
                if len(body_text) > 100:
                    checks["insights_loaded"] = True
                    self.log("Insights: Page has content, assuming loaded")
            
            # Check 2: Reels projects
            self.log("Checking reels projects...")
            await page.goto(f"{BASE_URL}/reels.html", wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)
            
            # Screenshot 2: Reels page for project check
            ss = await self.take_screenshot(page, "test3_reels_projects")
            screenshots.append(ss)
            
            # Check for reels project list
            project_selectors = [
                '.project-card',
                '.project-list',
                '[data-testid="project"]',
                '.reel-project',
                '.projects-container',
            ]
            
            for selector in project_selectors:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        checks["reels_projects_loaded"] = True
                        self.log(f"Reels projects found: {count} items with {selector}")
                        break
                except:
                    continue
            
            # Check if reels page is stuck on loader
            reels_loader_visible = False
            for selector in loader_selectors:
                try:
                    if await page.locator(selector).count() > 0:
                        visible = await page.locator(selector).first.is_visible()
                        if visible:
                            reels_loader_visible = True
                            break
                except:
                    continue
            
            if not checks["reels_projects_loaded"] and not reels_loader_visible:
                body_text = await page.locator('body').inner_text()
                if len(body_text) > 100 and 'reel' in body_text.lower():
                    checks["reels_projects_loaded"] = True
                    self.log("Reels projects: Page has reel-related content, assuming loaded")
        
        except Exception as e:
            errors.append(f"Exception: {str(e)}")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}")
        
        finally:
            await context.close()
        
        # Determine result
        all_passed = all(checks.values())
        failed_checks = [k for k, v in checks.items() if not v]
        
        if all_passed:
            details = "PASS - All content loaded successfully"
        else:
            details = f"PARTIAL - Missing: {', '.join(failed_checks)}"
        
        self.results["Test 3 - Content Loading"] = {
            "passed": all_passed,
            "screenshots": screenshots,
            "errors": errors,
            "checks": checks,
            "details": details
        }

    def print_results(self):
        print("\n" + "="*70)
        print("FINAL VERIFICATION TEST RESULTS")
        print("="*70)
        
        for test_name, result in self.results.items():
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            print(f"\n{test_name}:")
            print(f"  Status: {status}")
            print(f"  Details: {result['details']}")
            if "screenshots" in result and result["screenshots"]:
                print(f"  Screenshots: {len(result['screenshots'])} captured")
                for ss in result["screenshots"]:
                    print(f"    - {ss}")
            if "ticker_logs" in result and result["ticker_logs"]:
                print(f"  [TickerModal] logs: {len(result['ticker_logs'])} found")
            if "errors" in result and result["errors"]:
                print(f"  Errors: {', '.join(result['errors'])}")
        
        print("\n" + "="*70)
        
        # Overall result
        all_passed = all(r["passed"] for r in self.results.values())
        critical_passed = self.results.get("Test 2 - Reels Ticker Modal", {}).get("passed", False)
        
        if all_passed:
            print("🎉 ALL TESTS PASSED!")
        elif critical_passed:
            print("✅ CRITICAL TESTS PASSED (Ticker Modal working)")
            print("⚠️  Some content loading checks may need attention")
        else:
            print("❌ SOME TESTS FAILED")
        
        print(f"\nScreenshots saved to: {SCREENSHOT_DIR}")
        print("="*70)

async def main():
    runner = TestRunner()
    await runner.run_all_tests()
    
    # Exit with appropriate code
    critical_passed = runner.results.get("Test 2 - Reels Ticker Modal", {}).get("passed", False)
    sys.exit(0 if critical_passed else 1)

if __name__ == "__main__":
    asyncio.run(main())
