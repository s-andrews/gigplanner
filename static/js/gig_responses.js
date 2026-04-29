const gigId = window.GIG_ID;
const bandPlayers = window.BAND_PLAYERS || [];
const gigResponses = window.GIG_RESPONSES || [];
const playerById = new Map(bandPlayers.map((player) => [String(player.id), player]));
const responseByUserId = new Map(gigResponses.map((response) => [String(response.user_id), response]));
const responseClassNames = [
  'response-select-available',
  'response-select-not-available',
  'response-select-unsure-yet',
  'response-select-unanswered',
];
const summaryLabels = {
  available: 'Available',
  not_available: 'Not Available',
  unsure: 'Unsure',
  unanswered: 'Not Answered',
};
const statusToSummaryKey = {
  'Available': 'available',
  'Not Available': 'not_available',
  'Unsure yet': 'unsure',
  'Unanswered': 'unanswered',
};

function applyResponseSelectStyle(select) {
  select.classList.remove(...responseClassNames);
  const statusClass = `response-select-${select.value.toLowerCase().replaceAll(' ', '-')}`;
  select.classList.add(statusClass);
}

function applyResponseSelectStyleForStatus(select, status) {
  select.classList.remove(...responseClassNames);
  const statusClass = `response-select-${status.toLowerCase().replaceAll(' ', '-')}`;
  select.classList.add(statusClass);
}

function updateSummaryCount(summaryKey, nextCount) {
  const summaryItem = document.querySelector(`[data-summary-key="${summaryKey}"]`);
  if (!summaryItem) return;
  summaryItem.dataset.count = String(nextCount);
  summaryItem.textContent = `${nextCount} ${summaryLabels[summaryKey]}`;
}

function adjustSummary(previousStatus, nextStatus) {
  const previousKey = statusToSummaryKey[previousStatus];
  const nextKey = statusToSummaryKey[nextStatus];
  if (previousKey) {
    const previousItem = document.querySelector(`[data-summary-key="${previousKey}"]`);
    if (previousItem) {
      const currentCount = Number(previousItem.dataset.count || previousItem.textContent.split(' ')[0] || 0);
      updateSummaryCount(previousKey, Math.max(0, currentCount - 1));
    }
  }
  if (nextKey) {
    const nextItem = document.querySelector(`[data-summary-key="${nextKey}"]`);
    if (nextItem) {
      const currentCount = Number(nextItem.dataset.count || nextItem.textContent.split(' ')[0] || 0);
      updateSummaryCount(nextKey, currentCount + 1);
    }
  }
}

function buildPlayerOptions(selectedId) {
  const options = ['<option value="">-- Unassigned --</option>'];
  bandPlayers.forEach((player) => {
    options.push(
      `<option value="${player.id}" data-is-regular="${player.is_regular ? '1' : '0'}" ${String(selectedId) === String(player.id) ? 'selected' : ''}>${player.name}</option>`
    );
  });
  return options.join('');
}

function getPlayerStatus(userId) {
  if (!userId) return 'Unanswered';
  return responseByUserId.get(String(userId))?.availability_status || 'Unanswered';
}

function syncPlayerAvailabilityUI(userId, status) {
  document.querySelectorAll(`.gp-player[data-user-id="${userId}"]`).forEach((select) => {
    select.value = userId;
    applyResponseSelectStyleForStatus(select, status);
  });
  document.querySelectorAll(`.gig-part-availability-select[data-user-id="${userId}"]`).forEach((select) => {
    select.value = status;
    applyResponseSelectStyle(select);
    select.dataset.previousValue = status;
  });
}

