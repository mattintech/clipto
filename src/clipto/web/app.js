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

  let uploadedItems = [];
  let isOnceMode = false;

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

  // Format file size
  function formatSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  // Add upload to recent list
  function renderUploadItem(filename, size, isText = false) {
    const empty = uploadsList.querySelector('.empty-state');
    if (empty) empty.remove();

    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const item = document.createElement('div');
    item.className = 'upload-item';
    item.innerHTML = `
      <div class="upload-item-left">
        <div class="upload-icon">
          ${isText 
            ? '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>'
            : '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>'
          }
        </div>
        <div class="upload-item-info">
          <span class="upload-item-name" title="${filename}">${filename}</span>
          <span class="upload-item-meta">${formatSize(size)} • ${time}</span>
        </div>
      </div>
      <span class="badge" style="color: var(--success); border-color: rgba(16, 185, 129, 0.3);">Saved</span>
    `;

    uploadsList.prepend(item);
    uploadedItems.push(filename);
    uploadCountBadge.textContent = `${uploadedItems.length} item${uploadedItems.length === 1 ? '' : 's'}`;
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
        result.saved_files.forEach((file) => {
          renderUploadItem(file.name, file.size, file.name.endsWith('.txt'));
          showToast(`Saved ${file.name}`);
        });
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
  loadInfo();
})();
