/**
 * Евгения Казакова — психоаналитический консультант.
 * Интерактивность: меню, модальное окно записи, форма заявки, cookie-согласие.
 * Без зависимостей. Всё, что не критично для чтения страницы, вынесено за DOMContentLoaded.
 */
(function () {
  'use strict';

  var CONFIG = window.ANALYTICS_CONFIG || {};
  var CONSENT_KEY = 'kazakova_consent_v1';
  var TELEGRAM = CONFIG.telegram || 'KazakovaEvgeniya';

  /* ---------------------------------------------------------------------
   * Аналитика: подключается ТОЛЬКО после согласия на cookie.
   * ------------------------------------------------------------------- */
  var analyticsReady = false;

  function initMetrika(id) {
    if (!id || window.__ymLoaded) return;
    window.__ymLoaded = true;
    (function (m, e, t, r, i, k, a) {
      m[i] = m[i] || function () { (m[i].a = m[i].a || []).push(arguments); };
      m[i].l = 1 * new Date();
      for (var j = 0; j < document.scripts.length; j++) {
        if (document.scripts[j].src === r) { return; }
      }
      k = e.createElement(t);
      a = e.getElementsByTagName(t)[0];
      k.async = 1;
      k.src = r;
      a.parentNode.insertBefore(k, a);
    })(window, document, 'script', 'https://mc.yandex.ru/metrika/tag.js?id=' + id, 'ym');

    window.ym(id, 'init', {
      ssr: true,
      webvisor: false,      // Вебвизор записывал бы ввод в поле контакта
      clickmap: true,
      ecommerce: 'dataLayer',
      referrer: document.referrer,
      url: location.href,
      accurateTrackBounce: true,
      trackLinks: true
    });
  }

  function initGA4(id) {
    if (!id || !id.startsWith('G-')) return;
    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + id;
    document.head.appendChild(s);
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag('js', new Date());
    window.gtag('config', id);
  }

  function initVK(id) {
    if (!id || !id.startsWith('VK-')) return;
    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://vk.com/js/api/openapi.js?169';
    s.onload = function () {
      if (window.VK && window.VK.Retargeting) {
        window.VK.Retargeting.Init(id);
        window.VK.Retargeting.Hit();
      }
    };
    document.head.appendChild(s);
  }

  function startAnalytics() {
    if (analyticsReady) return;
    analyticsReady = true;
    initMetrika(CONFIG.ymId);
    initGA4(CONFIG.ga4Id);
    initVK(CONFIG.vkPixelId);
    if (CONFIG.debug) {
      console.log('[Аналитика] Включена после согласия. Счётчик:', CONFIG.ymId || '—');
    }
  }

  /** Цели: только обезличенные события. Значения формы сюда не попадают. */
  function track(goal, params) {
    if (!analyticsReady) {
      if (CONFIG.debug) console.log('[Аналитика] Событие без согласия (не отправлено):', goal, params || {});
      return;
    }
    try {
      if (CONFIG.debug) console.log('[Аналитика] Цель:', goal, params || {});
      if (CONFIG.ymId && typeof window.ym === 'function') window.ym(CONFIG.ymId, 'reachGoal', goal, params);
      if (typeof window.gtag === 'function') window.gtag('event', goal, params || {});
    } catch (err) {
      if (CONFIG.debug) console.warn('[Аналитика] Ошибка отправки цели:', goal, err);
    }
  }

  /* ---------------------------------------------------------------------
   * Cookie-баннер
   * ------------------------------------------------------------------- */
  function initConsent() {
    var banner = document.getElementById('cookieBanner');
    var stored = null;
    try { stored = localStorage.getItem(CONSENT_KEY); } catch (e) { stored = null; }

    if (stored === 'all') {
      startAnalytics();
      return;
    }
    if (!banner) return;

    banner.hidden = false;
    document.body.classList.add('cookie-open');

    function decide(choice) {
      try { localStorage.setItem(CONSENT_KEY, choice); } catch (e) { /* приватный режим */ }
      banner.hidden = true;
      document.body.classList.remove('cookie-open');
      if (choice === 'all') startAnalytics();
      track('cookie_consent', { value: choice });
    }

    var accept = document.getElementById('cookieAccept');
    var decline = document.getElementById('cookieDecline');
    if (accept) accept.addEventListener('click', function () { decide('all'); });
    if (decline) decline.addEventListener('click', function () { decide('necessary'); });
  }

  /* ---------------------------------------------------------------------
   * Мобильное меню
   * ------------------------------------------------------------------- */
  function initNav() {
    var toggle = document.getElementById('navToggle');
    var nav = document.getElementById('primaryNav');
    if (!toggle || !nav) return;

    function setOpen(open) {
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      toggle.setAttribute('aria-label', open ? 'Закрыть меню' : 'Открыть меню');
      nav.classList.toggle('nav--open', open);
      document.body.classList.toggle('nav-open', open);
    }

    toggle.addEventListener('click', function () {
      setOpen(toggle.getAttribute('aria-expanded') !== 'true');
    });

    nav.addEventListener('click', function (event) {
      if (event.target.closest('a')) setOpen(false);
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') {
        setOpen(false);
        toggle.focus();
      }
    });

    window.addEventListener('resize', function () {
      if (window.innerWidth > 860 && toggle.getAttribute('aria-expanded') === 'true') setOpen(false);
    });
  }

  /* ---------------------------------------------------------------------
   * Модальное окно записи: ловушка фокуса, возврат фокуса, inert на фоне
   * ------------------------------------------------------------------- */
  var FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function initModal() {
    var modal = document.getElementById('bookingModal');
    if (!modal) return;
    var openers = document.querySelectorAll('.open-booking-modal');
    var closeBtn = document.getElementById('closeBookingModal');
    var lastFocused = null;
    var background = null;

    function backgroundEls() {
      return Array.prototype.filter.call(document.body.children, function (el) {
        return el !== modal && el.tagName !== 'SCRIPT' && el.tagName !== 'LINK';
      });
    }

    function open() {
      lastFocused = document.activeElement;
      background = backgroundEls().map(function (el) {
        var prev = el.inert;
        el.inert = true;
        return { el: el, prev: prev };
      });
      // Баннер согласия не должен оказаться под inert-ом навсегда
      modal.classList.add('active');
      document.body.classList.add('modal-open');
      // Фокус ставим синхронно на карточку: она существует всегда, даже пока
      // идёт transition видимости. Переход к первому контролу сделает Tab.
      var card = modal.querySelector('.modal-card');
      if (card) card.focus();
      track('booking_modal_open');
    }

    function close() {
      modal.classList.remove('active');
      document.body.classList.remove('modal-open');
      if (background) {
        background.forEach(function (item) { item.el.inert = item.prev || false; });
        background = null;
      }
      if (lastFocused && typeof lastFocused.focus === 'function') lastFocused.focus();
      lastFocused = null;
    }

    openers.forEach(function (btn) {
      btn.addEventListener('click', function (event) {
        event.preventDefault();
        open();
      });
    });

    if (closeBtn) closeBtn.addEventListener('click', close);

    // «Перейти к форме заявки» внутри диалога
    var toForm = modal.querySelector('.scrollToFormBtn');
    if (toForm) {
      toForm.addEventListener('click', function () {
        close();
        var target = document.getElementById('contact');
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        var nameField = document.getElementById('clientName');
        if (nameField) {
          setTimeout(function () { nameField.focus({ preventScroll: true }); }, 400);
        }
      });
    }

    modal.addEventListener('click', function (event) {
      if (event.target === modal) close();
    });

    document.addEventListener('keydown', function (event) {
      if (!modal.classList.contains('active')) return;
      if (event.key === 'Escape') {
        close();
        return;
      }
      if (event.key !== 'Tab') return;
      var items = Array.prototype.filter.call(modal.querySelectorAll(FOCUSABLE), function (el) {
        return el.offsetParent !== null;
      });
      if (!items.length) return;
      var first = items[0];
      var last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });
  }

  /* ---------------------------------------------------------------------
   * Форма заявки: реальная доставка
   *   1. есть formEndpoint  -> POST JSON, успех только по response.ok
   *   2. нет formEndpoint   -> открываем Telegram с готовым текстом
   * ------------------------------------------------------------------- */
  function initForm() {
    var form = document.getElementById('mainBookingForm');
    if (!form) return;

    var nameInput = document.getElementById('clientName');
    var contactInput = document.getElementById('clientContact');
    var topicSelect = document.getElementById('clientTopic');
    var consent = document.getElementById('clientConsent');
    var submitBtn = document.getElementById('submitBtn');
    var status = document.getElementById('formStatus');
    var success = document.getElementById('formSuccess');
    var consentError = document.getElementById('consentError');

    var TOPIC_LABELS = {
      relationships: 'отношения, расставание, семья',
      anxiety: 'тревога, страх, истощение',
      motherhood: 'материнство, беременность, репродуктивные вопросы',
      patterns: 'повторяющиеся сценарии',
      crisis: 'кризис смыслов, самооценка',
      other: 'другое'
    };

    function setStatus(message, tone) {
      if (!status) return;
      status.textContent = message || '';
      status.className = 'form-status' + (tone ? ' form-status--' + tone : '');
    }

    function setFieldError(input, hasError) {
      if (!input) return;
      input.classList.toggle('is-invalid', !!hasError);
      input.setAttribute('aria-invalid', hasError ? 'true' : 'false');
    }

    function readForm() {
      var formatInput = form.querySelector('input[name="format"]:checked');
      return {
        name: (nameInput && nameInput.value || '').trim(),
        contact: (contactInput && contactInput.value || '').trim(),
        topic: (topicSelect && topicSelect.value) || '',
        format: formatInput ? formatInput.value : 'online'
      };
    }

    function buildMessage(data) {
      var formatText = data.format === 'offline' ? 'очно в Перми' : 'онлайн';
      var lines = [
        'Здравствуйте, Евгения Викторовна!',
        'Меня зовут ' + data.name + '. Хочу записаться на установочную встречу (' + formatText + ', 45 минут).',
        'Контакт для связи: ' + data.contact
      ];
      if (data.topic && TOPIC_LABELS[data.topic]) {
        lines.push('Тема обращения: ' + TOPIC_LABELS[data.topic] + '.');
      }
      lines.push('Спасибо!');
      return lines.join('\n');
    }

    function showSuccess(mode) {
      if (success) {
        success.hidden = false;
        success.focus();
      }
      form.classList.add('is-sent');
      setStatus(
        mode === 'telegram'
          ? 'Открыл Telegram с готовым сообщением. Осталось нажать «Отправить» — и я отвечу.'
          : 'Заявка доставлена.',
        'success'
      );
      track('form_submit', { method: mode });
    }

    function showFailure(reason) {
      if (!status) return;
      status.className = 'form-status form-status--error';
      status.textContent = reason + ' Напишите, пожалуйста, в Telegram: ';
      var link = document.createElement('a');
      link.href = 'https://t.me/' + TELEGRAM;
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = '@' + TELEGRAM;
      status.appendChild(link);
      status.appendChild(document.createTextNode(' — это займёт полминуты.'));
    }

    function validate(data) {
      var ok = true;
      if (!data.name) { setFieldError(nameInput, true); ok = false; } else { setFieldError(nameInput, false); }
      if (!data.contact) { setFieldError(contactInput, true); ok = false; } else { setFieldError(contactInput, false); }
      if (consent && !consent.checked) {
        if (consentError) consentError.hidden = false;
        ok = false;
      } else if (consentError) {
        consentError.hidden = true;
      }
      if (!ok) {
        setStatus('Проверьте, пожалуйста, выделенные поля.', 'error');
        var firstBad = form.querySelector('.is-invalid') || (consent && !consent.checked ? consent : null);
        if (firstBad) firstBad.focus();
      }
      return ok;
    }

    function sendToEndpoint(data) {
      return fetch(CONFIG.formEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({
          name: data.name,
          contact: data.contact,
          topic: data.topic,
          format: data.format,
          page: location.pathname,
          sentAt: new Date().toISOString()
        })
      }).then(function (response) {
        if (!response.ok) throw new Error('HTTP ' + response.status);
        return true;
      });
    }

    function openTelegram(data) {
      var url = 'https://t.me/' + TELEGRAM + '?text=' + encodeURIComponent(buildMessage(data));
      // window.open(url, '_blank', 'noopener') всегда возвращает null (так работает
      // noopener), и старый код из-за этого уводил текущую вкладку в Telegram.
      // Клик по настоящей ссылке открывает новую вкладку и не теряет страницу.
      var link = document.createElement('a');
      link.href = url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.style.display = 'none';
      document.body.appendChild(link);
      link.click();
      link.remove();
      return true;
    }

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      var data = readForm();
      if (!validate(data)) return;

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Отправляю…';
      }
      setStatus('Отправляю заявку…');

      var delivery = CONFIG.formEndpoint
        ? sendToEndpoint(data).then(function () { return 'server'; })
        : Promise.resolve().then(function () { return openTelegram(data) ? 'telegram' : 'none'; });

      delivery
        .then(function (mode) {
          if (mode === 'none') throw new Error('Не удалось открыть Telegram');
          showSuccess(mode);
        })
        .catch(function (error) {
          if (CONFIG.debug) console.warn('[Форма] Ошибка доставки:', error);
          showFailure('Не получилось отправить заявку автоматически.');
        })
        .then(function () {
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Отправить заявку';
          }
        });
    });

    if (consent && consentError) {
      consent.addEventListener('change', function () {
        if (consent.checked) consentError.hidden = true;
      });
    }
  }

  /* ---------------------------------------------------------------------
   * Цели на клики по ссылкам
   * ------------------------------------------------------------------- */
  function initTracking() {
    document.addEventListener('click', function (event) {
      var target = event.target.closest('[data-analytics-goal]');
      if (!target) return;
      track(target.getAttribute('data-analytics-goal'), {
        location: target.getAttribute('data-analytics-location') || 'page'
      });
    });
  }

  /* ---------------------------------------------------------------------
   * Инициализация
   * ------------------------------------------------------------------- */
  document.addEventListener('DOMContentLoaded', function () {
    initConsent();
    initNav();
    initModal();
    initForm();
    initTracking();
  });

  // Экспорт для автотестов (в обычной работе страницы не используется)
  window.__kazakova = { track: track };
})();
