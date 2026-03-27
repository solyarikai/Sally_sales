let scrapedData = [];
let scrapedHeaders = [];
let startTime = null;
let statusInterval = null;
let isScraping = false;
let shouldStop = false;
let scrapedPages = new Set(); // Track which pages have been scraped
let currentPageNumber = 1;

// Load saved progress from storage
async function loadProgress() {
  try {
    const result = await chrome.storage.local.get(['scrapedData', 'scrapedHeaders', 'scrapedPages', 'currentPageNumber']);
    if (result.scrapedData) {
      scrapedData = result.scrapedData;
      scrapedHeaders = result.scrapedHeaders || [];
      scrapedPages = new Set(result.scrapedPages || []);
      currentPageNumber = result.currentPageNumber || 1;
      return true;
    }
  } catch (error) {
    console.error('Error loading progress:', error);
  }
  return false;
}

// Save progress to storage
async function saveProgress() {
  try {
    await chrome.storage.local.set({
      scrapedData: scrapedData,
      scrapedHeaders: scrapedHeaders,
      scrapedPages: Array.from(scrapedPages),
      currentPageNumber: currentPageNumber
    });
  } catch (error) {
    console.error('Error saving progress:', error);
  }
}

// Clear saved progress
async function clearProgress() {
  try {
    await chrome.storage.local.remove(['scrapedData', 'scrapedHeaders', 'scrapedPages', 'currentPageNumber']);
    scrapedData = [];
    scrapedHeaders = [];
    scrapedPages = new Set();
    currentPageNumber = 1;
  } catch (error) {
    console.error('Error clearing progress:', error);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const scrapeBtn = document.getElementById('scrapeBtn');
  const stopBtn = document.getElementById('stopBtn');
  const downloadCsvBtn = document.getElementById('downloadCsvBtn');
  const copyToSheetsBtn = document.getElementById('copyToSheetsBtn');
  const statusBox = document.getElementById('status');
  const contactsCount = document.getElementById('contactsCount');
  const statusText = document.getElementById('statusText');
  const previewSection = document.getElementById('dataPreview');
  const progressFill = document.getElementById('progressFill');
  const elapsedTime = document.getElementById('elapsedTime');
  const remainingTime = document.getElementById('remainingTime');
  const currentPage = document.getElementById('currentPage'); // Keep for internal use
  const processedPages = document.getElementById('processedPages');
  const totalPages = document.getElementById('totalPages');
  const progressPercent = document.getElementById('progressPercent');
  const contactsScraped = document.getElementById('contactsScraped');
  const totalContacts = document.getElementById('totalContacts');
  const clearBtn = document.getElementById('clearBtn');

  // Get current active tab
  async function getCurrentTab() {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    return tab;
  }

  // Start scraping with pagination (can run in background)
  scrapeBtn.addEventListener('click', async () => {
    const tab = await getCurrentTab();
    
    // Check if there's saved progress
    const hasProgress = await loadProgress();
    
    if (hasProgress && scrapedData.length > 0) {
      const resume = confirm(`Found saved progress: ${scrapedData.length} contacts scraped.\n\nResume from page ${currentPageNumber}? (Cancel to start fresh)`);
      if (!resume) {
        await clearProgress();
        scrapedData = [];
        scrapedHeaders = [];
        scrapedPages = new Set();
        currentPageNumber = 1;
      }
    } else {
      // Start fresh
      await clearProgress();
      scrapedData = [];
      scrapedHeaders = [];
      scrapedPages = new Set();
      currentPageNumber = 1;
    }
    
    scrapeBtn.disabled = true;
    stopBtn.disabled = false;
    downloadCsvBtn.disabled = false; // Enable download during scraping
    copyToSheetsBtn.disabled = false; // Enable copy during scraping
    statusBox.classList.remove('hidden');
    
    if (scrapedData.length > 0) {
      statusText.textContent = `Resuming from page ${currentPageNumber}... (${scrapedData.length} contacts already scraped)`;
      contactsCount.textContent = scrapedData.length.toLocaleString();
      contactsScraped.textContent = scrapedData.length.toLocaleString();
      if (currentPage) currentPage.textContent = (currentPageNumber - 1).toString();
      // Update processed pages count
      const processedCount = scrapedPages.size;
      if (processedPages) processedPages.textContent = processedCount.toString();
      if (scrapedHeaders.length > 0) {
        showPreview(scrapedHeaders, scrapedData);
      }
    } else {
      statusText.textContent = 'Initializing...';
      // Reset progress display
      if (currentPage) currentPage.textContent = '-';
      processedPages.textContent = '-';
      totalPages.textContent = '-';
      progressPercent.textContent = '0';
      contactsScraped.textContent = '0';
      totalContacts.textContent = '-';
      progressFill.style.width = '0%';
      contactsCount.textContent = '0';
    }
    
    isScraping = true;
    shouldStop = false;
    
    // Check if we have a saved start time (for resuming), otherwise create new one
    const savedStart = await chrome.storage.local.get(['scrapingStartTime']);
    if (!savedStart.scrapingStartTime) {
      // First time starting - save start time
      await chrome.storage.local.set({ scrapingStartTime: Date.now() });
      startTime = Date.now();
    } else {
      // Resuming - use saved start time
      startTime = savedStart.scrapingStartTime;
    }
    
    // Update status timer
    statusInterval = setInterval(updateTimer, 1000);
    updateTimer();

    // Start background scraping
    try {
      
      console.log('Sending startScraping message for tab:', tab.id);
      const response = await chrome.runtime.sendMessage({
        action: 'startScraping',
        tabId: tab.id
      });
      console.log('Response from background:', response);
      
      // Start polling for updates
      startProgressPolling();
      
      statusText.textContent = 'Scraping started. Tab must stay open. You can close this popup.';
    } catch (error) {
      console.error('Error starting scraping:', error);
      statusText.textContent = 'Error: ' + error.message;
      isScraping = false;
      scrapeBtn.disabled = false;
      stopBtn.disabled = true;
    }
  });
  
  // Poll for progress updates from background script
  function startProgressPolling() {
    const pollInterval = setInterval(async () => {
      if (!isScraping) {
        clearInterval(pollInterval);
        return;
      }
      
      // Check if scraping is still running
      try {
        const response = await chrome.runtime.sendMessage({ action: 'getScrapingStatus' });
        if (response && !response.isScraping) {
          // Scraping finished
          isScraping = false;
          clearInterval(pollInterval);
          await loadProgress();
          contactsCount.textContent = scrapedData.length.toLocaleString();
          statusText.textContent = `Completed! Scraped ${scrapedData.length} contacts`;
          scrapeBtn.disabled = false;
          stopBtn.disabled = true;
          if (scrapedHeaders.length > 0) {
            showPreview(scrapedHeaders, scrapedData);
          }
        } else if (response && response.isScraping) {
          // Update UI with latest progress
          await loadProgress();
          contactsCount.textContent = scrapedData.length.toLocaleString();
          contactsScraped.textContent = scrapedData.length.toLocaleString();
          if (currentPage) currentPage.textContent = currentPageNumber.toString();
          
          // Calculate progress if we have total
          const saved = await chrome.storage.local.get(['totalContacts', 'scrapingStartTime', 'scrapedPages']);
          if (saved.totalContacts) {
            const percent = Math.min(100, Math.round((scrapedData.length / saved.totalContacts) * 100));
            progressPercent.textContent = percent;
            progressFill.style.width = percent + '%';
            totalContacts.textContent = saved.totalContacts.toLocaleString();
            
            // Show processed pages count
            const processedCount = saved.scrapedPages ? saved.scrapedPages.length : scrapedPages.size;
            if (processedPages) processedPages.textContent = processedCount.toString();
            
            // Calculate estimated remaining time (recalculate based on current progress)
            if (saved.scrapingStartTime && scrapedData.length > 0 && saved.totalContacts) {
              const elapsed = (Date.now() - saved.scrapingStartTime) / 1000;
              if (elapsed > 0 && scrapedData.length > 0) {
                const rate = scrapedData.length / elapsed; // contacts per second
                const remaining = Math.ceil((saved.totalContacts - scrapedData.length) / rate);
                remainingTime.textContent = formatTime(remaining);
              } else {
                remainingTime.textContent = '~';
              }
            } else {
              remainingTime.textContent = '~';
            }
            
            // Calculate total pages
            if (saved.totalContacts && response.rowsPerPage && response.rowsPerPage > 0) {
              const pages = Math.ceil(saved.totalContacts / response.rowsPerPage);
              totalPages.textContent = pages.toString();
            } else if (saved.totalContacts && scrapedData.length > 0 && currentPageNumber > 0) {
              // Fallback: estimate from current progress
              const estimatedRowsPerPage = scrapedData.length / currentPageNumber;
              if (estimatedRowsPerPage > 0) {
                const pages = Math.ceil(saved.totalContacts / estimatedRowsPerPage);
                totalPages.textContent = pages.toString();
              }
            }
          }
        }
      } catch (e) {
        // Background script might not be responding, continue polling
      }
    }, 2000); // Poll every 2 seconds
  }
  
  // Listen for progress updates from background
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'progressUpdate') {
      // Update UI with progress
      contactsScraped.textContent = request.data.totalScraped.toLocaleString();
      if (currentPage) currentPage.textContent = request.data.pageNumber.toString();
      if (request.data.totalContacts) {
        totalContacts.textContent = request.data.totalContacts.toLocaleString();
        const percent = Math.min(100, Math.round((request.data.totalScraped / request.data.totalContacts) * 100));
        progressPercent.textContent = percent;
        progressFill.style.width = percent + '%';
      }
      statusText.textContent = `Scraping page ${request.data.pageNumber}... (${request.data.totalScraped} contacts scraped)`;
      
      // Reload data for preview
      loadProgress().then(() => {
        if (scrapedHeaders.length > 0) {
          showPreview(scrapedHeaders, scrapedData);
        }
      });
    }
    return true;
  });

  // Scrape all pages with pagination
  async function scrapeAllPages(tab) {
    let pageNumber = currentPageNumber; // Start from saved page
    let totalContactsCount = null;
    
    // Get current page from the page to determine if we need to navigate
    const getCurrentPageResult = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      function: getCurrentPageNumber
    });
    
    if (getCurrentPageResult && getCurrentPageResult[0] && getCurrentPageResult[0].result) {
      const detectedPage = getCurrentPageResult[0].result.page;
      if (detectedPage && detectedPage !== pageNumber) {
        // We're on a different page, use detected page number
        pageNumber = detectedPage;
        currentPageNumber = pageNumber;
      }
    }
    
    while (!shouldStop && isScraping) {
      // Skip if this page was already scraped
      if (scrapedPages.has(pageNumber)) {
        statusText.textContent = `Page ${pageNumber} already scraped, skipping...`;
        // Try to go to next page
        const hasNextResult = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          function: hasNextPage
        });
        
        if (hasNextResult && hasNextResult[0] && hasNextResult[0].result) {
          const clickResult = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            function: clickNextButton
          });
          if (clickResult && clickResult[0] && clickResult[0].result && clickResult[0].result.clicked) {
            await new Promise(resolve => setTimeout(resolve, 2000));
            pageNumber++;
            currentPageNumber = pageNumber;
            continue;
          }
        }
        break; // No more pages or can't navigate
      }
      
      // Wait for table to load (including rightmost columns)
      statusText.textContent = `Waiting for table to fully load... (Page ${pageNumber})`;
      
      let tableLoaded = false;
      let rightmostLoaded = false;
      const maxWaitAttempts = 100; // 100 attempts with 300ms delay = 30 seconds max
      for (let attempt = 0; attempt < maxWaitAttempts && !shouldStop; attempt++) {
        const waitResult = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          function: waitForTableLoad
        });
        
        if (waitResult && waitResult[0] && waitResult[0].result) {
          const result = waitResult[0].result;
          if (result.loaded) {
            tableLoaded = true;
            // Check if rightmost columns are loaded (if that check was performed)
            if (result.rightmostLoaded !== undefined) {
              rightmostLoaded = result.rightmostLoaded;
              if (rightmostLoaded) {
                break; // Fully loaded, including rightmost columns
              }
            } else {
              // No rightmost check, but table is loaded - wait a bit more for columns
              await new Promise(resolve => setTimeout(resolve, 500));
              break;
            }
          }
        }
        
        // Wait 300ms before checking again (longer delay for slower pages)
        await new Promise(resolve => setTimeout(resolve, 300));
        
        // Update status
        if (attempt % 10 === 0 && attempt > 0) {
          statusText.textContent = `Waiting for table to fully load... (Page ${pageNumber}, attempt ${attempt}/${maxWaitAttempts})`;
        }
      }
      
      if (!tableLoaded) {
        statusText.textContent = 'Error: Table did not load in time';
        break;
      }
      
      if (!rightmostLoaded && tableLoaded) {
        // Table loaded but rightmost columns might not be ready - wait a bit more
        statusText.textContent = `Waiting for all columns to load... (Page ${pageNumber})`;
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      
      // Get total count if not already known
      if (totalContactsCount === null) {
        const countResult = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          function: getTotalContactsCount
        });
        
        if (countResult && countResult[0] && countResult[0].result) {
          totalContactsCount = countResult[0].result.total;
          totalContacts.textContent = totalContactsCount.toLocaleString();
        }
      }
      
      // Scrape current page
      statusText.textContent = `Scraping page ${pageNumber}...`;
      
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        function: scrapeTable
      });

      if (results && results[0] && results[0].result) {
        const result = results[0].result;
        
        if (result.error) {
          statusText.textContent = `Error: ${result.error}`;
          break;
        }
        
        const pageRows = result.rows || [];
        const pageHeaders = result.headers || [];
        
        if (pageRows.length === 0) {
          statusText.textContent = 'No more data found. Scraping complete.';
          break;
        }
        
        // Store headers if not already stored
        if (scrapedHeaders.length === 0 && pageHeaders.length > 0) {
          scrapedHeaders = pageHeaders;
        }
        
        // Function to create a unique key for a contact (Name + Company)
        function getContactKey(row) {
          const name = (row['Name'] || '').trim().toLowerCase();
          const company = (row['Company'] || '').trim().toLowerCase();
          return `${name}|${company}`;
        }
        
        // Create a Set of existing contact keys for fast lookup
        const existingKeys = new Set(scrapedData.map(row => getContactKey(row)));
        
        // Filter out duplicates from new rows
        const uniqueNewRows = pageRows.filter(row => {
          const key = getContactKey(row);
          if (existingKeys.has(key)) {
            console.log(`Skipping duplicate: ${row['Name'] || 'Unknown'} at ${row['Company'] || 'Unknown'}`);
            return false;
          }
          existingKeys.add(key); // Add to set to prevent duplicates within the same batch
          return true;
        });
        
        // Add only unique new rows
        const duplicatesCount = pageRows.length - uniqueNewRows.length;
        scrapedData.push(...uniqueNewRows);
        scrapedPages.add(pageNumber); // Mark this page as scraped
        
        // Save progress after each page
        await saveProgress();
        
        // Update UI
        contactsCount.textContent = scrapedData.length.toLocaleString();
        contactsScraped.textContent = scrapedData.length.toLocaleString();
        if (currentPage) currentPage.textContent = pageNumber.toString();
        currentPageNumber = pageNumber;
        
        // Update status message with duplicate info
        if (duplicatesCount > 0) {
          console.log(`Filtered out ${duplicatesCount} duplicate(s) from page ${pageNumber}`);
          statusText.textContent = `Page ${pageNumber}: Added ${uniqueNewRows.length} contacts (${duplicatesCount} duplicates skipped) - Total: ${scrapedData.length}`;
        } else {
          statusText.textContent = `Page ${pageNumber}: Scraped ${uniqueNewRows.length} contacts (Total: ${scrapedData.length})`;
        }
        
        // Calculate progress
        if (totalContactsCount && totalContactsCount > 0) {
          const percent = Math.min(100, Math.round((scrapedData.length / totalContactsCount) * 100));
          progressPercent.textContent = percent;
          progressFill.style.width = percent + '%';
          
          // Calculate estimated remaining time
          const elapsed = (Date.now() - startTime) / 1000;
          if (scrapedData.length > 0 && elapsed > 0) {
            const rate = scrapedData.length / elapsed; // contacts per second
            const remaining = Math.ceil((totalContactsCount - scrapedData.length) / rate);
            remainingTime.textContent = formatTime(remaining);
          }
        }
        
            // Calculate total pages
            if (totalContactsCount && pageRows.length > 0) {
              const pages = Math.ceil(totalContactsCount / pageRows.length);
              totalPages.textContent = pages.toString();
            }
            
            // Update processed pages count
            const processedCount = scrapedPages.size;
            if (processedPages) processedPages.textContent = processedCount.toString();
            
            statusText.textContent = `Page ${pageNumber}: Scraped ${pageRows.length} contacts (Total: ${scrapedData.length})`;
        
        // Show preview with latest data
        showPreview(scrapedHeaders, scrapedData);
        
        // Check if there's a next page
        const hasNextResult = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          function: hasNextPage
        });
        
        if (!hasNextResult || !hasNextResult[0] || !hasNextResult[0].result) {
          statusText.textContent = 'No more pages. Scraping complete.';
          break;
        }
        
        const hasNext = hasNextResult[0].result;
        if (!hasNext) {
          statusText.textContent = 'All pages scraped!';
          break;
        }
        
        // Click next button
        statusText.textContent = `Clicking next page... (Page ${pageNumber + 1})`;
        const clickResult = await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          function: clickNextButton
        });
        
        if (!clickResult || !clickResult[0] || !clickResult[0].result) {
          statusText.textContent = 'Could not navigate to next page. Scraping complete.';
          break;
        }
        
        // Wait a bit for the page to load
        await new Promise(resolve => setTimeout(resolve, 2000));
        pageNumber++;
      } else {
        statusText.textContent = 'No data found on this page.';
        break;
      }
    }
  }
  
  function formatTime(seconds) {
    if (isNaN(seconds) || seconds === Infinity) return '~';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  // Stop button
  stopBtn.addEventListener('click', async () => {
    shouldStop = true;
    isScraping = false;
    statusText.textContent = 'Stopping...';
    
    // Stop background scraping
    try {
      chrome.runtime.sendMessage({ action: 'stopScraping' });
    } catch (e) {
      console.error('Error stopping scraping:', e);
    }
    
    scrapeBtn.disabled = false;
    stopBtn.disabled = true;
    if (statusInterval) {
      clearInterval(statusInterval);
      statusInterval = null;
    }
    // Save progress before stopping (but keep scrapingStartTime for elapsed time)
    await loadProgress();
    await saveProgress();
    
    // Update elapsed time one more time
    const saved = await chrome.storage.local.get(['scrapingStartTime']);
    if (saved.scrapingStartTime) {
      const elapsed = Math.floor((Date.now() - saved.scrapingStartTime) / 1000);
      elapsedTime.textContent = formatTime(elapsed);
    }
    
    statusText.textContent = `Stopped. Scraped ${scrapedData.length} contacts so far. Progress saved.`;
  });

  // Clear progress button
  clearBtn.addEventListener('click', async () => {
    if (isScraping) {
      alert('Cannot clear progress while scraping is in progress. Please stop first.');
      return;
    }
    
    const confirmClear = confirm('Are you sure you want to clear all saved progress? This cannot be undone.');
    if (confirmClear) {
      await clearProgress();
      // Also clear the start time
      await chrome.storage.local.remove(['scrapingStartTime']);
      startTime = null;
      if (contactsCount) contactsCount.textContent = '0';
      if (contactsScraped) contactsScraped.textContent = '0';
      if (currentPage) currentPage.textContent = '-';
      if (processedPages) processedPages.textContent = '-';
      if (totalPages) totalPages.textContent = '-';
      if (progressPercent) progressPercent.textContent = '0';
      if (totalContacts) totalContacts.textContent = '-';
      if (progressFill) progressFill.style.width = '0%';
      if (elapsedTime) elapsedTime.textContent = '0:00';
      if (remainingTime) remainingTime.textContent = '~';
      if (previewSection) previewSection.classList.add('hidden');
      if (statusText) statusText.textContent = 'Progress cleared. Ready to start fresh.';
      if (downloadCsvBtn) downloadCsvBtn.disabled = true;
      if (copyToSheetsBtn) copyToSheetsBtn.disabled = true;
    }
  });

  // Load progress on popup open (will be called after DOM is ready)
  (async () => {
    const hasProgress = await loadProgress();
    if (hasProgress && scrapedData.length > 0) {
      contactsCount.textContent = scrapedData.length.toLocaleString();
      contactsScraped.textContent = scrapedData.length.toLocaleString();
      if (currentPage) currentPage.textContent = currentPageNumber.toString();
      if (scrapedHeaders.length > 0) {
        showPreview(scrapedHeaders, scrapedData);
      }
      statusBox.classList.remove('hidden');
      
      // Update elapsed time from saved start time
      const saved = await chrome.storage.local.get(['scrapingStartTime', 'totalContacts']);
      if (saved.scrapingStartTime) {
        const elapsed = Math.floor((Date.now() - saved.scrapingStartTime) / 1000);
        elapsedTime.textContent = formatTime(elapsed);
        
        // Also update remaining time if we have total contacts
        if (saved.totalContacts && scrapedData.length > 0) {
          if (elapsed > 0) {
            const rate = scrapedData.length / elapsed;
            const remaining = Math.ceil((saved.totalContacts - scrapedData.length) / rate);
            remainingTime.textContent = formatTime(remaining);
          }
        }
      }
      
      // Check if background scraping is active
      try {
        const response = await chrome.runtime.sendMessage({ action: 'getScrapingStatus' });
        if (response && response.isScraping) {
          statusText.textContent = `Scraping in progress: ${scrapedData.length} contacts, page ${currentPageNumber}`;
          isScraping = true;
          scrapeBtn.disabled = true;
          stopBtn.disabled = false;
          downloadCsvBtn.disabled = false;
          copyToSheetsBtn.disabled = false;
          
          // Use saved start time if available (for resuming), otherwise create new one
          const savedStart = await chrome.storage.local.get(['scrapingStartTime']);
          if (!savedStart.scrapingStartTime) {
            await chrome.storage.local.set({ scrapingStartTime: Date.now() });
            startTime = Date.now();
          } else {
            startTime = savedStart.scrapingStartTime;
          }
          
          statusInterval = setInterval(updateTimer, 1000);
          updateTimer(); // Update immediately
          startProgressPolling();
        } else {
          // Check if scraping was interrupted (wasScraping flag)
          const saved = await chrome.storage.local.get(['wasScraping']);
          if (saved.wasScraping) {
            statusText.textContent = `Scraping was interrupted. ${scrapedData.length} contacts, page ${currentPageNumber}. Auto-resuming when you return to the tab...`;
            // Auto-resume will happen when tab becomes active
          } else {
            // Update processed pages in saved progress
          const savedPages = await chrome.storage.local.get(['scrapedPages']);
          const processedCount = savedPages.scrapedPages ? savedPages.scrapedPages.length : scrapedPages.size;
          if (processedPages) processedPages.textContent = processedCount.toString();
          
          statusText.textContent = `Saved progress: ${scrapedData.length} contacts, page ${currentPageNumber}. Click "Start Scraping" to resume.`;
          }
        downloadCsvBtn.disabled = false;
        copyToSheetsBtn.disabled = false;
      }
    } catch (e) {
      statusText.textContent = `Saved progress: ${scrapedData.length} contacts, page ${currentPageNumber}. Click "Start Scraping" to resume.`;
      downloadCsvBtn.disabled = false;
      copyToSheetsBtn.disabled = false;
    }
    }
  })();

  // Download CSV (can be called anytime, even during scraping)
  downloadCsvBtn.addEventListener('click', () => {
    if (scrapedData.length === 0) {
      alert('No data to download yet. Start scraping first.');
      return;
    }
    
    if (scrapedHeaders.length === 0) {
      alert('No headers found. Please wait for at least one page to be scraped.');
      return;
    }
    
    const csv = convertToCSV(scrapedHeaders, scrapedData);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    
    // Create filename with contact count and date
    const contactCount = scrapedData.length.toLocaleString().replace(/,/g, '');
    const date = new Date().toISOString().split('T')[0];
    const filename = `contacts_${contactCount}_${date}.csv`;
    
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  });

  // Copy to Google Sheets (can be called anytime, even during scraping)
  copyToSheetsBtn.addEventListener('click', async () => {
    if (scrapedData.length === 0) {
      alert('No data to copy yet. Start scraping first.');
      return;
    }
    
    if (scrapedHeaders.length === 0) {
      alert('No headers found. Please wait for at least one page to be scraped.');
      return;
    }
    
    try {
      const tsv = convertToTSV(scrapedHeaders, scrapedData);
      await navigator.clipboard.writeText(tsv);
      
      // Show success feedback
      const originalText = copyToSheetsBtn.textContent;
      copyToSheetsBtn.textContent = '✓ Copied!';
      copyToSheetsBtn.style.backgroundColor = '#28a745';
      setTimeout(() => {
        copyToSheetsBtn.textContent = originalText;
        copyToSheetsBtn.style.backgroundColor = '';
      }, 2000);
      
      // Show instructions
      alert(`${scrapedData.length} contacts copied to clipboard!\n\nOpen Google Sheets and press Ctrl+V (or Cmd+V on Mac) to paste.`);
    } catch (error) {
      console.error('Error copying to clipboard:', error);
      alert('Failed to copy to clipboard. Please try again or use the Download CSV option.');
    }
  });

  async function updateTimer() {
    // Get start time from storage to persist across stop/start
    const saved = await chrome.storage.local.get(['scrapingStartTime']);
    if (!saved.scrapingStartTime) return;
    
    const elapsed = Math.floor((Date.now() - saved.scrapingStartTime) / 1000);
    elapsedTime.textContent = formatTime(elapsed);
  }

  function showPreview(headers, rows) {
    const tableHead = document.getElementById('previewTableHead');
    const tableBody = document.getElementById('previewTableBody');
    
    // Clear previous content
    tableHead.innerHTML = '';
    tableBody.innerHTML = '';
    
    // Create header row
    const headerRow = document.createElement('tr');
    headers.forEach(header => {
      const th = document.createElement('th');
      th.textContent = header;
      headerRow.appendChild(th);
    });
    tableHead.appendChild(headerRow);
    
    // Show first 5 rows
    const previewRows = rows.slice(0, 5);
    previewRows.forEach(row => {
      const tr = document.createElement('tr');
      headers.forEach(header => {
        const td = document.createElement('td');
        const value = row[header] || '';
        td.textContent = typeof value === 'string' ? value : JSON.stringify(value);
        td.title = td.textContent; // Tooltip for long values
        tr.appendChild(td);
      });
      tableBody.appendChild(tr);
    });
    
    previewSection.classList.remove('hidden');
  }

  function convertToCSV(headers, data) {
    if (data.length === 0) return '';
    
    // Escape CSV values
    function escapeCSV(value) {
      if (value === null || value === undefined) return '';
      const str = String(value);
      if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return '"' + str.replace(/"/g, '""') + '"';
      }
      return str;
    }
    
    // Create CSV rows using the provided headers to maintain order
    const csvRows = [headers.map(escapeCSV).join(',')];
    
    data.forEach(row => {
      const values = headers.map(header => {
        const value = row[header];
        if (value === undefined || value === null) {
          return '';
        }
        if (Array.isArray(value)) {
          return escapeCSV(value.join('; '));
        }
        return escapeCSV(value);
      });
      csvRows.push(values.join(','));
    });
    
    return csvRows.join('\n');
  }

  function convertToTSV(headers, data) {
    if (data.length === 0) return '';
    
    // Escape TSV values - replace tabs and newlines
    function escapeTSV(value) {
      if (value === null || value === undefined) return '';
      const str = String(value);
      // Replace tabs with spaces and newlines with spaces
      return str.replace(/\t/g, ' ').replace(/\n/g, ' ').replace(/\r/g, '');
    }
    
    // Create TSV rows using the provided headers to maintain order
    const tsvRows = [headers.map(escapeTSV).join('\t')];
    
    data.forEach(row => {
      const values = headers.map(header => {
        const value = row[header];
        if (value === undefined || value === null) {
          return '';
        }
        if (Array.isArray(value)) {
          return escapeTSV(value.join('; '));
        }
        return escapeTSV(value);
      });
      tsvRows.push(values.join('\t'));
    });
    
    return tsvRows.join('\n');
  }
});

