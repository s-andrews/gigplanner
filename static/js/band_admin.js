const bandId = window.BAND_ID;
let activeRehearsalDate = null;
let activeGigId = null;
let gigModalInstance = null;

function activateAdminTabFromHash() {
  if (!window.bootstrap || !location.hash) return;
  const tabButton = document.querySelector(`[data-bs-target="${location.hash}"]`);
  if (!tabButton) return;
  bootstrap.Tab.getOrCreateInstance(tabButton).show();
}

function getGigModal() {
  const modalElement = document.getElementById('gigModal');
  if (!modalElement || !window.bootstrap) return null;
  if (!gigModalInstance) {
    gigModalInstance = new bootstrap.Modal(modalElement);
  }
  return gigModalInstance;
}

function getGigCardData(card) {
  const dataNode = card.querySelector('.gig-card-data');
  if (!dataNode) return null;
  try {
    return JSON.parse(dataNode.textContent);
  } catch (error) {
    console.error('Could not parse gig card data', error);
    return null;
  }
}

function setGigModalFields(card) {
  const data = getGigCardData(card);
  if (!data) return;
  activeGigId = String(data.id || card.dataset.gigId || '');
  document.getElementById('modal-gig-id').value = activeGigId;
  document.getElementById('modal-gig-title').value = data.title || '';
  document.getElementById('modal-gig-date').value = data.gig_date || '';
  document.getElementById('modal-start-time').value = data.start_time || '';
  document.getElementById('modal-end-time').value = data.end_time || '';
  document.getElementById('modal-location').value = data.location || '';
  document.getElementById('modal-location-url').value = data.location_url || '';
  document.getElementById('modal-gig-notes').value = data.notes || '';
  document.getElementById('modal-status').value = data.status || 'Unconfirmed';
  document.getElementById('modal-fee-player').value = data.fee_per_player ?? '';
  document.getElementById('modal-fee-band').value = data.fee_for_band ?? '';
}

document.querySelectorAll('.nav-tabs [data-bs-toggle="tab"]').forEach((tabButton) => {
  tabButton.addEventListener('shown.bs.tab', (event) => {
    const target = event.target.dataset.bsTarget;
    if (!target) return;
    history.replaceState(null, '', `${location.pathname}${location.search}${target}`);
  });
});

activateAdminTabFromHash();

async function createGig() {
  const payload = {
    title: document.getElementById('gig-title').value,
    gig_date: document.getElementById('gig-date').value,
    start_time: document.getElementById('start-time').value,
    end_time: document.getElementById('end-time').value,
    location: document.getElementById('location').value,
    location_url: document.getElementById('location-url').value,
    notes: document.getElementById('gig-notes').value,
    status: document.getElementById('status').value,
    fee_per_player: document.getElementById('fee-player').value,
    fee_for_band: document.getElementById('fee-band').value,
  };
  const res = await fetch(`/api/band/${bandId}/gig`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  if (res.ok) {
    document.getElementById('gig-title').value = '';
    document.getElementById('gig-date').value = '';
    document.getElementById('start-time').value = '';
    document.getElementById('end-time').value = '';
    document.getElementById('location').value = '';
    document.getElementById('location-url').value = '';
    document.getElementById('gig-notes').value = '';
    document.getElementById('status').value = 'Unconfirmed';
    document.getElementById('fee-player').value = '';
    document.getElementById('fee-band').value = '';
    location.reload();
  } else {
    alert('Could not create gig');
  }
}

document.getElementById('create-gig-btn')?.addEventListener('click', createGig);

document.querySelectorAll('.edit-gig').forEach((btn) => {
  btn.addEventListener('click', (event) => {
    const card = event.target.closest('[data-gig-id]');
    if (!card) return;
    setGigModalFields(card);
    getGigModal()?.show();
  });
});

document.getElementById('save-gig-btn')?.addEventListener('click', async () => {
  const gigId = document.getElementById('modal-gig-id').value;
  if (!gigId) return;
  const payload = {
    title: document.getElementById('modal-gig-title').value,
    gig_date: document.getElementById('modal-gig-date').value,
    start_time: document.getElementById('modal-start-time').value,
    end_time: document.getElementById('modal-end-time').value,
    location: document.getElementById('modal-location').value,
    location_url: document.getElementById('modal-location-url').value,
    notes: document.getElementById('modal-gig-notes').value,
    status: document.getElementById('modal-status').value,
    fee_per_player: document.getElementById('modal-fee-player').value,
    fee_for_band: document.getElementById('modal-fee-band').value,
  };
  const res = await fetch(`/api/gig/${gigId}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    alert('Could not save gig changes.');
    return;
  }
  location.reload();
});

document.getElementById('delete-gig-btn')?.addEventListener('click', async () => {
  if (!activeGigId) return;
  const confirmed = window.confirm('Are you sure you want to delete this gig? This cannot be undone.');
  if (!confirmed) return;

  const res = await fetch(`/api/gig/${activeGigId}`, { method: 'DELETE' });
  if (!res.ok) {
    alert('Delete failed');
    return;
  }
  getGigModal()?.hide();
  const card = document.querySelector(`[data-gig-id="${activeGigId}"]`);
  if (card) {
    card.remove();
  }
  activeGigId = null;
});

async function openRehearsalModal(rehearsalDate) {
  activeRehearsalDate = rehearsalDate;
  const res = await fetch(`/api/band/${bandId}/rehearsal/${rehearsalDate}`);
  const data = await res.json();
  if (!data.ok) {
    alert('Could not load rehearsal details.');
    return;
  }
  document.getElementById('rehearsal-cancelled-toggle').checked = data.is_cancelled;
  const container = document.getElementById('rehearsal-players-list');
  container.innerHTML = data.players.map((player) => `
    <label class="rehearsal-player-row d-flex justify-content-between align-items-center mb-2 ${player.is_unavailable ? 'rehearsal-player-row-unavailable' : ''}">
      <span>${player.name} ${player.is_regular ? '<small class="text-muted">(Regular)</small>' : '<small class="text-muted">(Extra)</small>'} ${player.is_unavailable ? '<small class="rehearsal-player-status">(Unavailable)</small>' : ''}</span>
      <input class="form-check-input rehearsal-player-toggle" type="checkbox" value="${player.id}" ${player.is_scheduled ? 'checked' : ''}>
    </label>
  `).join('');
  const modal = new bootstrap.Modal(document.getElementById('rehearsalModal'));
  modal.show();
}

document.querySelectorAll('.manage-rehearsal').forEach((btn) => {
  btn.addEventListener('click', (event) => {
    const rehearsalDate = event.target.dataset.rehearsalDate;
    openRehearsalModal(rehearsalDate);
  });
});

document.getElementById('save-rehearsal-btn')?.addEventListener('click', async () => {
  if (!activeRehearsalDate) return;
  const scheduledPlayerIds = Array.from(document.querySelectorAll('.rehearsal-player-toggle:checked')).map((el) => Number(el.value));
  const cancelled = document.getElementById('rehearsal-cancelled-toggle').checked;
  const cancelRes = await fetch(`/api/band/${bandId}/rehearsal/${activeRehearsalDate}/cancel`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({is_cancelled: cancelled}),
  });
  const playersRes = await fetch(`/api/band/${bandId}/rehearsal/${activeRehearsalDate}/players`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({scheduled_player_ids: scheduledPlayerIds}),
  });
  if (!cancelRes.ok || !playersRes.ok) {
    alert('Could not save rehearsal changes.');
    return;
  }
  location.hash = '#admin-rehearsals-panel';
  location.reload();
});
