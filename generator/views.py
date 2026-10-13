import json

from django.conf import settings

from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .i18n import CONTRAST_PAIRS, GROUPS, TEXT, preview_data
from .models import SavedTheme
from .presets import PRESETS
from pyblade_ui.themes import DEFAULT_SHADOW

from .themes import EditorTheme, preset_cards, preset_values, swatches


def editor_page(request, lang, theme, preset="", shared=None):
    bases, colors, radii = swatches()
    t = TEXT[lang]
    data = {
        "theme": theme.as_dict(),
        "start": preset_values(theme.base, theme.color),
        "preset": preset,
        "presets": preset_cards(lang),
        "bases": bases,
        "colors": colors,
        "radii": radii,
        "groups": GROUPS[lang],
        "pairs": CONTRAST_PAIRS,
        "shared": shared,
        "default_shadow": DEFAULT_SHADOW,
        "sharing": settings.SHARING_ENABLED,
        "lang": lang,
        "t": t["js"],
    }
    context = {
        "t": t,
        "data": data,
        "bases": bases,
        "colors": colors,
        "presets": data["presets"],
        "groups": GROUPS[lang],
        "home": "/" if lang == "fr" else "/en/",
        "other_lang": {"label": "EN", "href": "/en/"} if lang == "fr" else {"label": "FR", "href": "/"},
        **preview_data(lang),
    }
    # Django's own engine comes first in TEMPLATES and only serves the admin
    return render(request, "editor.html", context, using="pyblade")


@ensure_csrf_cookie
def editor(request, lang="fr"):
    """The editor, starting from ?preset=ocean, or from ?base=…&color=…&radius=… (links from the first version)."""
    preset = request.GET.get("preset", "")
    if preset or "base" not in request.GET:
        preset = preset if any(p["id"] == preset for p in PRESETS) else "default"
        theme = EditorTheme.from_preset(preset)
    else:
        theme = EditorTheme.starting_point(request.GET.get("base", ""), request.GET.get("color", ""), request.GET.get("radius", ""))
    return editor_page(request, lang, theme, preset=preset)


@ensure_csrf_cookie
def shared(request, slug, lang="fr"):
    if not settings.SHARING_ENABLED:
        raise Http404
    saved = get_object_or_404(SavedTheme, slug=slug)
    info = {"slug": saved.slug, "name": saved.name, "url": saved.get_absolute_url(), "css": f"/t/{saved.slug}.css"}
    return editor_page(request, lang, saved.theme, shared=info)


def shared_css(request, slug):
    """A saved theme's theme.css: what a future `pyblade-ui theme add <url>` would fetch."""
    if not settings.SHARING_ENABLED:
        raise Http404
    saved = get_object_or_404(SavedTheme, slug=slug)
    return HttpResponse(saved.theme.stylesheet, content_type="text/css; charset=utf-8")


@require_GET
def api_preset(request):
    """The library's values for a base and a color: /api/preset?base=zinc&color=blue."""
    return JsonResponse(preset_values(request.GET.get("base", ""), request.GET.get("color", "")))


def _payload(request) -> dict:
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


@require_POST
def api_export(request):
    """The theme.css and the command for the theme being edited."""
    theme = EditorTheme.from_payload(_payload(request))
    return JsonResponse({"css": theme.stylesheet, "command": theme.command})


@require_POST
def api_save(request):
    """Saves the theme being edited and returns its short link."""
    if not settings.SHARING_ENABLED:
        return JsonResponse({"error": "Saving is not available here: no database is configured."}, status=503)
    data = _payload(request)
    theme = EditorTheme.from_payload(data.get("theme") or {})
    name = str(data.get("name", ""))[:60].strip()
    saved = SavedTheme.objects.create(name=name, **theme.as_dict())
    return JsonResponse({"slug": saved.slug, "url": saved.get_absolute_url(), "css": f"/t/{saved.slug}.css"}, status=201)


def stylesheet(request):
    """The theme.css of a base, color and radius (links from the first version): /theme/full.css?base=…"""
    theme = EditorTheme.starting_point(request.GET.get("base", ""), request.GET.get("color", ""), request.GET.get("radius", ""))
    response = HttpResponse(theme.stylesheet, content_type="text/css; charset=utf-8")
    if request.GET.get("download"):
        response["Content-Disposition"] = 'attachment; filename="theme.css"'
    return response
