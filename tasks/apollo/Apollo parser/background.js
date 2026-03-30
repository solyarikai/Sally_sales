// Background service worker for running scraping in background

let scrapingState = {
  isScraping: false,
  tabId: null,
  shouldStop: false,
  startTime: null,
  currentPageNumber: 1,
  scrapedPages: [],
  wasScraping: false // Track if scraping was active before tab became inactive
};

let _resumeLock = false; // Prevent concurrent auto-resume attempts

// Auto-resume function
async function tryAutoResume(tabId) {
  if (scrapingState.isScraping || _resumeLock) {
    return; // Already scraping or resume in progress
  }
  
  const saved = await chrome.storage.local.get(['wasScraping', 'tabId']);
  if (!saved.wasScraping || saved.tabId !== tabId) {
    return; // No saved scraping state for this tab
  }
  
  // Verify tab is Apollo.io
  try {
    const tab = await chrome.tabs.get(tabId);
    if (!tab || !tab.url || !tab.url.includes('apollo.io')) {
      return;
    }
  } catch (e) {
    return; // Tab doesn't exist
  }
  
  // Auto-resume scraping
  console.log('Auto-resuming scraping on tab', tabId);
  _resumeLock = true;
  scrapingState.wasScraping = false;
  scrapingState.isScraping = true;
  scrapingState.tabId = tabId;
  scrapingState.shouldStop = false;
  scrapingState.startTime = Date.now();
  
  const savedProgress = await chrome.storage.local.get(['currentPageNumber', 'scrapedPages']);
  scrapingState.currentPageNumber = savedProgress.currentPageNumber || 1;
  scrapingState.scrapedPages = savedProgress.scrapedPages || [];
  
  // Save wasScraping as false since we're resuming
  await chrome.storage.local.set({
    wasScraping: false,
    tabId: tabId
  });
  
  // Wait a bit for page to be ready, then resume
  setTimeout(() => {
    _resumeLock = false;
    scrapeAllPagesBackground(tabId);
  }, 3000);
}

// Listen for tab updates to auto-resume
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  // Only resume on full page loads, not SPA navigations
  // SPA navigations fire onUpdated but the scraper handles them internally
  if (changeInfo.status === 'complete' && tab.url && tab.url.includes('apollo.io')) {
    // Don't interfere if scraping is already active on this tab
    if (scrapingState.isScraping && scrapingState.tabId === tabId) {
      return;
    }
    await tryAutoResume(tabId);
  }
});

// Listen for tab activation
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  await tryAutoResume(activeInfo.tabId);
});

// Also listen for tab focus events
chrome.tabs.onHighlighted.addListener(async (highlightInfo) => {
  if (highlightInfo.tabIds && highlightInfo.tabIds.length > 0) {
    await tryAutoResume(highlightInfo.tabIds[0]);
  }
});

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('Background received message:', request.action);
  if (request.action === 'startScraping') {
    console.log('Starting scraping for tab:', request.tabId);
    startBackgroundScraping(request.tabId).catch(err => {
      console.error('Error in startBackgroundScraping:', err);
    });
    sendResponse({ success: true });
  } else if (request.action === 'stopScraping') {
    console.log('Stopping scraping');
    stopScraping().catch(err => {
      console.error('Error in stopScraping:', err);
    });
    sendResponse({ success: true });
  } else if (request.action === 'getScrapingStatus') {
    // Get latest data from storage (async)
    chrome.storage.local.get(['scrapedData', 'totalContacts', 'currentPageNumber', 'rowsPerPage'], (saved) => {
      const pageRows = saved.scrapedData ? saved.scrapedData.length : 0;
      
      sendResponse({ 
        isScraping: scrapingState.isScraping,
        pageRows: pageRows,
        rowsPerPage: saved.rowsPerPage || null,
        ...scrapingState 
      });
    });
    return true; // Keep channel open for async response
  } else if (request.action === 'updateProgress') {
    // Save progress from content script
    chrome.storage.local.set({
      scrapedData: request.data.scrapedData,
      scrapedHeaders: request.data.scrapedHeaders,
      scrapedPages: request.data.scrapedPages,
      currentPageNumber: request.data.currentPageNumber
    });
    sendResponse({ success: true });
  }
  return true; // Keep channel open for async response
});

async function startBackgroundScraping(tabId) {
  console.log('startBackgroundScraping called with tabId:', tabId);
  try {
    scrapingState.isScraping = true;
    scrapingState.tabId = tabId;
    scrapingState.shouldStop = false;
    scrapingState.startTime = Date.now();
    scrapingState.wasScraping = true;
    
    // Save that scraping is active
    await chrome.storage.local.set({
      wasScraping: true,
      tabId: tabId
    });
    
    // Load saved progress
    const saved = await chrome.storage.local.get(['currentPageNumber', 'scrapedPages']);
    scrapingState.currentPageNumber = saved.currentPageNumber || 1;
    scrapingState.scrapedPages = saved.scrapedPages || [];
    
    console.log('Starting scrapeAllPagesBackground for tab:', tabId);
    // Start scraping loop
    scrapeAllPagesBackground(tabId).catch(err => {
      console.error('Error in scrapeAllPagesBackground:', err);
      scrapingState.isScraping = false;
    });
  } catch (error) {
    console.error('Error in startBackgroundScraping:', error);
    scrapingState.isScraping = false;
    throw error;
  }
}

