"""
sketch_polish.py
Turns a Sketch2UI import (plain wireframe-level pages) into a presentable website.

Sketch2UI renders each sketched screen as a narrow phone column with no branding, and only
index.html reached Restruct Warp, so links to other screens went nowhere. Here every screen
becomes a <section data-screen="file.html"> in ONE page with a tiny router, then:
  1. "ai"    - Groq redesigns it (hero, layout, imagery) under strict keep-everything rules;
               the result is checked and thrown away if any screen, link, field or label went missing.
  2. "theme" - no LLM: a fixed design layer (brand bar, screen tabs, hero, wider layout, real images).
Sketch2UI's runtime script (toasts, tabs, form submit) is kept as-is and hooked to the router.
"""
import re
from html import escape, unescape
from urllib.parse import quote

from app.config import settings
from app.services.grok_service import _async_call, extract_code_block

TAILWIND_HEAD = """<meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script>tailwind.config = { theme: { extend: { fontFamily: { sans: ["Plus Jakarta Sans", "ui-sans-serif", "system-ui", "sans-serif"] } } } };</script>"""

# Shows one screen at a time; Sketch2UI's runtime calls window.__sketch2uiGo after a form submit
ROUTER = """<script>
// Restruct Warp: one page, one <section data-screen> per sketched screen
(() => {
  const screens = [...document.querySelectorAll("[data-screen]")];
  const show = (file, push) => {
    const target = screens.find((s) => s.dataset.screen === file) || screens[0];
    screens.forEach((s) => (s.hidden = s !== target));
    document.querySelectorAll("[data-screen-link]").forEach((a) => {
      const on = a.dataset.screenLink === target.dataset.screen;
      a.setAttribute("aria-current", on ? "page" : "false");
    });
    if (push) history.pushState(null, "", "#" + target.dataset.screen);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  window.__sketch2uiGo = (href) => show(href.replace(/^#/, ""), true);
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[href]");
    if (!a) return;
    const file = a.getAttribute("href").replace(/^#/, "");
    if (screens.some((s) => s.dataset.screen === file)) { e.preventDefault(); show(file, true); }
  });
  addEventListener("popstate", () => show(location.hash.slice(1), false));
  show(location.hash.slice(1), false);
})();
</script>"""

POLISH_SYSTEM = """You are a senior product designer and frontend engineer.
You receive the screens of an app that a student drew by hand and Sketch2UI turned into plain,
wireframe-level HTML. Redesign it into a polished, presentable, modern website that looks like a
real funded product - while keeping the sketch's content and behaviour EXACTLY.

HARD RULES (the output is machine-checked; breaking one throws your work away):
- Keep every <section data-screen="..."> wrapper, same data-screen values, same order. One screen per section.
- Keep every element from the input: all headings, texts, button/link labels (same words), inputs,
  textareas, selects, checkboxes, images, lists, tables, charts.
- Keep every href, id, name, type, placeholder, aria-*, role, data-* attribute value unchanged.
  Links stay <a href="...">, buttons stay <button> with their type and data-* attributes, forms stay <form>.
- Do not add <script> tags and do not add href links to pages that do not exist.
- Use Tailwind CSS utility classes only (Tailwind CDN is loaded); no <style> blocks needed.

DESIGN (make it impressive):
- Desktop-first responsive layout that also works on phones (sm:, md:, lg: breakpoints). Use the full
  width: max-w-6xl containers, two-column hero layouts (copy left, visual right) where it fits,
  grids for cards/lists, a centered elevated card for login/sign-up forms next to a brand panel.
- Each screen fills at least the viewport (min-h-[80vh]) - never a small band over empty space. After
  the screen's own content, add 1-2 short supporting sections that fit it (feature highlights, stats,
  how-it-works steps, testimonials) so the page feels complete.
- A sticky brand bar with screen tabs and a footer are added around your sections - do not add your own.
- Each screen opens with a striking hero/header band: gradient background (indigo/violet/fuchsia or a
  palette matching the content), large bold headline (text-4xl md:text-6xl, tracking-tight), soft
  decorative blurred gradient blobs (absolute, pointer-events-none, -z-10).
- You MAY add decoration and supporting copy that fits the app's purpose: a short tagline under the
  main heading, feature highlights, stats, trust badges, icons as inline SVG. Keep it relevant and brief.
- Images already point at real URLs; keep their src and alt, size and frame them nicely.
- Polished components: rounded-2xl cards with subtle ring + shadow, hover lift transitions, inputs with
  focus rings, primary buttons with gradient fill, secondary buttons outlined, generous spacing.
- Accessible: real contrast, visible focus states, labels kept.

OUTPUT: ONLY the redesigned screens - the <section data-screen> elements one after another.
No <html>, <head>, <body>, markdown fences or explanations."""


# ─── Reading Sketch2UI pages ─────────────────────────────────────────────────

