function showToast(message, type) {
  type = type || 'success';
  var toast = document.createElement('div');
  toast.className = 'toast';
  if (type === 'error') toast.style.background = 'var(--danger)';
  else if (type === 'warning') toast.style.background = 'var(--warning)';
  else if (type === 'info') toast.style.background = 'var(--info)';
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(function () {
    toast.style.animation = 'slideIn 0.3s ease reverse';
    setTimeout(function () { toast.remove(); }, 300);
  }, 3000);
}

window.showToast = showToast;

document.addEventListener('DOMContentLoaded', function () {
  var params = new URLSearchParams(window.location.search);
  if (params.get('created') === '1') showToast('Создано успешно');
  if (params.get('updated') === '1') showToast('Обновлено');
  if (params.get('deleted') === '1') showToast('Удалено', 'warning');
  if (params.get('saved') === '1') showToast('Сохранено');
  var err = params.get('error');
  if (err) showToast(decodeURIComponent(err), 'error');
});
