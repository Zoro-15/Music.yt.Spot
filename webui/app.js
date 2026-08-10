// Frontend JavaScript Application for Music.yt.Spot Web GUI

let selectedJSONPath = null;

document.addEventListener('DOMContentLoaded', () => {
  fetchDiscoveredJSONs();
  fetchStatus();
  fetchQueueDetails();
  fetchConfig();
  fetchReviewTracks();

  // Poll status every 2.5 seconds
  setInterval(fetchStatus, 2500);
  setInterval(fetchQueueDetails, 3500);
});

function switchTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));

  document.getElementById(`tab-${tabId}`).style.display = 'block';
  event.target.classList.add('active');

  if (tabId === 'review') fetchReviewTracks();
  if (tabId === 'settings') fetchConfig();
}

async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();

    document.getElementById('stat-total').innerText = data.total;
    document.getElementById('stat-success').innerText = data.success;
    document.getElementById('stat-review').innerText = data.review;
    document.getElementById('stat-failed').innerText = data.failed;

    const percent = data.total > 0 ? Math.round((data.processed / data.total) * 100) : 0;
    document.getElementById('progress-bar').style.width = `${percent}%`;
    document.getElementById('progress-text').innerText = `Progress: ${percent}% (${data.processed}/${data.total})`;
    document.getElementById('remaining-text').innerText = `${data.remaining} tracks remaining`;

    const pill = document.getElementById('status-pill');
    const statusText = document.getElementById('status-text');

    if (data.is_running) {
      pill.classList.add('active');
      statusText.innerText = data.current_task || 'Downloading...';
    } else {
      pill.classList.remove('active');
      statusText.innerText = 'Idle';
    }
  } catch (err) {
    console.error('Status poll error:', err);
  }
}

async function fetchDiscoveredJSONs() {
  const container = document.getElementById('json-list');
  try {
    const res = await fetch('/api/find-jsons');
    const data = await res.json();

    if (!data.jsons || data.jsons.length === 0) {
      container.innerHTML = '<div style="color: var(--status-warning);">No Exportify JSON files detected in input/, root folder, or Downloads. Export a playlist and place it in input/!</div>';
      return;
    }

    let html = '';
    data.jsons.forEach((item, idx) => {
      const isChecked = idx === 0 ? 'checked' : '';
      if (idx === 0) selectedJSONPath = item.path;
      html += `
        <label class="track-item" style="cursor: pointer; margin-bottom: 8px;">
          <div style="display: flex; align-items: center; gap: 12px;">
            <input type="radio" name="json_select" value="${item.path}" ${isChecked} onchange="selectedJSONPath='${item.path}'">
            <div>
              <div class="track-title">${item.name}</div>
              <div class="track-artist">Location: ${item.location}</div>
            </div>
          </div>
        </label>
      `;
    });
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = '<div style="color: var(--status-danger);">Error fetching JSON files.</div>';
  }
}

async function prepareSelectedJSON() {
  try {
    const res = await fetch('/api/prepare-spotify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ json_path: selectedJSONPath }),
    });
    const data = await res.json();
    if (data.success) {
      alert('Playlist CSV prepared successfully!');
      fetchQueueDetails();
      fetchStatus();
    } else {
      alert('Failed to prepare playlist JSON.');
    }
  } catch (err) {
    alert('Error preparing playlist JSON.');
  }
}

async function startSpotifyDownload() {
  try {
    const res = await fetch('/api/start-spotify', { method: 'POST' });
    const data = await res.json();
    if (data.error) {
      alert(data.error);
    } else {
      fetchStatus();
    }
  } catch (err) {
    alert('Error starting download.');
  }
}

async function fetchQueueDetails() {
  const container = document.getElementById('track-queue');
  try {
    const res = await fetch('/api/progress-details');
    const data = await res.json();

    if (!data.tracks || data.tracks.length === 0) {
      return;
    }

    let html = '';
    data.tracks.forEach(track => {
      let badgeClass = 'badge-pending';
      if (track.status === 'success') badgeClass = 'badge-success';
      if (track.status === 'review') badgeClass = 'badge-review';
      if (track.status === 'failed') badgeClass = 'badge-failed';

      html += `
        <div class="track-item">
          <div class="track-info">
            <div class="track-title">[${track.index}] ${track.title}</div>
            <div class="track-artist">${track.artist} ${track.album ? '• ' + track.album : ''}</div>
          </div>
          <span class="badge ${badgeClass}">${track.status}</span>
        </div>
      `;
    });
    container.innerHTML = html;
  } catch (err) {
    console.error('Queue poll error:', err);
  }
}

