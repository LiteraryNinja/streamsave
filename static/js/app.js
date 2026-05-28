// DOM Elements
const videoUrlInput = document.getElementById('videoUrlInput');
const btnPaste = document.getElementById('btnPaste');
const btnAnalyze = document.getElementById('btnAnalyze');
const btnBack = document.getElementById('btnBack');
const btnDownload = document.getElementById('btnDownload');

const mainCard = document.getElementById('mainCard');
const inputStage = document.getElementById('inputStage');
const previewStage = document.getElementById('previewStage');
const downloadStage = document.getElementById('downloadStage');

const videoThumbnail = document.getElementById('videoThumbnail');
const videoDuration = document.getElementById('videoDuration');
const platformBadge = document.getElementById('platformBadge');
const uploaderBadge = document.getElementById('uploaderBadge');
const videoTitle = document.getElementById('videoTitle');
const formatSelect = document.getElementById('formatSelect');

const progressBarFill = document.getElementById('progressBarFill');
const progressPercent = document.getElementById('progressPercent');
const progressFilesize = document.getElementById('progressFilesize');
const downloadStatusTitle = document.getElementById('downloadStatusTitle');
const toastContainer = document.getElementById('toastContainer');

// State Variables
let currentVideoData = null;

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
});

// Event Bindings
function setupEventListeners() {
    // Clipboard Paste Integration
    btnPaste.addEventListener('click', handlePaste);

    // Enter Key Submission in Input Box
    videoUrlInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            analyzeUrl();
        }
    });

    // Button Actions
    btnAnalyze.addEventListener('click', analyzeUrl);
    btnBack.addEventListener('click', resetApp);
    btnDownload.addEventListener('click', startDownload);
}

// Clipboard Paste Handler
async function handlePaste() {
    try {
        if (!navigator.clipboard) {
            showToast('Your browser does not support automatic pasting. Please use Cmd+V / Ctrl+V.', 'error');
            return;
        }
        const text = await navigator.clipboard.readText();
        if (text) {
            videoUrlInput.value = text.trim();
            videoUrlInput.focus();
            showToast('Link pasted successfully!', 'success');
        } else {
            showToast('Clipboard is empty or does not contain readable text.', 'info');
        }
    } catch (err) {
        showToast('Clipboard access denied. Please paste manually.', 'info');
    }
}

// Analyze Input Link
async function analyzeUrl() {
    const url = videoUrlInput.value.trim();
    if (!url) {
        showToast('Please paste a valid video address first.', 'info');
        return;
    }

    if (!isValidUrl(url)) {
        showToast('That does not look like a valid link. Please check it and try again.', 'error');
        return;
    }

    // Enter Loading State
    setLoadingState(true);

    try {
        const response = await fetch('/api/info', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to extract video information.');
        }

        // Cache response and render preview
        currentVideoData = data;
        renderPreview(data);

        // Transition Stages
        inputStage.classList.add('hide');
        previewStage.classList.remove('hide');
        showToast('Video analyzed successfully!', 'success');

    } catch (err) {
        console.error(err);
        showToast(err.message || 'An error occurred while loading video details.', 'error');
    } finally {
        setLoadingState(false);
    }
}

