"""Статические проверки лендинга: разметка, юридические блоки, доступность, CSS.

Запуск:  python -m unittest discover -s tests -v
"""
import json
import os
import re
import shutil
import subprocess
import unittest
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as fh:
        return fh.read()


INDEX = read("index.html")
APP = read("app.js")
CSS = read("styles.css")
PRIVACY = read("privacy.html") if os.path.exists(os.path.join(ROOT, "privacy.html")) else ""


# --------------------------------------------------------------------------
# Утилиты
# --------------------------------------------------------------------------
def css_var(name):
    match = re.search(r"--%s:\s*(#[0-9A-Fa-f]{6})" % re.escape(name), CSS)
    return match.group(1) if match else None


def _srgb(channel):
    c = channel / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color):
    value = hex_color.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _srgb(r) + 0.7152 * _srgb(g) + 0.0722 * _srgb(b)


def contrast(fg, bg):
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def parse(html):
    parser = _MetaParser()
    parser.feed(html)
    return parser.tags


# --------------------------------------------------------------------------
# 1. Заявки: доставка, ссылки, консент
# --------------------------------------------------------------------------
class TestLeadDelivery(unittest.TestCase):
    def test_every_telegram_link_is_prefilled(self):
        links = re.findall(r'href="(https://t\.me/[^"]*)"', INDEX)
        self.assertTrue(links, "не найдено ни одной ссылки Telegram")
        self.assertGreaterEqual(len(links), 5, "ссылок Telegram должно быть не меньше пяти")
        for link in links:
            self.assertIn("?text=", link, f"ссылка без префилла сообщения: {link[:80]}")

    def test_no_dead_policy_anchor(self):
        self.assertNotIn('href="#policy"', INDEX)
        self.assertNotIn("open-policy-modal", INDEX)

    def test_form_posts_and_does_not_leak_to_url(self):
        form = re.search(r'<form[^>]*id="mainBookingForm"[^>]*>', INDEX).group(0)
        self.assertIn('method="post"', form)

    def test_consent_checkbox_is_submitted(self):
        self.assertIn('name="consent"', INDEX)
        self.assertIn('id="clientConsent"', INDEX)
        self.assertIn('required aria-required="true"', INDEX)
        self.assertIn("отозвать", INDEX.lower())

    def test_form_has_no_console_log_of_personal_data(self):
        for line in APP.splitlines():
            if "console.log" in line or "console.warn" in line:
                self.assertNotIn("data.name", line)
                self.assertNotIn("data.contact", line)
                self.assertNotIn("contact:", line)

    def test_success_is_honest(self):
        self.assertNotIn("Заявка успешно отправлена", INDEX)
        self.assertNotIn("защищённому каналу (SSL)", INDEX)
        self.assertIn("formSuccess", INDEX)
        self.assertIn('role="status"', INDEX)
        self.assertIn('aria-live="polite"', INDEX)

    def test_analytics_goal_fires_after_delivery(self):
        self.assertIn("function showSuccess", APP)
        body = APP.split("function showSuccess", 1)[1].split("function showFailure", 1)[0]
        self.assertIn("track('form_submit'", body)

    def test_telegram_opens_without_leaving_page(self):
        """window.open(..., 'noopener') возвращает null — страница уходила в Telegram."""
        self.assertNotIn("window.open(", APP, "window.open с noopener всегда даёт null")
        self.assertIn("link.target = '_blank'", APP)
        self.assertIn("link.rel = 'noopener noreferrer'", APP)

    def test_messenger_links_are_tracked(self):
        """Каждая ссылка в мессенджер должна нести цель, иначе клики не считаются."""
        for line in INDEX.splitlines():
            if 'href="https://t.me/' in line:
                self.assertIn('data-analytics-goal="telegram_click"', line, line.strip()[:90])
            if 'href="https://wa.me/' in line:
                self.assertIn('data-analytics-goal="whatsapp_click"', line, line.strip()[:90])

    def test_no_topic_passed_to_analytics(self):
        for call in re.findall(r"track\([^;]*\);", APP):
            self.assertNotIn("data.topic", call, f"тема обращения уходит в аналитику: {call[:60]}")


