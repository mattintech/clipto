(() => {
  // Elements
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('file-input');
  const noteInput = document.getElementById('note-input');
  const btnSendNote = document.getElementById('btn-send-note');
  const hostnameDisplay = document.getElementById('hostname-display');
  const dirDisplay = document.getElementById('dir-display');
  const sessionTitle = document.getElementById('session-title');
  const connectionStatus = document.getElementById('connection-status');
  const uploadsList = document.getElementById('uploads-list');
  const uploadCountBadge = document.getElementById('upload-count');
  const toastContainer = document.getElementById('toast-container');
  const btnViewList = document.getElementById('btn-view-list');
  const btnViewGrid = document.getElementById('btn-view-grid');

  // Nav Tabs elements
  const tabBtnDropzone = document.getElementById('tab-btn-dropzone');
  const tabBtnFiles = document.getElementById('tab-btn-files');
  const panelDropzone = document.getElementById('panel-dropzone');
  const panelFiles = document.getElementById('panel-files');
  const filesBadgeCount = document.getElementById('files-badge-count');

  // Files & Gists Panel elements
  const fileSearchInput = document.getElementById('file-search-input');
  const filesFilterStatus = document.getElementById('files-filter-status');
  const btnRefreshFiles = document.getElementById('btn-refresh-files');
  const filesListBody = document.getElementById('files-list-body');

  // Gist Modal elements
  const gistModal = document.getElementById('gist-modal');
  const gistModalClose = document.getElementById('gist-modal-close');
  const gistModalBackdrop = gistModal.querySelector('.modal-backdrop');
  const gistFilename = document.getElementById('gist-filename');
  const gistMetaBadge = document.getElementById('gist-meta-badge');
  const btnGistCopyRaw = document.getElementById('btn-gist-copy-raw');
  const btnGistDownload = document.getElementById('btn-gist-download');
  const btnGistCopyCurl = document.getElementById('btn-gist-copy-curl');
  const gistLineNumbers = document.getElementById('gist-line-numbers');
  const gistCodeContent = document.getElementById('gist-code-content');

  // Phone QR Modal elements
  const btnPhoneQr = document.getElementById('btn-phone-qr');
  const qrModal = document.getElementById('qr-modal');
  const qrModalClose = document.getElementById('qr-modal-close');
  const qrModalBackdrop = qrModal.querySelector('.modal-backdrop');
  const qrUrlDisplay = document.getElementById('qr-url-display');
  const btnCopyUrl = document.getElementById('btn-copy-url');

  // Help Modal elements
  const btnHelpGuide = document.getElementById('btn-help-guide');
  const helpModal = document.getElementById('help-modal');
  const helpModalClose = document.getElementById('help-modal-close');
  const helpModalBackdrop = helpModal.querySelector('.modal-backdrop');
  const helpTabBtns = helpModal.querySelectorAll('.help-tab-btn');
  const helpTabPanels = helpModal.querySelectorAll('.help-tab-panel');

  // Lightbox elements
  const lightbox = document.getElementById('lightbox');
  const lightboxImg = document.getElementById('lightbox-img');
  const lightboxCaption = document.getElementById('lightbox-caption');
  const lightboxClose = document.getElementById('lightbox-close');
  const lightboxBackdrop = lightbox.querySelector('.lightbox-backdrop');

  // Lock Screen elements
  const lockScreen = document.getElementById('lock-screen');
  const lockCard = lockScreen.querySelector('.lock-card');
  const authForm = document.getElementById('auth-form');
  const authInput = document.getElementById('auth-input');
  const authError = document.getElementById('auth-error');

  let uploadedItems = [];
  let allFiles = [];
  let isOnceMode = false;
  let currentMobileUrl = '';
  let currentRawGistText = '';
  let currentGistFilename = '';
  let currentViewMode = localStorage.getItem('clipto_view_mode') || 'grid';

  // Sound chime via Web Audio API (zero external assets)
  function playSuccessChime() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(880.0, ctx.currentTime + 0.12);
      gain.gain.setValueAtTime(0.15, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.3);
    } catch (e) {
      // Audio context might be restricted before interaction
    }
  }

  // Toast notifications
  function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${message}</span>`;
    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // Format file size
  function formatSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  // Lightbox functions
  function openLightbox(imageUrl, title) {
    lightboxImg.src = imageUrl;
    lightboxCaption.textContent = title;
    lightbox.classList.add('active');
  }

  function closeLightbox() {
    lightbox.classList.remove('active');
    lightboxImg.src = '';
  }

  lightboxClose.addEventListener('click', closeLightbox);
  lightboxBackdrop.addEventListener('click', closeLightbox);

  // Phone QR Modal functions
  function openQrModal() {
    qrModal.classList.add('active');
  }

  function closeQrModal() {
    qrModal.classList.remove('active');
  }

  btnPhoneQr.addEventListener('click', openQrModal);
  qrModalClose.addEventListener('click', closeQrModal);
  qrModalBackdrop.addEventListener('click', closeQrModal);

  btnCopyUrl.addEventListener('click', async () => {
    if (!currentMobileUrl) return;
    try {
      await navigator.clipboard.writeText(currentMobileUrl);
      btnCopyUrl.textContent = 'Copied!';
      setTimeout(() => btnCopyUrl.textContent = 'Copy', 2000);
      showToast('URL copied to clipboard');
    } catch (err) {
      showToast('Could not copy to clipboard', 'error');
    }
  });

  // Help Modal functions
  function openHelpModal() {
    helpModal.classList.add('active');
  }

  function closeHelpModal() {
    helpModal.classList.remove('active');
  }

  btnHelpGuide.addEventListener('click', openHelpModal);
  helpModalClose.addEventListener('click', closeHelpModal);
  helpModalBackdrop.addEventListener('click', closeHelpModal);

  helpTabBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const tabId = btn.getAttribute('data-tab');
      helpTabBtns.forEach((b) => b.classList.remove('active'));
      helpTabPanels.forEach((p) => p.classList.remove('active'));

      btn.classList.add('active');
      const targetPanel = document.getElementById(tabId);
      if (targetPanel) targetPanel.classList.add('active');
    });
  });

  // Global Escape key handler
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (gistModal.classList.contains('active')) closeGistModal();
      if (helpModal.classList.contains('active')) closeHelpModal();
      if (qrModal.classList.contains('active')) closeQrModal();
      if (lightbox.classList.contains('active')) closeLightbox();
    }
  });

  // Render uploads list/grid
  function renderUploads() {
    uploadCountBadge.textContent = `${uploadedItems.length} item${uploadedItems.length === 1 ? '' : 's'}`;

    if (uploadedItems.length === 0) {
      uploadsList.innerHTML = '<div class="empty-state">No files uploaded yet in this session.</div>';
      return;
    }

    uploadsList.innerHTML = '';
    uploadsList.className = `uploads-list ${currentViewMode}-view`;

    uploadedItems.forEach((item) => {
      const fileUrl = `/api/file?name=${encodeURIComponent(item.name)}`;
      const isImg = item.is_image;

      if (currentViewMode === 'grid') {
        const card = document.createElement('div');
        card.className = 'grid-card';

        let mediaHtml = '';
        if (isImg) {
          mediaHtml = `
            <div class="grid-card-media" title="Click to enlarge">
              <img src="${fileUrl}" alt="${item.name}" loading="lazy">
            </div>
          `;
        } else {
          mediaHtml = `
            <div class="grid-card-media">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
            </div>
          `;
        }

        card.innerHTML = `
          ${mediaHtml}
          <div class="grid-card-body">
            <span class="grid-card-name" title="${item.name}">${item.name}</span>
            <div class="grid-card-meta">
              <span>${formatSize(item.size)}</span>
              <span>${item.time}</span>
            </div>
          </div>
        `;

        if (isImg) {
          card.querySelector('.grid-card-media').addEventListener('click', () => {
            openLightbox(fileUrl, item.name);
          });
        }

        uploadsList.appendChild(card);
      } else {
        const row = document.createElement('div');
        row.className = 'upload-item';

        let thumbHtml = '';
        if (isImg) {
          thumbHtml = `<img class="thumb-preview" src="${fileUrl}" alt="${item.name}" title="Click to enlarge">`;
        } else {
          thumbHtml = `
            <div class="thumb-icon-placeholder">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
            </div>
          `;
        }

        row.innerHTML = `
          <div class="upload-item-left">
            ${thumbHtml}
            <div class="upload-item-info">
              <span class="upload-item-name" title="${item.name}">${item.name}</span>
              <span class="upload-item-meta">${formatSize(item.size)} • ${item.time}</span>
            </div>
          </div>
          <span class="badge" style="color: var(--success); border-color: rgba(16, 185, 129, 0.3);">Saved</span>
        `;

        if (isImg) {
          row.querySelector('.thumb-preview').addEventListener('click', () => {
            openLightbox(fileUrl, item.name);
          });
        }

        uploadsList.appendChild(row);
      }
    });
  }

  // View toggle handlers
  function setViewMode(mode) {
    currentViewMode = mode;
    localStorage.setItem('clipto_view_mode', mode);
    if (mode === 'grid') {
      btnViewGrid.classList.add('active');
      btnViewList.classList.remove('active');
    } else {
      btnViewList.classList.add('active');
      btnViewGrid.classList.remove('active');
    }
    renderUploads();
  }

  btnViewList.addEventListener('click', () => setViewMode('list'));
  btnViewGrid.addEventListener('click', () => setViewMode('grid'));

  // Tab navigation handler
  function switchTab(tabName, updateHash = false) {
    if (tabName === 'files') {
      tabBtnFiles.classList.add('active');
      tabBtnFiles.setAttribute('aria-selected', 'true');
      tabBtnDropzone.classList.remove('active');
      tabBtnDropzone.setAttribute('aria-selected', 'false');

      panelFiles.classList.add('active');
      panelDropzone.classList.remove('active');

      if (allFiles.length === 0) {
        loadFiles();
      }
    } else {
      tabBtnDropzone.classList.add('active');
      tabBtnDropzone.setAttribute('aria-selected', 'true');
      tabBtnFiles.classList.remove('active');
      tabBtnFiles.setAttribute('aria-selected', 'false');

      panelDropzone.classList.add('active');
      panelFiles.classList.remove('active');
    }

    if (updateHash) {
      if (tabName === 'files' && window.location.hash !== '#files') {
        window.history.replaceState(null, '', '#files');
      } else if (tabName === 'dropzone' && window.location.hash !== '#dropzone') {
        window.history.replaceState(null, '', '#dropzone');
      }
    }
  }

  tabBtnDropzone.addEventListener('click', () => switchTab('dropzone', true));
  tabBtnFiles.addEventListener('click', () => switchTab('files', true));

  // File type icon helper (Material flat SVG)
  function getFileIconSvg(file) {
    if (file.is_image) {
      return `<svg class="file-icon image" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>`;
    }
    const ext = (file.extension || '').toLowerCase();
    const archiveExts = ['zip', 'tar', 'gz', 'tgz', 'bz2', 'xz', '7z', 'rar'];
    if (archiveExts.includes(ext)) {
      return `<svg class="file-icon archive" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8v13H3V8"></path><path d="M1 3h22v5H1z"></path><line x1="10" y1="12" x2="14" y2="12"></line></svg>`;
    }
    if (file.is_text) {
      return `<svg class="file-icon code" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>`;
    }
    return `<svg class="file-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path><polyline points="13 2 13 9 20 9"></polyline></svg>`;
  }

  // Load directory files from backend
  async function loadFiles() {
    try {
      filesListBody.innerHTML = '<tr><td colspan="4" class="empty-state">Loading files...</td></tr>';
      const res = await fetch('/api/files');
      if (res.status === 401) {
        lockScreen.classList.remove('hidden');
        authInput.focus();
        return;
      }
      if (!res.ok) throw new Error('Failed to load files');
      const data = await res.json();
      allFiles = data.files || [];
      filesBadgeCount.textContent = data.count !== undefined ? data.count : allFiles.length;
      renderFiles();
    } catch (err) {
      filesListBody.innerHTML = `<tr><td colspan="4" class="empty-state" style="color: var(--danger)">Error loading files: ${err.message}</td></tr>`;
    }
  }

  // Render directory files table
  function renderFiles() {
    const query = fileSearchInput.value.trim().toLowerCase();
    const filtered = allFiles.filter((f) => {
      if (!query) return true;
      return f.name.toLowerCase().includes(query) || (f.extension && f.extension.toLowerCase().includes(query));
    });

    if (query) {
      filesFilterStatus.textContent = `${filtered.length} of ${allFiles.length}`;
      filesFilterStatus.classList.remove('hidden');
    } else {
      filesFilterStatus.textContent = `${allFiles.length} file${allFiles.length === 1 ? '' : 's'}`;
    }

    if (filtered.length === 0) {
      filesListBody.innerHTML = `<tr><td colspan="4" class="empty-state">${query ? 'No matching files found.' : 'No files in this directory.'}</td></tr>`;
      return;
    }

    filesListBody.innerHTML = '';
    filtered.forEach((file) => {
      const tr = document.createElement('tr');

      let actionsHtml = '';
      if (file.is_text) {
        actionsHtml += `
          <button class="btn-action btn-gist" data-action="gist" title="View formatted Gist">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>
            <span>View Gist</span>
          </button>
        `;
      }
      actionsHtml += `
        <a href="${file.raw_url}" download="${file.name}" class="btn-action" title="Download raw file">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
          <span>Download</span>
        </a>
        <button class="btn-action" data-action="curl" title="Copy CLI curl command">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>
          <span>curl</span>
        </button>
      `;

      tr.innerHTML = `
        <td>
          <div class="file-cell">
            ${getFileIconSvg(file)}
            <a href="javascript:void(0)" class="file-name-link">${file.name}</a>
          </div>
        </td>
        <td class="td-size">${formatSize(file.size)}</td>
        <td class="td-time">${file.time || '-'}</td>
        <td>
          <div class="file-actions">
            ${actionsHtml}
          </div>
        </td>
      `;

      const nameLink = tr.querySelector('.file-name-link');
      if (file.is_text) {
        nameLink.addEventListener('click', () => openGist(file.name));
      } else if (file.is_image) {
        nameLink.addEventListener('click', () => openLightbox(file.raw_url, file.name));
      } else {
        nameLink.href = file.raw_url;
        nameLink.setAttribute('download', file.name);
      }

      const btnGist = tr.querySelector('[data-action="gist"]');
      if (btnGist) {
        btnGist.addEventListener('click', () => openGist(file.name));
      }

      const btnCurl = tr.querySelector('[data-action="curl"]');
      if (btnCurl) {
        btnCurl.addEventListener('click', () => copyCurlForFile(file.raw_url, file.name));
      }

      filesListBody.appendChild(tr);
    });
  }

  // Copy curl helper
  function copyCurlForFile(rawUrl, filename) {
    const origin = window.location.origin;
    const curlCmd = `curl -sSL "${origin}${rawUrl}" -o ${filename}`;
    navigator.clipboard.writeText(curlCmd).then(() => {
      showToast(`Copied curl command for ${filename}`);
    }).catch(() => {
      showToast('Failed to copy curl command', 'error');
    });
  }

  fileSearchInput.addEventListener('input', renderFiles);
  btnRefreshFiles.addEventListener('click', () => {
    loadFiles();
    showToast('Files refreshed');
  });

  // Gist Modal functions
  async function openGist(filename) {
    gistModal.classList.add('active');
    gistFilename.textContent = filename;
    gistMetaBadge.textContent = 'Loading...';
    gistLineNumbers.textContent = '';
    gistCodeContent.textContent = 'Fetching file content...';
    currentRawGistText = '';
    currentGistFilename = filename;

    // Update URL hash without reload
    window.history.replaceState(null, '', `#gist=${encodeURIComponent(filename)}`);

    try {
      const res = await fetch(`/api/content?name=${encodeURIComponent(filename)}`);
      if (res.status === 401) {
        lockScreen.classList.remove('hidden');
        authInput.focus();
        closeGistModal();
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || 'Failed to load file');
      }

      const data = await res.json();
      currentRawGistText = data.content;
      currentGistFilename = data.name;
      gistMetaBadge.textContent = `${data.lines} line${data.lines === 1 ? '' : 's'} • ${formatSize(data.size)}`;
      btnGistDownload.href = data.raw_url;
      btnGistDownload.setAttribute('download', data.name);

      const lines = data.content.split('\n');
      const lineNums = Array.from({ length: lines.length }, (_, i) => i + 1).join('\n');
      gistLineNumbers.textContent = lineNums;
      gistCodeContent.textContent = data.content;
    } catch (err) {
      gistMetaBadge.textContent = 'Error';
      gistLineNumbers.textContent = '!';
      gistCodeContent.textContent = `Could not preview file: ${err.message}`;
      showToast(err.message, 'error');
    }
  }

  function closeGistModal() {
    gistModal.classList.remove('active');
    if (window.location.hash.startsWith('#gist=')) {
      window.history.replaceState(null, '', '#files');
    }
  }

  gistModalClose.addEventListener('click', closeGistModal);
  gistModalBackdrop.addEventListener('click', closeGistModal);

  btnGistCopyRaw.addEventListener('click', async () => {
    if (!currentRawGistText) return;
    try {
      await navigator.clipboard.writeText(currentRawGistText);
      const span = btnGistCopyRaw.querySelector('span');
      const orig = span ? span.textContent : 'Copy Raw';
      if (span) span.textContent = 'Copied!';
      setTimeout(() => { if (span) span.textContent = orig; }, 2000);
      showToast(`Copied ${currentGistFilename} to clipboard`);
    } catch (err) {
      showToast('Failed to copy to clipboard', 'error');
    }
  });

  btnGistCopyCurl.addEventListener('click', () => {
    if (!currentGistFilename) return;
    copyCurlForFile(`/raw/${encodeURIComponent(currentGistFilename)}`, currentGistFilename);
  });

  // Configure lock screen text & input mode based on auth type
  function setLockScreenMode(authType) {
    const titleEl = lockScreen.querySelector('h2');
    const subtitleEl = lockScreen.querySelector('.lock-subtitle');

    if (authType === 'totp') {
      titleEl.textContent = 'Authenticator Code';
      subtitleEl.textContent = 'Enter the 6-digit code from Google / MS Authenticator, 1Password, or Apple Passwords';
      authInput.placeholder = '000000';
      authInput.maxLength = 6;
      authInput.inputMode = 'numeric';
      authInput.pattern = '[0-9]*';
    } else {
      titleEl.textContent = 'Protected Session';
      subtitleEl.textContent = 'Enter the PIN or password from your terminal to connect';
      authInput.placeholder = 'Enter PIN or Password';
      authInput.removeAttribute('maxLength');
      authInput.inputMode = 'text';
    }
  }

  // Auto-submit when 6 digits are reached in TOTP mode
  authInput.addEventListener('input', () => {
    if (authInput.maxLength === 6 && authInput.value.trim().length === 6) {
      submitAuth(authInput.value.trim());
    }
  });

  // Auth & Session functions
  async function submitAuth(key) {
    authError.classList.add('hidden');
    try {
      const res = await fetch('/api/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key }),
      });

      const data = await res.json();
      if (res.ok && data.authenticated) {
        lockScreen.classList.add('hidden');
        loadInfo();
        showToast('Connected to session');
        return true;
      } else {
        showAuthError(data.error || 'Authentication failed');
        return false;
      }
    } catch (err) {
      showAuthError('Connection failed');
      return false;
    }
  }

  function showAuthError(msg) {
    authError.textContent = msg;
    authError.classList.remove('hidden');
    lockCard.classList.remove('shake');
    void lockCard.offsetWidth;
    lockCard.classList.add('shake');
    authInput.value = '';
    authInput.focus();
  }

  authForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const key = authInput.value.trim();
    if (key) submitAuth(key);
  });

  // Fetch session info
  async function loadInfo() {
    try {
      const res = await fetch('/api/info');
      if (res.status === 401) {
        lockScreen.classList.remove('hidden');
        authInput.focus();
        return;
      }

      if (!res.ok) throw new Error('Failed to fetch info');
      const data = await res.json();

      hostnameDisplay.textContent = data.hostname || 'localhost';
      dirDisplay.textContent = data.dir || '.';
      isOnceMode = !!data.once;
      currentMobileUrl = data.mobile_url || window.location.href;
      qrUrlDisplay.textContent = currentMobileUrl;

      if (data.title) {
        sessionTitle.textContent = data.title;
        sessionTitle.classList.remove('hidden');
      }

      if (isOnceMode) {
        connectionStatus.className = 'status-pill once-mode';
        connectionStatus.querySelector('.status-text').textContent = 'One-Shot';
      }

      if (data.share_file) {
        if (!window.location.hash.startsWith('#gist=') && window.location.hash !== '#dropzone') {
          switchTab('files');
          openGist(data.share_file);
        }
      } else if (data.share_mode) {
        if (window.location.hash !== '#dropzone') {
          switchTab('files');
        }
      }
      loadFiles();
    } catch (err) {
      connectionStatus.className = 'status-pill';
      connectionStatus.querySelector('.status-text').textContent = 'Offline';
    }
  }

  // Upload formData to server
  async function uploadFormData(formData) {
    try {
      showToast('Uploading...', 'info');
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (res.status === 401) {
        lockScreen.classList.remove('hidden');
        showAuthError('Session expired. Please re-authenticate.');
        return;
      }

      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(errorText || 'Upload failed');
      }

      const result = await res.json();
      playSuccessChime();

      if (result.saved_files && result.saved_files.length > 0) {
        const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        result.saved_files.forEach((file) => {
          uploadedItems.unshift({
            name: file.name,
            size: file.size,
            is_image: file.is_image,
            path: file.path,
            time: now,
          });
          showToast(`Saved ${file.name}`);
        });
        renderUploads();
        loadFiles();
      }

      if (isOnceMode) {
        showToast('One-shot received! Server is shutting down.', 'info');
        connectionStatus.className = 'status-pill';
        connectionStatus.querySelector('.status-text').textContent = 'Completed';
      }
    } catch (err) {
      console.error(err);
      showToast(`Upload failed: ${err.message}`, 'error');
    }
  }

  // Handle files (from input or drop)
  function handleFiles(files) {
    if (!files || files.length === 0) return;
    const formData = new FormData();
    for (const file of files) {
      formData.append('files', file, file.name);
    }
    uploadFormData(formData);
  }

  // Global Paste Handler
  window.addEventListener('paste', (e) => {
    if (document.activeElement === noteInput || document.activeElement === authInput) {
      return;
    }

    const clipboardData = e.clipboardData || window.clipboardData;
    if (!clipboardData) return;

    const items = clipboardData.items;
    let foundImage = false;

    if (items) {
      for (let i = 0; i < items.length; i++) {
        if (items[i].type.indexOf('image') !== -1) {
          const blob = items[i].getAsFile();
          if (blob) {
            foundImage = true;
            e.preventDefault();
            const now = new Date();
            const dateStr = now.toISOString().slice(0, 10).replace(/-/g, '');
            const timeStr = now.toTimeString().slice(0, 8).replace(/:/g, '');
            const filename = `clip_${dateStr}_${timeStr}.png`;

            const formData = new FormData();
            formData.append('files', blob, filename);
            uploadFormData(formData);
            break;
          }
        }
      }
    }

    if (!foundImage) {
      const text = clipboardData.getData('text');
      if (text && text.trim().length > 0) {
        noteInput.value = text;
        btnSendNote.disabled = false;
        noteInput.focus();
        showToast('Pasted text into note box', 'info');
      }
    }
  });

  // Drag and drop handlers
  ['dragenter', 'dragover'].forEach((eventName) => {
    window.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('drag-active');
    }, false);
  });

  ['dragleave', 'drop'].forEach((eventName) => {
    window.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (e.target === dropzone || !dropzone.contains(e.relatedTarget)) {
        dropzone.classList.remove('drag-active');
      }
    }, false);
  });

  window.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('drag-active');
    const dt = e.dataTransfer;
    if (dt && dt.files && dt.files.length > 0) {
      handleFiles(dt.files);
    }
  });

  // File input picker
  fileInput.addEventListener('change', () => {
    handleFiles(fileInput.files);
    fileInput.value = '';
  });

  // Note box handlers
  noteInput.addEventListener('input', () => {
    btnSendNote.disabled = noteInput.value.trim().length === 0;
  });

  btnSendNote.addEventListener('click', () => {
    const text = noteInput.value.trim();
    if (!text) return;

    const now = new Date();
    const dateStr = now.toISOString().slice(0, 10).replace(/-/g, '');
    const timeStr = now.toTimeString().slice(0, 8).replace(/:/g, '');
    const filename = `note_${dateStr}_${timeStr}.txt`;

    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const formData = new FormData();
    formData.append('files', blob, filename);

    uploadFormData(formData);
    noteInput.value = '';
    btnSendNote.disabled = true;
  });

  // Hash routing helper
  function handleRoute(hash) {
    if (!hash) return;
    if (hash === '#help') {
      openHelpModal();
    } else if (hash === '#qr') {
      openQrModal();
    } else if (hash === '#files') {
      switchTab('files');
    } else if (hash === '#dropzone') {
      switchTab('dropzone');
    } else if (hash.startsWith('#gist=')) {
      const filename = decodeURIComponent(hash.substring(6));
      switchTab('files');
      openGist(filename);
    }
  }

  // Initialization & Auto-Auth Check
  async function init() {
    setViewMode(currentViewMode);

    // Check for query parameter ?k=... for magic link / QR code instant login
    const params = new URLSearchParams(window.location.search);
    const key = params.get('k');

    if (key) {
      const authed = await submitAuth(key);
      if (authed) {
        // Clean URL so the key doesn't sit in the address bar
        const cleanUrl = window.location.pathname;
        window.history.replaceState(null, '', cleanUrl);
        handleRoute(window.location.hash);
      }
    } else {
      // Check auth status
      try {
        const authRes = await fetch('/api/auth');
        const authData = await authRes.json();
        setLockScreenMode(authData.auth_type);

        if (authData.required && !authData.authenticated) {
          lockScreen.classList.remove('hidden');
          authInput.focus();
        } else {
          await loadInfo();
          handleRoute(window.location.hash);
        }
      } catch (err) {
        await loadInfo();
        handleRoute(window.location.hash);
      }
    }

    // Support hashchange dynamically
    window.addEventListener('hashchange', () => {
      handleRoute(window.location.hash);
    });
  }

  init();
})();