// This function will be injected into the page
function scrapeTable() {
  // Helper function to detect link type from URL (must be inside scrapeTable for injection)
  function detectLinkType(url) {
    if (!url) return null;
    
    const lowerUrl = url.toLowerCase();
    
    // Check for known social media platforms
    if (lowerUrl.includes('linkedin.com')) {
      return 'LinkedIn';
    } else if (lowerUrl.includes('facebook.com')) {
      return 'Facebook';
    } else if (lowerUrl.includes('twitter.com') || lowerUrl.includes('x.com')) {
      return 'Twitter';
    } else if (lowerUrl.includes('instagram.com')) {
      return 'Instagram';
    } else if (lowerUrl.includes('youtube.com')) {
      return 'YouTube';
    } else if (lowerUrl.includes('github.com')) {
      return 'GitHub';
    } else if (lowerUrl.startsWith('http://') || lowerUrl.startsWith('https://')) {
      // Any other HTTP/HTTPS URL is a website
      return 'Website';
    }
    
    return 'Website'; // Default fallback
  }

  // Try multiple selectors to find the table container
  let container = document.querySelector('[data-id="scrollable-table-container"]');
  
  if (!container) {
    // Fallback: look for table with role="rowgroup"
    container = document.querySelector('[role="rowgroup"]')?.closest('div');
  }
  
  if (!container) {
    // Another fallback: look for any table structure with role="row"
    const firstRow = document.querySelector('[role="row"][aria-rowindex]');
    container = firstRow?.closest('div');
  }
  
  if (!container) {
    console.error('Contacts Scraper: Could not find table container');
    return { headers: [], rows: [], error: 'Table container not found' };
  }

  // Find all column headers - look in the first rowgroup (header section)
  const headerRowGroups = container.querySelectorAll('[role="rowgroup"]');
  let headerRow = null;
  
  // First rowgroup should contain headers
  if (headerRowGroups.length > 0) {
    headerRow = headerRowGroups[0].querySelector('[role="row"]');
  }
  
  // Fallback: try to find header row directly
  if (!headerRow) {
    headerRow = container.querySelector('[role="row"]:not([aria-rowindex])');
  }
  
  // Another fallback: look for row with columnheader children
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
    console.error('Contacts Scraper: Could not find header row');
    return { headers: [], rows: [], error: 'Header row not found' };
  }

  const headers = [];
  const headerMap = new Map(); // Map aria-colindex to header info
  
  // Get all header cells including pinned containers
  const headerCells = headerRow.querySelectorAll('[role="columnheader"]');
  
  headerCells.forEach(cell => {
    const dataId = cell.getAttribute('data-id');
    const colIndex = parseInt(cell.getAttribute('aria-colindex') || '0');
    
    // Skip checkbox, add column buttons, and unwanted columns
    const unwantedColumns = ['leftActions', 'addNewColumn', 'actions'];
    const unwantedDataIds = ['actions'];
    
    if (dataId && !unwantedColumns.includes(dataId) && !unwantedDataIds.includes(dataId) && colIndex > 0) {
      // Get the readable header name
      const span = cell.querySelector('span');
      const headerName = span ? span.textContent.trim() : dataId;
      
      // Skip unwanted columns by name
      const unwantedNames = ['Actions', 'Emails', 'Phone numbers', 'People Auto-Score'];
      if (unwantedNames.includes(headerName)) {
        return; // Skip this column
      }
      
      const headerInfo = {
        id: dataId,
        name: headerName || dataId,
        colIndex: colIndex
      };
      
      headers.push(headerInfo);
      headerMap.set(colIndex, headerInfo);
    }
  });

  // Find all data rows - look in the second rowgroup (data section)
  const rowGroup = headerRowGroups.length > 1 ? headerRowGroups[1] : container.querySelector('[role="rowgroup"]:last-of-type');
  
  if (!rowGroup) {
    return { headers: headers.map(h => h.name), rows: [] };
  }

  const rows = [];
  const dataRows = rowGroup.querySelectorAll('[role="row"]');

  dataRows.forEach(row => {
    const rowData = {};
    
    headers.forEach((header) => {
      // Find cell by aria-colindex for accurate matching
      // Check both regular cells and gridcells, in all containers (including pinned)
      let cell = row.querySelector(`[role="cell"][aria-colindex="${header.colIndex}"], [role="gridcell"][aria-colindex="${header.colIndex}"]`);
      
      // If not found, try searching in pinned containers
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
        
        // Extract value based on column type
        switch (header.id) {
          case 'contact.name':
            // New format: button inside anchor with /contacts/ path
            const nameButtonSpan = cell.querySelector('a[href*="/contacts/"] button span.zp_pHNm5');
            if (nameButtonSpan) {
              value = nameButtonSpan.textContent.trim();
            } else {
              // Old format: text directly in anchor with /people/ path
              const nameLink = cell.querySelector('a[href*="/people/"]');
              value = nameLink ? nameLink.textContent.trim() : '';
            }
            break;
            
          case 'contact.job_title':
            const jobTitleSpan = cell.querySelector('.zp_FEm_X');
            value = jobTitleSpan ? jobTitleSpan.textContent.trim() : '';
            break;
            
          case 'contact.account':
            // Extract company name - try multiple strategies
            // Strategy 1: Look for span with class zp_xvo3G (most common)
            let companyNameSpan = cell.querySelector('.zp_xvo3G');
            if (companyNameSpan) {
              value = companyNameSpan.textContent.trim();
            } else {
              // Strategy 2: Find link with organizations, then look for span inside
              const companyLink = cell.querySelector('a[href*="/organizations/"], a[data-to*="/organizations/"]');
              if (companyLink) {
                // Look for the span inside the link
                companyNameSpan = companyLink.querySelector('.zp_xvo3G');
                if (companyNameSpan) {
                  value = companyNameSpan.textContent.trim();
                } else {
                  // Strategy 3: Get link text, but filter out images and icons
                  const linkClone = companyLink.cloneNode(true);
                  // Remove images and icons
                  linkClone.querySelectorAll('img, svg, i').forEach(el => el.remove());
                  let linkText = linkClone.textContent.trim();
                  // Clean up whitespace
                  linkText = linkText.replace(/\s+/g, ' ').trim();
                  if (linkText) {
                    value = linkText;
                  }
                }
              }
              
              // Strategy 4: If still empty, look for any text in zp_REh41 or zp_PaniY
              if (!value) {
                const companyTextElements = cell.querySelectorAll('.zp_REh41, .zp_PaniY, .zp_xvo3G');
                const texts = Array.from(companyTextElements)
                  .map(el => el.textContent.trim())
                  .filter(t => t && t.length > 0 && !t.match(/^(Copy|More)$/));
                if (texts.length > 0) {
                  value = texts[0]; // Take the first non-empty text
                }
              }
              
              // Strategy 5: Last resort - get all visible text and clean it
              if (!value) {
                const allText = cell.textContent.trim();
                // Remove common UI elements
                const cleaned = allText
                  .replace(/\s*(Copy|More)\s*/g, '')
                  .replace(/\s+/g, ' ')
                  .trim();
                if (cleaned && cleaned.length > 1) {
                  value = cleaned;
                }
              }
            }
            break;
            
          case 'contact.emails':
            // Skip this column - already filtered out at header level
            value = '';
            break;
            
          case 'contact.phone_numbers':
            // Skip this column - already filtered out at header level
            value = '';
            break;
            
          case 'contact.social':
            // Store links as array for later processing - we'll split by type
            const socialLinks = cell.querySelectorAll('a[href]');
            const contactLinks = Array.from(socialLinks).map(a => a.getAttribute('href')).filter(Boolean);
            // Store as special object to indicate it needs splitting
            value = { _type: 'contact_links', links: contactLinks };
            break;
            
          case 'account.social':
            // Store links as array for later processing - we'll split by type
            const companyLinks = cell.querySelectorAll('a[href]');
            const companyLinksArray = Array.from(companyLinks).map(a => a.getAttribute('href')).filter(Boolean);
            // Store as special object to indicate it needs splitting
            value = { _type: 'company_links', links: companyLinksArray };
            break;
            
          case 'account.industries':
            const industries = cell.querySelectorAll('.zp_izw7E span');
            value = Array.from(industries).map(s => s.textContent.trim()).filter(Boolean).join('; ');
            break;
            
          case 'account.keywords':
            const keywords = cell.querySelectorAll('.zp_izw7E span');
            const keywordTexts = Array.from(keywords).map(s => s.textContent.trim()).filter(Boolean);
            // Remove the "+X" count elements
            const filteredKeywords = keywordTexts.filter(k => !k.match(/^\+\d+$/));
            value = filteredKeywords.join('; ');
            break;
            
          default:
            // Generic extraction - try to find text content
            const textSpans = cell.querySelectorAll('.zp_FEm_X');
            if (textSpans.length > 0) {
              const texts = Array.from(textSpans)
                .map(s => s.textContent.trim())
                .filter(t => t && !t.match(/^(Copy|More)$/));
              value = texts.join('; ') || '';
            } else {
              // Fallback to all text, but clean it up
              let text = cell.textContent.trim();
              // Remove common UI text
              text = text.replace(/\s*(Copy|More)\s*/g, '');
              value = text;
            }
        }
        
        rowData[header.name] = value;
      } else {
        rowData[header.name] = '';
      }
    });
    
    // Only add row if it has at least one non-empty value
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
  
  return {
    headers: finalHeaders,
    rows: rows
  };
}

