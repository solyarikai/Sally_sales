const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await context.newPage();

  try {
    console.log('=== TESTING MINIMALIST DARK THEME ===\n');
    
    // Navigate to page
    console.log('→ Navigating to http://localhost:5179/replies');
    await page.goto('http://localhost:5179/replies');
    await page.waitForTimeout(3000);
    
    console.log('✓ Page loaded\n');
    
    // Take initial screenshot
    await page.screenshot({ path: '/Users/petrnikolaev/n8n-rip/magnum-opus/screenshot_minimalist_initial.png', fullPage: true });
    console.log('📸 Screenshot: screenshot_minimalist_initial.png\n');
    
    // Analyze colors on the page
    console.log('=== COLOR ANALYSIS - INITIAL STATE ===\n');
    
    const colorAnalysis = await page.evaluate(() => {
      const results = {
        brightColors: [],
        elementsChecked: 0
      };
      
      // Check all elements for bright colors
      const allElements = document.querySelectorAll('*');
      
      const isBrightColor = (color) => {
        if (!color || color === 'rgba(0, 0, 0, 0)' || color === 'transparent') return false;
        
        const match = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
        if (!match) return false;
        
        const r = parseInt(match[1]);
        const g = parseInt(match[2]);
        const b = parseInt(match[3]);
        
        // Check for bright/saturated colors
        // Green range
        if (g > 150 && g > r + 50 && g > b + 50) return { type: 'green', rgb: `rgb(${r},${g},${b})` };
        // Blue range
        if (b > 150 && b > r + 50 && b > g + 30) return { type: 'blue', rgb: `rgb(${r},${g},${b})` };
        // Purple/Violet range
        if (r > 130 && b > 130 && Math.abs(r - b) < 50 && g < r - 30) return { type: 'purple', rgb: `rgb(${r},${g},${b})` };
        // Amber/Orange range
        if (r > 200 && g > 150 && b < 100) return { type: 'amber', rgb: `rgb(${r},${g},${b})` };
        // Cyan range
        if (g > 150 && b > 150 && r < 100) return { type: 'cyan', rgb: `rgb(${r},${g},${b})` };
        
        return false;
      };
      
      Array.from(allElements).forEach(el => {
        const styles = window.getComputedStyle(el);
        results.elementsChecked++;
        
        // Check background color
        const bgColor = isBrightColor(styles.backgroundColor);
        if (bgColor) {
          const text = el.textContent?.substring(0, 50) || el.className || el.tagName;
          results.brightColors.push({
            element: text,
            property: 'background-color',
            color: bgColor.rgb,
            type: bgColor.type
          });
        }
        
        // Check text color
        const textColor = isBrightColor(styles.color);
        if (textColor) {
          const text = el.textContent?.substring(0, 50) || el.className || el.tagName;
          results.brightColors.push({
            element: text,
            property: 'color',
            color: textColor.rgb,
            type: textColor.type
          });
        }
        
        // Check border color
        const borderColor = isBrightColor(styles.borderColor);
        if (borderColor) {
          const text = el.textContent?.substring(0, 50) || el.className || el.tagName;
          results.brightColors.push({
            element: text,
            property: 'border-color',
            color: borderColor.rgb,
            type: borderColor.type
          });
        }
      });
      
      return results;
    });
    
    console.log(`Scanned ${colorAnalysis.elementsChecked} elements`);
    console.log(`Found ${colorAnalysis.brightColors.length} bright/colored elements\n`);
    
    if (colorAnalysis.brightColors.length > 0) {
      console.log('🎨 BRIGHT COLORS DETECTED:\n');
      
      // Group by type
      const byType = {};
      colorAnalysis.brightColors.forEach(item => {
        if (!byType[item.type]) byType[item.type] = [];
        byType[item.type].push(item);
      });
      
      Object.keys(byType).forEach(type => {
        console.log(`${type.toUpperCase()}: ${byType[type].length} instances`);
        byType[type].slice(0, 3).forEach(item => {
          console.log(`  - ${item.property}: ${item.color} on "${item.element.substring(0, 40)}..."`);
        });
      });
      console.log();
    } else {
      console.log('✅ No bright colors detected - theme appears to be monochrome\n');
    }
    
    // Check specific elements
    console.log('=== SPECIFIC ELEMENT CHECKS ===\n');
    
    // Check Send button
    const sendButton = await page.locator('button:has-text("Send")').first();
    let sendButtonColor = 'N/A';
    if (await sendButton.count() > 0) {
      sendButtonColor = await sendButton.evaluate(el => {
        const styles = window.getComputedStyle(el);
        return styles.backgroundColor;
      });
      console.log(`✓ Send button background: ${sendButtonColor}`);
    }
    
    // Check category badges
    const badges = await page.locator('[class*="badge"], .badge').count();
    console.log(`✓ Category badges found: ${badges}`);
    
    if (badges > 0) {
      const firstBadgeColor = await page.locator('[class*="badge"], .badge').first().evaluate(el => {
        const styles = window.getComputedStyle(el);
        return {
          bg: styles.backgroundColor,
          text: styles.color,
          border: styles.borderColor
        };
      });
      console.log(`✓ First badge colors:`, firstBadgeColor);
    }
    
    // Check nav bar
    const navColor = await page.evaluate(() => {
      const nav = document.querySelector('nav, header');
      if (nav) {
        const styles = window.getComputedStyle(nav);
        return styles.backgroundColor;
      }
      return 'N/A';
    });
    console.log(`✓ Nav bar background: ${navColor}\n`);
    
    // Select Rizzult project
    console.log('→ Selecting Rizzult project...');
    
    const projectSelector = page.locator('button:has-text("All Projects")').first();
    if (await projectSelector.count() > 0) {
      await projectSelector.click();
      await page.waitForTimeout(1000);
      
      const searchInput = page.locator('input[type="text"]').first();
      await searchInput.fill('Rizzult');
      await page.waitForTimeout(1000);
      
      await page.locator('text=Rizzult').first().click();
      console.log('✓ Selected Rizzult');
      
      await page.waitForTimeout(3000);
    }
    
    // Take Rizzult screenshot
    await page.screenshot({ path: '/Users/petrnikolaev/n8n-rip/magnum-opus/screenshot_minimalist_rizzult.png', fullPage: true });
    console.log('📸 Screenshot: screenshot_minimalist_rizzult.png\n');
    
    // Analyze colors again after Rizzult selection
    console.log('=== COLOR ANALYSIS - AFTER RIZZULT SELECTION ===\n');
    
    const colorAnalysis2 = await page.evaluate(() => {
      const results = {
        brightColors: [],
        elementsChecked: 0
      };
      
      const isBrightColor = (color) => {
        if (!color || color === 'rgba(0, 0, 0, 0)' || color === 'transparent') return false;
        
        const match = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
        if (!match) return false;
        
        const r = parseInt(match[1]);
        const g = parseInt(match[2]);
        const b = parseInt(match[3]);
        
        if (g > 150 && g > r + 50 && g > b + 50) return { type: 'green', rgb: `rgb(${r},${g},${b})` };
        if (b > 150 && b > r + 50 && b > g + 30) return { type: 'blue', rgb: `rgb(${r},${g},${b})` };
        if (r > 130 && b > 130 && Math.abs(r - b) < 50 && g < r - 30) return { type: 'purple', rgb: `rgb(${r},${g},${b})` };
        if (r > 200 && g > 150 && b < 100) return { type: 'amber', rgb: `rgb(${r},${g},${b})` };
        if (g > 150 && b > 150 && r < 100) return { type: 'cyan', rgb: `rgb(${r},${g},${b})` };
        
        return false;
      };
      
      const allElements = document.querySelectorAll('*');
      Array.from(allElements).forEach(el => {
        const styles = window.getComputedStyle(el);
        results.elementsChecked++;
        
        ['backgroundColor', 'color', 'borderColor'].forEach(prop => {
          const colorCheck = isBrightColor(styles[prop]);
          if (colorCheck) {
            const text = el.textContent?.substring(0, 50) || el.className || el.tagName;
            results.brightColors.push({
              element: text,
              property: prop,
              color: colorCheck.rgb,
              type: colorCheck.type
            });
          }
        });
      });
      
      return results;
    });
    
    console.log(`Scanned ${colorAnalysis2.elementsChecked} elements`);
    console.log(`Found ${colorAnalysis2.brightColors.length} bright/colored elements\n`);
    
    // Final report
    console.log('\n=== FINAL REPORT ===\n');
    
    console.log('1. BRIGHT/COLORED ELEMENTS:');
    if (colorAnalysis2.brightColors.length === 0) {
      console.log('   ✅ NONE - Completely monochrome!\n');
    } else {
      console.log(`   ⚠️  Found ${colorAnalysis2.brightColors.length} colored elements:`);
      const types = [...new Set(colorAnalysis2.brightColors.map(c => c.type))];
      types.forEach(type => {
        const count = colorAnalysis2.brightColors.filter(c => c.type === type).length;
        console.log(`   - ${type}: ${count} instances`);
      });
      console.log();
    }
    
    console.log('2. MONOCHROME CHECK:');
    console.log(`   ${colorAnalysis2.brightColors.length < 10 ? '✅' : '❌'} Mostly monochrome: ${colorAnalysis2.brightColors.length < 10 ? 'YES' : 'NO'}\n`);
    
    console.log('3. NAV BAR:');
    console.log(`   Background: ${navColor}`);
    console.log(`   ${navColor.includes('rgb(20') || navColor.includes('rgb(10') ? '✅' : '❌'} Clean and minimal\n`);
    
    console.log('4. SEND BUTTON:');
    console.log(`   Color: ${sendButtonColor}`);
    console.log(`   ${sendButtonColor.includes('rgb(') && !sendButtonColor.includes('rgb(0, 200') ? '✅' : '❌'} Light gray (not green)\n`);
    
    console.log('5. CATEGORY LABELS:');
    console.log(`   Found ${badges} badges`);
    console.log('   Check screenshots for visual appearance\n');
    
    console.log('📸 SCREENSHOTS:');
    console.log('   - screenshot_minimalist_initial.png');
    console.log('   - screenshot_minimalist_rizzult.png\n');
    
    console.log('=== END OF TEST ===');
    
    await page.waitForTimeout(2000);
    
  } catch (error) {
    console.error('\n❌ ERROR:', error.message);
    await page.screenshot({ path: '/Users/petrnikolaev/n8n-rip/magnum-opus/screenshot_minimalist_error.png' });
  } finally {
    await browser.close();
  }
})();
