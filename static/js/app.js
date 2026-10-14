(() => {
  'use strict';
  const $ = (s, scope = document) => scope.querySelector(s);
  const $$ = (s, scope = document) => [...scope.querySelectorAll(s)];

  // Persist theme locally. The first paint is handled by a small script in <head>.
  $('#themeToggle')?.addEventListener('click', () => {
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('echo-theme', next); } catch (_) { /* private mode */ }
  });

  const sidebar = $('#sidebar');
  const shade = $('#mobileShade');
  function toggleMenu(open) {
    sidebar?.classList.toggle('is-open', open);
    shade?.classList.toggle('is-open', open);
    document.body.style.overflow = open ? 'hidden' : '';
  }
  $('#menuToggle')?.addEventListener('click', () => toggleMenu(true));
  shade?.addEventListener('click', () => toggleMenu(false));
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') toggleMenu(false);
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      const search = $('#entrySearch');
      if (search) { e.preventDefault(); search.focus(); }
    }
  });

  // Filter and sort the actual server-rendered entries, no extra API required.
  const feed = $('#entryList');
  const search = $('#entrySearch');
  const sort = $('#entrySort');
  const chips = $$('[data-filter]');
  let filter = 'all';
  const entries = feed ? $$('[data-entry]', feed) : [];
  function localDay(input) {
    return new Date(input).toLocaleDateString('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' });
  }
  function updateFeed() {
    if (!feed) return;
    const q = (search?.value || '').toLocaleLowerCase('vi').trim();
    const now = new Date();
    const today = localDay(now);
    const start = new Date(now.getTime() - 6 * 86400000);
    const startDay = localDay(start);
    let visible = 0;
    const ordered = [...entries].sort((a, b) => {
      if (sort?.value === 'oldest') return Number(a.dataset.id) - Number(b.dataset.id);
      if (sort?.value === 'name') return a.dataset.name.localeCompare(b.dataset.name, 'vi');
      return Number(b.dataset.id) - Number(a.dataset.id);
    });
    ordered.forEach((card) => {
      const matchText = (card.dataset.name + ' ' + card.dataset.text).includes(q);
      const day = localDay(card.dataset.timestamp);
      const matchDate = filter === 'all' || (filter === 'today' && day === today) ||
        (filter === 'week' && day >= startDay && day <= today);
      card.hidden = !(matchText && matchDate);
      if (!card.hidden) visible += 1;
      feed.appendChild(card);
    });
    const empty = $('#emptySearch');
    if (empty) empty.hidden = !entries.length || visible > 0;
    const end = $('.feed-end');
    if (end) end.hidden = entries.length > 0 && visible === 0;
  }
  search?.addEventListener('input', updateFeed);
  sort?.addEventListener('change', updateFeed);
  chips.forEach(chip => chip.addEventListener('click', () => {
    filter = chip.dataset.filter;
    chips.forEach(item => item.classList.toggle('active', item === chip));
    updateFeed();
  }));
  $('#resetFilters')?.addEventListener('click', () => {
    filter = 'all';
    if (search) search.value = '';
    if (sort) sort.value = 'newest';
    chips.forEach(item => item.classList.toggle('active', item.dataset.filter === 'all'));
    updateFeed();
  });

  // Native confirmation dialog: deletion is intentionally POST-only.
  const modal = $('#deleteDialog');
  const form = $('#deleteForm');
  $$('[data-delete-id]').forEach(button => button.addEventListener('click', () => {
    if (!modal || !form) return;
    form.action = '/delete/' + encodeURIComponent(button.dataset.deleteId);
    $('#deleteName').textContent = button.dataset.deleteName || 'người gửi';
    if (typeof modal.showModal === 'function') modal.showModal();
    else if (window.confirm('Xóa lời nhắn này?')) form.submit();
  }));
  $('#cancelDelete')?.addEventListener('click', () => modal?.close());
  modal?.addEventListener('click', (e) => { if (e.target === modal) modal.close(); });

  // Copy a deep link to one entry.
  $$('[data-copy]').forEach(button => button.addEventListener('click', async () => {
    const link = `${location.origin}/#entry-${button.dataset.copy}`;
    try {
      await navigator.clipboard.writeText(link);
      toast('Đã sao chép liên kết lời nhắn.');
    } catch (_) {
      window.prompt('Sao chép liên kết:', link);
    }
  }));

  // Live preview and accessible character counter.
  const name = $('#name');
  const message = $('#message');
  function updatePreview() {
    if (!name || !message) return;
    const n = name.value.trim();
    const m = message.value.trim();
    $('#previewName').textContent = n || 'Bạn sẽ xuất hiện ở đây';
    $('#previewAvatar').textContent = (n[0] || 'B').toLocaleUpperCase('vi');
    $('#previewMessage').textContent = m || 'Lời nhắn của bạn sẽ được hiển thị tại đây khi bạn bắt đầu viết...';
    $('#charCounter').textContent = `${message.value.length}/600`;
  }
  name?.addEventListener('input', updatePreview);
  message?.addEventListener('input', updatePreview);
  updatePreview();
  $$('[data-tip]').forEach(button => button.addEventListener('click', () => {
    if (!message) return;
    message.value = button.dataset.tip;
    message.focus();
    updatePreview();
  }));
  $('#entryForm')?.addEventListener('submit', e => {
    const n = name?.value.trim();
    const m = message?.value.trim();
    if (!n || !m) {
      e.preventDefault();
      toast('Vui lòng nhập tên và lời nhắn trước khi gửi.', 'error');
      (!n ? name : message)?.focus();
    }
  });

  function toast(text, type = 'success') {
    document.querySelector('[data-toast]')?.remove();
    const node = document.createElement('div');
    node.className = `toast toast-${type}`;
    node.setAttribute('data-toast', '');
    node.setAttribute('role', 'status');
    node.textContent = text;
    document.body.appendChild(node);
    window.setTimeout(() => node.remove(), 4800);
  }
  const systemToast = $('[data-toast]');
  $('[data-dismiss-toast]')?.addEventListener('click', () => systemToast?.remove());
  if (systemToast) window.setTimeout(() => systemToast.remove(), 6500);
})();
