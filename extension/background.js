chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'take_screenshot') {
    chrome.tabs.captureVisibleTab(null, { format: 'png' }, (dataUrl) => {
      if (chrome.runtime.lastError) {
        console.error('Capture error:', chrome.runtime.lastError.message);
        sendResponse({ error: chrome.runtime.lastError.message });
      } else {
        sendResponse({ screenshotUrl: dataUrl });
      }
    });
    return true; // async response
  }
});
