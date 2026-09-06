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

  // Lightbox elements
  const lightbox = document.getElementById('lightbox');
  const lightboxImg = document.getElementById('lightbox-img');
  const lightboxCaption = document.getElementById('lightbox-caption');
  const lightboxClose = document.getElementById('lightbox-close');
  const lightboxBackdrop = lightbox.querySelector('.lightbox-backdrop');

  let uploadedItems = [];
  let isOnceMode = false;
  let currentViewMode = localStorage.getItem('clipto_view_mode') || 'grid'; // Default to thumbnail grid!

  // Sound chime via Web Audio API (zero external assets)
  function playSuccessChime() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
      osc.frequency.exponentialRampToValueAtTime(880.0, ctx.currentTime + 0.12); // A5
      gain.gain.setValueAtTime(0.15, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.3);
    } catch (e) {
      // Audio context might be restricted before user interaction
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
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && lightbox.classList.contains('active')) {
      closeLightbox();
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
        // Thumbnail Card View
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
        // List View
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

  // Fetch session info
  async function loadInfo() {
    try {
      const res = await fetch('/api/info');
      if (!res.ok) throw new Error('Failed to fetch info');
      const data = await res.json();

      hostnameDisplay.textContent = data.hostname || 'localhost';
      dirDisplay.textContent = data.dir || '.';
      isOnceMode = !!data.once;

      if (data.title) {
        sessionTitle.textContent = data.title;
        sessionTitle.classList.remove('hidden');
      }

      if (isOnceMode) {
        connectionStatus.className = 'status-pill once-mode';
        connectionStatus.querySelector('.status-text').textContent = 'One-Shot';
      }
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
    // If active element is the note input textarea, allow standard paste inside it
    if (document.activeElement === noteInput) {
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

    // If no image, but text was pasted and user isn't in an input, paste into note input
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
    fileInput.value = ''; // reset
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

  // Initialize
  setViewMode(currentViewMode);
  loadInfo();
})();