async function searchSong() {
  const input = document.getElementById('search-input');
  const status = document.getElementById('search-result-status');
  const query = input.value.trim();
  if (!query) return;

  status.innerText = `Searching and downloading: '${query}'...`;
  try {
    const res = await fetch('/api/search-song', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: query }),
    });
    const data = await res.json();
    if (data.error) {
      status.innerText = `Error: ${data.error}`;
    } else {
      status.innerText = `✓ Download task launched for: '${query}'`;
      fetchStatus();
    }
  } catch (err) {
    status.innerText = 'Failed to submit search.';
  }
}

async function downloadLink() {
  const input = document.getElementById('link-input');
  const status = document.getElementById('link-result-status');
  const url = input.value.trim();
  if (!url) return;

  status.innerText = 'Submitting download link...';
  try {
    const res = await fetch('/api/download-link', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url }),
    });
    const data = await res.json();
    if (data.error) {
      status.innerText = `Error: ${data.error}`;
    } else {
      status.innerText = '✓ Download task launched for specified URL.';
      fetchStatus();
    }
  } catch (err) {
    status.innerText = 'Failed to submit link.';
  }
}

async function fetchReviewTracks() {
  const container = document.getElementById('review-queue');
  try {
    const res = await fetch('/api/review-tracks');
    const data = await res.json();

    if (!data.review_tracks || data.review_tracks.length === 0) {
      container.innerHTML = '<div style="text-align: center; color: var(--text-sub); padding: 20px;">No tracks currently flagged for review.</div>';
      return;
    }

    let html = '';
    data.review_tracks.forEach(item => {
      html += `
        <div class="track-item" style="flex-direction: column; align-items: flex-start; gap: 8px;">
          <div style="width: 100%; display: flex; justify-content: space-between;">
            <div class="track-title">[#${item.index}] ${item.title} - ${item.artist}</div>
            <span class="badge badge-review">Score: ${item.score}</span>
          </div>
          <div style="font-size: 12px; color: var(--text-sub);">Matched: ${item.yt_title}</div>
          <div style="display: flex; gap: 10px; width: 100%; margin-top: 4px;">
            <button class="btn btn-primary" style="padding: 6px 12px; font-size: 12px;" onclick="resolveReview('${item.index}', '${item.url}', '${item.title}', '${item.artist}')">✓ Accept</button>
          </div>
        </div>
      `;
    });
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = '<div style="color: var(--status-danger);">Error fetching review tracks.</div>';
  }
}

async function resolveReview(idx, url, title, artist) {
  try {
    const res = await fetch('/api/resolve-review', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ index: idx, url: url, title: title, artist: artist }),
    });
    const data = await res.json();
    if (data.success) {
      alert('Track match accepted!');
      fetchReviewTracks();
      fetchQueueDetails();
    }
  } catch (err) {
    alert('Error resolving review track.');
  }
}

async function fetchConfig() {
  try {
    const res = await fetch('/api/config');
    const cfg = await res.json();

    document.getElementById('cfg-workers').value = cfg.max_workers || 8;
    document.getElementById('cfg-ytmusic').checked = cfg.ytmusic_priority !== false;
    document.getElementById('cfg-lyrics').checked = cfg.fetch_lyrics !== false;
    document.getElementById('cfg-crop').checked = cfg.square_crop_artwork !== false;
    document.getElementById('cfg-android-sync').checked = cfg.auto_sync_android_music !== false;
    document.getElementById('cfg-index').checked = cfg.include_index_in_filename === true;
  } catch (err) {
    console.error('Config fetch error:', err);
  }
}

async function saveSettings() {
  const cfg = {
    max_workers: parseInt(document.getElementById('cfg-workers').value) || 8,
    ytmusic_priority: document.getElementById('cfg-ytmusic').checked,
    fetch_lyrics: document.getElementById('cfg-lyrics').checked,
    square_crop_artwork: document.getElementById('cfg-crop').checked,
    auto_sync_android_music: document.getElementById('cfg-android-sync').checked,
    include_index_in_filename: document.getElementById('cfg-index').checked,
  };

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cfg),
    });
    const data = await res.json();
    if (data.success) {
      alert('Settings saved successfully!');
    }
  } catch (err) {
    alert('Failed to save settings.');
  }
}

async function cleanCache() {
  if (!confirm('Are you sure you want to reset CSV data, progress state, and cache?')) return;

  try {
    const res = await fetch('/api/clean', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ include_output: false }),
    });
    const data = await res.json();
    if (data.success) {
      alert('Cache and logs reset successfully!');
      fetchStatus();
      fetchQueueDetails();
    }
  } catch (err) {
    alert('Failed to clean cache.');
  }
}
