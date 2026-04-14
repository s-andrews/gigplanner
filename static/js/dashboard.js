document.querySelectorAll('.availability-select').forEach((select) => {
  select.addEventListener('change', async (e) => {
    const parent = e.target.closest('.availability-control');
    const gigId = parent.dataset.gigId;
    const res = await fetch(`/api/gig/${gigId}/availability`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({status: e.target.value})
    });
    if (!res.ok) {
      alert('Could not update availability.');
    }
  });
});
