const bandId = window.BAND_ID;
let renameBandModalInstance = null;

function getRenameBandModal() {
  const modalElement = document.getElementById('renameBandModal');
  if (!modalElement || !window.bootstrap) return null;
  if (!renameBandModalInstance) {
    renameBandModalInstance = new bootstrap.Modal(modalElement);
  }
  return renameBandModalInstance;
}

function syncDefaultPartSelections() {
  document.querySelectorAll('.default-part-select').forEach((select) => {
    const selectedUserId = select.dataset.selectedUserId || '';
    select.value = selectedUserId;
  });
}

syncDefaultPartSelections();

document.getElementById('add-part-btn')?.addEventListener('click', async () => {
  const name = document.getElementById('new-part-name').value.trim();
  if (!name) return;
  await fetch(`/api/band/${bandId}/part`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name})
  });
  location.reload();
});

document.getElementById('add-player-btn')?.addEventListener('click', async () => {
  const payload = {
    name: document.getElementById('p-name').value,
    email: document.getElementById('p-email').value,
    phone: document.getElementById('p-phone').value,
    instruments_played: document.getElementById('p-inst').value,
  };
  const res = await fetch(`/api/band/${bandId}/player`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    alert('Could not add player');
    return;
  }
  document.getElementById('p-name').value = '';
  document.getElementById('p-email').value = '';
  document.getElementById('p-phone').value = '';
  document.getElementById('p-inst').value = '';
  location.reload();
});

document.querySelectorAll('.co-admin-toggle').forEach((el) => {
  el.addEventListener('change', async (e) => {
    await fetch(`/api/band/${bandId}/player/${e.target.dataset.userId}/coadmin`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({is_co_admin: e.target.checked})
    });
  });
});

const rehearsalEnabledInput = document.getElementById('rehearsal-enabled');
const rehearsalFields = document.getElementById('rehearsal-settings-fields');
rehearsalEnabledInput?.addEventListener('change', () => {
  rehearsalFields?.classList.toggle('d-none', !rehearsalEnabledInput.checked);
});

document.getElementById('save-rehearsal-settings-btn')?.addEventListener('click', async () => {
  const payload = {
    enabled: rehearsalEnabledInput?.checked,
    weekday: document.getElementById('rehearsal-weekday').value || null,
    location: document.getElementById('rehearsal-location').value,
    start_time: document.getElementById('rehearsal-start-time').value || null,
    end_time: document.getElementById('rehearsal-end-time').value || null,
  };
  const res = await fetch(`/api/band/${bandId}/rehearsal-settings`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    alert(data.error || 'Could not save rehearsal settings');
    return;
  }
  alert('Rehearsal settings saved.');
});

document.getElementById('save-band-name-btn')?.addEventListener('click', async () => {
  const nameInput = document.getElementById('rename-band-name');
  const timezoneSelect = document.getElementById('rename-band-timezone');
  const name = nameInput?.value.trim() || '';
  const timezone = timezoneSelect?.value || '';
  if (!name) {
    alert('Band name is required.');
    return;
  }
  if (!timezone) {
    alert('Band timezone is required.');
    return;
  }

  const res = await fetch(`/api/band/${bandId}/name`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name, timezone}),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    alert(data.error || 'Could not update band name');
    return;
  }

  document.getElementById('band-name-heading').textContent = name;
  document.getElementById('band-timezone-heading').textContent =
    timezoneSelect?.selectedOptions?.[0]?.textContent || timezone;
  getRenameBandModal()?.hide();
});

document.querySelectorAll('.default-part-select').forEach((el) => {
  el.addEventListener('change', async (e) => {
    const partId = e.target.dataset.partId;
    const user_id = e.target.value || null;
    await fetch(`/api/band/${bandId}/part/${partId}/default`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({user_id})
    });
    e.target.dataset.selectedUserId = e.target.value || '';
  });
});

document.querySelectorAll('.delete-player-btn').forEach((btn) => {
  btn.addEventListener('click', async (e) => {
    const row = e.target.closest('tr');
    const userId = row.dataset.userId;
    const confirmed = window.confirm('Are you sure you want to delete this player from the band?');
    if (!confirmed) return;

    const res = await fetch(`/api/band/${bandId}/player/${userId}`, { method: 'DELETE' });
    if (!res.ok) {
      alert('Could not delete player');
      return;
    }
    location.reload();
  });
});

document.querySelectorAll('.delete-part-btn').forEach((btn) => {
  btn.addEventListener('click', async (e) => {
    const item = e.target.closest('[data-part-id]');
    const partId = item.dataset.partId;
    const confirmed = window.confirm('Are you sure you want to delete this part from the default lineup?');
    if (!confirmed) return;

    const res = await fetch(`/api/band/${bandId}/part/${partId}`, { method: 'DELETE' });
    if (!res.ok) {
      alert('Could not delete part');
      return;
    }
    location.reload();
  });
});
