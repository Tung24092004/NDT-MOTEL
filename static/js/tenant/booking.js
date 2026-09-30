(() => {
  'use strict';
  const qr = document.querySelector('#deposit-qr-image');
  if (qr) qr.addEventListener('error', () => { document.querySelector('#qr-error').hidden = false; });
  document.querySelectorAll('[data-copy-target]').forEach(button => {
    button.addEventListener('click', async () => {
      const value = document.getElementById(button.dataset.copyTarget)?.textContent.trim() || '';
      const feedback = button.parentElement.querySelector('.copy-feedback');
      try {
        await navigator.clipboard.writeText(value);
        feedback.textContent = 'Đã sao chép';
      } catch (error) {
        feedback.textContent = 'Không thể sao chép tự động';
      }
    });
  });
  document.querySelectorAll('[data-cancel-booking-form]').forEach(cancelForm => {
    function rememberCancelTrigger(event) {
      const trigger = event.target.closest('button[type=submit], input[type=submit]');
      if (trigger && cancelForm.contains(trigger)) cancelForm.ndtDialogTrigger = trigger;
    }
    cancelForm.addEventListener('focusin', rememberCancelTrigger);
    cancelForm.addEventListener('pointerdown', rememberCancelTrigger);
    cancelForm.addEventListener('click', rememberCancelTrigger);
    cancelForm.addEventListener('submit', async event => {
      if (cancelForm.dataset.confirmed === 'true') return;
      event.preventDefault();
      const confirmed = await window.NDTDialog.confirm({
        title: cancelForm.dataset.confirmTitle,
        message: cancelForm.dataset.confirmMessage,
        confirmLabel: 'Xác nhận hủy',
        danger: true,
        trigger: cancelForm.ndtDialogTrigger || event.submitter || document.activeElement
      });
      if (confirmed) {
        cancelForm.dataset.confirmed = 'true';
        cancelForm.requestSubmit();
      }
    });
  });
  const form = document.querySelector('#booking-create');
  if (!form) return;
  const sections = [...form.querySelectorAll('[data-step]')];
  const rows = document.querySelector('#companion-rows');
  const total = document.querySelector('#id_companions-TOTAL_FORMS');
  const people = form.querySelector('[name=so_nguoi_o]');
  const capacity = Number(form.dataset.capacity);
  const add = document.querySelector('#add-companion');
  document.querySelector('#prepare-companions').hidden = true;
  const progress = [...document.querySelectorAll('.booking-progress li')];
  const wizard = form.dataset.hasErrors !== 'true';
  let step = 0;
  function updateSummary() {
    const active = [...rows.querySelectorAll('.companion-row')].filter(r => !r.hidden);
    active.forEach((r, i) => { r.querySelector('.companion-number').textContent = i + 1; });
    const chosen = Number(people.value || 1);
    document.querySelector('#companion-count').textContent = `${active.length} / ${Math.max(0, chosen - 1)} người đi cùng`;
    document.querySelector('#remaining-preview').textContent = Math.max(0, capacity - chosen);
    add.disabled = active.length >= chosen - 1 || Number(total.value) >= 100;
    const start = form.querySelector('[name=ngay_nhan_phong]').value;
    const months = Number(form.querySelector('[name=so_thang_thue]').value);
    let endText = 'Chưa chọn ngày';
    if (start && months >= 1 && months <= 36) {
      const [y, m, d] = start.split('-').map(Number);
      const target = new Date(Date.UTC(y, m - 1 + months, 1));
      const last = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
      target.setUTCDate(Math.min(d, last));
      if (d <= last) target.setUTCDate(target.getUTCDate() - 1);
      endText = target.toLocaleDateString('vi-VN', {timeZone: 'UTC'});
    }
    document.querySelector('#checkout-preview').textContent = endText;
    const summary = document.querySelector('#confirmation-summary');
    summary.replaceChildren();
    const sharing = form.querySelector('[name=dong_y_nhan_yeu_cau_ghep]').checked ? 'Có' : 'Không';
    const values = [`Nhận phòng: ${start || 'Chưa chọn'}; trả dự kiến: ${endText}; ${months} tháng`,
      `${chosen} người; nhận yêu cầu ghép sau này: ${sharing}`,
      ...active.map(r => `${r.querySelector('[name$=-ho_ten]').value} · ${r.querySelector('[name$=-cccd]').value}`),
      `Điều khoản: ${form.querySelector('[name=da_dong_y_dieu_khoan]').checked ? 'Đã đồng ý' : 'Chưa đồng ý'}`];
    values.forEach(text => { const p = document.createElement('p'); p.textContent = text; summary.append(p); });
  }
  function showStep(index) {
    step = index;
    if (wizard) sections.forEach((s, i) => { s.hidden = i !== step; });
    progress.forEach((p, i) => {
      p.classList.toggle('is-complete', i < step);
      if (i === step) p.setAttribute('aria-current', 'step'); else p.removeAttribute('aria-current');
    });
    document.querySelector('#booking-prev').disabled = step === 0;
    document.querySelector('#booking-next').hidden = step === sections.length - 1;
    const position = document.querySelector('#step-position');
    position.replaceChildren();
    const current = document.createElement('strong');
    current.textContent = `Bước ${step + 1}`;
    const totalText = document.createElement('span');
    totalText.textContent = `trong ${sections.length}`;
    position.append(current, totalText);
    updateSummary();
  }
  function validate(section) {
    const invalid = [...section.querySelectorAll('input, select, textarea')].find(e => !e.disabled && !e.checkValidity());
    if (invalid) { invalid.reportValidity(); return false; }
    return true;
  }
  add.addEventListener('click', () => {
    const index = Number(total.value);
    if (add.disabled) return;
    const template = document.querySelector('#companion-template');
    rows.insertAdjacentHTML('beforeend', template.innerHTML.replaceAll('__prefix__', index));
    total.value = index + 1;
    updateSummary();
  });
  rows.addEventListener('click', event => {
    const button = event.target.closest('.remove-companion');
    if (!button) return;
    const row = button.closest('.companion-row');
    row.querySelector('[name$=-DELETE]').checked = true;
    row.hidden = true;
    row.querySelectorAll('input, select, textarea').forEach(e => { if (!e.name.endsWith('-DELETE')) e.disabled = true; });
    updateSummary();
  });
  form.addEventListener('input', updateSummary);
  document.querySelector('.booking-step-actions').hidden = !wizard;
  document.querySelector('#booking-prev').addEventListener('click', () => showStep(step - 1));
  document.querySelector('#booking-next').addEventListener('click', () => { if (validate(sections[step])) showStep(step + 1); });
  // Enable focusable validation across wizard steps, including no-JS server errors.
  form.noValidate = true;
  form.addEventListener('submit', event => {
    for (let i = 0; i < sections.length; i++) {
      const invalid = [...sections[i].querySelectorAll('input, select, textarea')].some(e => !e.disabled && !e.checkValidity());
      if (invalid) { event.preventDefault(); showStep(i); validate(sections[i]); return; }
    }
  });
  showStep(0);
})();
