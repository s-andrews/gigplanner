const dashboardCardClasses = [
  'dashboard-gig-card-available',
  'dashboard-gig-card-not-available',
  'dashboard-gig-card-unsure-yet',
  'dashboard-gig-card-unanswered',
];

function applyDashboardGigCardStyle(select) {
  const card = select.closest('.dashboard-gig-card');
  if (!card) return;
  card.classList.remove(...dashboardCardClasses);
  card.classList.add(`dashboard-gig-card-${select.value.toLowerCase().replaceAll(' ', '-')}`);
}

document.querySelectorAll('.availability-select').forEach((select) => {
  applyDashboardGigCardStyle(select);
  select.addEventListener('change', async (e) => {
    const parent = e.target.closest('.availability-control');
    const gigId = parent.dataset.gigId;
    const previousValue = e.target.dataset.previousValue || '';
    applyDashboardGigCardStyle(e.target);
    const res = await fetch(`/api/gig/${gigId}/availability`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({status: e.target.value})
    });
    if (!res.ok) {
      e.target.value = previousValue;
      applyDashboardGigCardStyle(e.target);
      alert('Could not update availability.');
      return;
    }
    e.target.dataset.previousValue = e.target.value;
  });
  select.dataset.previousValue = select.value;
});

document.querySelectorAll('.rehearsal-availability-select').forEach((select) => {
  select.dataset.previousValue = select.value;
  select.addEventListener('change', async (e) => {
    const parent = e.target.closest('.rehearsal-availability-control');
    const previousValue = e.target.dataset.previousValue || 'Available';
    const payload = {
      band_id: Number(parent.dataset.bandId),
      rehearsal_date: parent.dataset.rehearsalDate,
      is_available: e.target.value === 'Available',
    };
    const res = await fetch('/api/rehearsal/availability', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      e.target.value = previousValue;
      alert('Could not update rehearsal availability.');
      return;
    }
    e.target.dataset.previousValue = e.target.value;
  });
});
