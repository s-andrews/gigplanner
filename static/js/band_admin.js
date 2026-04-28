const bandId = window.BAND_ID;
const players = window.PLAYERS;
let activeGigId = null;
let activeRehearsalDate = null;

function activateAdminTabFromHash() {
  if (!window.bootstrap || !location.hash) return;
  const tabButton = document.querySelector(`[data-bs-target="${location.hash}"]`);
  if (!tabButton) return;
  bootstrap.Tab.getOrCreateInstance(tabButton).show();
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
    gig_date: document.getElementById('gig-date').value,
    start_time: document.getElementById('start-time').value,
    end_time: document.getElementById('end-time').value,
    location: document.getElementById('location').value,
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
    document.getElementById('gig-date').value = '';
    document.getElementById('start-time').value = '';
    document.getElementById('end-time').value = '';
    document.getElementById('location').value = '';
    document.getElementById('status').value = 'Unconfirmed';
    document.getElementById('fee-player').value = '';
    document.getElementById('fee-band').value = '';
    location.reload();
  } else alert('Could not create gig');
}

document.getElementById('create-gig-btn')?.addEventListener('click', createGig);

async function saveGigCard(card) {
  const gigId = card.dataset.gigId;
  const payload = {
    gig_date: card.querySelector('.fld-date').value,
    start_time: card.querySelector('.fld-start').value,
    end_time: card.querySelector('.fld-end').value,
    location: card.querySelector('.fld-location').value,
    status: card.querySelector('.fld-status').value,
  };
  const res = await fetch(`/api/gig/${gigId}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    alert('Could not save gig changes.');
  }
}

document.querySelectorAll('#gigs-list [data-gig-id]').forEach((card) => {
  card.querySelectorAll('.fld-date, .fld-start, .fld-end, .fld-location, .fld-status').forEach((field) => {
    field.addEventListener('change', async (e) => {
      await saveGigCard(e.target.closest('[data-gig-id]'));
    });
  });
});

document.querySelectorAll('.delete-gig').forEach((btn) => {
  btn.addEventListener('click', async (e) => {
    const card = e.target.closest('[data-gig-id]');
    const gigId = card.dataset.gigId;
    const confirmed = window.confirm('Are you sure you want to delete this gig? This cannot be undone.');
    if (!confirmed) return;

    const res = await fetch(`/api/gig/${gigId}`, { method: 'DELETE' });
    if (!res.ok) {
      alert('Delete failed');
      return;
    }
    card.remove();
  });
});

function playerOptions(selectedId) {
  const opts = ['<option value="">-- Unassigned --</option>'];
  players.forEach(p => {
    opts.push(`<option value="${p.id}" ${String(selectedId)===String(p.id)?'selected':''}>${p.name}</option>`);
  });
  return opts.join('');
}

async function loadParts(gigId) {
  const res = await fetch(`/api/gig/${gigId}/parts`);
  const data = await res.json();
  const container = document.getElementById('parts-list');
  if (!data.ok) {
    container.innerHTML = '<div class="alert alert-danger">Could not load parts</div>';
    return;
  }
  container.innerHTML = data.parts.map(part => `
    <div class="row g-2 mb-2 align-items-center" data-gp-id="${part.id}">
      <div class="col-md-5"><input class="form-control form-control-sm gp-name" value="${part.part_name}"></div>
      <div class="col-md-5"><select class="form-select form-select-sm gp-player">${playerOptions(part.assigned_user_id)}</select></div>
      <div class="col-md-2 d-flex justify-content-end"><button class="btn btn-sm btn-danger gp-del">Remove Part</button></div>
    </div>
  `).join('');

  async function savePart(row) {
    const gpId = row.dataset.gpId;
    await fetch(`/api/gig/part/${gpId}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        part_name: row.querySelector('.gp-name').value,
        assigned_user_id: row.querySelector('.gp-player').value || null,
      })
    });
  }

  container.querySelectorAll('.gp-name, .gp-player').forEach((field) => {
    field.addEventListener('change', async (e) => {
      const row = e.target.closest('[data-gp-id]');
      await savePart(row);
    });
  });

  container.querySelectorAll('.gp-del').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      const gpId = e.target.closest('[data-gp-id]').dataset.gpId;
      const confirmed = window.confirm('Are you sure you want to remove this part from the lineup?');
      if (!confirmed) return;
      await fetch(`/api/gig/part/${gpId}`, {method: 'DELETE'});
      loadParts(gigId);
    });
  });
}

document.querySelectorAll('.manage-parts').forEach((btn) => {
  btn.addEventListener('click', (e) => {
    activeGigId = e.target.closest('[data-gig-id]').dataset.gigId;
    loadParts(activeGigId);
    const modal = new bootstrap.Modal(document.getElementById('partsModal'));
    modal.show();
  });
});

document.getElementById('add-gig-part-btn')?.addEventListener('click', async () => {
  if (!activeGigId) return;
  await fetch(`/api/gig/${activeGigId}/part`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      part_name: document.getElementById('new-gig-part-name').value,
      assigned_user_id: document.getElementById('new-gig-part-player').value || null,
    })
  });
  document.getElementById('new-gig-part-name').value = '';
  loadParts(activeGigId);
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
  btn.addEventListener('click', (e) => {
    const rehearsalDate = e.target.dataset.rehearsalDate;
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
