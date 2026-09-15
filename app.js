/**
 * Психоаналитический консультант (Евгения)
 * Скрипт интерактивности: Модальные окна, FAQ аккордеон, валидация формы.
 * Чистый Vanilla JS без внешних зависимостей.
 */

document.addEventListener('DOMContentLoaded', () => {
  // --------------------------------------------------------------------------
  // 1. Управление модальными окнами (Запись и Политика конфиденциальности)
  // --------------------------------------------------------------------------
  const bookingModal = document.getElementById('bookingModal');
  const policyModal = document.getElementById('policyModal');
  const openBookingBtns = document.querySelectorAll('.open-booking-modal');
  const openPolicyBtns = document.querySelectorAll('.open-policy-modal');
  const closeBookingBtn = document.getElementById('closeBookingModal');
  const closePolicyBtn = document.getElementById('closePolicyModal');
  const scrollToFormBtns = document.querySelectorAll('.scrollToFormBtn');

  function openModal(modal) {
    if (!modal) return;
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
    
    // Фокус на кнопку закрытия для доступности
    const closeBtn = modal.querySelector('.modal-close');
    if (closeBtn) {
      setTimeout(() => closeBtn.focus(), 50);
    }
  }

  function closeModal(modal) {
    if (!modal) return;
    modal.classList.remove('active');
    // Восстанавливаем скролл только если нет других открытых модалок
    if (!document.querySelector('.modal-overlay.active')) {
      document.body.style.overflow = '';
    }
  }

  // Слушатели открытия модалки записи
  openBookingBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      openModal(bookingModal);
    });
  });

  // Слушатели открытия модалки политики
  openPolicyBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      openModal(policyModal);
    });
  });

  // Кнопки закрытия
  if (closeBookingBtn) {
    closeBookingBtn.addEventListener('click', () => closeModal(bookingModal));
  }
  if (closePolicyBtn) {
    closePolicyBtn.addEventListener('click', () => closeModal(policyModal));
  }

  // Закрытие по клику на фон (overlay)
  [bookingModal, policyModal].forEach(modal => {
    if (!modal) return;
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        closeModal(modal);
      }
    });
  });

  // Закрытие по клавише Esc
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeModal(bookingModal);
      closeModal(policyModal);
    }
  });

  // Переход к форме из модального окна записи
  scrollToFormBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      closeModal(bookingModal);
      const formElement = document.getElementById('contact');
      if (formElement) {
        formElement.scrollIntoView({ behavior: 'smooth' });
        setTimeout(() => {
          const nameInput = document.getElementById('clientName');
          if (nameInput) nameInput.focus();
        }, 600);
      }
    });
  });

  // --------------------------------------------------------------------------
  // 2. Доступный FAQ-аккордеон
  // --------------------------------------------------------------------------
  const faqButtons = document.querySelectorAll('.faq-button');

  faqButtons.forEach(button => {
    button.addEventListener('click', () => {
      const item = button.closest('.faq-item');
      const isExpanded = button.getAttribute('aria-expanded') === 'true';

      // Закрываем остальные вкладки (одиночный режим раскрытия)
      document.querySelectorAll('.faq-item').forEach(otherItem => {
        if (otherItem !== item) {
          otherItem.classList.remove('active');
          const otherBtn = otherItem.querySelector('.faq-button');
          if (otherBtn) otherBtn.setAttribute('aria-expanded', 'false');
        }
      });

      // Переключаем текущую
      if (isExpanded) {
        item.classList.remove('active');
        button.setAttribute('aria-expanded', 'false');
      } else {
        item.classList.add('active');
        button.setAttribute('aria-expanded', 'true');
      }
    });
  });

  // --------------------------------------------------------------------------
  // 3. Обработка отправки формы записи (152-ФЗ compliant)
  // --------------------------------------------------------------------------
  const bookingForm = document.getElementById('mainBookingForm');
  const formSuccess = document.getElementById('formSuccess');

  if (bookingForm) {
    bookingForm.addEventListener('submit', (e) => {
      e.preventDefault();

      const nameInput = document.getElementById('clientName');
      const contactInput = document.getElementById('clientContact');
      const topicSelect = document.getElementById('clientTopic');
      const formatRadio = document.querySelector('input[name="format"]:checked');

      // Простая валидация
      if (!nameInput.value.trim() || !contactInput.value.trim()) {
        alert('Пожалуйста, заполните обязательные поля: имя и контакт для связи.');
        return;
      }

      // Визуальный отклик отправки
      const submitBtn = bookingForm.querySelector('button[type="submit"]');
      const originalBtnText = submitBtn.textContent;
      submitBtn.disabled = true;
      submitBtn.textContent = 'Отправка...';

      // Эмуляция защищенной отправки (в продакшене здесь отправка в Telegram-бот или на email)
      setTimeout(() => {
        submitBtn.style.display = 'none';
        
        // Скрываем поля формы и показываем сообщение об успехе
        bookingForm.querySelectorAll('.form-group, .form-checkbox, .form-disclaimer').forEach(el => {
          el.style.display = 'none';
        });

        if (formSuccess) {
          formSuccess.style.display = 'block';
        }

        console.log('Данные заявки получены:', {
          name: nameInput.value.trim(),
          contact: contactInput.value.trim(),
          topic: topicSelect ? topicSelect.value : '',
          format: formatRadio ? formatRadio.value : 'online',
          timestamp: new Date().toISOString()
        });
      }, 700);
    });
  }

  // --------------------------------------------------------------------------
  // 4. Плавный скролл для якорных ссылок шапки
  // --------------------------------------------------------------------------
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      const targetId = this.getAttribute('href');
      if (targetId === '#' || targetId.startsWith('#policy')) return;
      
      const targetElement = document.querySelector(targetId);
      if (targetElement) {
        e.preventDefault();
        targetElement.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
      }
    });
  });
});

