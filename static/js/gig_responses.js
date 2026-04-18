const gigId = window.GIG_ID;
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

function formatUpdatedAt(timestamp) {
  if (!timestamp) return '-';
  return new Date(timestamp).toLocaleString();
}

function applyResponseSelectStyle(select) {
  select.classList.remove(...responseClassNames);
  const statusClass = `response-select-${select.value.toLowerCase().replaceAll(' ', '-')}`;
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

document.querySelectorAll('.response-updated').forEach((cell) => {
  cell.textContent = formatUpdatedAt(cell.dataset.updatedAt);
});

document.querySelectorAll('.response-select').forEach((select) => {
  applyResponseSelectStyle(select);
  select.dataset.previousValue = select.value;

  select.addEventListener('change', async (e) => {
    const row = e.target.closest('tr');
    const previousValue = e.target.dataset.previousValue || '';
    const userId = row.dataset.userId;
    applyResponseSelectStyle(e.target);
    const res = await fetch(`/api/gig/${gigId}/response/${userId}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({status: e.target.value})
    });

    if (!res.ok) {
      e.target.value = previousValue;
      applyResponseSelectStyle(e.target);
      alert('Could not update response.');
      return;
    }

    const data = await res.json();
    adjustSummary(previousValue, e.target.value);
    e.target.dataset.previousValue = e.target.value;
    const updatedCell = row.querySelector('.response-updated');
    updatedCell.dataset.updatedAt = data.updated_at;
    updatedCell.textContent = formatUpdatedAt(data.updated_at);
  });
});