# --------------------------------------------------------------------------
# 2. Согласие и аналитика
# --------------------------------------------------------------------------
class TestConsent(unittest.TestCase):
    def test_counter_not_loaded_in_head(self):
        head = INDEX.split("</head>")[0]
        self.assertNotIn("mc.yandex.ru/metrika", head)
        self.assertNotIn("webvisor:true", head.replace(" ", ""))

    def test_webvisor_disabled(self):
        self.assertIn("webvisor: false", APP)

    def test_analytics_starts_only_after_consent(self):
        self.assertIn("startAnalytics()", APP)
        self.assertIn("stored === 'all'", APP)
        self.assertIn("if (choice === 'all') startAnalytics();", APP)

    def test_cookie_banner_present(self):
        self.assertIn('id="cookieBanner"', INDEX)
        self.assertIn('id="cookieAccept"', INDEX)
        self.assertIn('id="cookieDecline"', INDEX)
        self.assertIn("privacy.html", INDEX)


# --------------------------------------------------------------------------
# 3. Юридический контур
# --------------------------------------------------------------------------
class TestLegal(unittest.TestCase):
    def test_privacy_page_exists_and_complete(self):
        self.assertTrue(PRIVACY, "privacy.html отсутствует")
        for needle in [
            "152-ФЗ", "ИНН", "nazaretcev@mail.ru", "отзыв", "Отзыв",
            "cookie", "Метрика", "18 лет", "10 рабочих дней",
            "Роскомнадзор", "Трансграничная",
        ]:
            self.assertIn(needle, PRIVACY, f"в политике нет обязательного блока: {needle}")

    def test_index_links_to_privacy(self):
        self.assertIn('href="privacy.html"', INDEX)

    def test_no_special_category_option(self):
        select = re.search(r'<select id="clientTopic".*?</select>', INDEX, re.S).group(0)
        self.assertNotIn("ПРД", select)
        self.assertIn("Не хочу указывать", select)
        self.assertIn("не указывайте диагнозы", INDEX.lower())

    def test_requirements_in_footer(self):
        footer = INDEX.split("<footer", 1)[1]
        self.assertIn("ИНН", footer)
        self.assertIn("Оператор персональных данных", footer)
        self.assertIn("nazaretcev@mail.ru", footer)

    def test_cancellation_follows_consumer_law(self):
        self.assertNotIn("пропущенная сессия оплачивается", INDEX)
        self.assertIn("30%", INDEX)
        self.assertIn("Возврат", INDEX)


# --------------------------------------------------------------------------
# 4. Этика и тексты
# --------------------------------------------------------------------------
class TestEthics(unittest.TestCase):
    def test_no_etiologic_claim_about_infertility(self):
        self.assertNotIn("психологические причины невозможности иметь детей", INDEX)

    def test_no_promise_of_permanent_result(self):
        forbidden = ["на всю жизнь", "симптом уходит сам", "гарантия результата"]
        for phrase in forbidden:
            self.assertNotIn(phrase, INDEX, f"обещание результата: {phrase}")

    def test_single_professional_title(self):
        self.assertNotIn("Психоаналитический терапевт", INDEX)
        self.assertNotIn("клинической практики", INDEX)
        self.assertIn("Психоаналитический консультант", INDEX)

    def test_crisis_routing_present(self):
        self.assertIn("112", INDEX)
        self.assertIn("989-50-50", INDEX)
        self.assertIn("не оказываю экстренную помощь", INDEX)

    def test_session_length_consistent(self):
        self.assertNotIn("50 минут", INDEX)
        self.assertIn("45 минут", INDEX)

    def test_no_fake_reading_time(self):
        self.assertNotIn("Время чтения", INDEX)

    def test_price_without_from(self):
        self.assertNotIn("от 5 000", INDEX)
        self.assertIn("5 000 ₽", INDEX)


