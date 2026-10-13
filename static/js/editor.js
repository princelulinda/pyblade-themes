/*
 * The theme editor's state, for Alpine: x-data="themeEditor(data)".
 * Edits are applied live by writing the variables into <style id="theme-live">; the final theme.css is
 * built by the server (/api/export), with the library's own render_theme.
 */
(() => {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 1;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });

  /** [r, g, b, a] (0-255) of any CSS color the browser knows, or null. */
  function rgba(color) {
    if (!color) return null;
    ctx.fillStyle = "#010203";
    ctx.fillStyle = color;
    if (ctx.fillStyle === "#010203" && color.trim().toLowerCase() !== "#010203") return null;
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillRect(0, 0, 1, 1);
    return Array.from(ctx.getImageData(0, 0, 1, 1).data);
  }

  const hex = (c) => {
    const v = rgba(c);
    return v ? "#" + v.slice(0, 3).map((n) => n.toString(16).padStart(2, "0")).join("") : "#000000";
  };

  function luminance(c) {
    const v = rgba(c);
    if (!v) return null;
    const ch = v.slice(0, 3).map((n) => {
      n /= 255;
      return n <= 0.04045 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
  }

  /** The WCAG contrast ratio of two colors, or null. */
  function contrast(a, b) {
    const la = luminance(a), lb = luminance(b);
    if (la === null || lb === null) return null;
    return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
  }

  /** :root and .dark variables of a stylesheet: { light: {}, dark: {}, radius }. shadcn's raw HSL channels get hsl(). */
  function parseTheme(css, tokens) {
    const out = { light: {}, dark: {}, radius: null, shadow: {} };
    const shadowVars = { "shadow-color": "color", "shadow-opacity": "opacity", "shadow-blur": "blur", "shadow-spread": "spread", "shadow-offset-x": "x", "shadow-offset-y": "y" };
    const blocks = [...css.matchAll(/(:root|\.dark)\s*\{([^}]*)\}/g)];
    for (const [, selector, body] of blocks) {
      const mode = selector === ":root" ? "light" : "dark";
      for (const [, name, raw] of body.matchAll(/--([\w-]+)\s*:\s*([^;]+);/g)) {
        let value = raw.trim();
        if (mode === "light" && shadowVars[name]) {
          const key = shadowVars[name];
          if (key === "color") { if (rgba(value)) out.shadow.color = value; }
          else if (!Number.isNaN(parseFloat(value))) out.shadow[key] = parseFloat(value);
          continue;
        }
        if (name === "radius") {
          if (/^\d*\.?\d+(rem)?$/.test(value)) out.radius = value === "0" ? "0" : value.endsWith("rem") ? value : value + "rem";
          continue;
        }
        if (!tokens.includes(name)) continue;
        if (/^-?\d*\.?\d+\s+\d*\.?\d+%\s+\d*\.?\d+%(\s*\/\s*[\d.%]+)?$/.test(value)) value = `hsl(${value})`;
        if (rgba(value)) out[mode][name] = value;
      }
    }
    return out;
  }

  // Each size, as layers relative to the base shadow (as pyblade_ui.themes.SHADOW_SCALE):
  // [offset factor, blur factor, spread added, opacity factor]
  const SCALE = {
    "shadow-2xs": [[1, 0, 0, 0.5]],
    "shadow-xs": [[1, 2 / 3, 0, 0.5]],
    "shadow-sm": [[1, 1, 0, 1], [1, 2 / 3, -1, 1]],
    "shadow-md": [[4, 2, -1, 1], [2, 4 / 3, -2, 1]],
    "shadow-lg": [[10, 5, -3, 1], [4, 2, -4, 1]],
    "shadow-xl": [[20, 25 / 3, -5, 1], [8, 10 / 3, -6, 1]],
    "shadow-2xl": [[25, 50 / 3, -12, 2.5]],
  };
  const px = (n) => {
    n = Math.round(n * 100) / 100;
    return n === 0 ? "0" : `${n}px`;
  };
  /** shadow-2xs ... shadow-2xl for a base shadow {color, opacity, blur, spread, x, y}. */
  function shadows(s) {
    const out = {};
    for (const [name, layers] of Object.entries(SCALE)) {
      out[name] = layers
        .map(([o, b, sp, a]) => {
          const alpha = Math.round(Math.min(Math.max(s.opacity * a, 0), 1) * 1000) / 10;
          return `${px(s.x * o)} ${px(s.y * o)} ${px(s.blur * b)} ${px(s.spread + sp)} color-mix(in oklab, ${s.color} ${alpha}%, transparent)`;
        })
        .join(", ");
    }
    return out;
  }

  /** A plain copy: structuredClone cannot copy Alpine's reactive proxies. */
  const clone = (o) => JSON.parse(JSON.stringify(o));

  const csrf = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || "";

  window.themeEditor = (data) => ({
    t: data.t,
    lang: data.lang,
    tokens: Object.keys(data.theme.light),
    pairs: data.pairs,
    presets: data.presets,
    theme: clone(data.theme),
    defaultShadow: data.default_shadow,
    start: clone(data.start),
    preset: data.preset,
    shared: data.shared,
    mode: document.documentElement.classList.contains("dark") ? "dark" : "light",
    past: [],
    future: [],
    last: "",
    timer: null,
    importText: "",
    importError: "",
    saveName: data.shared ? data.shared.name : "",
    exportCss: "",
    exportCommand: "",
    copied: "",
    busy: false,

    init() {
      this.paint();
      this.last = this.state();
      this.$watch("mode", (m) => {
        document.documentElement.classList.toggle("dark", m === "dark");
        try { localStorage.setItem("theme", m); } catch (e) {}
      });
      // the header's mode toggle changes the class: follow it
      new MutationObserver(() => {
        const m = document.documentElement.classList.contains("dark") ? "dark" : "light";
        if (m !== this.mode) this.mode = m;
      }).observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
      window.addEventListener("keydown", (e) => {
        if (!(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== "z" || e.target.closest("input, textarea")) return;
        e.preventDefault();
        e.shiftKey ? this.redo() : this.undo();
      });
    },

    // the live stylesheet
    css() {
      const block = (sel, values, extra = "") =>
        `${sel} {\n${extra}${this.tokens.map((k) => `  --${k}: ${values[k]};`).join("\n")}\n}`;
      const shadowLines = Object.entries(shadows(this.theme.shadow)).map(([k, v]) => `  --${k}: ${v};`).join("\n");
      const root = `  --radius: ${this.theme.radius === "0" ? "0rem" : this.theme.radius};\n${shadowLines}\n`;
      return block(":root", this.theme.light, root) + "\n" + block(".dark", this.theme.dark);
    },
    paint() {
      document.getElementById("theme-live").textContent = this.css();
    },

    // editing
    values() {
      return this.theme[this.mode];
    },
    set(name, value) {
      if (!rgba(value)) return false;
      this.theme[this.mode][name] = value.trim();
      this.changed();
      return true;
    },
    setRadius(value) {
      const n = Math.max(0, Math.min(1.5, parseFloat(value) || 0));
      this.theme.radius = n === 0 ? "0" : `${Math.round(n * 1000) / 1000}rem`;
      this.changed();
    },
    setShadow(key, value) {
      if (key === "color") {
        if (!rgba(value)) return false;
        this.theme.shadow.color = value.trim();
      } else {
        const [lo, hi] = { opacity: [0, 1], blur: [0, 50], spread: [-20, 20], x: [-20, 20], y: [-20, 20] }[key];
        this.theme.shadow[key] = Math.min(hi, Math.max(lo, parseFloat(value) || 0));
      }
      this.changed();
      return true;
    },
    resetShadow() {
      this.theme.shadow = clone(this.defaultShadow);
      this.changed();
    },
    shadowChanged() {
      return JSON.stringify(this.theme.shadow) !== JSON.stringify(this.defaultShadow);
    },
    radiusNumber() {
      return parseFloat(this.theme.radius) || 0;
    },
    modified(name) {
      return this.theme[this.mode][name] !== this.start[this.mode][name];
    },
    modifiedCount() {
      return ["light", "dark"].reduce((n, m) => n + this.tokens.filter((k) => this.theme[m][k] !== this.start[m][k]).length, 0);
    },
    changed() {
      this.paint();
      clearTimeout(this.timer);
      this.timer = setTimeout(() => this.remember(), 300);
    },

    // history
    state() {
      return JSON.stringify(this.theme);
    },
    remember() {
      const now = this.state();
      if (now === this.last) return;
      this.past.push(this.last);
      if (this.past.length > 100) this.past.shift();
      this.future = [];
      this.last = now;
    },
    undo() {
      if (!this.past.length) return;
      this.future.push(this.state());
      this.load(this.past.pop());
    },
    redo() {
      if (!this.future.length) return;
      this.past.push(this.state());
      this.load(this.future.pop());
    },
    load(json) {
      this.theme = JSON.parse(json);
      this.last = json;
      this.paint();
    },
    resetToStart() {
      this.theme.light = clone(this.start.light);
      this.theme.dark = clone(this.start.dark);
      this.changed();
    },

    // starting points
    async startFrom(base, color) {
      const res = await fetch(`/api/preset?base=${encodeURIComponent(base)}&color=${encodeURIComponent(color)}`);
      const values = await res.json();
      this.start = { light: values.light, dark: values.dark };
      Object.assign(this.theme, { base: values.base, color: values.color, light: clone(values.light), dark: clone(values.dark) });
      this.preset = "";
      this.changed();
    },
    async applyPreset(card) {
      const res = await fetch(`/api/preset?base=${card.theme.base}&color=${card.theme.color}`);
      const values = await res.json();
      this.start = { light: values.light, dark: values.dark };
      this.theme = clone(card.theme);
      this.preset = card.id;
      this.changed();
    },

    // colors
    hex,
    contrastOf(name) {
      const pair = this.pairs.find(([fg]) => fg === name);
      if (!pair) return null;
      return contrast(this.values()[pair[0]], this.values()[pair[1]]);
    },
    ratio(a, b) {
      return contrast(this.values()[a], this.values()[b]);
    },
    grade(r) {
      return r === null ? "" : r >= 7 ? "AAA" : r >= 4.5 ? "AA" : r >= 3 ? "AA L" : "✕"; // L: large text only (3:1)
    },
    gradeClass(r) {
      return r === null ? "" : r >= 4.5 ? "text-success" : r >= 3 ? "text-warning" : "text-destructive";
    },

    // import, export, save
    importTheme() {
      const parsed = parseTheme(this.importText, this.tokens);
      if (!Object.keys(parsed.light).length && !Object.keys(parsed.dark).length) {
        this.importError = this.t.import_empty;
        return;
      }
      Object.assign(this.theme.light, parsed.light);
      Object.assign(this.theme.dark, parsed.dark);
      if (parsed.radius) this.theme.radius = parsed.radius;
      if (Object.keys(parsed.shadow).length) this.theme.shadow = { ...this.theme.shadow, ...parsed.shadow };
      this.preset = "";
      this.importText = this.importError = "";
      this.changed();
      this.$dispatch("dialog-close", "import");
      toast({ title: this.t.imported, variant: "success" });
    },
    async post(url, body) {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(res.status);
      return res.json();
    },
    async openCode() {
      try {
        const out = await this.post("/api/export", this.theme);
        this.exportCss = out.css;
        this.exportCommand = out.command;
        this.$dispatch("dialog-open", "code");
      } catch (e) {
        toast({ title: this.t.error, variant: "destructive" });
      }
    },
    download() {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([this.exportCss], { type: "text/css" }));
      a.download = "theme.css";
      a.click();
      URL.revokeObjectURL(a.href);
    },
    async save() {
      this.busy = true;
      try {
        const out = await this.post("/api/themes", { name: this.saveName, theme: this.theme });
        this.shared = { slug: out.slug, name: this.saveName, url: out.url, css: out.css };
        history.replaceState(null, "", (this.lang === "en" ? "/en" : "") + out.url);
        toast({ title: this.t.saved, variant: "success" });
      } catch (e) {
        toast({ title: this.t.error, variant: "destructive" });
      } finally {
        this.busy = false;
      }
    },
    shareUrl() {
      return this.shared ? location.origin + (this.lang === "en" ? "/en" : "") + this.shared.url : "";
    },
    copy(text, key) {
      navigator.clipboard.writeText(text);
      this.copied = key;
      setTimeout(() => (this.copied = ""), 1500);
    },
  });
})();