// Check if table is loaded (checks for rightmost columns to ensure full load)
function waitForTableLoad() {
  const container = document.querySelector('[data-id="scrollable-table-container"]');
  if (!container) {
    return { loaded: false };
  }
  
  // Check if table has rows
  const rows = container.querySelectorAll('[role="row"][aria-rowindex]');
  if (rows.length === 0) {
    return { loaded: false };
  }
  
  // Check for rightmost columns to ensure everything is loaded
  // These columns are typically loaded last: Company · Website, Company · LinkedIn, etc.
  const rightmostColumnIds = [
    'account.social',  // Company · Links (contains Website, LinkedIn, etc.)
    'account.keywords', // Company · Keywords
    'contact.location', // Location
    'account.number_of_employees' // Company · Number of employees
  ];
  
  // Get header row to find column indices
  const headerRowGroups = container.querySelectorAll('[role="rowgroup"]');
  if (headerRowGroups.length === 0) {
    return { loaded: false };
  }
  
  const headerRow = headerRowGroups[0].querySelector('[role="row"]');
  if (!headerRow) {
    return { loaded: false };
  }
  
  // Find rightmost column indices
  const rightmostColIndices = [];
  const headerCells = headerRow.querySelectorAll('[role="columnheader"]');
  headerCells.forEach(cell => {
    const dataId = cell.getAttribute('data-id');
    const colIndex = parseInt(cell.getAttribute('aria-colindex') || '0');
    if (rightmostColumnIds.includes(dataId) && colIndex > 0) {
      rightmostColIndices.push(colIndex);
    }
  });
  
  // If we found rightmost columns, check if they have data
  if (rightmostColIndices.length > 0) {
    let samplesWithRightmostData = 0;
    const sampleSize = Math.min(3, rows.length); // Check first 3 rows
    
    for (let i = 0; i < sampleSize; i++) {
      const row = rows[i];
      let hasRightmostData = false;
      
      // Check if at least one rightmost column has data in this row
      for (const colIndex of rightmostColIndices) {
        const cell = row.querySelector(`[role="cell"][aria-colindex="${colIndex}"], [role="gridcell"][aria-colindex="${colIndex}"]`);
        if (cell) {
          // Check for Company · Website (account.social) - look for links
          if (colIndex === rightmostColIndices[0]) { // account.social
            const links = cell.querySelectorAll('a[href]');
            if (links.length > 0) {
              hasRightmostData = true;
              break;
            }
          } else {
            // For other columns, check if there's any text content
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
    
    // If at least 2 out of 3 sample rows have rightmost data, consider loaded
    if (samplesWithRightmostData >= Math.min(2, sampleSize)) {
      return { loaded: true, rowCount: rows.length, rightmostLoaded: true };
    }
    
    // If we have rows but rightmost columns aren't loaded yet
    return { loaded: false, rowCount: rows.length, rightmostLoaded: false };
  }
  
  // Fallback: if we can't find rightmost columns, just check if rows exist
  return { loaded: rows.length > 0, rowCount: rows.length };
}

// Get total contacts count from pagination
function getTotalContactsCount() {
  // Look for pagination text like "1 - 25 of 2,690"
  const paginationText = document.body.innerText.match(/(\d+)\s*-\s*(\d+)\s+of\s+([\d,]+)/i);
  if (paginationText && paginationText[3]) {
    const total = parseInt(paginationText[3].replace(/,/g, ''));
    return { total: total };
  }
  
  // Alternative: look for pagination elements
  const paginationElements = document.querySelectorAll('[role="status"], [aria-live]');
  for (let el of paginationElements) {
    const text = el.textContent;
    const match = text.match(/of\s+([\d,]+)/i);
    if (match && match[1]) {
      const total = parseInt(match[1].replace(/,/g, ''));
      return { total: total };
    }
  }
  
  // Look in any element that might contain the count
  const allText = document.body.innerText;
  const matches = allText.match(/of\s+([\d,]+)/gi);
  if (matches && matches.length > 0) {
    const lastMatch = matches[matches.length - 1];
    const totalMatch = lastMatch.match(/([\d,]+)/);
    if (totalMatch) {
      const total = parseInt(totalMatch[1].replace(/,/g, ''));
      if (total > 0) {
        return { total: total };
      }
    }
  }
  
  return { total: null };
}

// Check if there's a next page
function hasNextPage() {
  // Find the next button
  const nextButton = document.querySelector('button[aria-label="Next"], button[aria-label*="Next" i]');
  if (!nextButton) {
    return false;
  }
  
  // Check if button is disabled
  const isDisabled = nextButton.disabled || 
                  nextButton.getAttribute('aria-disabled') === 'true' ||
                  nextButton.classList.contains('disabled') ||
                  nextButton.hasAttribute('disabled');
  
  return !isDisabled;
}

// Click the next button
function clickNextButton() {
  const nextButton = document.querySelector('button[aria-label="Next"], button[aria-label*="Next" i]');
  if (!nextButton) {
    return { clicked: false, error: 'Next button not found' };
  }
  
  // Check if button is disabled
  const isDisabled = nextButton.disabled || 
                  nextButton.getAttribute('aria-disabled') === 'true' ||
                  nextButton.classList.contains('disabled') ||
                  nextButton.hasAttribute('disabled');
  
  if (isDisabled) {
    return { clicked: false, error: 'Next button is disabled' };
  }
  
  // Click the button
  try {
    nextButton.click();
    return { clicked: true };
  } catch (error) {
    return { clicked: false, error: error.message };
  }
}

// Get current page number from pagination
function getCurrentPageNumber() {
  // Look for pagination text like "1 - 25 of 2,690" or "1-25 of 2,690"
  const paginationText = document.body.innerText.match(/(\d+)\s*-\s*(\d+)\s+of\s+([\d,]+)/i);
  if (paginationText && paginationText[1]) {
    // Calculate page number from "1 - 25" means page 1 if first number is 1
    // If "26 - 50" and page size is 25, that's page 2
    const start = parseInt(paginationText[1]);
    const end = parseInt(paginationText[2]);
    const pageSize = end - start + 1;
    if (pageSize > 0) {
      const page = Math.ceil(start / pageSize);
      return { page: page };
    }
  }
  
  // Try to find page number input
  const pageInput = document.querySelector('input[type="number"][aria-label*="page" i], input[type="number"][aria-label*="Page" i]');
  if (pageInput && pageInput.value) {
    return { page: parseInt(pageInput.value) };
  }
  
  // Look for URL parameter if it contains page number
  const urlParams = new URLSearchParams(window.location.search);
  const pageParam = urlParams.get('page');
  if (pageParam) {
    const page = parseInt(pageParam);
    if (!isNaN(page) && page > 0) {
      return { page: page };
    }
  }
  
  // Default to page 1 if we can't determine
  return { page: 1 };
}