# --------------------------------------------------------------------------
# 5. SEO и метаданные
# --------------------------------------------------------------------------
class TestSeo(unittest.TestCase):
    def test_meta_set(self):
        tags = dict((t, a) for t, a in parse(INDEX) if t == "meta")
        raw = INDEX
        self.assertIn('rel="canonical"', raw)
        for prop in ["og:title", "og:description", "og:image", "og:url", "og:type"]:
            self.assertIn(f'property="{prop}"', raw, f"нет {prop}")
        self.assertIn('name="twitter:card"', raw)

    def test_json_ld_is_valid(self):
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', INDEX, re.S
        )
        self.assertTrue(blocks, "нет структурированных данных")
        for block in blocks:
            json.loads(block)

    def test_crawlable_files(self):
        for name in ["robots.txt", "sitemap.xml", "404.html", "favicon.ico"]:
            self.assertTrue(os.path.exists(os.path.join(ROOT, name)), f"нет {name}")
        self.assertIn("<urlset", read("sitemap.xml"))
        self.assertIn("Sitemap:", read("robots.txt"))

    def test_title_and_description(self):
        title = re.search(r"<title>(.*?)</title>", INDEX, re.S).group(1).strip()
        desc = re.search(r'name="description" content="(.*?)"', INDEX, re.S).group(1)
        self.assertLessEqual(len(title), 70, f"title слишком длинный: {len(title)}")
        self.assertIn("Психоаналитический консультант", title)
        self.assertLessEqual(len(desc), 180, f"description слишком длинный: {len(desc)}")

    def test_h1_contains_service(self):
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", INDEX, re.S).group(1)
        self.assertIn("Психоаналитическая консультация", h1)

    def test_single_h1(self):
        self.assertEqual(len(re.findall(r"<h1", INDEX)), 1)


# --------------------------------------------------------------------------
# 6. Изображения и производительность
# --------------------------------------------------------------------------
class TestPerformance(unittest.TestCase):
    def test_modern_image_variants(self):
        for name in ["hero-380.webp", "hero-760.webp", "hero-380.avif", "hero-760.avif"]:
            self.assertTrue(os.path.exists(os.path.join(ROOT, "images", name)), f"нет {name}")

    def test_picture_with_srcset_and_priority(self):
        self.assertIn("<picture>", INDEX)
        self.assertIn("images/hero-380.webp 380w", INDEX)
        self.assertIn('fetchpriority="high"', INDEX)
        self.assertIn('imagesrcset=', INDEX)
        self.assertIn('width="760"', INDEX)

    def test_hero_image_is_small(self):
        size = os.path.getsize(os.path.join(ROOT, "images", "hero-760.webp"))
        self.assertLess(size, 60 * 1024, f"hero-760.webp весит {size // 1024} КБ")

    def test_og_image_size(self):
        size = os.path.getsize(os.path.join(ROOT, "images", "og-image.jpg"))
        self.assertLess(size, 120 * 1024)

    def test_fonts_reduced_to_used_weights(self):
        links = re.findall(r'href="(https://fonts\.googleapis\.com[^"]*)"', INDEX)
        self.assertTrue(links)
        for link in links:
            self.assertNotIn("ital", link)
            self.assertNotIn("wght@0,500", link)

    def test_css_and_js_are_versioned(self):
        self.assertIn("styles.css?v=2", INDEX)
        self.assertIn("app.js?v=2", INDEX)


