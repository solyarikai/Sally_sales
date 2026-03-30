const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await context.newPage();

  try {
    console.log('=== CURSOR IDE DARK THEME VERIFICATION ===\n');
    
    // Navigate to page
    console.log('→ Navigating to http://localhost:5179/replies');
    await page.goto('http://localhost:5179/replies');
    await page.waitForTimeout(3000);
    console.log('✓ Page loaded\n');
    
    // Take initial screenshot
    await page.screenshot({ path: '/Users/petrnikolaev/n8n-rip/magnum-opus/screenshot_cursor_theme_initial.png', fullPage: true });
    console.log('📸 Screenshot: screenshot_cursor_theme_initial.png\n');
    
    // Get actual color values
    console.log('=== COLOR VALUES INSPECTION ===\n');
    
    const colors = await page.evaluate(() => {
      const results = {};
      
      // Main page background
      const body = document.body;
      results.pageBackground = window.getComputedStyle(body).backgroundColor;
      
      // Nav bar
      const nav = document.querySelector('nav, header, [role="banner"]');
      if (nav) {
        results.navBar = window.getComputedStyle(nav).backgroundColor;
      }
      
      // Card background
      const card = document.querySelector('[class*="card"], .card, [class*="bg-"]');
      if (card) {
        results.cardBackground = window.getComputedStyle(card).backgroundColor;
      }
      
      // Primary text
      const primaryText = document.querySelector('p, div[class*="text"]');
      if (primaryText) {
        results.primaryText = window.getComputedStyle(primaryText).color;
      }
      
      // Secondary text (look for muted/gray text)
      const allText = Array.from(document.querySelectorAll('span, small, [class*="text-gray"]'));
      if (allText.length > 0) {
        results.secondaryText = window.getComputedStyle(allText[0]).color;
      }
      
      // Border color
      const borderedElement = document.querySelector('[class*="border"]');
      if (borderedElement) {
        results.border = window.getComputedStyle(borderedElement).borderColor;
      }
      
      // Input background
      const input = document.querySelector('input');
      if (input) {
        results.inputBackground = window.getComputedStyle(input).backgroundColor;
      }
      
      // Button background
      const button = document.querySelector('button');
      if (button) {
        results.buttonBackground = window.getComputedStyle(button).backgroundColor;
      }
      
      return results;
    });
    
    // Convert RGB to hex for comparison
    const rgbToHex = (rgb) => {
      if (!rgb) return 'N/A';
      const match = rgb.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
      if (!match) return rgb;
      
      const r = parseInt(match[1]);
      const g = parseInt(match[2]);
      const b = parseInt(match[3]);
      
      return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
    };
    
    console.log('📊 ACTUAL COLOR VALUES:\n');
    console.log(`Main page background:  ${colors.pageBackground || 'N/A'}`);
    console.log(`                       ${rgbToHex(colors.pageBackground)}`);
    console.log();
    console.log(`Nav bar background:    ${colors.navBar || 'N/A'}`);
    console.log(`                       ${rgbToHex(colors.navBar)}`);
    console.log();
    console.log(`Card background:       ${colors.cardBackground || 'N/A'}`);
    console.log(`                       ${rgbToHex(colors.cardBackground)}`);
    console.log();
    console.log(`Primary text:          ${colors.primaryText || 'N/A'}`);
    console.log(`                       ${rgbToHex(colors.primaryText)}`);
    console.log();
    console.log(`Secondary text:        ${colors.secondaryText || 'N/A'}`);
    console.log(`                       ${rgbToHex(colors.secondaryText)}`);
    console.log();
    console.log(`Border color:          ${colors.border || 'N/A'}`);
    console.log(`                       ${rgbToHex(colors.border)}`);
    console.log();
    console.log(`Input background:      ${colors.inputBackground || 'N/A'}`);
    console.log(`                       ${rgbToHex(colors.inputBackground)}`);
    console.log();
    console.log(`Button background:     ${colors.buttonBackground || 'N/A'}`);
    console.log(`                       ${rgbToHex(colors.buttonBackground)}`);
    console.log();
    
    // Compare with Cursor IDE target values
    console.log('=== COMPARISON WITH CURSOR IDE THEME ===\n');
    
    const targets = {
      background: '#1e1e1e',
      card: '#252526',
      primaryText: '#d4d4d4',
      secondaryText: '#969696',
      border: '#333333',
      activeHighlight: '#37373d',
      input: '#3c3c3c'
    };
    
    console.log('Target vs Actual:\n');
    console.log(`Background:     ${targets.background} → ${rgbToHex(colors.pageBackground)}`);
    console.log(`Card:           ${targets.card} → ${rgbToHex(colors.cardBackground)}`);
    console.log(`Primary Text:   ${targets.primaryText} → ${rgbToHex(colors.primaryText)}`);
    console.log(`Secondary Text: ${targets.secondaryText} → ${rgbToHex(colors.secondaryText)}`);
    console.log(`Border:         ${targets.border} → ${rgbToHex(colors.border)}`);
    console.log(`Input:          ${targets.input} → ${rgbToHex(colors.inputBackground)}`);
    console.log();
    
    // Select Rizzult project
    console.log('→ Selecting Rizzult project...');
    
    const projectSelector = page.locator('button:has-text("All Projects"), button:has-text("Projects")').first();
    if (await projectSelector.count() > 0) {
      await projectSelector.click();
      await page.waitForTimeout(1000);
      
      const searchInput = page.locator('input[type="text"]').first();
      if (await searchInput.count() > 0) {
        await searchInput.fill('Rizzult');
        await page.waitForTimeout(1000);
        
        await page.locator('text=Rizzult').first().click();
        console.log('✓ Selected Rizzult');
        
        await page.waitForTimeout(3000);
      }
    }
    
    // Take Rizzult screenshot
    await page.screenshot({ path: '/Users/petrnikolaev/n8n-rip/magnum-opus/screenshot_cursor_theme_rizzult.png', fullPage: true });
    console.log('📸 Screenshot: screenshot_cursor_theme_rizzult.png\n');
    
    // Readability check
    console.log('=== READABILITY ASSESSMENT ===\n');
    
    const readability = await page.evaluate(() => {
      // Get sample text from message and draft
      const messageText = document.querySelector('[class*="message"], p');
      const draftText = document.querySelector('[class*="draft"]');
      
      const messageColor = messageText ? window.getComputedStyle(messageText).color : null;
      const draftColor = draftText ? window.getComputedStyle(draftText).color : null;
      
      const messageBg = messageText ? window.getComputedStyle(messageText.closest('[class*="card"], .card') || document.body).backgroundColor : null;
      
      return {
        messageColor,
        draftColor,
        messageBg
      };
    });
    
    console.log('Text samples:\n');
    console.log(`Message text color:    ${readability.messageColor}`);
    console.log(`                       ${rgbToHex(readability.messageColor)}`);
    console.log();
    console.log(`Draft text color:      ${readability.draftColor || 'Same as message'}`);
    console.log(`                       ${rgbToHex(readability.draftColor)}`);
    console.log();
    console.log(`Message background:    ${readability.messageBg}`);
    console.log(`                       ${rgbToHex(readability.messageBg)}`);
    console.log();
    
    // Calculate contrast ratio
    const calculateContrast = (rgb1, rgb2) => {
      if (!rgb1 || !rgb2) return 'N/A';
      
      const match1 = rgb1.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
      const match2 = rgb2.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
      
      if (!match1 || !match2) return 'N/A';
      
      const getLuminance = (r, g, b) => {
        const [rs, gs, bs] = [r, g, b].map(val => {
          val = val / 255;
          return val <= 0.03928 ? val / 12.92 : Math.pow((val + 0.055) / 1.055, 2.4);
        });
        return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
      };
      
      const l1 = getLuminance(parseInt(match1[1]), parseInt(match1[2]), parseInt(match1[3]));
      const l2 = getLuminance(parseInt(match2[1]), parseInt(match2[2]), parseInt(match2[3]));
      
      const lighter = Math.max(l1, l2);
      const darker = Math.min(l1, l2);
      
      return ((lighter + 0.05) / (darker + 0.05)).toFixed(2);
    };
    
    const textContrast = calculateContrast(readability.messageColor, readability.messageBg);
    console.log(`Text contrast ratio:   ${textContrast}:1`);
    console.log(`                       ${textContrast >= 7 ? '✅ AAA' : textContrast >= 4.5 ? '✅ AA' : '⚠️  Low'}\n`);
    
    // Final assessment
    console.log('=== FINAL ASSESSMENT ===\n');
    
    console.log('1. READABILITY:');
    const pageHex = rgbToHex(colors.pageBackground);
    const textHex = rgbToHex(readability.messageColor);
    
    if (textContrast >= 7) {
      console.log('   ✅ Excellent - Text is easily readable (AAA standard)');
    } else if (textContrast >= 4.5) {
      console.log('   ✅ Good - Text is readable (AA standard)');
    } else {
      console.log('   ⚠️  Could be better - Consider increasing contrast');
    }
    
    console.log(`   Message text: ${textHex} on ${rgbToHex(readability.messageBg)}`);
    console.log(`   Contrast: ${textContrast}:1\n`);
    
    console.log('2. CONTRAST FEEL:');
    
    // Check if background is too dark (pitch black) or too bright
    const bgMatch = colors.pageBackground.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (bgMatch) {
      const avgBg = (parseInt(bgMatch[1]) + parseInt(bgMatch[2]) + parseInt(bgMatch[3])) / 3;
      
      if (avgBg < 15) {
        console.log('   ⚠️  Background might be too dark (almost pitch black)');
        console.log('   Cursor IDE uses ~#1e1e1e (30,30,30) for warmth');
      } else if (avgBg > 40) {
        console.log('   ⚠️  Background might be too bright for dark theme');
      } else {
        console.log('   ✅ Comfortable - Similar to Cursor IDE dark theme');
        console.log('   Background is appropriately dark but not pitch black');
      }
      console.log(`   Average RGB value: ${avgBg.toFixed(0)}\n`);
    }
    
    console.log('3. NAV BAR DISTINCTION:');
    
    const navHex = rgbToHex(colors.navBar);
    if (navHex !== pageHex) {
      console.log(`   ✅ Distinguishable - Nav (${navHex}) differs from content (${pageHex})`);
    } else {
      console.log(`   ⚠️  Nav bar same color as content area (${navHex})`);
    }
    console.log();
    
    console.log('📸 SCREENSHOTS:');
    console.log('   - screenshot_cursor_theme_initial.png');
    console.log('   - screenshot_cursor_theme_rizzult.png\n');
    
    console.log('=== END OF VERIFICATION ===');
    
    await page.waitForTimeout(2000);
    
  } catch (error) {
    console.error('\n❌ ERROR:', error.message);
    await page.screenshot({ path: '/Users/petrnikolaev/n8n-rip/magnum-opus/screenshot_cursor_error.png' });
  } finally {
    await browser.close();
  }
})();