async function stopScraping() {
  scrapingState.shouldStop = true;
  scrapingState.isScraping = false;
  scrapingState.wasScraping = false;
  
  // Clear wasScraping flag
  await chrome.storage.local.set({
    wasScraping: false
  });
}

async function scrapeAllPagesBackground(tabId) {
  console.log('scrapeAllPagesBackground started for tab:', tabId);
  // Check if tab still exists and is accessible
  try {
    const tab = await chrome.tabs.get(tabId);
    console.log('Tab found:', tab.url);
    if (!tab || !tab.url || !tab.url.includes('apollo.io')) {
      console.log('Tab no longer accessible or not Apollo.io. URL:', tab?.url);
      scrapingState.isScraping = false;
      scrapingState.wasScraping = false;
      await chrome.storage.local.set({ wasScraping: false });
      return;
    }
  } catch (e) {
    console.error('Error getting tab:', e.message);
    scrapingState.isScraping = false;
    scrapingState.wasScraping = false;
    await chrome.storage.local.set({ wasScraping: false });
    return;
  }
  
  let pageNumber = scrapingState.currentPageNumber;
  let totalContactsCount = null;
  let consecutiveNoNewData = 0; // Loop detection: count pages with no new data
  const maxConsecutiveNoNewData = 3; // Stop after 3 consecutive pages with no new data
  console.log('Starting from page:', pageNumber);
  
  // On fresh start: navigate to page 1 so we don't start mid-list
  // On resume: we have saved pages, so start from where we left off
  const isFreshStart = scrapingState.scrapedPages.length === 0 && pageNumber === 1;

  if (isFreshStart) {
    // Navigate to page 1 via URL hash (Apollo uses hash routing)
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tabId },
        function: navigateToFirstPage
      });
      await sleep(3000);
      console.log('Navigated to page 1 for fresh start');
    } catch (e) {
      console.log('Could not navigate to page 1:', e.message);
      scrapingState.wasScraping = true;
      await chrome.storage.local.set({ wasScraping: true, tabId: tabId });
      scrapingState.isScraping = false;
      return;
    }
  }
  
  while (!scrapingState.shouldStop && scrapingState.isScraping) {
    // Skip if already scraped
    if (scrapingState.scrapedPages.includes(pageNumber)) {
      console.log(`Page ${pageNumber} already scraped, skipping...`);
      // Try next page
      let hasNext;
      try {
        hasNext = await checkNextPage(tabId);
      } catch (e) {
        console.log('Tab inactive during check, pausing');
        scrapingState.wasScraping = true;
        scrapingState.isScraping = false;
        await chrome.storage.local.set({
          wasScraping: true,
          tabId: tabId,
          currentPageNumber: pageNumber,
          scrapedPages: scrapingState.scrapedPages
        });
        return;
      }
      if (hasNext) {
        try {
          await clickNext(tabId);
          await sleep(2000);
          pageNumber++;
          scrapingState.currentPageNumber = pageNumber;
          continue;
        } catch (e) {
          console.log('Tab inactive during navigation, pausing');
          scrapingState.wasScraping = true;
          scrapingState.isScraping = false;
          await chrome.storage.local.set({
            wasScraping: true,
            tabId: tabId,
            currentPageNumber: pageNumber,
            scrapedPages: scrapingState.scrapedPages
          });
          return;
        }
      } else {
        break;
      }
    }
    
    // Wait for table to load
    let loaded = false;
    let rowsSeen = 0; // How many iterations we've seen rows without rightmost data
    for (let i = 0; i < 100; i++) {
      try {
        const result = await chrome.scripting.executeScript({
          target: { tabId: tabId },
          function: waitForTableLoad
        });

        if (result && result[0] && result[0].result) {
          const loadResult = result[0].result;
          if (loadResult.loaded && loadResult.rightmostLoaded) {
            // Best case: table fully loaded including rightmost columns
            loaded = true;
            break;
          }
          if (loadResult.rowCount > 0) {
            rowsSeen++;
            // If we've seen rows for ~6 seconds but rightmost columns are still empty,
            // accept the table as loaded (free accounts may have empty/locked columns)
            if (rowsSeen >= 20) {
              console.log(`Table has ${loadResult.rowCount} rows but rightmost columns empty after ${rowsSeen} checks, proceeding anyway`);
              loaded = true;
              break;
            }
          }
        }
      } catch (e) {
        console.log('Tab might be inactive, pausing scraping:', e.message);
        // Tab might have become inactive, pause and wait for reactivation
        scrapingState.wasScraping = true;
        scrapingState.isScraping = false;
        await chrome.storage.local.set({
          wasScraping: true,
          tabId: tabId,
          currentPageNumber: pageNumber,
          scrapedPages: scrapingState.scrapedPages
        });
        return; // Will auto-resume when tab becomes active
      }
      await sleep(300);
    }

    if (!loaded) {
      console.error('Table did not load after all retries, pausing');
      scrapingState.wasScraping = true;
      scrapingState.isScraping = false;
      await chrome.storage.local.set({
        wasScraping: true,
        tabId: tabId,
        currentPageNumber: pageNumber,
        scrapedPages: scrapingState.scrapedPages
      });
      return; // Will auto-resume when tab becomes active
    }
    
    // Get total count if needed
    if (totalContactsCount === null) {
      try {
        const countResult = await chrome.scripting.executeScript({
          target: { tabId: tabId },
          function: getTotalContactsCount
        });
        if (countResult && countResult[0] && countResult[0].result) {
          totalContactsCount = countResult[0].result.total;
          await chrome.storage.local.set({ totalContacts: totalContactsCount });
        }
      } catch (e) {
        console.log('Could not get total count, tab might be inactive');
        scrapingState.wasScraping = true;
        scrapingState.isScraping = false;
        await chrome.storage.local.set({ 
          wasScraping: true, 
          tabId: tabId,
          currentPageNumber: pageNumber,
          scrapedPages: scrapingState.scrapedPages
        });
        return;
      }
    }
    
    // Try to dismiss any modals/overlays that might block the table
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tabId },
        function: dismissModals
      });
    } catch (e) {
      // Ignore - modal dismissal is best-effort
    }

    // Scrape current page - inject the full scrapeTable function (with retry)
    let results;
    let scrapeRetries = 0;
    const maxScrapeRetries = 3;
    while (scrapeRetries < maxScrapeRetries) {
      try {
        results = await chrome.scripting.executeScript({
          target: { tabId: tabId },
          func: scrapeTableFunction,
          args: []
        });
        break; // Success
      } catch (e) {
        scrapeRetries++;
        if (scrapeRetries >= maxScrapeRetries) {
          console.log('Could not scrape after retries, tab might be inactive:', e.message);
          scrapingState.wasScraping = true;
          scrapingState.isScraping = false;
          await chrome.storage.local.set({
            wasScraping: true,
            tabId: tabId,
            currentPageNumber: pageNumber,
            scrapedPages: scrapingState.scrapedPages
          });
          return; // Will auto-resume when tab becomes active
        }
        console.log(`Scrape attempt ${scrapeRetries} failed, retrying in 2s...`);
        await sleep(2000);
      }
    }

    if (results && results[0] && results[0].result) {
      let result = results[0].result;
      console.log('Scraped page', pageNumber, '- Found', result.rows.length, 'rows');
      if (result.error) {
        console.error('Scraping error:', result.error);
        break;
      }
      if (result.rows.length === 0) {
        // Retry: wait and try once more before giving up
        console.log('No rows found on page', pageNumber, '- waiting 3s and retrying...');
        await sleep(3000);
        try {
          await chrome.scripting.executeScript({
            target: { tabId: tabId },
            function: dismissModals
          });
        } catch (e) { /* ignore */ }
        try {
          const retryResults = await chrome.scripting.executeScript({
            target: { tabId: tabId },
            func: scrapeTableFunction,
            args: []
          });
          if (retryResults && retryResults[0] && retryResults[0].result && retryResults[0].result.rows.length > 0) {
            result = retryResults[0].result;
            console.log('Retry succeeded - Found', result.rows.length, 'rows');
          } else {
            console.log('Still no rows after retry on page', pageNumber);
            break;
          }
        } catch (e) {
          console.log('Retry failed:', e.message);
          break;
        }
      }
      
      // Get existing data
      const existing = await chrome.storage.local.get(['scrapedData', 'scrapedHeaders', 'rowsPerPage']);
      const scrapedData = existing.scrapedData || [];
      const scrapedHeaders = existing.scrapedHeaders || [];
      
      // Case-insensitive row field lookup (Apollo headers can be "NAME", "Name", etc.)
      function getField(row, ...possibleNames) {
        const keys = Object.keys(row);
        for (const name of possibleNames) {
          // Exact match first
          if (row[name] !== undefined) return row[name];
          // Case-insensitive match
          const key = keys.find(k => k.toLowerCase() === name.toLowerCase());
          if (key !== undefined && row[key] !== undefined) return row[key];
        }
        return '';
      }

      // Function to create a unique key for a contact
      function getContactKey(row) {
        const name = String(getField(row, 'Name', 'Contact Name')).trim().toLowerCase();
        const company = String(getField(row, 'Company', 'Account', 'Company Name', 'Organization')).trim().toLowerCase();
        const title = String(getField(row, 'Title', 'Job Title')).trim().toLowerCase();
        return `${name}|${company}|${title}`;
      }

      // Create a Set of existing contact keys for fast lookup
      const existingKeys = new Set(scrapedData.map(row => getContactKey(row)));

      // Filter out duplicates from new rows
      const uniqueNewRows = result.rows.filter(row => {
        const name = String(getField(row, 'Name', 'Contact Name')).trim();
        // If name is empty, don't deduplicate — we can't reliably identify this contact
        if (!name) {
          return true;
        }
        const key = getContactKey(row);
        if (existingKeys.has(key)) {
          console.log(`Skipping duplicate: ${name} at ${String(getField(row, 'Company', 'Account')).trim() || 'Unknown'}`);
          return false;
        }
        existingKeys.add(key); // Add to set to prevent duplicates within the same batch
        return true;
      });
      
      // Add only unique new rows
      const duplicatesCount = result.rows.length - uniqueNewRows.length;
      if (duplicatesCount > 0) {
        console.log(`Filtered out ${duplicatesCount} duplicate(s) from page ${pageNumber}`);
      }

      // Loop detection: if no new data is being added, we might be stuck
      if (uniqueNewRows.length === 0) {
        consecutiveNoNewData++;
        console.log(`No new data from page ${pageNumber} (${consecutiveNoNewData}/${maxConsecutiveNoNewData} consecutive)`);
        if (consecutiveNoNewData >= maxConsecutiveNoNewData) {
          console.log('Stopping: no new data for too many consecutive pages (likely looping)');
          scrapingState.isScraping = false;
          break;
        }
      } else {
        consecutiveNoNewData = 0; // Reset counter when we get new data
      }

      scrapedData.push(...uniqueNewRows);
      // Merge headers: keep existing headers and add any new ones from this page
      let finalHeaders;
      if (scrapedHeaders.length === 0) {
        finalHeaders = result.headers;
      } else if (result.headers.length > 0) {
        const existingHeaderSet = new Set(scrapedHeaders);
        finalHeaders = [...scrapedHeaders];
        for (const h of result.headers) {
          if (!existingHeaderSet.has(h)) {
            finalHeaders.push(h);
            existingHeaderSet.add(h);
          }
        }
      } else {
        finalHeaders = scrapedHeaders;
      }
      
      // Mark page as scraped (avoid duplicates)
      if (!scrapingState.scrapedPages.includes(pageNumber)) {
        scrapingState.scrapedPages.push(pageNumber);
      }
      
      // Calculate rows per page from first page (if not already saved)
      let rowsPerPage = existing.rowsPerPage;
      if (!rowsPerPage && result.rows.length > 0) {
        rowsPerPage = result.rows.length;
      }
      
      // Save progress
      await chrome.storage.local.set({
        scrapedData: scrapedData,
        scrapedHeaders: finalHeaders,
        scrapedPages: scrapingState.scrapedPages,
        currentPageNumber: pageNumber,
        rowsPerPage: rowsPerPage
      });
      
      // Notify popup if it's open (use .catch since sendMessage returns a Promise)
      chrome.runtime.sendMessage({
        action: 'progressUpdate',
        data: {
          pageNumber: pageNumber,
          totalScraped: scrapedData.length,
          totalContacts: totalContactsCount
        }
      }).catch(() => {
        // Popup might be closed, that's ok
      });
      
      // Send progress update to content script for page display
      let statusMsg = `Scraping page ${pageNumber}...`;
      if (duplicatesCount > 0) {
        statusMsg = `Page ${pageNumber}: Added ${uniqueNewRows.length} contacts (${duplicatesCount} duplicates skipped)`;
      }

      chrome.tabs.sendMessage(tabId, {
        action: 'updateProgress',
        data: {
          pageNumber: pageNumber,
          totalScraped: scrapedData.length,
          totalContacts: totalContactsCount,
          status: statusMsg
        }
      }).catch(() => {
        // Content script might not be loaded, that's ok
      });
      
      // Check for next page
      let hasNext;
      try {
        hasNext = await checkNextPage(tabId);
      } catch (e) {
        console.log('Could not check next page, tab might be inactive');
        scrapingState.wasScraping = true;
        scrapingState.isScraping = false;
        await chrome.storage.local.set({ 
          wasScraping: true, 
          tabId: tabId,
          currentPageNumber: pageNumber,
          scrapedPages: scrapingState.scrapedPages
        });
        return;
      }
      
      if (!hasNext) {
        scrapingState.isScraping = false;
        break;
      }
      
      // Click next
      try {
        await clickNext(tabId);
        await sleep(3000);
        pageNumber++;
        scrapingState.currentPageNumber = pageNumber;
      } catch (e) {
        console.log('Could not click next, tab might be inactive');
        scrapingState.wasScraping = true;
        scrapingState.isScraping = false;
        await chrome.storage.local.set({
          wasScraping: true,
          tabId: tabId,
          currentPageNumber: pageNumber,
          scrapedPages: scrapingState.scrapedPages
        });
        return;
      }
    } else {
      break;
    }
  }
  
  scrapingState.isScraping = false;
  
  // Hide progress overlay on page
  chrome.tabs.sendMessage(tabId, {
    action: 'hideProgress'
  }).catch(() => {
    // Content script might not be loaded
  });
  
  // Scraping finished (either naturally or by user stop) - clear wasScraping
  scrapingState.wasScraping = false;
  await chrome.storage.local.set({ wasScraping: false });
  
  // Final save
  await chrome.storage.local.set({
    currentPageNumber: scrapingState.currentPageNumber,
    scrapedPages: scrapingState.scrapedPages
  });
}