# --------------------------------------------------------------------------
# 7. Доступность
# --------------------------------------------------------------------------
class TestAccessibility(unittest.TestCase):
    def test_skip_link_and_main(self):
        self.assertIn('class="skip-link"', INDEX)
        self.assertIn('id="main"', INDEX)
        self.assertIn('tabindex="-1"', INDEX)

    def test_mobile_nav_is_accessible(self):
        self.assertIn('id="navToggle"', INDEX)
        self.assertIn('aria-controls="primaryNav"', INDEX)
        self.assertIn('aria-expanded="false"', INDEX)

    def test_modal_has_focus_trap_code(self):
        self.assertIn("function initModal", APP)
        self.assertIn("inert = true", APP)
        self.assertIn("lastFocused.focus()", APP)
        self.assertIn("aria-modal=\"true\"", INDEX)

    def test_faq_works_without_js(self):
        self.assertIn("<details", INDEX)
        self.assertEqual(INDEX.count("<details"), 5)
        self.assertNotIn('class="faq-button" aria-expanded', INDEX)

    def test_form_labels_and_input_types(self):
        for field in ['for="clientName"', 'for="clientContact"', 'for="clientTopic"']:
            self.assertIn(field, INDEX)
        self.assertIn('autocomplete="name"', INDEX)
        self.assertIn('autocomplete="tel"', INDEX)
        self.assertIn('inputmode="tel"', INDEX)
        self.assertIn("<fieldset", INDEX)
        self.assertIn("<legend", INDEX)

    def test_reduced_motion_and_print(self):
        self.assertIn("prefers-reduced-motion", CSS)
        self.assertIn("@media print", CSS)


# --------------------------------------------------------------------------
# 8. Цветовой контраст (WCAG 2.1 AA)
# --------------------------------------------------------------------------
class TestContrast(unittest.TestCase):
    def test_tertiary_text_on_surfaces(self):
        fg = css_var("text-tertiary")
        self.assertIsNotNone(fg)
        for bg_var in ["bg-page", "bg-surface-subtle", "bg-surface"]:
            ratio = contrast(fg, css_var(bg_var))
            self.assertGreaterEqual(ratio, 4.5, f"{fg} на {css_var(bg_var)} = {ratio:.2f}")

    def test_secondary_and_primary_text(self):
        for fg_var in ["text-secondary", "text-primary"]:
            ratio = contrast(css_var(fg_var), css_var("bg-page"))
            self.assertGreaterEqual(ratio, 4.5, f"{fg_var} = {ratio:.2f}")

    def test_primary_button(self):
        ratio = contrast("#FFFFFF", css_var("accent-sage"))
        self.assertGreaterEqual(ratio, 4.5, f"белый текст на sage = {ratio:.2f}")

    def test_input_border(self):
        ratio = contrast(css_var("border-input"), "#FFFFFF")
        self.assertGreaterEqual(ratio, 3.0, f"граница поля = {ratio:.2f}")

    def test_crisis_and_footer_notes(self):
        self.assertGreaterEqual(contrast("#4A3226", css_var("accent-amber-light")), 4.5)
        self.assertGreaterEqual(contrast("#C9CFCC", css_var("bg-dark")), 4.5)
        self.assertGreaterEqual(contrast("#DCE3DF", css_var("bg-dark")), 4.5)

    def test_nav_link_and_spec_label(self):
        self.assertGreaterEqual(contrast(css_var("text-secondary"), css_var("bg-page")), 4.5)


# --------------------------------------------------------------------------
# 9. Вёрстка: защита от возврата регрессий
# --------------------------------------------------------------------------
class TestLayoutGuards(unittest.TestCase):
    def test_no_overflow_hiding(self):
        body_rule = re.search(r"\nbody \{(.*?)\}", CSS, re.S).group(1)
        self.assertNotIn("overflow-x: hidden", body_rule)

    def test_buttons_can_wrap(self):
        btn_rule = re.search(r"\n\.btn \{(.*?)\}", CSS, re.S).group(1)
        self.assertIn("white-space: normal", btn_rule)

    def test_grids_use_min_100(self):
        self.assertNotIn("minmax(310px, 1fr)", CSS)
        self.assertIn("minmax(min(100%, 310px), 1fr)", CSS)

    def test_scroll_padding_for_anchor(self):
        self.assertIn("scroll-padding-top", CSS)

    def test_modal_can_receive_focus(self):
        """visibility нельзя анимировать: пока она hidden, фокус в диалог не встаёт."""
        rule = re.search(r"\.modal-overlay \{(.*?)\}", CSS, re.S).group(1)
        transition = re.search(r"transition:([^;]*);", rule)
        self.assertIsNotNone(transition)
        self.assertNotIn(
            "visibility", transition.group(1),
            "visibility в transition не даёт перевести фокус в открытый диалог",
        )

    def test_tap_targets(self):
        self.assertIn("min-height: 48px", CSS)
        self.assertRegex(CSS, r"\.nav-toggle \{[^}]*width: 48px")
        self.assertRegex(CSS, r"\.modal-close \{[^}]*width: 48px")


