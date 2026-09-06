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
  const tlsWarningBadge = document.getElementById('tls-warning-badge');
  const isSecure = window.isSecureContext || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  const uploadsList = document.getElementById('uploads-list');
  const uploadCountBadge = document.getElementById('upload-count');
  const toastContainer = document.getElementById('toast-container');
  const btnViewList = document.getElementById('btn-view-list');
  const btnViewGrid = document.getElementById('btn-view-grid');

  // Nav Tabs elements
  const tabBtnDropzone = document.getElementById('tab-btn-dropzone');
  const tabBtnFiles = document.getElementById('tab-btn-files');
  const tabBtnGist = document.getElementById('tab-btn-gist');
  const panelDropzone = document.getElementById('panel-dropzone');
  const panelFiles = document.getElementById('panel-files');
  const panelGist = document.getElementById('panel-gist');
  const filesBadgeCount = document.getElementById('files-badge-count');

  // Files Browser elements
  const fileSearchInput = document.getElementById('file-search-input');
  const filesFilterStatus = document.getElementById('files-filter-status');
  const btnRefreshFiles = document.getElementById('btn-refresh-files');
  const filesListBody = document.getElementById('files-list-body');

  // Dedicated Gist Panel elements
  const gistFileSelect = document.getElementById('gist-file-select');
  const gistMetaBadge = document.getElementById('gist-meta-badge');
  const btnGistNew = document.getElementById('btn-gist-new');
  const btnGistCopyRaw = document.getElementById('btn-gist-copy-raw');
  const btnGistDownload = document.getElementById('btn-gist-download');
  const btnGistCopyCurl = document.getElementById('btn-gist-copy-curl');
  const btnGistPasteClipboard = document.getElementById('btn-gist-paste-clipboard');
  const btnGistSave = document.getElementById('btn-gist-save');
  const btnGistCancel = document.getElementById('btn-gist-cancel');
  const gistNewFilename = document.getElementById('gist-new-filename');
  const gistNewContent = document.getElementById('gist-new-content');
  const gistViewSelectors = document.getElementById('gist-view-selectors');
  const gistCreateSelectors = document.getElementById('gist-create-selectors');
  const gistViewActions = document.getElementById('gist-view-actions');
  const gistCreateActions = document.getElementById('gist-create-actions');
  const gistViewWrapper = document.getElementById('gist-view-wrapper');
  const gistCreateWrapper = document.getElementById('gist-create-wrapper');
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

  // Clipboard Info Modal elements
  const clipboardModal = document.getElementById('clipboard-modal');
  const clipboardModalClose = document.getElementById('clipboard-modal-close');
  const clipboardModalBackdrop = clipboardModal ? clipboardModal.querySelector('.modal-backdrop') : null;
  const clipboardModalOkBtn = document.getElementById('clipboard-modal-ok-btn');

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
  function showToast(message, type = 'success', duration = 4000, options = {}) {
    const toast = document.createElement('div');
    const isHelp = !!options.help;
    toast.className = `toast ${type}${isHelp ? ' toast-clickable' : ''}`;

    const textSpan = document.createElement('span');
    textSpan.textContent = message;
    toast.appendChild(textSpan);

    if (isHelp) {
      const helpBadge = document.createElement('span');
      helpBadge.className = 'toast-help-badge';
      helpBadge.textContent = '?';
      helpBadge.title = 'Why? Click for details';
      toast.appendChild(helpBadge);
    }

    toastContainer.appendChild(toast);

    let isDismissed = false;
    function dismiss() {
      if (isDismissed) return;
      isDismissed = true;
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }

    const timer = setTimeout(dismiss, duration);

    if (isHelp) {
      toast.addEventListener('click', () => {
        clearTimeout(timer);
        dismiss();
        openClipboardModal(options.reason);
      });
    }
  }

  // Universal clipboard copy helper (requires secure context)
  async function copyTextToClipboard(text) {
    if (!isSecure || !navigator.clipboard || !navigator.clipboard.writeText) {
      return { ok: false };
    }

    try {
      await navigator.clipboard.writeText(text);
      return { ok: true };
    } catch (err) {
      return { ok: false };
    }
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
    const res = await copyTextToClipboard(currentMobileUrl);
    if (res.ok) {
      btnCopyUrl.textContent = 'Copied!';
      setTimeout(() => (btnCopyUrl.textContent = 'Copy'), 2000);
      showToast('URL copied to clipboard');
    } else {
      showToast('Failed to copy to clipboard', 'error', 6000, { help: true });
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

  // Clipboard Info Modal functions
  function openClipboardModal(reason) {
    if (!clipboardModal) return;
    const reasonEl = document.getElementById('clipboard-modal-reason');
    if (reasonEl && reason) {
      reasonEl.textContent = reason;
    }
    clipboardModal.classList.add('active');
  }

  function closeClipboardModal() {
    if (clipboardModal) clipboardModal.classList.remove('active');
  }

  if (clipboardModalClose) clipboardModalClose.addEventListener('click', closeClipboardModal);
  if (clipboardModalBackdrop) clipboardModalBackdrop.addEventListener('click', closeClipboardModal);
  if (clipboardModalOkBtn) clipboardModalOkBtn.addEventListener('click', closeClipboardModal);

  // Global Escape key handler
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (clipboardModal && clipboardModal.classList.contains('active')) closeClipboardModal();
      if (helpModal && helpModal.classList.contains('active')) closeHelpModal();
      if (qrModal && qrModal.classList.contains('active')) closeQrModal();
      if (lightbox && lightbox.classList.contains('active')) closeLightbox();
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
    const tabs = [
      { name: 'dropzone', btn: tabBtnDropzone, panel: panelDropzone },
      { name: 'files', btn: tabBtnFiles, panel: panelFiles },
      { name: 'gist', btn: tabBtnGist, panel: panelGist },
    ];

    tabs.forEach((t) => {
      const active = t.name === tabName;
      if (t.btn) {
        t.btn.classList.toggle('active', active);
        t.btn.setAttribute('aria-selected', active ? 'true' : 'false');
      }
      if (t.panel) {
        t.panel.classList.toggle('active', active);
      }
    });

    if (tabName === 'files') {
      if (allFiles.length === 0) {
        loadFiles();
      }
    } else if (tabName === 'gist') {
      if (allFiles.length === 0) {
        loadFiles().then(() => {
          syncGistTabState();
        });
      } else {
        syncGistTabState();
      }
    }

    if (updateHash) {
      if (tabName === 'gist') {
        const hash = currentGistFilename ? `#gist=${encodeURIComponent(currentGistFilename)}` : '#gist';
        if (window.location.hash !== hash) window.history.replaceState(null, '', hash);
      } else {
        const hash = `#${tabName}`;
        if (window.location.hash !== hash) window.history.replaceState(null, '', hash);
      }
    }
  }

  function syncGistTabState() {
    // If user is actively in create mode, keep create mode
    if (!gistCreateWrapper.classList.contains('hidden')) {
      return;
    }
    const gistFiles = allFiles.filter((f) => f.is_gist);
    if (gistFiles.length === 0) {
      setGistMode('create');
    } else if (currentGistFilename && gistFiles.some((f) => f.name === currentGistFilename)) {
      gistFileSelect.value = currentGistFilename;
    } else {
      openGist(gistFiles[0].name, false);
    }
  }

  tabBtnDropzone.addEventListener('click', () => switchTab('dropzone', true));
  tabBtnFiles.addEventListener('click', () => switchTab('files', true));
  tabBtnGist.addEventListener('click', () => switchTab('gist', true));

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

      // Populate Gist dropdown ONLY with gists
      const gistFiles = allFiles.filter((f) => f.is_gist);
      if (gistFiles.length > 0) {
        gistFileSelect.innerHTML = gistFiles
          .map((f) => `<option value="${f.name}">${f.name}</option>`)
          .join('');
        if (currentGistFilename && gistFiles.some((f) => f.name === currentGistFilename)) {
          gistFileSelect.value = currentGistFilename;
        }
      } else {
        gistFileSelect.innerHTML = '<option value="">No gists created yet</option>';
      }
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
      if (file.is_gist) {
        actionsHtml += `
          <button class="btn-action btn-gist" data-action="gist" title="View Gist">
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

      const gistTag = file.is_gist ? '<span class="badge" style="margin-left: 6px; font-size: 11px;">Gist</span>' : '';

      tr.innerHTML = `
        <td>
          <div class="file-cell">
            ${getFileIconSvg(file)}
            <a href="javascript:void(0)" class="file-name-link">${file.name}</a>
            ${gistTag}
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
      if (file.is_gist) {
        nameLink.addEventListener('click', () => openGist(file.name, true));
      } else if (file.is_image) {
        nameLink.addEventListener('click', () => openLightbox(file.raw_url, file.name));
      } else {
        nameLink.href = file.raw_url;
        nameLink.setAttribute('download', file.name);
      }

      const btnGist = tr.querySelector('[data-action="gist"]');
      if (btnGist) {
        btnGist.addEventListener('click', () => openGist(file.name, true));
      }

      const btnCurl = tr.querySelector('[data-action="curl"]');
      if (btnCurl) {
        btnCurl.addEventListener('click', () => copyCurlForFile(file.raw_url, file.name));
      }

      filesListBody.appendChild(tr);
    });
  }

  // Copy curl helper
  async function copyCurlForFile(rawUrl, filename) {
    const origin = window.location.origin;
    const isSsl = window.location.protocol === 'https:';
    const insecureFlag = isSsl && (!isSecure || window.location.hostname !== 'localhost') ? ' -k' : '';
    const curlCmd = `curl -sSL${insecureFlag} "${origin}${rawUrl}" -o ${filename}`;
    const res = await copyTextToClipboard(curlCmd);
    if (res.ok) {
      showToast(`Copied curl command for ${filename}`);
    } else {
      showToast('Failed to copy to clipboard', 'error', 6000, { help: true });
    }
  }

  fileSearchInput.addEventListener('input', renderFiles);
  btnRefreshFiles.addEventListener('click', () => {
    loadFiles();
    showToast('Files refreshed');
  });

  // Gist Panel functions & mode toggling
  function setGistMode(mode) {
    if (mode === 'create') {
      gistViewSelectors.classList.add('hidden');
      gistCreateSelectors.classList.remove('hidden');
      gistViewActions.classList.add('hidden');
      gistCreateActions.classList.remove('hidden');
      gistViewWrapper.classList.add('hidden');
      gistCreateWrapper.classList.remove('hidden');

      if (!gistNewFilename.value.trim()) {
        const now = new Date();
        const dateStr = now.toISOString().slice(0, 10).replace(/-/g, '');
        const timeStr = now.toTimeString().slice(0, 8).replace(/:/g, '');
        gistNewFilename.value = `gist_${dateStr}_${timeStr}.txt`;
      }
      gistNewContent.focus();
    } else {
      gistViewSelectors.classList.remove('hidden');
      gistCreateSelectors.classList.add('hidden');
      gistViewActions.classList.remove('hidden');
      gistCreateActions.classList.add('hidden');
      gistViewWrapper.classList.remove('hidden');
      gistCreateWrapper.classList.add('hidden');
    }
  }

  btnGistNew.addEventListener('click', () => {
    switchTab('gist', false);
    setGistMode('create');
    window.history.replaceState(null, '', '#gist-new');
  });

  btnGistCancel.addEventListener('click', () => {
    const gistFiles = allFiles.filter((f) => f.is_gist);
    if (gistFiles.length > 0) {
      setGistMode('view');
      const hash = currentGistFilename ? `#gist=${encodeURIComponent(currentGistFilename)}` : '#gist';
      window.history.replaceState(null, '', hash);
    } else {
      switchTab('dropzone', true);
    }
  });

  // Paste from clipboard button
  btnGistPasteClipboard.addEventListener('click', async () => {
    if (!isSecure || !navigator.clipboard || !navigator.clipboard.readText) {
      showToast('Failed to paste from clipboard', 'error', 6000, { help: true });
      gistNewContent.focus();
      return;
    }

    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        gistNewContent.value = text;
        showToast('Pasted clipboard contents into editor');
        gistNewContent.focus();
      } else {
        showToast('Clipboard is currently empty', 'info');
        gistNewContent.focus();
      }
    } catch (err) {
      showToast('Failed to paste from clipboard', 'error', 6000, { help: true });
      gistNewContent.focus();
    }
  });

  // Save new gist
  btnGistSave.addEventListener('click', async () => {
    const content = gistNewContent.value;
    if (!content.trim()) {
      showToast('Please enter or paste content for your gist', 'error');
      gistNewContent.focus();
      return;
    }

    let filename = gistNewFilename.value.trim();
    if (!filename) {
      const now = new Date();
      const dateStr = now.toISOString().slice(0, 10).replace(/-/g, '');
      const timeStr = now.toTimeString().slice(0, 8).replace(/:/g, '');
      filename = `gist_${dateStr}_${timeStr}.txt`;
    }

    try {
      showToast('Saving gist...', 'info');
      const res = await fetch('/api/gist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename, content }),
      });

      if (res.status === 401) {
        lockScreen.classList.remove('hidden');
        showAuthError('Session expired. Please re-authenticate.');
        return;
      }

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || 'Failed to save gist');
      }

      const result = await res.json();
      playSuccessChime();
      showToast(`Gist saved: ${result.name}`);

      // Clear editor
      gistNewContent.value = '';
      gistNewFilename.value = '';

      // Reload files list and open newly created gist
      await loadFiles();
      setGistMode('view');
      openGist(result.name, true);
    } catch (err) {
      showToast(`Failed to save gist: ${err.message}`, 'error');
    }
  });

  gistFileSelect.addEventListener('change', () => {
    const selected = gistFileSelect.value;
    if (selected) {
      openGist(selected, true);
    }
  });

  async function openGist(filename, updateHash = true) {
    if (!filename) return;
    currentGistFilename = filename;

    if (panelGist && !panelGist.classList.contains('active')) {
      switchTab('gist', false);
    }
    setGistMode('view');
    if (gistFileSelect && gistFileSelect.value !== filename) {
      gistFileSelect.value = filename;
    }
    gistMetaBadge.textContent = 'Loading...';
    gistLineNumbers.textContent = '';
    gistCodeContent.textContent = 'Fetching file content...';
    currentRawGistText = '';

    if (updateHash) {
      window.history.replaceState(null, '', `#gist=${encodeURIComponent(filename)}`);
    }

    try {
      const res = await fetch(`/api/content?name=${encodeURIComponent(filename)}`);
      if (res.status === 401) {
        lockScreen.classList.remove('hidden');
        authInput.focus();
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

  btnGistCopyRaw.addEventListener('click', async () => {
    if (!currentRawGistText) {
      showToast('No gist content to copy', 'error');
      return;
    }
    const res = await copyTextToClipboard(currentRawGistText);
    if (res.ok) {
      const span = btnGistCopyRaw.querySelector('span');
      const orig = span ? span.textContent : 'Copy Gist';
      if (span) span.textContent = '✓ Copied!';
      btnGistCopyRaw.classList.add('copied');
      setTimeout(() => {
        if (span) span.textContent = orig;
        btnGistCopyRaw.classList.remove('copied');
      }, 2000);
      showToast(`Copied ${currentGistFilename} to clipboard`);
    } else {
      showToast('Failed to copy to clipboard', 'error', 6000, { help: true });
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
          openGist(data.share_file);
        }
      } else if (data.share_mode) {
        if (window.location.hash !== '#dropzone') {
          switchTab('files');
        }
      }
      await loadFiles();
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
    } else if (hash === '#gist') {
      switchTab('gist');
    } else if (hash === '#gist-new') {
      switchTab('gist');
      setGistMode('create');
    } else if (hash.startsWith('#gist=')) {
      const filename = decodeURIComponent(hash.substring(6));
      openGist(filename, false);
    }
  }

  // Initialization & Auto-Auth Check
  async function init() {
    setViewMode(currentViewMode);

    if (!isSecure && tlsWarningBadge) {
      tlsWarningBadge.classList.remove('hidden');
      tlsWarningBadge.addEventListener('click', () => {
        openClipboardModal();
      });
    }

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
