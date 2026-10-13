"""Themes, from the PyBlade UI library itself: the CSS exported here is the CSS `pyblade-ui theme set` writes.

An edited theme is a starting point (a base, a color and a radius, which `pyblade-ui theme set` knows)
and every variable's value in light and dark mode. On export, the values that differ from the starting
point are written below the theme's custom marker: the part `pyblade-ui theme set` keeps when it
regenerates the file, so the edits survive.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pyblade_ui.themes import BASES, COLORS, DEFAULT_SHADOW, RADII, SHADOW_TOKENS, TOKENS, render_theme, shadows, tokens

from .presets import PRESETS, get_preset

DEFAULT = {"base": "neutral", "color": "neutral", "radius": "0.625rem"}
RADIUS = re.compile(r"^(0|\d(\.\d{1,3})?rem)$")
# A CSS color, and nothing that could close the declaration or the block it is written in
COLOR = re.compile(r"^[#a-zA-Z0-9.,%()/+\- ]{1,80}$")


def valid_color(value: str) -> bool:
    return bool(COLOR.match(value.strip()))


# The base shadow's settings: name -> (lowest, highest)
SHADOW_RANGES = {"opacity": (0, 1), "blur": (0, 50), "spread": (-20, 20), "x": (-20, 20), "y": (-20, 20)}
# How tweakcn names them, so a theme exported here can be imported back (there or here)
SHADOW_VARS = {"color": "shadow-color", "opacity": "shadow-opacity", "blur": "shadow-blur", "spread": "shadow-spread",
               "x": "shadow-offset-x", "y": "shadow-offset-y"}


def clean_shadow(value) -> dict:
    """A base shadow from untrusted input: a safe color and numbers within their range."""
    shadow = dict(DEFAULT_SHADOW)
    if not isinstance(value, dict):
        return shadow
    if isinstance(value.get("color"), str) and valid_color(value["color"]):
        shadow["color"] = value["color"].strip()
    for key, (low, high) in SHADOW_RANGES.items():
        try:
            shadow[key] = min(max(round(float(value.get(key, shadow[key])), 3), low), high)
        except (TypeError, ValueError):
            pass
    return shadow


def shadow_setting(key: str, value) -> str:
    if key == "color":
        return value
    return f"{float(value):g}" + ("" if key == "opacity" else "px")


def valid_radius(value: str) -> bool:
    return bool(RADIUS.match(value)) and float(value.removesuffix("rem") or 0) <= 2


@dataclass
class EditorTheme:
    base: str = DEFAULT["base"]
    color: str = DEFAULT["color"]
    radius: str = DEFAULT["radius"]
    light: dict = field(default_factory=dict)
    dark: dict = field(default_factory=dict)
    shadow: dict = field(default_factory=lambda: dict(DEFAULT_SHADOW))

    # Building one
    @classmethod
    def starting_point(cls, base: str, color: str, radius: str) -> "EditorTheme":
        base = base if base in BASES else DEFAULT["base"]
        color = color if color in COLORS else DEFAULT["color"]
        radius = radius if valid_radius(radius) else DEFAULT["radius"]
        light, dark = tokens(base, color)
        return cls(base, color, radius, dict(light), dict(dark), dict(DEFAULT_SHADOW))

    @classmethod
    def from_preset(cls, preset_id: str) -> "EditorTheme":
        preset = get_preset(preset_id)
        theme = cls.starting_point(preset["base"], preset["color"], preset["radius"])
        for mode in ("light", "dark"):
            values = dict(preset[mode])
            # the sidebar follows the preset's primary color unless the preset says otherwise
            for name in ("primary", "primary-foreground", "ring"):
                if name in values:
                    values.setdefault(f"sidebar-{name}", values[name])
            getattr(theme, mode).update(values)
        theme.shadow = clean_shadow({**DEFAULT_SHADOW, **preset.get("shadow", {})})
        return theme

    @classmethod
    def from_payload(cls, data: dict) -> "EditorTheme":
        """A theme sent by the editor. Unknown variables and unsafe values are dropped."""
        theme = cls.starting_point(str(data.get("base", "")), str(data.get("color", "")), str(data.get("radius", "")))
        for mode in ("light", "dark"):
            values = data.get(mode) or {}
            if isinstance(values, dict):
                for name in TOKENS:
                    value = values.get(name)
                    if isinstance(value, str) and valid_color(value):
                        getattr(theme, mode)[name] = value.strip()
        theme.shadow = clean_shadow(data.get("shadow"))
        return theme

    # What it exports
    def overrides(self) -> tuple[dict, dict]:
        """The variables whose value differs from the starting point, in light and dark mode."""
        light, dark = tokens(self.base, self.color)
        return (
            {k: v for k, v in self.light.items() if k in light and v != light[k]},
            {k: v for k, v in self.dark.items() if k in dark and v != dark[k]},
        )

    @property
    def custom_shadow(self) -> bool:
        return clean_shadow(self.shadow) != clean_shadow(DEFAULT_SHADOW)

    @property
    def custom(self) -> str:
        light, dark = self.overrides()
        blocks = []
        for selector, values in ((":root", light), (".dark", dark)):
            lines = [f"  --{name}: {values[name]};" for name in TOKENS if name in values]
            if selector == ":root" and self.custom_shadow:
                lines += [f"  --{var}: {shadow_setting(key, self.shadow[key])};" for key, var in SHADOW_VARS.items()]
                lines += [f"  --{name}: {value};" for name, value in shadows(self.shadow).items()]
            if lines:
                blocks.append(f"{selector} {{\n" + "\n".join(lines) + "\n}")
        return "\n\n".join(blocks)

    @property
    def stylesheet(self) -> str:
        return render_theme(self.base, self.color, self.radius, custom=self.custom)

    @property
    def command(self) -> str:
        return f"pyblade-ui theme set --base {self.base} --color {self.color} --radius {self.radius}"

    def as_dict(self) -> dict:
        return {"base": self.base, "color": self.color, "radius": self.radius, "light": self.light, "dark": self.dark,
                "shadow": self.shadow}


def preset_values(base: str, color: str) -> dict:
    """The library's own values for a base and a color, for the editor's quick pickers."""
    theme = EditorTheme.starting_point(base, color, DEFAULT["radius"])
    return {"base": theme.base, "color": theme.color, "light": theme.light, "dark": theme.dark}


def swatches():
    """What the pickers show: each base by its mid gray, each color by its primary, each preset by its colors."""
    bases = [{"value": name, "swatch": shades[500]} for name, shades in BASES.items()]
    colors = [
        {"value": name, "swatch": accent.light if accent else BASES["neutral"][900]}
        for name, accent in COLORS.items()
    ]
    radii = [{"value": r, "label": r.replace("rem", "") or "0"} for r in RADII]
    return bases, colors, radii


def preset_cards(lang: str) -> list[dict]:
    cards = []
    for preset in PRESETS:
        theme = EditorTheme.from_preset(preset["id"])
        cards.append({
            "id": preset["id"],
            "name": preset["name"][lang],
            "swatches": [theme.light[k] for k in ("background", "primary", "secondary", "accent")],
            "dark_swatches": [theme.dark[k] for k in ("background", "primary", "secondary", "accent")],
            "theme": theme.as_dict(),
        })
    return cards