async function checkNextPage(tabId) {
  // Let errors propagate so callers can handle tab inactivity
  const result = await chrome.scripting.executeScript({
    target: { tabId: tabId },
    function: hasNextPage
  });
  return result && result[0] && result[0].result;
}

async function clickNext(tabId) {
  // Let errors propagate so callers can handle tab inactivity
  await chrome.scripting.executeScript({
    target: { tabId: tabId },
    function: clickNextButton
  });
  return true;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Navigate to page 1 by updating the URL hash parameter
function navigateToFirstPage() {
  const hash = window.location.hash;
  if (hash && hash.includes('page=')) {
    // Replace existing page parameter with page=1
    const newHash = hash.replace(/page=\d+/, 'page=1');
    if (newHash !== hash) {
      window.location.hash = newHash;
      return { navigated: true };
    }
  }
  return { navigated: false };
}

// Dismiss any modals/overlays that might block the table (upgrade prompts, etc.)
function dismissModals() {
  // Close any modal overlays
  const closeSelectors = [
    'button[aria-label="Close"]',
    'button[aria-label="close"]',
    'button[aria-label="Dismiss"]',
    '[data-testid="close-modal"]',
    '.modal-close',
    '.zp_fTwp1', // Apollo's close button class
    'button.zp_aFf3m', // Another Apollo close class
  ];

  for (const selector of closeSelectors) {
    const buttons = document.querySelectorAll(selector);
    buttons.forEach(btn => {
      // Only click if it's visible and inside a modal/overlay
      const rect = btn.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        const parent = btn.closest('[role="dialog"], [class*="modal"], [class*="overlay"], [class*="Modal"]');
        if (parent) {
          btn.click();
        }
      }
    });
  }

  // Also try pressing Escape to close any open modals
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
}

