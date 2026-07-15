// Maintenance Tracker shell behaviors. Everything is data-attribute
// driven so templates never embed URLs or logic in script blocks.

document.addEventListener('DOMContentLoaded', function () {
  // Toasts: auto-dismiss after 5s
  document.querySelectorAll('.mt-toast').forEach(function (toast) {
    setTimeout(function () {
      toast.style.transition = 'opacity 0.3s ease';
      toast.style.opacity = '0';
      setTimeout(function () { toast.remove(); }, 300);
    }, 5000);
  });

  // Confirmations: <form data-confirm="message">
  document.querySelectorAll('form[data-confirm]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      if (!window.confirm(form.getAttribute('data-confirm'))) {
        event.preventDefault();
      }
    });
  });

  // Shared delete modal: buttons carry data-delete-url / data-delete-label
  var deleteModal = document.getElementById('mtDeleteModal');
  if (deleteModal) {
    var deleteForm = deleteModal.querySelector('form');
    var deleteLabel = deleteModal.querySelector('[data-role="delete-label"]');
    deleteModal.addEventListener('show.bs.modal', function (event) {
      var button = event.relatedTarget;
      deleteForm.action = button.getAttribute('data-delete-url');
      deleteLabel.textContent = button.getAttribute('data-delete-label');
    });
  }

  // Mobile sidebar toggle
  var sidebar = document.querySelector('.mt-sidebar');
  var backdrop = document.querySelector('.mt-backdrop');
  var toggle = document.querySelector('[data-role="sidebar-toggle"]');
  if (toggle && sidebar) {
    toggle.addEventListener('click', function () {
      sidebar.classList.toggle('open');
      if (backdrop) backdrop.classList.toggle('show');
    });
    if (backdrop) {
      backdrop.addEventListener('click', function () {
        sidebar.classList.remove('open');
        backdrop.classList.remove('show');
      });
    }
  }
});
