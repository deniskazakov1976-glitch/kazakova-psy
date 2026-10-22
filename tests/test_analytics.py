"""Проверка подключения Яндекс.Метрики: что реально уходит в счётчик и когда.

Запуск:  python -m unittest discover -s tests -v
Сеть намеренно заблокирована (`MAP * ~NOTFOUND`), чтобы тестовые визиты
не попадали в настоящий счётчик. tag.js не загружается, поэтому в `window.ym`
остаётся очередь — по ней видно, какие вызовы сайт отправляет.
"""
import json
import os
import re
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS = os.path.join(ROOT, "tests", "analytics.html")
COUNTER = "112744330"

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as fh:
        return fh.read()


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
                # Полный офлайн: настоящий tag.js не загрузится, счётчик не загрязнится
                '--host-resolver-rules=MAP * ~NOTFOUND',
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

    match = re.search(r'<pre id="out">(.*?)</pre>', result.stdout, re.S)
    if not match:
        raise AssertionError("нет блока результатов: " + result.stdout[:600])
    payload = (
        match.group(1)
        .replace("&quot;", '"')
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .strip()
    )
    if payload.startswith("REPORTERROR"):
        raise AssertionError("харнесс упал: " + payload[:900])
    if not payload.startswith("RESULT "):
        raise AssertionError("харнесс не завершил проверки: " + payload[:600])
    return json.loads(payload[len("RESULT "):])


class TestConsentGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = run_harness()

    def test_banner_shown_on_first_visit(self):
        self.assertTrue(self.data["before"]["bannerVisible"], "баннер согласия не показан")

    def test_nothing_loads_before_consent(self):
        before = self.data["before"]
        self.assertEqual(before["metrikaScripts"], 0, "tag.js загрузился до согласия")
        self.assertEqual(before["ymType"], "undefined", "window.ym создан до согласия")
        for src in before["allScripts"]:
            self.assertNotIn("mc.yandex.ru", src)
            self.assertNotIn("googletagmanager", src)

    def test_click_without_consent_sends_nothing(self):
        before = self.data["before"]
        self.assertEqual(before["ymAfterClick"], "undefined", "клик включил трекинг без согласия")
        self.assertEqual(before["scriptsAfterClick"], 0)


class TestCounter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = run_harness()

    def test_tag_loaded_with_right_counter(self):
        scripts = self.data["after"]["metrikaScripts"]
        self.assertEqual(len(scripts), 1, f"ожидался один тег Метрики, получено: {scripts}")
        self.assertIn(f"tag.js?id={COUNTER}", scripts[0])

    def test_init_params(self):
        params = self.data["after"]["initParams"]
        self.assertIsNotNone(params, "init не вызван")
        self.assertEqual(str(self.data["after"]["initCounter"]), COUNTER)
        self.assertIs(params["webvisor"], False, "Вебвизор должен быть выключен")
        self.assertIs(params["clickmap"], True, "карта кликов не включена")
        self.assertIs(params["trackLinks"], True, "внешние ссылки не учитываются")

    def test_banner_closes_and_choice_is_stored(self):
        after = self.data["after"]
        self.assertTrue(after["bannerHidden"], "баннер не закрылся после «Принять»")
        self.assertIn(after["consentStored"], ("all", "unavailable"))

    def test_decline_keeps_analytics_off(self):
        decline = self.data["decline"]
        self.assertEqual(decline["metrikaScripts"], 0, "аналитика включилась после отказа")
        self.assertEqual(decline["ymType"], "undefined")
        self.assertTrue(decline["bannerHidden"])

    def test_choice_persists_between_visits(self):
        persistence = self.data["persistence"]
        if not persistence.get("storageWorks"):
            self.skipTest("localStorage недоступен на file://")
        self.assertTrue(persistence["bannerHidden"], "баннер показан повторно при сохранённом согласии")
        self.assertEqual(persistence["ymType"], "function", "аналитика не стартовала из сохранённого согласия")
        self.assertEqual(persistence["scripts"], 1)


class TestGoals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = run_harness()
        cls.goals = {g["goal"]: g.get("params") or {} for g in cls.data["goals"]}

    def test_expected_goals_arrive(self):
        expected = ["telegram_click", "booking_click", "booking_modal_open", "form_submit"]
        for goal in expected:
            self.assertIn(goal, self.goals, f"цель не отправлена: {goal}. Пришло: {sorted(self.goals)}")

    def test_click_goals_carry_location(self):
        for goal in ("telegram_click", "booking_click"):
            self.assertIn("location", self.goals[goal], f"у цели {goal} нет параметра location")
            self.assertTrue(self.goals[goal]["location"], f"location у {goal} пустой")

    def test_form_submit_reports_method_not_pii(self):
        params = self.goals["form_submit"]
        self.assertEqual(params.get("method"), "telegram")
        serialized = self.data["goalsRaw"]
        self.assertNotIn("Секретное", serialized, "имя клиента попало в аналитику")
        self.assertNotIn("secret_login", serialized, "контакт клиента попал в аналитику")


class TestConfigConsistency(unittest.TestCase):
    def test_counter_matches_privacy_policy(self):
        index = read("index.html")
        privacy = read("privacy.html")
        match = re.search(r"ymId:\s*'(\d+)'", index)
        self.assertIsNotNone(match, "ymId не найден в конфиге")
        counter = match.group(1)
        self.assertIn(counter, privacy, "номер счётчика в политике не совпадает с конфигом")
        self.assertEqual(counter, COUNTER)

    def test_documented_goals_cover_code_goals(self):
        doc = read("ANALYTICS_SETUP.md")
        code = set(re.findall(r"track\('([a-z_]+)'", read("app.js")))
        code |= set(re.findall(r'data-analytics-goal="([a-z_]+)"', read("index.html")))
        self.assertTrue(code, "в коде не найдено ни одной цели")
        missing = sorted(g for g in code if g not in doc)
        self.assertFalse(missing, f"цели не описаны в ANALYTICS_SETUP.md: {missing}")

    def test_setup_guide_does_not_ask_for_webvisor(self):
        doc = read("ANALYTICS_SETUP.md")
        self.assertNotIn(
            "Вебвизор, карта скроллинга",
            doc,
            "инструкция требует включить Вебвизор, а политика обещает обратное",
        )

    def test_no_metrika_snippet_in_html(self):
        for name in ("index.html", "privacy.html", "404.html"):
            html = read(name)
            self.assertNotIn("ym(", html, f"{name}: счётчик вызывается напрямую")
            self.assertNotIn("mc.yandex.ru/metrika/tag.js", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