// Helper functions (same as in popup.js, injected into page)
function waitForTableLoad() {
  const container = document.querySelector('[data-id="scrollable-table-container"]');
  if (!container) {
    return { loaded: false };
  }
  
  const rows = container.querySelectorAll('[role="row"][aria-rowindex]');
  if (rows.length === 0) {
    return { loaded: false };
  }
  
  const rightmostColumnIds = [
    'account.social',
    'account.keywords',
    'contact.location',
    'account.number_of_employees'
  ];
  
  const headerRowGroups = container.querySelectorAll('[role="rowgroup"]');
  if (headerRowGroups.length === 0) {
    return { loaded: false };
  }
  
  const headerRow = headerRowGroups[0].querySelector('[role="row"]');
  if (!headerRow) {
    return { loaded: false };
  }
  
  const rightmostColIndices = [];
  const headerCells = headerRow.querySelectorAll('[role="columnheader"]');
  headerCells.forEach(cell => {
    const dataId = cell.getAttribute('data-id');
    const colIndex = parseInt(cell.getAttribute('aria-colindex') || '0');
    if (rightmostColumnIds.includes(dataId) && colIndex > 0) {
      rightmostColIndices.push(colIndex);
    }
  });
  
  if (rightmostColIndices.length > 0) {
    let samplesWithRightmostData = 0;
    const sampleSize = Math.min(3, rows.length);
    
    for (let i = 0; i < sampleSize; i++) {
      const row = rows[i];
      let hasRightmostData = false;
      
      for (const colIndex of rightmostColIndices) {
        const cell = row.querySelector(`[role="cell"][aria-colindex="${colIndex}"], [role="gridcell"][aria-colindex="${colIndex}"]`);
        if (cell) {
          if (colIndex === rightmostColIndices[0]) {
            const links = cell.querySelectorAll('a[href]');
            if (links.length > 0) {
              hasRightmostData = true;
              break;
            }
          } else {
            const text = cell.textContent.trim();
            if (text && text.length > 0 && !text.match(/^(Copy|More)$/)) {
              hasRightmostData = true;
              break;
            }
          }
        }
      }
      
      if (hasRightmostData) {
        samplesWithRightmostData++;
      }
    }
    
    if (samplesWithRightmostData >= Math.min(2, sampleSize)) {
      return { loaded: true, rowCount: rows.length, rightmostLoaded: true };
    }
    
    return { loaded: false, rowCount: rows.length, rightmostLoaded: false };
  }
  
  // No expected rightmost columns found in the table - consider fully loaded
  return { loaded: rows.length > 0, rowCount: rows.length, rightmostLoaded: rows.length > 0 };
}

