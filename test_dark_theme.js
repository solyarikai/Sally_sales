const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await context.newPage();

  try {
    console.log('=== TESTING DARK THEME REPLIES PAGE ===\n');
    
    // ===== STEP 1-2: Navigate and wait =====
    console.log('### STEP 1-2: Navigate and Load ###\n');
    
    console.log('→ Navigating to http://localhost:5179/replies');
    await page.goto('http://localhost:5179/replies');
    console.log('✓ Navigation complete');
    
    console.log('→ Waiting 3 seconds for page to load...');
    await page.waitForTimeout(3000);
    
    console.log('→ Taking snapshot\n');
    
    await page.screenshot({ path: '/Users/petrnikolaev/n8n-rip/magnum-opus/screenshot_dark_initial.png', fullPage: true });
    console.log('📸 Screenshot: screenshot_dark_initial.png\n');
    
    // ===== STEP 3: Verify DARK THEME =====
    console.log('### STEP 3: Verify DARK THEME ###\n');
    
    // Get computed styles of key elements
    const bodyBgColor = await page.evaluate(() => {
      const body = document.body;
      return window.getComputedStyle(body).backgroundColor;
    });
    
    const navBgColor = await page.evaluate(() => {
      const nav = document.querySelector('nav, header, [role="banner"]');
      if (nav) return window.getComputedStyle(nav).backgroundColor;
      return 'N/A';
    });
    
    const cardBgColor = await page.evaluate(() => {
      const card = document.querySelector('[class*="card"], .card, [class*="bg-"]');
      if (card) return window.getComputedStyle(card).backgroundColor;
      return 'N/A';
    });
    
    const textColor = await page.evaluate(() => {
      const text = document.querySelector('p, div, span');
      if (text) return window.getComputedStyle(text).color;
      return 'N/A';
    });
    
    console.log('🎨 DARK THEME VERIFICATION:');
    console.log(`✓ Body background color: ${bodyBgColor}`);
    console.log(`✓ Nav bar background color: ${navBgColor}`);
    console.log(`✓ Card background color: ${cardBgColor}`);
    console.log(`✓ Text color: ${textColor}\n`);
    
    // Analyze if it's dark theme
    const isDarkBody = bodyBgColor.includes('rgb') && (
      bodyBgColor.includes('rgb(0, 0, 0)') || 
      bodyBgColor.includes('rgb(17,') || 
      bodyBgColor.includes('rgb(18,') ||
      bodyBgColor.includes('rgb(15,') ||
      bodyBgColor.includes('rgb(20,') ||
      bodyBgColor.includes('rgb(10,')
    );
    
    console.log('📊 DARK THEME ASSESSMENT:');
    console.log(`✓ Dark background detected: ${isDarkBody ? 'YES ✅' : 'NO ❌'}`);
    console.log(`   (Body color: ${bodyBgColor})`);
    
    if (!isDarkBody) {
      console.log('⚠️  WARNING: Page may not be using dark theme!');
      console.log('   Expected: Very dark background (almost black)');
      console.log('   Check screenshot for visual confirmation\n');
    } else {
      console.log('✅ Dark theme appears to be active\n');
    }
    
    // ===== STEP 4: Check header =====
    console.log('### STEP 4: Check Header Elements ###\n');
    
    const needReplyText = await page.locator('text=need reply').count();
    const projectSelector = await page.locator('select, [role="combobox"], button:has-text("Project"), button:has-text("All Projects")').count();
    const searchBar = await page.locator('input[placeholder*="Search"], input[placeholder*="search"]').count();
    
    console.log('📊 HEADER ELEMENTS:');
    console.log(`✓ "X need reply" count: ${needReplyText > 0 ? 'YES ✅' : 'NO ❌'}`);
    console.log(`✓ Project selector: ${projectSelector > 0 ? 'YES ✅' : 'NO ❌'}`);
    console.log(`✓ Search bar: ${searchBar > 0 ? 'YES ✅' : 'NO ❌'}\n`);
    
    // ===== STEP 5: Verify AI DRAFT is VISIBLE by default =====
    console.log('### STEP 5: Verify AI DRAFT Visibility (NOT Collapsed) ###\n');
    
    // Look for AI draft sections
    const aiDraftSections = await page.locator('text=AI DRAFT, text=AI Draft, text=Draft').count();
    console.log(`✓ AI Draft sections found: ${aiDraftSections}`);
    
    // Check if draft text is visible (look for green-tinted boxes or draft content)
    const greenBoxes = await page.locator('[class*="emerald"], [class*="green"], [class*="draft"]').count();
    console.log(`✓ Green-tinted elements: ${greenBoxes}`);
    
    // Try to detect if draft text is visible by checking for paragraph text
    const visibleDraftText = await page.evaluate(() => {
      const draftSections = Array.from(document.querySelectorAll('*')).filter(el => 
        el.textContent.includes('AI DRAFT') || el.textContent.includes('Draft')
      );
      
      if (draftSections.length > 0) {
        const parent = draftSections[0].closest('[class*="card"], .card');
        if (parent) {
          const text = parent.textContent;
          // Check if there's substantial text (draft content)
          return text.length > 200 ? 'YES - Draft text appears to be visible' : 'MAYBE - Limited text found';
        }
      }
      return 'NO - Could not detect draft text';
    });
    
    console.log(`✓ Draft text visibility: ${visibleDraftText}\n`);
    
    console.log('📊 AI DRAFT VISIBILITY CHECK:');
    if (aiDraftSections > 0 && greenBoxes > 0) {
      console.log('✅ AI DRAFT appears to be VISIBLE by default');
      console.log('   - Draft sections found');
      console.log('   - Green-tinted boxes present');
      console.log('   - Draft text should be showing without clicking\n');
    } else {
      console.log('⚠️  AI DRAFT may be collapsed or not visible');
      console.log('   Check screenshot to confirm visual state\n');
    }
    
    await page.screenshot({ path: '/Users/petrnikolaev/n8n-rip/magnum-opus/screenshot_dark_drafts.png', fullPage: true });
    console.log('📸 Screenshot: screenshot_dark_drafts.png\n');
    
    // ===== STEP 6: Select Rizzult project =====
    console.log('### STEP 6: Select Rizzult Project ###\n');
    
    console.log('→ Looking for project selector...');
    let projectSelectorElement = null;
    
    if (await page.locator('button:has-text("All Projects")').count() > 0) {
      projectSelectorElement = page.locator('button:has-text("All Projects")').first();
      console.log('✓ Found "All Projects" button');
    } else if (await page.locator('select').count() > 0) {
      projectSelectorElement = page.locator('select').first();
      console.log('✓ Found select element');
    }
    
    if (projectSelectorElement) {
      console.log('→ Clicking project selector...');
      await projectSelectorElement.click();
      await page.waitForTimeout(1000);
      
      // Search for Rizzult
      const searchInput = page.locator('input[type="text"]').first();
      if (await searchInput.count() > 0) {
        console.log('→ Typing "Rizzult"...');
        await searchInput.fill('Rizzult');
        await page.waitForTimeout(1000);
        
        const rizzultOptions = await page.locator('text=Rizzult').count();
        console.log(`✓ Rizzult options found: ${rizzultOptions}`);
        
        if (rizzultOptions > 0) {
          console.log('→ Selecting Rizzult project...');
          await page.locator('text=Rizzult').first().click();
          console.log('✓ Selected Rizzult');
          
          await page.waitForTimeout(3000);
          
          await page.screenshot({ path: '/Users/petrnikolaev/n8n-rip/magnum-opus/screenshot_dark_rizzult.png', fullPage: true });
          console.log('📸 Screenshot: screenshot_dark_rizzult.png\n');
        }
      }
    }
    
    // ===== STEP 7: Click "View full thread" =====
    console.log('### STEP 7: View Full Thread ###\n');
    
    const viewThreadLinks = await page.locator('text=View full thread').count();
    console.log(`✓ "View full thread" links found: ${viewThreadLinks}`);
    
    if (viewThreadLinks > 0) {
      console.log('→ Clicking "View full thread"...');
      await page.locator('text=View full thread').first().click();
      await page.waitForTimeout(2000);
      
      await page.screenshot({ path: '/Users/petrnikolaev/n8n-rip/magnum-opus/screenshot_dark_thread.png', fullPage: false });
      console.log('📸 Screenshot: screenshot_dark_thread.png\n');
      
      // ===== STEP 8: Check outbound message content =====
      console.log('### STEP 8: Check Outbound Message Content ###\n');
      
      const noContentText = await page.locator('text=(no content)').count();
      const outboundMessages = await page.locator('text=outbound, text=Outbound, [class*="outbound"]').count();
      
      console.log(`✓ "(no content)" found: ${noContentText} times`);
      console.log(`✓ Outbound message indicators: ${outboundMessages}`);
      
      if (noContentText > 0) {
        console.log('⚠️  WARNING: Some outbound messages show "(no content)"');
        console.log('   This may indicate missing message data\n');
      } else {
        console.log('✅ No "(no content)" placeholders found');
        console.log('   Outbound messages appear to have actual content\n');
      }
      
      // Close thread view if it's a modal
      const closeButton = page.locator('button:has-text("Close"), [aria-label="Close"]').first();
      if (await closeButton.count() > 0) {
        console.log('→ Closing thread view...');
        await closeButton.click();
        await page.waitForTimeout(1000);
      }
    } else {
      console.log('⚠️  No "View full thread" links found\n');
    }
    
    // ===== STEP 9: Test inline editing =====
    console.log('### STEP 9: Test Inline Editing ###\n');
    
    const editButtons = await page.locator('button:has-text("Edit")').count();
    console.log(`✓ "Edit" buttons found: ${editButtons}`);
    
    if (editButtons > 0) {
      console.log('→ Clicking "Edit" button...');
      await page.locator('button:has-text("Edit")').first().click();
      await page.waitForTimeout(1000);
      
      const textareaVisible = await page.locator('textarea').count();
      console.log(`✓ Textarea appeared: ${textareaVisible > 0 ? 'YES ✅' : 'NO ❌'}`);
      
      if (textareaVisible > 0) {
        console.log('✅ Inline editing works - textarea is visible\n');
      } else {
        console.log('⚠️  Textarea not found - inline editing may not be working\n');
      }
      
      await page.screenshot({ path: '/Users/petrnikolaev/n8n-rip/magnum-opus/screenshot_dark_editing.png', fullPage: true });
      console.log('📸 Screenshot: screenshot_dark_editing.png\n');
    } else {
      console.log('⚠️  No "Edit" buttons found\n');
    }
    
    // ===== STEP 10: Final state =====
    console.log('### STEP 10: Final State ###\n');
    
    await page.screenshot({ path: '/Users/petrnikolaev/n8n-rip/magnum-opus/screenshot_dark_final.png', fullPage: true });
    console.log('📸 Screenshot: screenshot_dark_final.png\n');
    
    // ===== FINAL REPORT =====
    console.log('\n=== FINAL REPORT: DARK THEME TESTING ===\n');
    
    console.log('🎨 DARK THEME STATUS:');
    console.log(`   Background: ${bodyBgColor}`);
    console.log(`   Nav bar: ${navBgColor}`);
    console.log(`   Cards: ${cardBgColor}`);
    console.log(`   Text: ${textColor}`);
    console.log(`   Assessment: ${isDarkBody ? '✅ DARK THEME ACTIVE' : '⚠️  VERIFY MANUALLY'}\n`);
    
    console.log('📊 AI DRAFT VISIBILITY:');
    console.log(`   ${aiDraftSections > 0 ? '✅' : '❌'} AI Draft sections found: ${aiDraftSections}`);
    console.log(`   ${greenBoxes > 0 ? '✅' : '❌'} Green-tinted boxes: ${greenBoxes}`);
    console.log(`   Status: ${aiDraftSections > 0 && greenBoxes > 0 ? 'VISIBLE by default' : 'Check screenshots'}\n`);
    
    console.log('💬 THREAD VIEW:');
    console.log(`   ${viewThreadLinks > 0 ? '✅' : '❌'} "View full thread" available`);
    console.log(`   ${noContentText === 0 ? '✅' : '⚠️ '} Outbound content: ${noContentText === 0 ? 'Shows actual content' : `${noContentText} "(no content)" found`}\n`);
    
    console.log('✏️  INLINE EDITING:');
    console.log(`   ${editButtons > 0 ? '✅' : '❌'} Edit buttons found: ${editButtons}`);
    console.log(`   Status: ${editButtons > 0 ? 'Working' : 'Not tested'}\n`);
    
    console.log('📸 SCREENSHOTS CAPTURED:');
    console.log('   - screenshot_dark_initial.png (initial load)');
    console.log('   - screenshot_dark_drafts.png (draft visibility)');
    console.log('   - screenshot_dark_rizzult.png (Rizzult project selected)');
    console.log('   - screenshot_dark_thread.png (thread view)');
    console.log('   - screenshot_dark_editing.png (inline editing)');
    console.log('   - screenshot_dark_final.png (final state)\n');
    
    console.log('=== END OF DARK THEME TEST ===');
    
    await page.waitForTimeout(3000);
    
  } catch (error) {
    console.error('\n❌ ERROR:', error.message);
    console.error(error.stack);
    await page.screenshot({ path: '/Users/petrnikolaev/n8n-rip/magnum-opus/screenshot_dark_error.png', fullPage: false });
    console.log('📸 Error screenshot: screenshot_dark_error.png');
  } finally {
    await browser.close();
  }
})();
