let scrapedData = [];
let scrapedHeaders = [];
let startTime = null;
let statusInterval = null;
let isScraping = false;
let shouldStop = false;
let scrapedPages = new Set(); // Track which pages have been scraped
let currentPageNumber = 1;

// === Cat-themed UI state ===
let memeInterval = null;
let currentMemeIndex = 0;

const catMemes = [
  "I can haz data?",
  "Purring through the rows...",
  "Knocking things off tables... into CSV",
  "If I fits, I scrapes",
  "Did someone say tuna? I mean data...",
  "Nap time? No! Scrape time!",
  "*aggressive biscuit making*",
  "This table is mine now",
  "Plotting world domination... one row at a time",
  "Am not lazy. Am energy efficient.",
  "Human, I require more pages",
  "404: Sleep not found",
  "*knocks your coffee off desk* More scraping!",
  "Meow-velous progress!",
  "I see data, I take data. Simple."
];

const catSVGs = {
  idle: `<svg class="cat-sitting" viewBox="0 0 48 48" fill="currentColor">
    <path d="M14 20L10 6l8 8h12l8-8-4 14"/>
    <ellipse cx="24" cy="24" rx="12" ry="10"/>
    <ellipse cx="24" cy="38" rx="10" ry="8"/>
    <circle cx="20" cy="22" r="2" fill="#1a1a2e"/>
    <circle cx="28" cy="22" r="2" fill="#1a1a2e"/>
    <ellipse cx="24" cy="26" rx="1.5" ry="1" fill="#f5a623"/>
    <path d="M34 36 Q40 32 42 26" stroke="currentColor" stroke-width="3" fill="none" stroke-linecap="round"/>
  </svg>`,
  scraping: `<svg class="cat-running" viewBox="0 0 48 48" fill="currentColor">
    <path d="M10 16L6 4l8 8h12l8-8-4 12"/>
    <ellipse cx="22" cy="22" rx="13" ry="9"/>
    <circle cx="18" cy="20" r="2.5" fill="#1a1a2e"/>
    <circle cx="27" cy="20" r="2.5" fill="#1a1a2e"/>
    <circle cx="19" cy="19" r="0.8" fill="#fff"/>
    <circle cx="28" cy="19" r="0.8" fill="#fff"/>
    <ellipse cx="22" cy="25" rx="1.5" ry="1" fill="#f5a623"/>
    <path d="M6 30 Q2 38 6 42" stroke="currentColor" stroke-width="3" fill="none" stroke-linecap="round"/>
    <path d="M38 30 Q42 38 38 42" stroke="currentColor" stroke-width="3" fill="none" stroke-linecap="round"/>
    <path d="M14 28 L10 40" stroke="currentColor" stroke-width="3" fill="none" stroke-linecap="round"/>
    <path d="M30 28 L34 40" stroke="currentColor" stroke-width="3" fill="none" stroke-linecap="round"/>
    <path d="M36 18 Q42 14 46 16" stroke="currentColor" stroke-width="3" fill="none" stroke-linecap="round"/>
  </svg>`,
  paused: `<svg class="cat-sleeping" viewBox="0 0 48 48" fill="currentColor">
    <path d="M14 22L10 8l8 8h12l8-8-4 14"/>
    <ellipse cx="24" cy="26" rx="13" ry="10"/>
    <ellipse cx="24" cy="40" rx="10" ry="6"/>
    <path d="M18 25 Q20 23 22 25" stroke="#1a1a2e" stroke-width="2" fill="none" stroke-linecap="round"/>
    <path d="M26 25 Q28 23 30 25" stroke="#1a1a2e" stroke-width="2" fill="none" stroke-linecap="round"/>
    <ellipse cx="24" cy="29" rx="1.5" ry="1" fill="#f5a623"/>
    <path d="M34 38 Q40 34 42 28" stroke="currentColor" stroke-width="3" fill="none" stroke-linecap="round"/>
    <text x="36" y="14" font-size="10" fill="#f5a623" font-weight="bold">z</text>
    <text x="40" y="10" font-size="8" fill="#f5a623" font-weight="bold">z</text>
    <text x="43" y="7" font-size="6" fill="#f5a623" font-weight="bold">z</text>
  </svg>`,
  finished: `<svg class="cat-happy" viewBox="0 0 48 48" fill="currentColor">
    <path d="M12 18L8 4l8 8h16l8-8-4 14"/>
    <ellipse cx="24" cy="24" rx="14" ry="11"/>
    <ellipse cx="24" cy="38" rx="10" ry="8"/>
    <path d="M17 22 Q19 19 21 22" stroke="#1a1a2e" stroke-width="2" fill="none" stroke-linecap="round"/>
    <path d="M27 22 Q29 19 31 22" stroke="#1a1a2e" stroke-width="2" fill="none" stroke-linecap="round"/>
    <ellipse cx="24" cy="27" rx="2" ry="1.2" fill="#f5a623"/>
    <path d="M20 29 Q24 34 28 29" stroke="#e94560" stroke-width="2" fill="none" stroke-linecap="round"/>
    <path d="M34 36 Q40 32 44 28" stroke="currentColor" stroke-width="3" fill="none" stroke-linecap="round"/>
    <circle cx="16" cy="26" r="3" fill="#e94560" opacity="0.3"/>
    <circle cx="32" cy="26" r="3" fill="#e94560" opacity="0.3"/>
  </svg>`
};