function getTotalContactsCount() {
  // Look for pagination text specifically in pagination areas first
  const paginationContainers = document.querySelectorAll('[role="navigation"], [aria-label*="pagination" i], [class*="pagination" i]');
  for (const container of paginationContainers) {
    const match = container.textContent.match(/(\d+)\s*-\s*(\d+)\s+of\s+([\d,]+)/i);
    if (match && match[3]) {
      const total = parseInt(match[3].replace(/,/g, ''));
      if (total > 0) return { total: total };
    }
  }

  // Fallback: search in status/aria-live elements
  const paginationElements = document.querySelectorAll('[role="status"], [aria-live]');
  for (const el of paginationElements) {
    const match = el.textContent.match(/(\d+)\s*-\s*(\d+)\s+of\s+([\d,]+)/i);
    if (match && match[3]) {
      const total = parseInt(match[3].replace(/,/g, ''));
      if (total > 0) return { total: total };
    }
  }

  // Last resort: broad search requiring full "X - Y of Z" pattern
  const paginationText = document.body.innerText.match(/(\d+)\s*-\s*(\d+)\s+of\s+([\d,]+)/i);
  if (paginationText && paginationText[3]) {
    const total = parseInt(paginationText[3].replace(/,/g, ''));
    if (total > 0) return { total: total };
  }

  return { total: null };
}