// Render Video Preview Data
function renderPreview(data) {
    videoThumbnail.src = data.thumbnail || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500&auto=format&fit=crop&q=60';
    videoThumbnail.onerror = () => {
        videoThumbnail.src = 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500&auto=format&fit=crop&q=60';
    };

    videoTitle.textContent = data.title;
    videoDuration.textContent = formatDuration(data.duration);
    uploaderBadge.textContent = data.uploader;
    
    // Platform styling
    const platform = data.platform.toLowerCase();
    platformBadge.textContent = data.platform;
    platformBadge.className = 'platform-badge'; // reset
    if (platform.includes('youtube')) {
        platformBadge.style.background = 'rgba(239, 68, 68, 0.15)';
        platformBadge.style.color = '#f87171';
        platformBadge.style.borderColor = 'rgba(239, 68, 68, 0.25)';
    } else if (platform.includes('tiktok')) {
        platformBadge.style.background = 'rgba(0, 0, 0, 0.4)';
        platformBadge.style.color = '#ffffff';
        platformBadge.style.borderColor = 'rgba(255, 255, 255, 0.15)';
    } else if (platform.includes('vimeo')) {
        platformBadge.style.background = 'rgba(14, 165, 233, 0.15)';
        platformBadge.style.color = '#38bdf8';
        platformBadge.style.borderColor = 'rgba(14, 165, 233, 0.25)';
    } else {
        platformBadge.style.background = 'rgba(168, 85, 247, 0.15)';
        platformBadge.style.color = '#c084fc';
        platformBadge.style.borderColor = 'rgba(168, 85, 247, 0.25)';
    }

    // Populate format dropdown
    formatSelect.innerHTML = '';
    
    if (!data.formats || data.formats.length === 0) {
        // Fallback option
        const opt = document.createElement('option');
        opt.value = JSON.stringify({ url: data.original_url, ext: 'mp4' });
        opt.textContent = 'Best Quality (Direct Stream)';
        formatSelect.appendChild(opt);
    } else {
        data.formats.forEach(f => {
            const opt = document.createElement('option');
            opt.value = JSON.stringify(f);
            
            const sizeText = f.filesize ? ` ~ ${f.filesize} MB` : ' (Size unknown)';
            const extText = f.ext ? `.${f.ext.toUpperCase()}` : '.MP4';
            opt.textContent = `${f.resolution} (${extText})${sizeText}`;
            formatSelect.appendChild(opt);
        });
    }
}

// Active ReadableStream Downloading Manager
async function startDownload() {
    const selectVal = formatSelect.value;
    if (!selectVal) {
        showToast('Please select a format quality.', 'info');
        return;
    }

    const selectedFormat = JSON.parse(selectVal);
    const downloadUrl = selectedFormat.url;
    const formatId = selectedFormat.format_id;
    const ext = selectedFormat.ext || 'mp4';
    const title = currentVideoData.title;

    if (!downloadUrl && !currentVideoData.original_url) {
        showToast('Video download parameters not found.', 'error');
        return;
    }

    // Transition to Download Stage
    previewStage.classList.add('hide');
    downloadStage.classList.remove('hide');
    
    // Reset progress UI
    progressBarFill.style.width = '0%';
    progressPercent.textContent = 'Connecting...';
    progressFilesize.textContent = '';
    downloadStatusTitle.textContent = 'Saving Your Video...';

    try {
        let fetchUrl;
        if (currentVideoData.original_url) {
            fetchUrl = `/api/download?original_url=${encodeURIComponent(currentVideoData.original_url)}&format_id=${encodeURIComponent(formatId)}&title=${encodeURIComponent(title)}&ext=${ext}`;
        } else {
            fetchUrl = `/api/download?url=${encodeURIComponent(downloadUrl)}&title=${encodeURIComponent(title)}&ext=${ext}`;
        }
        const response = await fetch(fetchUrl);

        if (!response.ok) {
            throw new Error('Server returned error while launching stream download.');
        }

        const reader = response.body.getReader();
        const totalBytes = parseInt(response.headers.get('Content-Length'), 10) || 0;
        
        let receivedBytes = 0;
        const chunks = [];

        // Read stream data chunk-by-chunk
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            chunks.push(value);
            receivedBytes += value.length;

            // Compute and render real-time UI updates
            if (totalBytes > 0) {
                const percent = Math.round((receivedBytes / totalBytes) * 100);
                progressBarFill.style.width = `${percent}%`;
                progressPercent.textContent = `Downloading: ${percent}%`;
                progressFilesize.textContent = `${formatBytes(receivedBytes)} of ${formatBytes(totalBytes)}`;
            } else {
                progressBarFill.style.width = '100%';
                progressBarFill.style.animation = 'pulseGlow 1.5s infinite';
                progressPercent.textContent = 'Downloading (Size unknown)...';
                progressFilesize.textContent = `${formatBytes(receivedBytes)} downloaded`;
            }
        }

        // Processing / Saving local file trigger
        downloadStatusTitle.textContent = 'Saving File to Device...';
        progressPercent.textContent = 'Almost done!';

        // Stitch together all gathered binary chunks
        const blob = new Blob(chunks, { type: response.headers.get('Content-Type') || 'video/mp4' });
        const blobUrl = URL.createObjectURL(blob);

        // Prompt a local device download dialog automatically
        const downloadLink = document.createElement('a');
        downloadLink.href = blobUrl;
        
        // Sanitize clean saving filename
        const safeTitle = title.replace(/[^\w\s-]/gi, '').trim().replace(/[-\s]+/g, '_') || 'video';
        downloadLink.download = `${safeTitle}.${ext}`;
        
        document.body.appendChild(downloadLink);
        downloadLink.click();
        
        // Clean up memory anchors
        document.body.removeChild(downloadLink);
        URL.revokeObjectURL(blobUrl);

        showToast('Video saved successfully!', 'success');
        
        // Transition back to preview stage or input stage slowly after success
        setTimeout(() => {
            resetApp();
        }, 1500);

    } catch (err) {
        console.error(err);
        showToast(err.message || 'Stream download disconnected or failed.', 'error');
        // fallback to preview panel
        downloadStage.classList.add('hide');
        previewStage.classList.remove('hide');
    }
}

