import json

from django.test import TestCase
from pyblade_ui.themes import CUSTOM_MARKER, render_theme

from .models import SavedTheme
from .presets import PRESETS
from .themes import EditorTheme, valid_color


class EditorThemeTests(TestCase):
    def test_an_untouched_theme_exports_exactly_what_the_cli_writes(self):
        theme = EditorTheme.starting_point("zinc", "blue", "0.5rem")
        self.assertEqual(theme.stylesheet, render_theme("zinc", "blue", "0.5rem"))
        self.assertEqual(theme.command, "pyblade-ui theme set --base zinc --color blue --radius 0.5rem")

    def test_only_edited_variables_go_below_the_marker(self):
        theme = EditorTheme.starting_point("neutral", "neutral", "0.625rem")
        theme.light["primary"] = "#e11d48"
        theme.dark["background"] = "oklch(0.1 0 0)"
        custom = theme.stylesheet.split(CUSTOM_MARKER, 1)[1]
        self.assertIn(":root {\n  --primary: #e11d48;\n}", custom)
        self.assertIn(".dark {\n  --background: oklch(0.1 0 0);\n}", custom)
        self.assertNotIn("--foreground", custom)

    def test_payload_drops_unknown_variables_and_unsafe_values(self):
        theme = EditorTheme.from_payload({
            "base": "slate", "color": "rose", "radius": "9rem",
            "light": {"primary": "red; } body { display: none", "background": "#ffffff", "nope": "#000"},
        })
        self.assertEqual(theme.radius, "0.625rem")
        self.assertNotIn("body { display: none", theme.stylesheet)
        self.assertEqual(theme.light["primary"], EditorTheme.starting_point("slate", "rose", "").light["primary"])
        self.assertEqual(theme.light["background"], "#ffffff")
        self.assertNotIn("nope", theme.light)

    def test_color_validation(self):
        for ok in ["#fff", "oklch(0.5 0.2 240)", "hsl(262.1 83.3% 57.8%)", "oklch(1 0 0 / 10%)", "rebeccapurple"]:
            self.assertTrue(valid_color(ok), ok)
        for bad in ["red;", "}", "url(x)<", "a" * 81, ""]:
            self.assertFalse(valid_color(bad), bad)

    def test_every_preset_loads(self):
        for preset in PRESETS:
            theme = EditorTheme.from_preset(preset["id"])
            self.assertEqual(set(theme.light), set(theme.dark))
            for name, value in preset["light"].items():
                self.assertEqual(theme.light[name], value)

    def test_a_preset_carries_its_primary_into_the_sidebar(self):
        theme = EditorTheme.from_preset("ocean")
        self.assertEqual(theme.light["sidebar-primary"], theme.light["primary"])


class ShadowTests(TestCase):
    def test_default_shadow_adds_nothing_to_the_export(self):
        theme = EditorTheme.starting_point("zinc", "blue", "0.5rem")
        self.assertNotIn("--shadow-", theme.custom)

    def test_a_custom_shadow_goes_below_the_marker_with_its_settings(self):
        theme = EditorTheme.from_payload({"shadow": {"color": "#635bff", "opacity": 0.2, "blur": 6, "y": 2}})
        custom = theme.stylesheet.split(CUSTOM_MARKER, 1)[1]
        self.assertIn("--shadow-color: #635bff;", custom)
        self.assertIn("--shadow-blur: 6px;", custom)
        self.assertIn("--shadow-sm: 0 2px 6px 0 color-mix(in oklab, #635bff 20%, transparent)", custom)

    def test_shadow_settings_are_cleaned(self):
        theme = EditorTheme.from_payload({"shadow": {"color": "red; }", "opacity": 7, "blur": "x", "spread": -99}})
        self.assertEqual(theme.shadow["color"], "oklch(0 0 0)")
        self.assertEqual((theme.shadow["opacity"], theme.shadow["blur"], theme.shadow["spread"]), (1, 3, -20))

    def test_presets_bring_their_shadow(self):
        self.assertEqual(EditorTheme.from_preset("stripe").shadow["color"], "#32325d")
        self.assertIn("--shadow-lg:", EditorTheme.from_preset("neon").custom)


class PageAndApiTests(TestCase):
    def test_pages_render_every_component(self):
        for url, title in [("/", "Générateur de thèmes"), ("/en/", "Theme generator"), ("/?preset=forest", "Générateur")]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            html = response.content.decode()
            self.assertIn(title, html)
            self.assertNotIn("<pb-", html)
            self.assertNotIn("TemplateRenderError", html)

    def test_preset_endpoint(self):
        data = self.client.get("/api/preset?base=stone&color=green").json()
        self.assertEqual((data["base"], data["color"]), ("stone", "green"))
        self.assertIn("primary", data["light"])

    def test_export(self):
        payload = {"base": "gray", "color": "violet", "radius": "1rem", "light": {"primary": "#123456"}, "dark": {}}
        data = self.client.post("/api/export", json.dumps(payload), content_type="application/json").json()
        self.assertIn("--primary: #123456;", data["css"])
        self.assertEqual(data["command"], "pyblade-ui theme set --base gray --color violet --radius 1rem")

    def test_save_and_share(self):
        payload = {"name": "Mon thème", "theme": {"base": "slate", "color": "blue", "radius": "0.75rem", "light": {"primary": "#0ea5e9"}, "dark": {},
                                                  "shadow": {"color": "#0ea5e9", "opacity": 0.3, "blur": 8, "y": 4}}}
        response = self.client.post("/api/themes", json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        slug = response.json()["slug"]
        saved = SavedTheme.objects.get(slug=slug)
        self.assertEqual((saved.name, saved.base, saved.light["primary"]), ("Mon thème", "slate", "#0ea5e9"))

        page = self.client.get(f"/t/{slug}/").content.decode()
        self.assertIn("Mon thème", page)
        self.assertIn("#0ea5e9", page)
        css = self.client.get(f"/t/{slug}.css").content.decode()
        self.assertIn("--primary: #0ea5e9;", css.split(CUSTOM_MARKER, 1)[1])
        self.assertIn("--shadow-color: #0ea5e9;", css.split(CUSTOM_MARKER, 1)[1])
        self.assertEqual(self.client.get("/t/missing/").status_code, 404)

    def test_api_needs_the_csrf_token(self):
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        response = client.post("/api/themes", "{}", content_type="application/json")
        self.assertEqual(response.status_code, 403)


class WithoutDatabaseTests(TestCase):
    """On Vercel without DATABASE_URL, the editor works and saving is turned off cleanly."""

    def test_saving_is_off_without_a_database(self):
        from django.test import override_settings

        with override_settings(SHARING_ENABLED=False):
            html = self.client.get("/").content.decode()
            self.assertNotIn("dialog-open', 'save'", html)
            response = self.client.post("/api/themes", "{}", content_type="application/json")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(self.client.get("/t/anything/").status_code, 404)
            self.assertEqual(self.client.post("/api/export", "{}", content_type="application/json").status_code, 200)