function hasNextPage() {
  const nextButton = document.querySelector('button[aria-label="Next"], button[aria-label*="Next" i]');
  if (!nextButton) {
    return false;
  }
  
  const isDisabled = nextButton.disabled || 
                  nextButton.getAttribute('aria-disabled') === 'true' ||
                  nextButton.classList.contains('disabled') ||
                  nextButton.hasAttribute('disabled');
  
  return !isDisabled;
}

function clickNextButton() {
  const nextButton = document.querySelector('button[aria-label="Next"], button[aria-label*="Next" i]');
  if (!nextButton) {
    return { clicked: false, error: 'Next button not found' };
  }
  
  const isDisabled = nextButton.disabled || 
                  nextButton.getAttribute('aria-disabled') === 'true' ||
                  nextButton.classList.contains('disabled') ||
                  nextButton.hasAttribute('disabled');
  
  if (isDisabled) {
    return { clicked: false, error: 'Next button is disabled' };
  }
  
  try {
    nextButton.click();
    return { clicked: true };
  } catch (error) {
    return { clicked: false, error: error.message };
  }
}

function getCurrentPageNumber() {
  // Apollo.io uses hash routing: /#/people?page=3
  // Try hash-based URL params first (most reliable for Apollo)
  const hash = window.location.hash;
  if (hash) {
    const hashParts = hash.split('?');
    if (hashParts.length > 1) {
      const hashParams = new URLSearchParams(hashParts[1]);
      const pageParam = hashParams.get('page');
      if (pageParam) {
        const page = parseInt(pageParam);
        if (!isNaN(page) && page > 0) {
          return { page: page };
        }
      }
    }
  }

  // Try regular URL query params
  const urlParams = new URLSearchParams(window.location.search);
  const pageParam = urlParams.get('page');
  if (pageParam) {
    const page = parseInt(pageParam);
    if (!isNaN(page) && page > 0) {
      return { page: page };
    }
  }

  // Try to find page number input
  const pageInput = document.querySelector('input[type="number"][aria-label*="page" i], input[type="number"][aria-label*="Page" i]');
  if (pageInput && pageInput.value) {
    return { page: parseInt(pageInput.value) };
  }

  // Default to page 1 if we can't determine
  return { page: 1 };
}

