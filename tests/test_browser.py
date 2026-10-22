"""Проверки в реальном движке: геометрия, меню, модалка, форма.

Запуск:  python -m unittest discover -s tests -v
Требует Edge/Chrome. Если браузер не найден — тесты пропускаются.
"""
import json
import os
import re
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS = os.path.join(ROOT, "tests", "harness.html")

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_browser():
    for path in BROWSERS:
        if os.path.exists(path):
            return path
    return None


def run_harness():
    browser = find_browser()
    if not browser:
        raise unittest.SkipTest("не найден Edge/Chrome")
    url = "file:///" + HARNESS.replace("\\", "/")
    try:
        result = subprocess.run(
            [
                browser,
                "--headless=new",
                "--disable-gpu",
                "--allow-file-access-from-files",
                "--hide-scrollbars",
                "--virtual-time-budget=20000",
                "--dump-dom",
                url,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=240,
        )
    except subprocess.TimeoutExpired:
        raise AssertionError("браузер не ответил за 240 секунд")

    dom = result.stdout
    match = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
    if not match:
        raise AssertionError("не найден блок результатов в DOM: " + dom[:600])
    payload = match.group(1)
    payload = (
        payload.replace("&quot;", '"')
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )
    payload = payload.strip()
    if payload.startswith("REPORTERROR"):
        raise AssertionError("харнесс упал: " + payload[:800])
    if not payload.startswith("RESULT "):
        raise AssertionError("харнесс не завершил проверки: " + payload[:600])
    return json.loads(payload[len("RESULT "):])


class TestGeometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = run_harness()

    def test_no_horizontal_overflow_at_any_width(self):
        for width, metrics in self.data["widths"].items():
            self.assertLessEqual(
                metrics["scrollWidth"],
                metrics["clientWidth"] + 1,
                f"на {width}px контент шире экрана: "
                f"scrollWidth={metrics['scrollWidth']} clientWidth={metrics['clientWidth']}",
            )

    def test_body_does_not_hide_overflow(self):
        for width, metrics in self.data["widths"].items():
            self.assertNotEqual(
                metrics["bodyOverflowX"], "hidden",
                f"на {width}px overflow-x спрятан — обрезка станет недостижимой",
            )

    def test_header_cta_inside_viewport_on_mobile(self):
        for width in ("320", "360", "375", "390"):
            metrics = self.data["widths"][width]
            self.assertIsNotNone(metrics["headerCtaRight"])
            self.assertLessEqual(
                metrics["headerCtaRight"], metrics["clientWidth"] + 1,
                f"на {width}px кнопка в шапке выходит за край",
            )

    def test_cta_visible_above_fold_on_phone(self):
        metrics = self.data["widths"]["390"]
        self.assertIsNotNone(metrics["ctaTop"])
        self.assertLess(
            metrics["ctaTop"], 700,
            f"главный CTA начинается на {metrics['ctaTop']}px — ниже первого экрана",
        )

    def test_cta_visible_above_fold_on_small_phone(self):
        metrics = self.data["widths"]["375"]
        self.assertLess(metrics["ctaTop"], 700, f"CTA на {metrics['ctaTop']}px при высоте экрана 667px")

    def test_cookie_banner_does_not_cover_cta(self):
        """Баннер согласия всплывает сразу и не должен закрывать главную кнопку."""
        for width, metrics in self.data["widths"].items():
            if metrics["bannerTop"] is None:
                continue
            self.assertLessEqual(
                metrics["bannerTop"], metrics["clientHeight"] + 1,
                f"на {width}px баннер ниже экрана",
            )
            overlap = metrics["ctaBottom"] - metrics["bannerTop"]
            self.assertLessEqual(
                overlap, 0,
                f"на {width}px баннер перекрывает CTA на {overlap}px",
            )

    def test_cookie_banner_buttons_are_tappable(self):
        metrics = self.data["widths"]["390"]
        self.assertIsNotNone(metrics["bannerHeight"])
        self.assertLess(metrics["bannerHeight"], 170, "баннер занимает слишком много экрана")

    def test_mobile_nav_has_burger(self):
        for width in ("320", "375", "414"):
            metrics = self.data["widths"][width]
            self.assertNotEqual(metrics["toggleDisplay"], "none", f"на {width}px нет кнопки меню")
            self.assertEqual(metrics["toggleSize"], [48, 48], f"на {width}px тач-таргет меню {metrics['toggleSize']}")

    def test_desktop_nav_is_visible(self):
        for width in ("1024", "1440"):
            metrics = self.data["widths"][width]
            self.assertEqual(metrics["toggleDisplay"], "none", f"на {width}px бургер не нужен")
            self.assertNotEqual(metrics["navDisplay"], "none", f"на {width}px навигация скрыта")

    def test_tap_targets(self):
        metrics = self.data["widths"]["390"]
        self.assertGreaterEqual(metrics["ctaHeight"], 48, f"CTA {metrics['ctaHeight']}px")
        self.assertGreaterEqual(metrics["headerCtaSize"][1], 48, f"шапка {metrics['headerCtaSize']}")


class TestInteractions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = run_harness()["interactions"]

    def test_burger_opens_and_closes(self):
        self.assertEqual(self.data["navBefore"], "none")
        self.assertNotEqual(self.data["navAfterClick"], "none")
        self.assertEqual(self.data["navAriaAfterClick"], "true")
        self.assertEqual(self.data["navAfterClose"], "none")

    def test_modal_traps_focus(self):
        self.assertTrue(self.data["modalOpen"], "модалка не открылась")
        self.assertTrue(self.data["modalFocusInside"], "фокус остался вне диалога")
        self.assertTrue(self.data["backgroundInert"], "фон не заблокирован для фокуса")
        self.assertTrue(self.data["bodyLocked"], "страница прокручивается под модалкой")

    def test_modal_returns_focus(self):
        self.assertTrue(self.data["modalClosed"], "Esc не закрыл модалку")
        self.assertTrue(self.data["focusReturned"], "фокус не вернулся на кнопку-триггер")
        self.assertTrue(self.data["backgroundRestored"], "inert не снят после закрытия")

    def test_form_requires_consent(self):
        self.assertTrue(self.data["consentErrorShown"], "форма отправилась без согласия")
        self.assertTrue(self.data["successHiddenOnInvalid"], "показан успех при ошибке")

    def test_form_delivers_via_telegram(self):
        url = self.data.get("openedUrl") or ""
        self.assertIn("t.me/", url)
        self.assertIn("?text=", url, "Telegram открыт без текста заявки")
        self.assertIn("%D0%97%D0%B4", url)  # «Зд»
        self.assertTrue(self.data["successShown"], "успех не показан после доставки")
        self.assertIn("Telegram", self.data["statusText"])

    def test_faq_works_without_js(self):
        self.assertEqual(self.data["detailsCount"], 5)
        self.assertTrue(self.data["faqWithoutJs"])

    def test_skip_link_and_close_button_size(self):
        self.assertTrue(self.data["skipLink"])
        self.assertGreaterEqual(min(self.data["modalCloseSize"]), 48, "крестик меньше 48px")


if __name__ == "__main__":
    unittest.main(verbosity=2)
