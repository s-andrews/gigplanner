const bandId = window.BAND_ID;
const players = window.PLAYERS;
let activeGigId = null;

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
  if (res.ok) location.reload();
  else alert('Could not create gig');
}

document.getElementById('create-gig-btn')?.addEventListener('click', createGig);

document.querySelectorAll('.save-gig').forEach((btn) => {
  btn.addEventListener('click', async (e) => {
    const row = e.target.closest('tr');
    const gigId = row.dataset.gigId;
    const payload = {
      gig_date: row.querySelector('.fld-date').value,
      start_time: row.querySelector('.fld-start').value,
      end_time: row.querySelector('.fld-end').value,
      location: row.querySelector('.fld-location').value,
      status: row.querySelector('.fld-status').value,
    };
    const res = await fetch(`/api/gig/${gigId}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    alert(res.ok ? 'Saved' : 'Save failed');
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
      await fetch(`/api/gig/part/${gpId}`, {method: 'DELETE'});
      loadParts(gigId);
    });
  });
}

document.querySelectorAll('.manage-parts').forEach((btn) => {
  btn.addEventListener('click', (e) => {
    activeGigId = e.target.closest('tr').dataset.gigId;
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

async function loadResponses(gigId) {
  const res = await fetch(`/api/gig/${gigId}/responses`);
  const data = await res.json();
  const container = document.getElementById('responses-list');
  if (!data.ok) {
    container.innerHTML = '<div class="alert alert-danger">Could not load responses</div>';
    return;
  }

  container.innerHTML = `
    <div class="table-responsive">
      <table class="table table-sm table-striped align-middle mb-0">
        <thead>
          <tr><th>Player</th><th>Response</th><th>Updated</th></tr>
        </thead>
        <tbody>
          ${data.responses.map((row) => `
            <tr>
              <td>${row.player_name}</td>
              <td>${row.availability_status}</td>
              <td>${row.updated_at ? new Date(row.updated_at).toLocaleString() : '-'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

document.querySelectorAll('.view-responses').forEach((btn) => {
  btn.addEventListener('click', (e) => {
    const gigId = e.target.closest('tr').dataset.gigId;
    loadResponses(gigId);
    const modal = new bootstrap.Modal(document.getElementById('responsesModal'));
    modal.show();
  });
});