// Full scrapeTable function for injection into page
// This duplicates the logic from popup.js but is necessary for background execution
function scrapeTableFunction() {
  // Helper function to detect link type from URL
  function detectLinkType(url) {
    if (!url) return null;
    const lowerUrl = url.toLowerCase();
    if (lowerUrl.includes('linkedin.com')) return 'LinkedIn';
    if (lowerUrl.includes('facebook.com')) return 'Facebook';
    if (lowerUrl.includes('twitter.com') || lowerUrl.includes('x.com')) return 'Twitter';
    if (lowerUrl.includes('instagram.com')) return 'Instagram';
    if (lowerUrl.includes('youtube.com')) return 'YouTube';
    if (lowerUrl.includes('github.com')) return 'GitHub';
    if (lowerUrl.startsWith('http://') || lowerUrl.startsWith('https://')) return 'Website';
    return 'Website';
  }

  let container = document.querySelector('[data-id="scrollable-table-container"]');
  if (!container) {
    container = document.querySelector('[role="rowgroup"]')?.closest('div');
  }
  if (!container) {
    const firstRow = document.querySelector('[role="row"][aria-rowindex]');
    container = firstRow?.closest('div');
  }
  if (!container) {
    return { headers: [], rows: [], error: 'Table container not found' };
  }

  const headerRowGroups = container.querySelectorAll('[role="rowgroup"]');
  let headerRow = null;
  if (headerRowGroups.length > 0) {
    headerRow = headerRowGroups[0].querySelector('[role="row"]');
  }
  if (!headerRow) {
    headerRow = container.querySelector('[role="row"]:not([aria-rowindex])');
  }
  if (!headerRow) {
    const rows = container.querySelectorAll('[role="row"]');
    for (let row of rows) {
      if (row.querySelector('[role="columnheader"]')) {
        headerRow = row;
        break;
      }
    }
  }
  if (!headerRow) {
    return { headers: [], rows: [], error: 'Header row not found' };
  }

  const headers = [];
  const headerCells = headerRow.querySelectorAll('[role="columnheader"]');
  headerCells.forEach(cell => {
    const dataId = cell.getAttribute('data-id');
    const colIndex = parseInt(cell.getAttribute('aria-colindex') || '0');
    const unwantedColumns = ['leftActions', 'addNewColumn', 'actions'];
    if (dataId && !unwantedColumns.includes(dataId) && colIndex > 0) {
      const span = cell.querySelector('span');
      const headerName = span ? span.textContent.trim() : dataId;
      const unwantedNames = ['Actions', 'Emails', 'Phone numbers', 'People Auto-Score'];
      if (!unwantedNames.includes(headerName)) {
        headers.push({ id: dataId, name: headerName || dataId, colIndex: colIndex });
      }
    }
  });

  const rowGroup = headerRowGroups.length > 1 ? headerRowGroups[1] : container.querySelector('[role="rowgroup"]:last-of-type');
  if (!rowGroup) {
    return { headers: headers.map(h => h.name), rows: [] };
  }

  const rows = [];
  const dataRows = rowGroup.querySelectorAll('[role="row"]');
  dataRows.forEach(row => {
    const rowData = {};
    headers.forEach((header) => {
      let cell = row.querySelector(`[role="cell"][aria-colindex="${header.colIndex}"], [role="gridcell"][aria-colindex="${header.colIndex}"]`);
      if (!cell) {
        const pinnedLeft = row.querySelector('[data-testid="table-pinned-container-left"]');
        const pinnedRight = row.querySelector('[data-testid="table-pinned-container-right"]');
        if (pinnedLeft) {
          cell = pinnedLeft.querySelector(`[role="cell"][aria-colindex="${header.colIndex}"], [role="gridcell"][aria-colindex="${header.colIndex}"]`);
        }
        if (!cell && pinnedRight) {
          cell = pinnedRight.querySelector(`[role="cell"][aria-colindex="${header.colIndex}"], [role="gridcell"][aria-colindex="${header.colIndex}"]`);
        }
      }
      if (cell) {
        let value = '';
        switch (header.id) {
          case 'contact.name':
            // Try multiple selectors since Apollo changes DOM structure frequently
            // 1. New format: button inside anchor with /contacts/ path
            const nameButtonSpan = cell.querySelector('a[href*="/contacts/"] button span.zp_pHNm5');
            if (nameButtonSpan) {
              value = nameButtonSpan.textContent.trim();
            }
            // 2. Any anchor with /contacts/ path
            if (!value) {
              const contactLink = cell.querySelector('a[href*="/contacts/"]');
              if (contactLink) {
                // Get text, excluding icons/images
                const clone = contactLink.cloneNode(true);
                clone.querySelectorAll('img, svg, i, [class*="icon"]').forEach(el => el.remove());
                value = clone.textContent.trim().replace(/\s+/g, ' ');
              }
            }
            // 3. Old format: anchor with /people/ path
            if (!value) {
              const nameLink = cell.querySelector('a[href*="/people/"]');
              if (nameLink) {
                const clone = nameLink.cloneNode(true);
                clone.querySelectorAll('img, svg, i, [class*="icon"]').forEach(el => el.remove());
                value = clone.textContent.trim().replace(/\s+/g, ' ');
              }
            }
            // 4. Any anchor with text content in the name cell
            if (!value) {
              const anyLink = cell.querySelector('a[href]');
              if (anyLink) {
                const clone = anyLink.cloneNode(true);
                clone.querySelectorAll('img, svg, i, [class*="icon"], [class*="avatar"]').forEach(el => el.remove());
                const text = clone.textContent.trim().replace(/\s+/g, ' ');
                if (text && text.length > 1 && !text.match(/^(Copy|More|Select)$/i)) {
                  value = text;
                }
              }
            }
            // 5. Last resort: get cell text directly
            if (!value) {
              const cellText = cell.textContent.trim()
                .replace(/\s*(Copy|More|Select|checkbox)\s*/gi, '')
                .replace(/\s+/g, ' ')
                .trim();
              if (cellText && cellText.length > 1) {
                value = cellText;
              }
            }
            break;
          case 'contact.job_title':
            const jobTitleSpan = cell.querySelector('.zp_FEm_X');
            value = jobTitleSpan ? jobTitleSpan.textContent.trim() : '';
            break;
          case 'contact.account':
            let companyNameSpan = cell.querySelector('.zp_xvo3G');
            if (companyNameSpan) {
              value = companyNameSpan.textContent.trim();
            } else {
              const companyLink = cell.querySelector('a[href*="/organizations/"], a[data-to*="/organizations/"]');
              if (companyLink) {
                companyNameSpan = companyLink.querySelector('.zp_xvo3G');
                if (companyNameSpan) {
                  value = companyNameSpan.textContent.trim();
                } else {
                  const linkClone = companyLink.cloneNode(true);
                  linkClone.querySelectorAll('img, svg, i').forEach(el => el.remove());
                  let linkText = linkClone.textContent.trim().replace(/\s+/g, ' ').trim();
                  if (linkText) value = linkText;
                }
              }
              if (!value) {
                const companyTextElements = cell.querySelectorAll('.zp_REh41, .zp_PaniY, .zp_xvo3G');
                const texts = Array.from(companyTextElements).map(el => el.textContent.trim()).filter(t => t && t.length > 0 && !t.match(/^(Copy|More)$/));
                if (texts.length > 0) value = texts[0];
              }
              if (!value) {
                const allText = cell.textContent.trim().replace(/\s*(Copy|More)\s*/g, '').replace(/\s+/g, ' ').trim();
                if (allText && allText.length > 1) value = allText;
              }
            }
            break;
          case 'contact.emails':
          case 'contact.phone_numbers':
            value = '';
            break;
          case 'contact.social':
            const socialLinks = cell.querySelectorAll('a[href]');
            const contactLinks = Array.from(socialLinks).map(a => a.getAttribute('href')).filter(Boolean);
            value = { _type: 'contact_links', links: contactLinks };
            break;
          case 'account.social':
            const companyLinks = cell.querySelectorAll('a[href]');
            const companyLinksArray = Array.from(companyLinks).map(a => a.getAttribute('href')).filter(Boolean);
            value = { _type: 'company_links', links: companyLinksArray };
            break;
          case 'account.industries':
            const industries = cell.querySelectorAll('.zp_izw7E span');
            value = Array.from(industries).map(s => s.textContent.trim()).filter(Boolean).join('; ');
            break;
          case 'account.keywords':
            const keywords = cell.querySelectorAll('.zp_izw7E span');
            const keywordTexts = Array.from(keywords).map(s => s.textContent.trim()).filter(Boolean);
            const filteredKeywords = keywordTexts.filter(k => !k.match(/^\+\d+$/));
            value = filteredKeywords.join('; ');
            break;
          default:
            const textSpans = cell.querySelectorAll('.zp_FEm_X');
            if (textSpans.length > 0) {
              const texts = Array.from(textSpans).map(s => s.textContent.trim()).filter(t => t && !t.match(/^(Copy|More)$/));
              value = texts.join('; ') || '';
            } else {
              let text = cell.textContent.trim().replace(/\s*(Copy|More)\s*/g, '').replace(/\s+/g, ' ').trim();
              value = text;
            }
        }
        rowData[header.name] = value;
      } else {
        rowData[header.name] = '';
      }
    });
    const hasData = Object.values(rowData).some(v => {
      if (typeof v === 'object' && v !== null) {
        if (v._type === 'company_links' || v._type === 'contact_links') {
          return v.links.length > 0;
        }
      }
      return v && (typeof v === 'string' ? v.trim() !== '' : true);
    });
    if (hasData) {
      rows.push(rowData);
    }
  });

  // Post-process rows to split both Links and Company · Links into dynamic columns
  const contactLinkTypesMap = new Map(); // Map for personal contact links
  const companyLinkTypesMap = new Map(); // Map for company links
  const linksKey = 'Links'; // Personal contact links
  const companyLinksKey = 'Company · Links'; // Company links
  
  // First pass: collect all link types for both personal and company links
  rows.forEach(row => {
    // Process personal contact links
    if (row[linksKey] && typeof row[linksKey] === 'object' && row[linksKey]._type === 'contact_links') {
      row[linksKey].links.forEach(link => {
        const linkType = detectLinkType(link);
        if (linkType && !contactLinkTypesMap.has(linkType)) {
          contactLinkTypesMap.set(linkType, `Links · ${linkType}`);
        }
      });
    }
    
    // Process company links
    if (row[companyLinksKey] && typeof row[companyLinksKey] === 'object' && row[companyLinksKey]._type === 'company_links') {
      row[companyLinksKey].links.forEach(link => {
        const linkType = detectLinkType(link);
        if (linkType && !companyLinkTypesMap.has(linkType)) {
          companyLinkTypesMap.set(linkType, `Company · ${linkType}`);
        }
      });
    }
  });
  
  // Second pass: split links into columns and remove the original columns
  // First, initialize all link type columns for all rows
  rows.forEach(row => {
    contactLinkTypesMap.forEach((columnName, linkType) => {
      row[columnName] = '';
    });
    companyLinkTypesMap.forEach((columnName, linkType) => {
      row[columnName] = '';
    });
  });
  
  // Then, populate the link columns for rows that have links
  rows.forEach(row => {
    // Process personal contact links
    if (row[linksKey] && typeof row[linksKey] === 'object' && row[linksKey]._type === 'contact_links') {
      row[linksKey].links.forEach(link => {
        const linkType = detectLinkType(link);
        if (linkType) {
          const columnName = contactLinkTypesMap.get(linkType);
          if (row[columnName]) {
            row[columnName] += '; ' + link;
          } else {
            row[columnName] = link;
          }
        }
      });
      // Remove the original Links column
      delete row[linksKey];
    }
    
    // Process company links
    if (row[companyLinksKey] && typeof row[companyLinksKey] === 'object' && row[companyLinksKey]._type === 'company_links') {
      row[companyLinksKey].links.forEach(link => {
        const linkType = detectLinkType(link);
        if (linkType) {
          const columnName = companyLinkTypesMap.get(linkType);
          if (row[columnName]) {
            row[columnName] += '; ' + link;
          } else {
            row[columnName] = link;
          }
        }
      });
      // Remove the original Company · Links column
      delete row[companyLinksKey];
    }
  });
  
  // Build final headers list
  const finalHeaders = [];
  headers.forEach(header => {
    // Skip the original Links and Company · Links columns
    if (header.name !== linksKey && header.name !== companyLinksKey) {
      finalHeaders.push(header.name);
    }
  });
  
  // Add dynamic link type columns in sorted order (personal links first, then company links)
  const contactLinkColumns = Array.from(contactLinkTypesMap.values()).sort();
  const companyLinkColumns = Array.from(companyLinkTypesMap.values()).sort();
  finalHeaders.push(...contactLinkColumns);
  finalHeaders.push(...companyLinkColumns);

  return { headers: finalHeaders, rows: rows };
}