// Reset App to Input Stage
function resetApp() {
    videoUrlInput.value = '';
    currentVideoData = null;
    
    downloadStage.classList.add('hide');
    previewStage.classList.add('hide');
    inputStage.classList.remove('hide');
    videoUrlInput.focus();
}

// Set loading UI on submit
function setLoadingState(isLoading) {
    if (isLoading) {
        btnAnalyze.disabled = true;
        btnAnalyze.querySelector('.btn-text').classList.add('hide');
        btnAnalyze.querySelector('.spinner-icon').classList.remove('hide');
        videoUrlInput.disabled = true;
        btnPaste.disabled = true;
    } else {
        btnAnalyze.disabled = false;
        btnAnalyze.querySelector('.btn-text').classList.remove('hide');
        btnAnalyze.querySelector('.spinner-icon').classList.add('hide');
        videoUrlInput.disabled = false;
        btnPaste.disabled = false;
    }
}

// Helper: URL Validation
function isValidUrl(string) {
    try {
        new URL(string);
        return true;
    } catch (_) {
        return false;
    }
}

// Helper: Human-readable video duration format (seconds to MM:SS or HH:MM:SS)
function formatDuration(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00';
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    let result = '';
    if (hrs > 0) {
        result += `${hrs}:${mins < 10 ? '0' : ''}`;
    }
    result += `${mins}:${secs < 10 ? '0' : ''}${secs}`;
    return result;
}

// Helper: Human-readable file size format
function formatBytes(bytes, decimals = 1) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// Toast alerts component dispatch
function showToast(message, type = 'info', duration = 4000) {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let iconSvg = '';
    if (type === 'error') {
        iconSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;
    } else if (type === 'success') {
        iconSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`;
    } else {
        iconSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`;
    }

    toast.innerHTML = `
        <div style="display:flex;align-items:center;width:20px;height:20px;color:inherit;">${iconSvg}</div>
        <span class="toast-message">${message}</span>
        <button class="toast-close" type="button" aria-label="Close Toast">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
    `;

    toastContainer.appendChild(toast);

    // Toast Close binding
    toast.querySelector('.toast-close').addEventListener('click', () => {
        dismissToast(toast);
    });

    // Auto dismiss scheduling
    setTimeout(() => {
        dismissToast(toast);
    }, duration);
}

function dismissToast(toast) {
    if (toast && toast.parentNode) {
        toast.style.animation = 'slideIn 0.25s cubic-bezier(0.25, 0.8, 0.25, 1) reverse forwards';
        setTimeout(() => {
            if (toast && toast.parentNode) {
                toast.remove();
            }
        }, 250);
    }
}