async function updatePlayerAvailability(userId, nextStatus, previousStatus) {
  const res = await fetch(`/api/gig/${gigId}/response/${userId}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({status: nextStatus}),
  });
  if (!res.ok) {
    document.querySelectorAll(`.gp-player[data-user-id="${userId}"]`).forEach((select) => {
      applyResponseSelectStyleForStatus(select, previousStatus);
    });
    document.querySelectorAll(`.gig-part-availability-select[data-user-id="${userId}"]`).forEach((select) => {
      select.value = previousStatus;
      applyResponseSelectStyle(select);
      select.dataset.previousValue = previousStatus;
    });
    alert('Could not update response.');
    return;
  }
  const data = await res.json();
  adjustSummary(previousStatus, nextStatus);
  responseByUserId.set(String(userId), {
    ...(responseByUserId.get(String(userId)) || {user_id: userId}),
    availability_status: nextStatus,
    updated_at: data.updated_at,
  });
  syncPlayerAvailabilityUI(userId, nextStatus);
}

function renderParts(parts) {
  const container = document.getElementById('gig-parts-list');
  if (!container) return;
  if (!parts.length) {
    container.innerHTML = '<div class="text-muted">No parts assigned to this gig yet.</div>';
    attachPartEventHandlers();
    return;
  }
  container.innerHTML = parts.map((part) => {
    const player = playerById.get(String(part.assigned_user_id || ''));
    const isDep = Boolean(part.assigned_user_id && player && !player.is_regular);
    const status = getPlayerStatus(part.assigned_user_id);
    return `
      <div class="gig-part-row" data-gp-id="${part.id}">
        <div class="gig-part-main">
          <input class="form-control gp-name" value="${part.part_name}">
          <div class="gig-part-player-slot">
            <span class="gig-part-player-meta">
              <span class="gig-part-dep ${isDep ? '' : 'd-none'}">Dep</span>
            </span>
            <select class="form-select gp-player response-select response-select-${status.toLowerCase().replaceAll(' ', '-')}" data-user-id="${part.assigned_user_id || ''}">${buildPlayerOptions(part.assigned_user_id)}</select>
          </div>
          <div class="gig-part-availability-wrap">
            <select class="form-select gig-part-availability-select response-select response-select-${status.toLowerCase().replaceAll(' ', '-')}" data-user-id="${part.assigned_user_id || ''}" ${part.assigned_user_id ? '' : 'disabled'}>
              <option value="Unanswered" ${status === 'Unanswered' ? 'selected' : ''}>Unanswered</option>
              <option value="Available" ${status === 'Available' ? 'selected' : ''}>Available</option>
              <option value="Not Available" ${status === 'Not Available' ? 'selected' : ''}>Not Available</option>
              <option value="Unsure yet" ${status === 'Unsure yet' ? 'selected' : ''}>Unsure yet</option>
            </select>
          </div>
        </div>
        <button class="btn btn-sm btn-danger gp-del">Remove</button>
      </div>
    `;
  }).join('');
  attachPartEventHandlers();
}

async function loadParts() {
  const res = await fetch(`/api/gig/${gigId}/parts`);
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    const container = document.getElementById('gig-parts-list');
    if (container) {
      container.innerHTML = '<div class="alert alert-danger mb-0">Could not load lineup.</div>';
    }
    return;
  }
  renderParts(data.parts || []);
}

async function savePart(row) {
  const gpId = row.dataset.gpId;
  const res = await fetch(`/api/gig/part/${gpId}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      part_name: row.querySelector('.gp-name').value,
      assigned_user_id: row.querySelector('.gp-player').value || null,
    }),
  });
  if (!res.ok) {
    alert('Could not update lineup.');
    return;
  }
  await loadParts();
}

function attachPartEventHandlers() {
  document.querySelectorAll('#gig-parts-list .gp-name, #gig-parts-list .gp-player').forEach((field) => {
    field.addEventListener('change', async (event) => {
      const row = event.target.closest('[data-gp-id]');
      if (!row) return;
      if (event.target.classList.contains('gp-player')) {
        event.target.dataset.userId = event.target.value || '';
        if (event.target.value) {
          applyResponseSelectStyleForStatus(event.target, getPlayerStatus(event.target.value));
        } else {
          event.target.classList.remove(...responseClassNames);
        }
      }
      await savePart(row);
    });
  });

  document.querySelectorAll('#gig-parts-list .gp-del').forEach((button) => {
    button.addEventListener('click', async (event) => {
      const row = event.target.closest('[data-gp-id]');
      if (!row) return;
      const confirmed = window.confirm('Are you sure you want to remove this part from the lineup?');
      if (!confirmed) return;
      const res = await fetch(`/api/gig/part/${row.dataset.gpId}`, {method: 'DELETE'});
      if (!res.ok) {
        alert('Could not remove part.');
        return;
      }
      await loadParts();
    });
  });

  document.querySelectorAll('#gig-parts-list .gig-part-availability-select').forEach((select) => {
    applyResponseSelectStyle(select);
    select.dataset.previousValue = select.value;
    select.addEventListener('change', async (event) => {
      const userId = event.target.dataset.userId;
      if (!userId) return;
      const previousValue = event.target.dataset.previousValue || 'Unanswered';
      applyResponseSelectStyle(event.target);
      await updatePlayerAvailability(userId, event.target.value, previousValue);
    });
  });
}

document.getElementById('add-gig-part-btn')?.addEventListener('click', async () => {
  const nameInput = document.getElementById('new-gig-part-name');
  const playerSelect = document.getElementById('new-gig-part-player');
  const partName = nameInput.value.trim();
  if (!partName) return;
  const res = await fetch(`/api/gig/${gigId}/part`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      part_name: partName,
      assigned_user_id: playerSelect.value || null,
    }),
  });
  if (!res.ok) {
    alert('Could not add part.');
    return;
  }
  nameInput.value = '';
  playerSelect.value = '';
  await loadParts();
});

loadParts();
