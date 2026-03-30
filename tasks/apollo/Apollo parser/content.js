// Content script to display scraping progress on the page

let progressOverlay = null;

// Create progress overlay
function createProgressOverlay() {
  if (progressOverlay) {
    return; // Already exists
  }
  
  progressOverlay = document.createElement('div');
  progressOverlay.id = 'contacts-scraper-overlay';
  progressOverlay.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: #fff;
    border: 2px solid #4CAF50;
    border-radius: 8px;
    padding: 16px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    z-index: 100000;
    min-width: 250px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 14px;
    display: none;
  `;
  
  progressOverlay.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
      <strong style="color: #4CAF50; font-size: 16px;">Contacts Scraper</strong>
      <button id="scraper-close-btn" style="background: none; border: none; font-size: 20px; cursor: pointer; color: #999;">×</button>
    </div>
    <div id="scraper-status" style="color: #666; margin-bottom: 8px;">Ready</div>
    <div style="margin-bottom: 8px;">
      <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
        <span>Progress:</span>
        <span id="scraper-percent">0%</span>
      </div>
      <div style="background: #e0e0e0; border-radius: 4px; height: 8px; overflow: hidden;">
        <div id="scraper-progress-bar" style="background: #4CAF50; height: 100%; width: 0%; transition: width 0.3s;"></div>
      </div>
    </div>
    <div style="font-size: 12px; color: #888; line-height: 1.6;">
      <div>Scraped: <span id="scraper-count">0</span></div>
      <div>Page: <span id="scraper-page">-</span></div>
    </div>
  `;
  
  document.body.appendChild(progressOverlay);
  
  // Close button
  const closeBtn = progressOverlay.querySelector('#scraper-close-btn');
  closeBtn.addEventListener('click', () => {
    progressOverlay.style.display = 'none';
  });
}

// Update progress display
function updateProgress(data) {
  if (!progressOverlay) {
    createProgressOverlay();
  }
  
  progressOverlay.style.display = 'block';
  
  const statusEl = document.getElementById('scraper-status');
  const percentEl = document.getElementById('scraper-percent');
  const progressBarEl = document.getElementById('scraper-progress-bar');
  const countEl = document.getElementById('scraper-count');
  const pageEl = document.getElementById('scraper-page');
  
  if (statusEl) statusEl.textContent = data.status || 'Scraping...';
  if (pageEl) pageEl.textContent = data.pageNumber || '-';
  if (countEl) countEl.textContent = (data.totalScraped || 0).toLocaleString();
  
  if (data.totalContacts && data.totalScraped !== undefined) {
    const percent = Math.min(100, Math.round((data.totalScraped / data.totalContacts) * 100));
    if (percentEl) percentEl.textContent = percent + '%';
    if (progressBarEl) progressBarEl.style.width = percent + '%';
  }
}

// Listen for messages from background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'updateProgress') {
    updateProgress(request.data);
    sendResponse({ success: true });
  } else if (request.action === 'hideProgress') {
    if (progressOverlay) {
      progressOverlay.style.display = 'none';
    }
    sendResponse({ success: true });
  }
  // Don't return true — all responses are synchronous
});

// Initialize on page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', createProgressOverlay);
} else {
  createProgressOverlay();
}
