const chatDiv = document.getElementById('chat');
const input = document.getElementById('input');

const screenshotBtn = document.getElementById('screenshotBtn');
const saveScreenshotBtn = document.getElementById('saveScreenshotBtn');

const startRecordingBtn = document.getElementById('startRecordingBtn');
const stopRecordingBtn = document.getElementById('stopRecordingBtn');

let lastScreenshotUrl = null;
let mediaRecorder = null;
let recordedChunks = [];

// Helper to log messages in chat div
function logMessage(message) {
  const msgElem = document.createElement('div');
  msgElem.textContent = message;
  chatDiv.appendChild(msgElem);
  chatDiv.scrollTop = chatDiv.scrollHeight;
}

// --- Screenshot ---

screenshotBtn.addEventListener('click', () => {
  logMessage('Taking screenshot...');
  chrome.runtime.sendMessage({ action: 'take_screenshot' }, (response) => {
    if (response && response.screenshotUrl) {
      lastScreenshotUrl = response.screenshotUrl;

      const img = document.createElement('img');
      img.src = lastScreenshotUrl;
      img.style.maxWidth = '100%';
      chatDiv.appendChild(img);
      chatDiv.scrollTop = chatDiv.scrollHeight;

      saveScreenshotBtn.disabled = false;
      logMessage('Screenshot taken!');
    } else {
      logMessage('Error taking screenshot: ' + (response?.error || 'Unknown error'));
      saveScreenshotBtn.disabled = true;
      lastScreenshotUrl = null;
    }
  });
});

saveScreenshotBtn.addEventListener('click', () => {
  if (!lastScreenshotUrl) return;

  const a = document.createElement('a');
  a.href = lastScreenshotUrl;
  a.download = 'screenshot.png';
  a.click();

  logMessage('Screenshot saved.');
});

// --- Chat input ---

input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && input.value.trim() !== '') {
    const message = `You: ${input.value.trim()}`;
    logMessage(message);
    input.value = '';
  }
});

// --- Screen recording ---

startRecordingBtn.addEventListener('click', async () => {
  try {
    logMessage('Requesting screen and audio capture...');
    const stream = await navigator.mediaDevices.getDisplayMedia({
      video: true,
      audio: true,
    });

    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) recordedChunks.push(e.data);
    };

    mediaRecorder.onstop = () => {
      const blob = new Blob(recordedChunks, { type: 'video/webm' });
      recordedChunks = [];

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'recording.webm';
      a.click();
      URL.revokeObjectURL(url);

      logMessage('Screen recording saved.');
    };

    mediaRecorder.start();

    startRecordingBtn.disabled = true;
    stopRecordingBtn.disabled = false;

    logMessage('Recording started.');

    // Stop tracks on recording stop
    mediaRecorder.stream = stream;
  } catch (err) {
    logMessage('Error starting recording: ' + err);
  }
});

stopRecordingBtn.addEventListener('click', () => {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach(track => track.stop());

    startRecordingBtn.disabled = false;
    stopRecordingBtn.disabled = true;

    logMessage('Recording stopped.');
  }
});