function startMemeRotation() {
  const bubble = document.getElementById('memeBubble');
  const memeText = document.getElementById('memeText');
  if (!bubble || !memeText) return;

  currentMemeIndex = Math.floor(Math.random() * catMemes.length);
  memeText.textContent = catMemes[currentMemeIndex];
  bubble.classList.remove('hidden', 'fade-out');

  if (memeInterval) clearInterval(memeInterval);
  memeInterval = setInterval(() => {
    bubble.classList.add('fade-out');
    setTimeout(() => {
      currentMemeIndex = (currentMemeIndex + 1) % catMemes.length;
      memeText.textContent = catMemes[currentMemeIndex];
      bubble.classList.remove('fade-out');
    }, 400);
  }, 5000);
}

function stopMemeRotation() {
  if (memeInterval) {
    clearInterval(memeInterval);
    memeInterval = null;
  }
  const bubble = document.getElementById('memeBubble');
  if (bubble) bubble.classList.add('hidden');
}

function updateCatReaction(state) {
  const container = document.getElementById('catReaction');
  if (!container) return;
  const svg = catSVGs[state] || catSVGs.idle;
  container.innerHTML = svg;
}

function updateCatWalkerPosition() {
  const walker = document.getElementById('catWalker');
  const fill = document.getElementById('progressFill');
  if (!walker || !fill) return;
  const width = fill.style.width ? parseFloat(fill.style.width) : 0;
  walker.style.left = `calc(${width}% - 4px)`;
  if (width > 0 && width < 100) {
    walker.classList.add('walking');
  } else {
    walker.classList.remove('walking');
  }
}

function triggerConfetti() {
  const container = document.getElementById('confettiContainer');
  if (!container) return;
  container.classList.remove('hidden');
  container.innerHTML = '';
  const colors = ['#e94560', '#f5a623', '#00d2ff', '#533483', '#4CAF50', '#ff6b6b'];
  for (let i = 0; i < 30; i++) {
    const piece = document.createElement('div');
    piece.className = 'confetti-piece';
    piece.style.left = Math.random() * 100 + '%';
    piece.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
    piece.style.animationDelay = (Math.random() * 2) + 's';
    piece.style.animationDuration = (2 + Math.random() * 2) + 's';
    container.appendChild(piece);
  }
  setTimeout(() => {
    container.classList.add('hidden');
    container.innerHTML = '';
  }, 5000);
}

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
    updateCatReaction('scraping');
    startMemeRotation();
    progressFill.classList.add('animating');

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
          progressFill.classList.remove('animating');
          updateCatReaction('finished');
          stopMemeRotation();
          triggerConfetti();
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
            updateCatWalkerPosition();
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
        updateCatWalkerPosition();
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
    progressFill.classList.remove('animating');
    updateCatReaction('paused');
    stopMemeRotation();
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
      updateCatReaction('idle');
      stopMemeRotation();
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
          updateCatReaction('scraping');
          startMemeRotation();
          progressFill.classList.add('animating');
        } else {
          // Check if scraping was interrupted (wasScraping flag)
          const saved = await chrome.storage.local.get(['wasScraping']);
          if (saved.wasScraping) {
            statusText.textContent = `Scraping was interrupted. ${scrapedData.length} contacts, page ${currentPageNumber}. Auto-resuming when you return to the tab...`;
            updateCatReaction('paused');
            // Auto-resume will happen when tab becomes active
          } else {
            // Update processed pages in saved progress
          const savedPages = await chrome.storage.local.get(['scrapedPages']);
          const processedCount = savedPages.scrapedPages ? savedPages.scrapedPages.length : scrapedPages.size;
          if (processedPages) processedPages.textContent = processedCount.toString();
          
          statusText.textContent = `Saved progress: ${scrapedData.length} contacts, page ${currentPageNumber}. Click "Start Scraping" to resume.`;
            updateCatReaction('idle');
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
    // Add UTF-8 BOM so Excel correctly handles non-ASCII characters
    const bom = '\uFEFF';
    const blob = new Blob([bom + csv], { type: 'text/csv;charset=utf-8;' });
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
        // Handle unprocessed link objects gracefully
        if (typeof value === 'object' && value._type && value.links) {
          return escapeCSV(value.links.join('; '));
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
        // Handle unprocessed link objects gracefully
        if (typeof value === 'object' && value._type && value.links) {
          return escapeTSV(value.links.join('; '));
        }
        return escapeTSV(value);
      });
      tsvRows.push(values.join('\t'));
    });
    
    return tsvRows.join('\n');
  }
});