def _between(html: str, tag: str) -> str:
    m = re.search(rf"<{tag}\b[^>]*>(.*)</{tag}>", html, re.S | re.I)
    return m.group(1).strip() if m else ""


def page_title(html: str, fallback: str) -> str:
    return unescape(_between(html, "title")) or fallback


def runtime_script(html: str) -> str:
    """Sketch2UI's toast/tab/submit runtime: everything after </main> up to </body>."""
    m = re.search(r"</main>(.*?)</body>", html, re.S | re.I)
    return m.group(1).strip() if m else ""


def ordered_pages(index_html: str, pages: dict[str, str] | None) -> dict[str, str]:
    """index.html first, then the other screens in the order Sketch2UI drew them."""
    out = {"index.html": index_html}
    for name, html in (pages or {}).items():
        if name != "index.html" and re.fullmatch(r"[a-z0-9-]+\.html", name):
            out[name] = html
    return out


def screens_markup(pages: dict[str, str], app_name: str) -> str:
    """Every screen's <main> in a <section data-screen>, with placeholder images already swapped."""
    return "\n".join(f'<section data-screen="{name}">\n{_restyle_images(_between(html, "main"), app_name)}\n</section>'
                     for name, html in pages.items())


# ─── What a redesign must keep ───────────────────────────────────────────────

_ATTRS = ("href", "name", "data-toast", "data-next")


def _labels(markup: str) -> set[str]:
    """Visible words of headings, buttons and links: the sketch's content."""
    out = set()
    for m in re.finditer(r"<(h[1-6]|button|a)\b[^>]*>(.*?)</\1>", markup, re.S | re.I):
        text = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip().lower()
        if text:
            out.add(text)
    return out


def must_keep(markup: str) -> dict[str, set[str]]:
    keep = {a: set(re.findall(rf'\b{a}="([^"]*)"', markup)) for a in _ATTRS}
    keep["data-screen"] = set(re.findall(r'data-screen="([^"]*)"', markup))
    keep["labels"] = _labels(markup)
    return keep


def missing(original: str, redesigned: str) -> list[str]:
    """What the redesign dropped; empty means it is safe to use."""
    before, after = must_keep(original), must_keep(redesigned)
    lost = [f"{k}={v}" for k in before if k != "labels" for v in sorted(before[k] - after[k])]
    text = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", redesigned))).lower()
    lost += [f"label={t}" for t in sorted(before["labels"]) if t not in text]
    if re.search(r"<script\b", redesigned, re.I):
        lost.append("added a <script>")
    return lost


# ─── Theme (no LLM) ──────────────────────────────────────────────────────────

def pollinations(description: str, w: int, h: int) -> str:
    prompt = quote(f"{description}, modern clean product photography, soft light")
    return f"https://image.pollinations.ai/prompt/{prompt}?width={w}&height={h}&nologo=true"


def _brand_mark(name: str) -> str:
    initial = escape((name.strip() or "S")[0].upper())
    return ('<span class="inline-flex items-center gap-2 font-extrabold tracking-tight text-slate-900">'
            '<span class="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-indigo-500 '
            f'to-fuchsia-500 text-white shadow-lg shadow-indigo-500/30">{initial}</span>{escape(name)}</span>')


def _restyle_images(markup: str, app_name: str) -> str:
    def swap(m):
        tag = m.group(0)
        src = re.search(r'src="([^"]*)"', tag)
        alt = (re.search(r'alt="([^"]*)"', tag) or [None, ""])[1]
        if src and src.group(1).startswith("http"):
            return tag
        if "logo" in alt.lower():
            return _brand_mark(app_name)
        thumb = re.search(r'class="[^"]*\b(?:h|w)-(?:8|10|12|14|16|20|24)\b', tag)
        url = pollinations(unescape(alt) or f"{app_name} app", *((200, 200) if thumb else (1200, 600)))
        return re.sub(r'src="[^"]*"', f'src="{escape(url)}" loading="lazy"', tag) if src else tag
    return re.sub(r"<img\b[^>]*>", swap, markup)


def _restyle(markup: str) -> str:
    """Wider, richer versions of Sketch2UI's default classes."""
    swaps = [
        ("bg-indigo-600 text-white hover:bg-indigo-500",
         "bg-gradient-to-r from-indigo-600 to-fuchsia-600 text-white shadow-lg shadow-indigo-500/30 hover:brightness-110"),
        ("rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-900/5 transition hover:shadow-md",
         "rounded-3xl bg-white/90 p-6 shadow-xl shadow-slate-900/5 ring-1 ring-slate-900/5 backdrop-blur "
         "transition duration-300 hover:-translate-y-1 hover:shadow-2xl"),
        ("rounded-2xl bg-white/80 px-4 py-3 shadow-sm ring-1 ring-slate-900/5 backdrop-blur",
         "rounded-2xl bg-white/70 px-5 py-3 shadow-sm ring-1 ring-slate-900/5 backdrop-blur"),
        ("font-semibold tracking-tight text-slate-900 text-3xl",
         "font-extrabold tracking-tight text-4xl md:text-5xl bg-gradient-to-r from-slate-900 via-indigo-800 "
         "to-fuchsia-700 bg-clip-text text-transparent"),
        ("rounded-xl border-0 bg-white px-4 py-2.5", "rounded-xl border-0 bg-slate-50/80 px-4 py-3"),
    ]
    for old, new in swaps:
        markup = markup.replace(old, new)
    return markup


