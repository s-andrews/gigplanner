const bandId = window.BAND_ID;

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
