// Auto-dismiss alerts after 4 seconds
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.alert').forEach(function (alert) {
    setTimeout(function () {
      alert.style.transition = 'opacity .4s';
      alert.style.opacity = '0';
      setTimeout(function () { alert.remove(); }, 400);
    }, 4000);
  });
});

// Confirm before dangerous actions
function confirmAction(message) {
  return confirm(message || 'Are you sure?');
}