def theme_screen(name: str, title: str, main_html: str, app_name: str, first: bool) -> str:
    body = _restyle(_restyle_images(main_html, app_name))
    has_form = "<form" in body
    width = "max-w-md" if has_form and body.count("<section") < 2 else "max-w-4xl"
    kicker = "Welcome" if first else "Screen"
    return f"""<section data-screen="{name}">
  <div class="relative overflow-hidden">
    <div class="pointer-events-none absolute -top-24 left-1/2 -z-10 h-80 w-[44rem] -translate-x-1/2 rounded-full bg-gradient-to-r from-indigo-300/50 via-fuchsia-300/40 to-sky-300/50 blur-3xl"></div>
    <header class="mx-auto max-w-4xl px-5 pb-6 pt-14 text-center">
      <p class="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-600">{kicker} · {escape(app_name)}</p>
      <p class="mt-2 text-sm text-slate-500">{escape(title)}</p>
    </header>
  </div>
  <div class="mx-auto flex {width} flex-col gap-6 px-5 pb-16">
{body}
  </div>
</section>"""


def theme_site(app_name: str, pages: dict[str, str]) -> str:
    titles = {n: page_title(h, n) for n, h in pages.items()}
    return shell(app_name, titles, "\n".join(theme_screen(n, titles[n], _between(h, "main"), app_name, i == 0)
                                             for i, (n, h) in enumerate(pages.items())))


def shell(app_name: str, titles: dict[str, str], sections: str) -> str:
    """Sticky brand bar with one tab per screen, the screens, a footer."""
    tabs = "".join(
        f'<a href="{n}" data-screen-link="{n}" class="rounded-full px-3 py-1.5 text-sm font-medium text-slate-600 '
        f'transition hover:bg-slate-900/5 aria-[current=page]:bg-slate-900 aria-[current=page]:text-white">'
        f'{escape(t)}</a>' for n, t in titles.items()) if len(titles) > 1 else ""
    return f"""<div class="sticky top-0 z-40 border-b border-slate-900/5 bg-white/70 backdrop-blur-xl">
  <div class="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-3">
    {_brand_mark(app_name)}
    <nav aria-label="Screens" class="flex flex-wrap gap-1">{tabs}</nav>
  </div>
</div>
{sections}
<footer class="border-t border-slate-900/5 py-8 text-center text-xs text-slate-500">
  {escape(app_name)} · drawn by hand, built with Sketch2UI + Restruct Warp
</footer>"""


# ─── Assembling the page ─────────────────────────────────────────────────────

def wrap(app_name: str, body: str, runtime: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  {TAILWIND_HEAD}
  <title>{escape(app_name)}</title>
</head>
<body class="min-h-screen bg-slate-50 font-sans text-slate-900 antialiased selection:bg-indigo-200">
{body}
{runtime}
{ROUTER}
</body>
</html>
"""


async def ai_screens(markup: str, app_name: str) -> str:
    content = await _async_call(
        model=settings.POLISH_MODEL,
        messages=[
            {"role": "system", "content": POLISH_SYSTEM},
            {"role": "user", "content": f"App name: {app_name}\n\nSCREENS:\n{markup}"},
        ],
        temperature=0.4,
        max_tokens=16000,
    )
    out = extract_code_block(content or "")
    start = out.find("<section")
    return out[start:] if start >= 0 else ""


async def polish(app_name: str, index_html: str, pages: dict[str, str] | None = None,
                 mode: str = "ai") -> tuple[str, str]:
    """(html, mode used). mode: "ai" (falls back to "theme"), "theme" or "none"."""
    if mode == "none":
        return index_html, "none"
    ordered = ordered_pages(index_html, pages)
    runtime = runtime_script(index_html)
    if mode == "ai":
        markup = screens_markup(ordered, app_name)
        try:
            redesigned = await ai_screens(markup, app_name)
            lost = missing(markup, redesigned) if redesigned else ["empty reply"]
            if not lost:
                titles = {n: page_title(h, n) for n, h in ordered.items()}
                return wrap(app_name, shell(app_name, titles, redesigned), runtime), "ai"
            print(f"[sketch_polish] AI redesign dropped {lost[:5]}, using theme")
        except Exception as e:
            print(f"[sketch_polish] AI redesign failed ({e}), using theme")
    return wrap(app_name, theme_site(app_name, ordered), runtime), "theme"