# --------------------------------------------------------------------------
# 10. Гигиена репозитория
# --------------------------------------------------------------------------
class TestSiteUrl(unittest.TestCase):
    """Единый базовый адрес: одна правка не должна расходиться по четырём файлам."""

    BASE = "https://deniskazakov1976-glitch.github.io/kazakova-psy"

    def test_no_stale_domain(self):
        for name in ("index.html", "privacy.html", "404.html", "sitemap.xml", "robots.txt"):
            content = read(name)
            self.assertNotIn(
                "https://kazakova-psy.ru", content, f"{name}: остался старый домен в URL"
            )

    def test_canonical_matches_og_url(self):
        canonical = re.search(r'rel="canonical" href="([^"]+)"', INDEX).group(1)
        og_url = re.search(r'property="og:url" content="([^"]+)"', INDEX).group(1)
        self.assertEqual(canonical, og_url)
        self.assertTrue(canonical.startswith(self.BASE), f"canonical мимо базового адреса: {canonical}")

    def test_og_image_is_absolute(self):
        image = re.search(r'property="og:image" content="([^"]+)"', INDEX).group(1)
        self.assertTrue(image.startswith(self.BASE), f"og:image не абсолютный: {image}")
        rest = image[len(self.BASE):]
        self.assertTrue(os.path.exists(os.path.join(ROOT, rest.lstrip("/"))), f"нет файла {rest}")

    def test_sitemap_and_robots_use_base(self):
        sitemap = read("sitemap.xml")
        for loc in re.findall(r"<loc>([^<]+)</loc>", sitemap):
            self.assertTrue(loc.startswith(self.BASE), f"sitemap: {loc}")
        robots = read("robots.txt")
        line = [ln for ln in robots.splitlines() if ln.startswith("Sitemap:")][0]
        self.assertTrue(line.split("Sitemap:")[1].strip().startswith(self.BASE))

    def test_privacy_canonical(self):
        privacy = read("privacy.html")
        canonical = re.search(r'rel="canonical" href="([^"]+)"', privacy).group(1)
        self.assertEqual(canonical, self.BASE + "/privacy.html")

    def test_assets_are_relative_for_subpath_hosting(self):
        """GitHub Pages отдаёт сайт из подпапки — пути от корня сломались бы."""
        for name in ("index.html", "privacy.html", "404.html"):
            content = read(name)
            self.assertNotRegex(
                content, r'(?:href|src)="/[^/]', f"{name}: путь от корня сайта"
            )


class TestRepoHygiene(unittest.TestCase):
    def test_js_syntax(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node недоступен")
        result = subprocess.run(
            [node, "--check", os.path.join(ROOT, "app.js")],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr[:800])

    def test_gitignore_hides_internal_docs(self):
        ignore = read(".gitignore")
        for name in ["TZ_v2.1.md", "ANALYTICS_SETUP.md", ".council/"]:
            self.assertIn(name, ignore)

    def test_internal_docs_not_tracked(self):
        try:
            tracked = subprocess.run(
                ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, timeout=20
            ).stdout
        except (OSError, subprocess.SubprocessError):
            self.skipTest("git недоступен")
        self.assertNotIn("TZ_v2.1.md", tracked)
        self.assertNotIn("ANALYTICS_SETUP.md", tracked)

    def test_no_secrets_in_repo(self):
        for name in ["index.html", "app.js"]:
            content = read(name)
            self.assertNotRegex(content, r"sk-or-v1-[A-Za-z0-9]{10,}")
            self.assertNotRegex(content, r"sk-[A-Za-z0-9]{32,}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
