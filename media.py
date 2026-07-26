print("WINDOW RUNNIG.....")
import os, platform, shutil, subprocess, threading, time, webbrowser
from io import BytesIO
from urllib.request import urlopen, Request

import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image
import yt_dlp
print("WINDOW CREATED.....")
# ======================================================================
#  THEME
# ======================================================================

COLORS = {
    "bg": "#0F172A",
    "bg2": "#1E293B",
    "card": "#334155",
    "card_hover": "#3B4A63",
    "accent": "#3B82F6",
    "accent_hover": "#2563EB",
    "success": "#22C55E",
    "warning": "#FACC15",
    "error": "#EF4444",
    "text": "#F8FAFC",
    "text2": "#CBD5E1",
    "border": "#475569",
}

FONT_FAMILY = "Segoe UI"  # falls back gracefully on macOS/Linux to a system sans-serif

def F(size, weight="normal"):
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36"}
# NOTE ON QUALITY FIX:
# The "android" player client that YouTube serves only exposes a limited
# set of itags (it commonly tops out around 360p-720p and hides the
# separate high-resolution DASH video streams). To unlock 1080p/1440p/4K
# we must let yt-dlp query the "web" client first (full format list,
# including high-res video-only DASH streams), and keep "android"/"tv"
# only as fallbacks for when web is throttled or blocked.
YDL_BASE = {
    "quiet": True,
    "no_warnings": True,
    "extractor_args": {"youtube": {"player_client": ["web", "android", "tv"]}},
    "http_headers": UA,
}

# ======================================================================
#  APP STATE  (unchanged from the original — logic layer is untouched)
# ======================================================================

folder = os.getcwd()
info = None
cancel_evt = threading.Event()
downloading = False
thumb_img = None
history_items = []  # keep a data copy so we can filter/search/sort the history cards


def fmt_dur(s):
    if not s: return "Live/Unknown"
    s = int(s); h, r = divmod(s, 3600); m, sec = divmod(r, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def fmt_count(n):
    if not n: return "N/A"
    return f"{n/1_000_000:.1f}M" if n >= 1e6 else f"{n/1_000:.1f}K" if n >= 1e3 else str(n)


def fmt_bytes(n):
    if not n: return "N/A"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def has_ffmpeg():
    return shutil.which("ffmpeg") is not None


def heights_from(formats):
    hs = sorted({f.get("height") for f in formats if f.get("vcodec") != "none" and f.get("height")}, reverse=True)
    return [f"{h}p" for h in hs]


def ui(fn, *a, **kw):
    app.after(0, lambda: fn(*a, **kw))


# ======================================================================
#  SMALL REUSABLE UI COMPONENTS
# ======================================================================

class Card(ctk.CTkFrame):
    """A rounded elevated container used throughout the dashboard."""
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", COLORS["bg2"])
        kw.setdefault("corner_radius", 16)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", COLORS["border"])
        super().__init__(master, **kw)


class PrimaryButton(ctk.CTkButton):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", COLORS["accent"])
        kw.setdefault("hover_color", COLORS["accent_hover"])
        kw.setdefault("text_color", COLORS["text"])
        kw.setdefault("corner_radius", 12)
        kw.setdefault("height", 44)
        kw.setdefault("font", F(14, "bold"))
        super().__init__(master, **kw)


class SecondaryButton(ctk.CTkButton):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", COLORS["success"])
        kw.setdefault("hover_color", "#1DA750")
        kw.setdefault("text_color", "#04210C")
        kw.setdefault("corner_radius", 12)
        kw.setdefault("height", 44)
        kw.setdefault("font", F(14, "bold"))
        super().__init__(master, **kw)


class GhostButton(ctk.CTkButton):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", "transparent")
        kw.setdefault("hover_color", COLORS["card_hover"])
        kw.setdefault("text_color", COLORS["text2"])
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", COLORS["border"])
        kw.setdefault("corner_radius", 12)
        kw.setdefault("height", 40)
        kw.setdefault("font", F(13))
        super().__init__(master, **kw)


class DangerButton(ctk.CTkButton):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", COLORS["card"])
        kw.setdefault("hover_color", COLORS["error"])
        kw.setdefault("text_color", COLORS["text"])
        kw.setdefault("corner_radius", 12)
        kw.setdefault("height", 44)
        kw.setdefault("font", F(14, "bold"))
        super().__init__(master, **kw)


def fade_in(widget, steps=10, delay=15):
    """A lightweight fade-in simulated by animating a frame's height/alpha
    isn't natively supported by Tk, so we approximate with a quick
    scale/slide-in via padding — keeps things smooth without extra deps."""
    try:
        widget.configure(fg_color=COLORS["card_hover"])
        widget.after(120, lambda: widget.configure(fg_color=COLORS["bg2"]))
    except Exception:
        pass


def pulse(widget, on_color, off_color, times=3, delay=250):
    """Simple pulse animation for status indicators."""
    def step(n, state=True):
        if n <= 0:
            widget.configure(fg_color=off_color)
            return
        widget.configure(fg_color=on_color if state else off_color)
        widget.after(delay, lambda: step(n - 1, not state))
    step(times * 2)


# ======================================================================
#  MAIN WINDOW
# ======================================================================

app = ctk.CTk()
app.title("MediaHarbor Studio - Youtube Media Downloader")
app.geometry("1100x750")
app.minsize(1000, 700)
app.configure(fg_color=COLORS["bg"])

theme_mode = ctk.StringVar(value="dark")
active_page = ctk.StringVar(value="home")

# ---------- root layout: header (top) / body (sidebar + content) / status bar (bottom) ----------
app.grid_rowconfigure(1, weight=1)
app.grid_columnconfigure(0, weight=1)

# ======================================================================
#  HEADER
# ======================================================================

header = ctk.CTkFrame(app, fg_color=COLORS["bg2"], height=64, corner_radius=0)
header.grid(row=0, column=0, sticky="ew")
header.grid_propagate(False)
header.grid_columnconfigure(1, weight=1)

brand = ctk.CTkFrame(header, fg_color="transparent")
brand.grid(row=0, column=0, padx=20, pady=10, sticky="w")
ctk.CTkLabel(brand, text="🎬 MediaHarbor Studio", font=F(20, "bold"), text_color=COLORS["text"]).pack(anchor="w")
ctk.CTkLabel(brand, text="Download • Convert • Organize", font=F(11), text_color=COLORS["accent"]).pack(anchor="w")

header_actions = ctk.CTkFrame(header, fg_color="transparent")
header_actions.grid(row=0, column=2, padx=20, pady=10, sticky="e")


# def toggle_theme():
#     new_mode = "light" if theme_mode.get() == "dark" else "dark"
#     theme_mode.set(new_mode)
#     ctk.set_appearance_mode(new_mode)
#     theme_btn.configure(text="☀" if new_mode == "light" else "🌙")


# theme_btn = GhostButton(header_actions, text="🌙", width=40, command=toggle_theme)
# theme_btn.pack(side="left", padx=4)


def show_about():
    messagebox.showinfo(
        "About MediaHarbor Studio",
        "MediaHarbor Studio 1.0\nDownload • Convert • Organize\n\n"
        "Built with CustomTkinter, yt-dlp, Pillow, and ffmpeg."
    )


GhostButton(header_actions, text="⚙", width=40, command=lambda: select_page("settings")).pack(side="left", padx=4)
GhostButton(header_actions, text="ℹ", width=40, command=show_about).pack(side="left", padx=4)

# ======================================================================
#  BODY: SIDEBAR + CONTENT
# ======================================================================

body = ctk.CTkFrame(app, fg_color="transparent")
body.grid(row=1, column=0, sticky="nsew")
body.grid_columnconfigure(1, weight=1)
body.grid_rowconfigure(0, weight=1)

# ---------------- Sidebar ----------------
sidebar = ctk.CTkFrame(body, fg_color=COLORS["bg2"], width=200, corner_radius=0)
sidebar.grid(row=0, column=0, sticky="nsw")
sidebar.grid_propagate(False)

NAV_ITEMS = [
    ("home", "🏠  Home"),
    ("downloads", "⬇  Downloads"),
    ("history", "📜  History"),
    ("settings", "⚙️ Settings"),
    ("about", "ℹ  About"),
]
nav_buttons = {}


def select_page(page_id):
    active_page.set(page_id)
    for pid, btn in nav_buttons.items():
        if pid == page_id:
            btn.configure(fg_color=COLORS["accent"], text_color=COLORS["text"])
        else:
            btn.configure(fg_color="transparent", text_color=COLORS["text2"])
    for pid, frame in pages.items():
        if pid == page_id:
            frame.pack(fill="both", expand=True)
            fade_in(frame)
        else:
            frame.pack_forget()


ctk.CTkLabel(sidebar, text="NAVIGATION", font=F(10, "bold"), text_color=COLORS["text2"]).pack(anchor="w", padx=20, pady=(20, 8))
for pid, label in NAV_ITEMS:
    b = ctk.CTkButton(sidebar, text=label, anchor="w", corner_radius=10, height=40,
                       fg_color="transparent", hover_color=COLORS["card_hover"],
                       text_color=COLORS["text2"], font=F(13),
                       command=lambda p=pid: select_page(p))
    b.pack(fill="x", padx=12, pady=3)
    nav_buttons[pid] = b

sidebar_footer = ctk.CTkFrame(sidebar, fg_color="transparent")
sidebar_footer.pack(side="bottom", fill="x", padx=16, pady=16)
ctk.CTkLabel(sidebar_footer, text="ffmpeg: " + ("detected ✅" if has_ffmpeg() else "not found ⚠"),
             font=F(10), text_color=COLORS["text2"], wraplength=170, justify="left").pack(anchor="w")

# ---------------- Content area (each "page" is a frame; only Home is fully interactive,
# the rest are lightweight companion views built from the same underlying state) ----------------
content = ctk.CTkFrame(body, fg_color="transparent")
content.grid(row=0, column=1, sticky="nsew")
content.grid_rowconfigure(0, weight=1)
content.grid_columnconfigure(0, weight=1)

pages = {}

# ======================================================================
#  HOME PAGE
# ======================================================================

home_page = ctk.CTkScrollableFrame(content, fg_color="transparent")
pages["home"] = home_page

# ----- URL card -----
url_card = Card(home_page)
url_card.pack(fill="x", padx=24, pady=(20, 12))
url_card.grid_columnconfigure(0, weight=1)

ctk.CTkLabel(url_card, text="Add a link", font=F(14, "bold"), text_color=COLORS["text"]).grid(
    row=0, column=0, columnspan=4, sticky="w", padx=18, pady=(14, 6))

url_entry = ctk.CTkEntry(url_card, placeholder_text="Paste YouTube video or playlist URL...",
                          height=44, corner_radius=12, border_width=1, border_color=COLORS["border"],
                          fg_color=COLORS["bg"], font=F(13))
url_entry.grid(row=1, column=0, sticky="ew", padx=(18, 8), pady=(0, 16))


def paste_clip():
    try:
        url_entry.delete(0, "end"); url_entry.insert(0, app.clipboard_get())
    except Exception:
        pass


def clear_url():
    url_entry.delete(0, "end")


def copy_url():
    try:
        app.clipboard_clear(); app.clipboard_append(url_entry.get())
    except Exception:
        pass


GhostButton(url_card, text="📋 Paste", width=90, command=paste_clip).grid(row=1, column=1, padx=4, pady=(0, 16))
GhostButton(url_card, text="✕ Clear", width=90, command=clear_url).grid(row=1, column=2, padx=4, pady=(0, 16))
fetch_btn = PrimaryButton(url_card, text="🔍 Fetch", width=110, command=lambda: fetch_info())
fetch_btn.grid(row=1, column=3, padx=(4, 18), pady=(0, 16))

# ----- Thumbnail + options row -----
mid_row = ctk.CTkFrame(home_page, fg_color="transparent")
mid_row.pack(fill="x", padx=24, pady=8)
mid_row.grid_columnconfigure(0, weight=0)
mid_row.grid_columnconfigure(1, weight=1)

preview_card = Card(mid_row, width=340)
preview_card.grid(row=0, column=0, sticky="n", padx=(0, 16))
preview_card.grid_propagate(False)
preview_card.configure(width=340)

thumb_lbl = ctk.CTkLabel(preview_card, text="🖼\n\nPaste a link and hit Fetch\nto preview your video here",
                          width=308, height=173, fg_color=COLORS["card"], corner_radius=12,
                          text_color=COLORS["text2"], font=F(12), justify="center")
thumb_lbl.pack(padx=16, pady=16)

title_lbl = ctk.CTkLabel(preview_card, text="No video loaded", font=F(14, "bold"),
                          text_color=COLORS["text"], wraplength=300, justify="left", anchor="w")
title_lbl.pack(fill="x", padx=16)
channel_lbl = ctk.CTkLabel(preview_card, text="", font=F(12), text_color=COLORS["accent"], anchor="w")
channel_lbl.pack(fill="x", padx=16, pady=(2, 0))

meta_grid = ctk.CTkFrame(preview_card, fg_color="transparent")
meta_grid.pack(fill="x", padx=16, pady=(8, 16))
meta_labels = {}
for i, key in enumerate(["Duration", "Views", "Resolution", "Est. size"]):
    row = ctk.CTkFrame(meta_grid, fg_color="transparent")
    row.pack(fill="x", pady=1)
    ctk.CTkLabel(row, text=key, font=F(10), text_color=COLORS["text2"], width=80, anchor="w").pack(side="left")
    val = ctk.CTkLabel(row, text="—", font=F(10, "bold"), text_color=COLORS["text"], anchor="w")
    val.pack(side="left")
    meta_labels[key] = val

# ----- Options card -----
opts_card = Card(mid_row)
opts_card.grid(row=0, column=1, sticky="nsew")
opts_card.grid_columnconfigure(1, weight=1)

ctk.CTkLabel(opts_card, text="Download Options", font=F(14, "bold"), text_color=COLORS["text"]).grid(
    row=0, column=0, columnspan=2, sticky="w", padx=18, pady=(16, 10))


def opt_row(r, label):
    ctk.CTkLabel(opts_card, text=label, font=F(12), text_color=COLORS["text2"]).grid(
        row=r, column=0, sticky="w", padx=18, pady=8)


opt_row(1, "Video quality")
quality_var = ctk.StringVar(value="Best")
quality_menu = ctk.CTkOptionMenu(opts_card, values=["Best"], variable=quality_var,
                                  fg_color=COLORS["card"], button_color=COLORS["accent"],
                                  button_hover_color=COLORS["accent_hover"], corner_radius=10,
                                  font=F(12))
quality_menu.grid(row=1, column=1, sticky="ew", padx=(0, 18), pady=8)

opt_row(2, "Audio format")
audio_fmt_var = ctk.StringVar(value="MP3")
ctk.CTkOptionMenu(opts_card, values=["MP3", "M4A", "WAV"], variable=audio_fmt_var,
                   fg_color=COLORS["card"], button_color=COLORS["accent"],
                   button_hover_color=COLORS["accent_hover"], corner_radius=10, font=F(12)
                   ).grid(row=2, column=1, sticky="ew", padx=(0, 18), pady=8)

opt_row(3, "Whole playlist")
pl_switch = ctk.CTkSwitch(opts_card, text="", progress_color=COLORS["accent"], state="disabled")
pl_switch.grid(row=3, column=1, sticky="w", padx=(0, 18), pady=8)

opt_row(4, "Subtitles (.srt)")
subs_switch = ctk.CTkSwitch(opts_card, text="", progress_color=COLORS["accent"])
subs_switch.grid(row=4, column=1, sticky="w", padx=(0, 18), pady=8)

opt_row(5, "Embed thumbnail")
embed_switch = ctk.CTkSwitch(opts_card, text="", progress_color=COLORS["accent"])
embed_switch.select() if has_ffmpeg() else embed_switch.configure(state="disabled")
embed_switch.grid(row=5, column=1, sticky="w", padx=(0, 18), pady=8)

opt_row(6, "Auto-open folder")
autoopen_switch = ctk.CTkSwitch(opts_card, text="", progress_color=COLORS["accent"])
autoopen_switch.grid(row=6, column=1, sticky="w", padx=(0, 18), pady=8)

opt_row(7, "Save to")
frow = ctk.CTkFrame(opts_card, fg_color="transparent")
frow.grid(row=7, column=1, sticky="ew", padx=(0, 18), pady=(8, 18))
frow.grid_columnconfigure(0, weight=1)
folder_lbl = ctk.CTkLabel(frow, text=folder, text_color=COLORS["text2"], font=F(11), anchor="w")
folder_lbl.grid(row=0, column=0, sticky="ew")


def choose_folder():
    global folder
    f = filedialog.askdirectory()
    if f:
        folder = f
        folder_lbl.configure(text=folder)


GhostButton(frow, text="Change", width=70, height=28, command=choose_folder).grid(row=0, column=1, padx=(8, 0))

# ----- Action buttons -----
actions = ctk.CTkFrame(home_page, fg_color="transparent")
actions.pack(fill="x", padx=24, pady=(16, 8))
actions.grid_columnconfigure((0, 1, 2), weight=1)

video_btn = PrimaryButton(actions, text="⬇  Download Video", command=lambda: start_download("video"))
video_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))
audio_btn = SecondaryButton(actions, text="🎵  Download MP3", command=lambda: start_download("audio"))
audio_btn.grid(row=0, column=1, sticky="ew", padx=8)
cancel_btn = DangerButton(actions, text="⏹  Cancel", command=lambda: cancel_download(), state="disabled")
cancel_btn.grid(row=0, column=2, sticky="ew", padx=(8, 0))

# ----- Progress card -----
prog_card = Card(home_page)
prog_card.pack(fill="x", padx=24, pady=8)
prog_card.grid_columnconfigure(0, weight=1)

status_row = ctk.CTkFrame(prog_card, fg_color="transparent")
status_row.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 6))
status_row.grid_columnconfigure(1, weight=1)

status_dot = ctk.CTkLabel(status_row, text="●", font=F(14), text_color=COLORS["text2"], width=16)
status_dot.grid(row=0, column=0, sticky="w")
status_lbl = ctk.CTkLabel(status_row, text="Ready", font=F(13, "bold"), text_color=COLORS["text"], anchor="w")
status_lbl.grid(row=0, column=1, sticky="w", padx=(4, 0))
progress_pct_lbl = ctk.CTkLabel(status_row, text="", font=F(12, "bold"), text_color=COLORS["accent"])
progress_pct_lbl.grid(row=0, column=2, sticky="e")

progress_bar = ctk.CTkProgressBar(prog_card, progress_color=COLORS["accent"], fg_color=COLORS["card"], height=10, corner_radius=6)
progress_bar.set(0)
progress_bar.grid(row=1, column=0, sticky="ew", padx=18, pady=4)

stats_row = ctk.CTkFrame(prog_card, fg_color="transparent")
stats_row.grid(row=2, column=0, sticky="ew", padx=18, pady=(6, 16))
stats_labels = {}
for key in ["Speed", "ETA", "Downloaded", "File"]:
    box = ctk.CTkFrame(stats_row, fg_color="transparent")
    box.pack(side="left", padx=(0, 24))
    ctk.CTkLabel(box, text=key.upper(), font=F(9, "bold"), text_color=COLORS["text2"]).pack(anchor="w")
    v = ctk.CTkLabel(box, text="—", font=F(11), text_color=COLORS["text"])
    v.pack(anchor="w")
    stats_labels[key] = v

open_folder_btn = GhostButton(prog_card, text="📂 Open Download Folder", command=lambda: open_folder(), state="disabled")
open_folder_btn.grid(row=3, column=0, sticky="w", padx=18, pady=(0, 16))

# ----- History preview on Home -----
hist_header = ctk.CTkFrame(home_page, fg_color="transparent")
hist_header.pack(fill="x", padx=24, pady=(16, 6))
ctk.CTkLabel(hist_header, text="Recent Downloads", font=F(14, "bold"), text_color=COLORS["text"]).pack(side="left")
GhostButton(hist_header, text="View all →", width=100, height=30, command=lambda: select_page("history")).pack(side="right")

hist_list = ctk.CTkFrame(home_page, fg_color="transparent")
hist_list.pack(fill="x", padx=24, pady=(0, 24))

# ======================================================================
#  DOWNLOADS PAGE (queue/status companion view)
# ======================================================================

downloads_page = ctk.CTkScrollableFrame(content, fg_color="transparent")
pages["downloads"] = downloads_page
ctk.CTkLabel(downloads_page, text="Active & Recent Transfers", font=F(16, "bold"), text_color=COLORS["text"]).pack(
    anchor="w", padx=24, pady=(20, 10))
downloads_info_card = Card(downloads_page)
downloads_info_card.pack(fill="x", padx=24, pady=8)
ctk.CTkLabel(downloads_info_card,
             text="Start a download from Home — its live progress and every completed\n"
                  "transfer will also be tracked here.",
             font=F(12), text_color=COLORS["text2"], justify="left").pack(anchor="w", padx=18, pady=18)

# ======================================================================
#  HISTORY PAGE
# ======================================================================

history_page = ctk.CTkFrame(content, fg_color="transparent")
pages["history"] = history_page

hist_top = ctk.CTkFrame(history_page, fg_color="transparent")
hist_top.pack(fill="x", padx=24, pady=(20, 10))
ctk.CTkLabel(hist_top, text="Download History", font=F(16, "bold"), text_color=COLORS["text"]).pack(side="left")

hist_filter_var = ctk.StringVar(value="All")
hist_search_var = ctk.StringVar(value="")


def render_history():
    for w in hist_scroll.winfo_children():
        w.destroy()
    for w in hist_list.winfo_children():
        w.destroy()

    q = hist_search_var.get().lower().strip()
    f = hist_filter_var.get()
    filtered = [h for h in history_items
                if (f == "All" or h["type"] == f) and (q in h["title"].lower() if q else True)]
    filtered_sorted = sorted(filtered, key=lambda h: h["ts"], reverse=True)

    if not filtered_sorted:
        ctk.CTkLabel(hist_scroll, text="No downloads yet.", font=F(12), text_color=COLORS["text2"]).pack(pady=20)

    for h in filtered_sorted:
        _render_history_row(hist_scroll, h)
    for h in filtered_sorted[:5]:
        _render_history_row(hist_list, h)


def _render_history_row(parent, h):
    row = Card(parent, fg_color=COLORS["card"])
    row.pack(fill="x", pady=5)
    row.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(row, text=h["icon"], font=F(18), text_color=h["color"], width=36).grid(row=0, column=0, rowspan=2, padx=(14, 4), pady=10)
    ctk.CTkLabel(row, text=h["title"], font=F(13, "bold"), text_color=COLORS["text"], anchor="w").grid(
        row=0, column=1, sticky="ew", padx=6, pady=(10, 0))
    ctk.CTkLabel(row, text=h["sub"], font=F(11), text_color=COLORS["text2"], anchor="w").grid(
        row=1, column=1, sticky="ew", padx=6, pady=(0, 10))

    btns = ctk.CTkFrame(row, fg_color="transparent")
    btns.grid(row=0, column=2, rowspan=2, padx=10)
    GhostButton(btns, text="📂", width=36, height=32, command=lambda: open_folder()).pack(side="left", padx=2)


hist_scroll = ctk.CTkScrollableFrame(history_page, fg_color="transparent")

hist_controls = ctk.CTkFrame(history_page, fg_color="transparent")
hist_controls.pack(fill="x", padx=24, pady=(0, 10))
search_entry = ctk.CTkEntry(hist_controls, placeholder_text="Search history...", width=220,
                             fg_color=COLORS["bg2"], border_color=COLORS["border"], corner_radius=10)
search_entry.pack(side="left", padx=(0, 8))


def on_search(*_):
    hist_search_var.set(search_entry.get())
    render_history()


search_entry.bind("<KeyRelease>", on_search)

for label in ["All", "Video", "Audio (MP3)"]:
    GhostButton(hist_controls, text=label, width=90, height=32,
                command=lambda l=label: (hist_filter_var.set(l), render_history())).pack(side="left", padx=4)


def clear_history():
    history_items.clear()
    render_history()


GhostButton(hist_controls, text="🗑 Clear all", width=100, height=32, command=clear_history).pack(side="right")

hist_scroll.pack(fill="both", expand=True, padx=24, pady=(0, 20))

# ======================================================================
#  SETTINGS PAGE
# ======================================================================

settings_page = ctk.CTkScrollableFrame(content, fg_color="transparent")
pages["settings"] = settings_page
ctk.CTkLabel(settings_page, text="Settings", font=F(16, "bold"), text_color=COLORS["text"]).pack(
    anchor="w", padx=24, pady=(20, 10))

settings_card = Card(settings_page)
settings_card.pack(fill="x", padx=24, pady=8)
settings_card.grid_columnconfigure(1, weight=1)

ctk.CTkLabel(settings_card, text="Appearance", font=F(12), text_color=COLORS["text2"]).grid(
    row=0, column=0, sticky="w", padx=18, pady=14)
ctk.CTkSegmentedButton(settings_card, values=["Dark", "Light"],
                        command=lambda v: (theme_mode.set(v.lower()), ctk.set_appearance_mode(v.lower()))
                        ).grid(row=0, column=1, sticky="w", padx=(0, 18), pady=14)

ctk.CTkLabel(settings_card, text="Accent color", font=F(12), text_color=COLORS["text2"]).grid(
    row=1, column=0, sticky="w", padx=18, pady=14)
accent_row = ctk.CTkFrame(settings_card, fg_color="transparent")
accent_row.grid(row=1, column=1, sticky="w", padx=(0, 18), pady=14)
for c in ["#3B82F6", "#22C55E", "#F97316", "#A855F7", "#EF4444"]:
    ctk.CTkButton(accent_row, text="", width=26, height=26, corner_radius=13, fg_color=c,
                  hover_color=c, command=lambda col=c: set_accent(col)).pack(side="left", padx=3)


def set_accent(color):
    COLORS["accent"] = color
    progress_bar.configure(progress_color=color)
    fetch_btn.configure(fg_color=color)
    video_btn.configure(fg_color=color)


ctk.CTkLabel(settings_card, text="Default download folder", font=F(12), text_color=COLORS["text2"]).grid(
    row=2, column=0, sticky="w", padx=18, pady=14)
GhostButton(settings_card, text="Choose folder", width=140, command=choose_folder).grid(
    row=2, column=1, sticky="w", padx=(0, 18), pady=14)

ctk.CTkLabel(settings_card, text="Keyboard shortcuts", font=F(12), text_color=COLORS["text2"]).grid(
    row=3, column=0, sticky="nw", padx=18, pady=14)
ctk.CTkLabel(settings_card,
             text="Ctrl+V  Paste URL     Ctrl+Enter  Fetch info\nCtrl+D  Download video     Esc  Cancel download",
             font=F(11), text_color=COLORS["text"], justify="left").grid(
    row=3, column=1, sticky="w", padx=(0, 18), pady=14)

# ======================================================================
#  ABOUT PAGE
# ======================================================================

about_page = ctk.CTkScrollableFrame(content, fg_color="transparent")
pages["about"] = about_page
about_card = Card(about_page)
about_card.pack(fill="x", padx=24, pady=20)
ctk.CTkLabel(about_card, text="🎬 MediaHarbor Studio", font=F(22, "bold"), text_color=COLORS["text"]).pack(
    anchor="w", padx=20, pady=(20, 4))
ctk.CTkLabel(about_card, text="Download • Convert • Organize", font=F(12), text_color=COLORS["accent"]).pack(
    anchor="w", padx=20)
ctk.CTkLabel(about_card,
             text="A modern desktop companion for saving YouTube video and audio for "
                  "offline, personal use — built on yt-dlp and ffmpeg, wrapped in a "
                  "clean dashboard interface.",
             font=F(12), text_color=COLORS["text2"], wraplength=600, justify="left").pack(
    anchor="w", padx=20, pady=(10, 20))

# ======================================================================
#  STATUS BAR
# ======================================================================

status_bar = ctk.CTkFrame(app, fg_color=COLORS["bg2"], height=30, corner_radius=0)
status_bar.grid(row=2, column=0, sticky="ew")
status_bar.grid_propagate(False)
bottom_dot = ctk.CTkLabel(status_bar, text="●", font=F(11), text_color=COLORS["text2"])
bottom_dot.pack(side="left", padx=(16, 4), pady=4)
bottom_status_lbl = ctk.CTkLabel(status_bar, text="Ready", font=F(12), text_color=COLORS["text2"])
bottom_status_lbl.pack(side="left", pady=4)
ctk.CTkLabel(status_bar, text=f" Developed by Paramjeet Lamba \t\t\t\t\t\t ffmpeg: {'available' if has_ffmpeg() else 'missing'}", font=F(12),
             text_color=COLORS["text2"]).pack(side="right", padx=16, pady=4)
             



# ======================================================================
#  STATUS / HISTORY HELPERS  (wired to both the Home card and status bar)
# ======================================================================

STATUS_COLORS = {
    "idle": COLORS["text2"],
    "busy": COLORS["accent"],
    "ok": COLORS["success"],
    "warn": COLORS["warning"],
    "err": COLORS["error"],
}


def status(text, kind="idle"):
    color = STATUS_COLORS.get(kind, COLORS["text2"])
    ui(status_lbl.configure, text=text, text_color=COLORS["text"])
    ui(status_dot.configure, text_color=color)
    ui(bottom_status_lbl.configure, text=text, text_color=color)
    ui(bottom_dot.configure, text_color=color)
    if kind == "busy":
        ui(pulse, status_dot, color, COLORS["text2"], 4, 350)


def add_history(title, sub, icon, color, dtype="Video"):
    entry = {"title": title, "sub": sub, "icon": icon, "color": color, "type": dtype, "ts": time.time()}
    history_items.append(entry)
    ui(render_history)


def set_buttons(enabled):
    st = "normal" if enabled else "disabled"
    for b in (video_btn, audio_btn, fetch_btn):
        ui(b.configure, state=st)
    ui(cancel_btn.configure, state=("disabled" if enabled else "normal"))


# ======================================================================
#  FETCH METADATA  (logic unchanged; only wired to the new widgets)
# ======================================================================

def fetch_info():
    url = url_entry.get().strip()
    if not url:
        messagebox.showerror("Error", "Paste a YouTube URL first."); return
    set_buttons(False)
    status("Fetching video info...", "busy")
    threading.Thread(target=_fetch_worker, args=(url,), daemon=True).start()


def _fetch_worker(url):
    global info
    try:
        with yt_dlp.YoutubeDL({**YDL_BASE, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)

        is_pl = "entries" in info and info["entries"] is not None
        if is_pl:
            entries = list(info["entries"])
            first = entries[0] if entries else {}
            title, channel = info.get("title", "Playlist"), info.get("uploader", "Unknown")
            thumb = first.get("thumbnail") or info.get("thumbnail")
            duration_txt = f"{len(entries)} videos"
            views_txt = "—"
            heights = heights_from(first.get("formats", []) or [])
            ui(pl_switch.select); ui(pl_switch.configure, state="normal")
        else:
            title, channel = info.get("title", "Unknown"), info.get("uploader", "Unknown")
            thumb = info.get("thumbnail")
            duration_txt = fmt_dur(info.get("duration"))
            views_txt = fmt_count(info.get("view_count"))
            heights = heights_from(info.get("formats", []))
            ui(pl_switch.deselect); ui(pl_switch.configure, state="disabled")

        ui(quality_menu.configure, values=["Best"] + heights); ui(quality_var.set, "Best")
        ui(title_lbl.configure, text=title)
        ui(channel_lbl.configure, text=channel)
        ui(meta_labels["Duration"].configure, text=duration_txt)
        ui(meta_labels["Views"].configure, text=views_txt)
        ui(meta_labels["Resolution"].configure, text=(heights[0] if heights else "N/A"))
        ui(meta_labels["Est. size"].configure, text="~ varies")
        if thumb:
            _load_thumb(thumb)
        status("Info loaded — ready to download.", "ok")
    except Exception as e:
        status("Could not fetch video info.", "err")
        ui(messagebox.showerror, "Fetch Error", str(e))
    finally:
        set_buttons(True)


def _load_thumb(url):
    global thumb_img
    try:
        data = urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=10).read()
        img = Image.open(BytesIO(data)).convert("RGB")
        tw, th = 308, 173
        if img.width / img.height > tw / th:
            nh = th; nw = int(nh * img.width / img.height)
        else:
            nw = tw; nh = int(nw * img.height / img.width)
        img = img.resize((nw, nh))
        left, top = (nw - tw) // 2, (nh - th) // 2
        img = img.crop((left, top, left + tw, top + th))
        thumb_img = ctk.CTkImage(light_image=img, dark_image=img, size=(tw, th))
        ui(thumb_lbl.configure, image=thumb_img, text="")
    except Exception:
        ui(thumb_lbl.configure, image=None, text="🖼\n\nThumbnail unavailable")


# ======================================================================
#  DOWNLOAD  (progress hook unchanged; format-selection logic reworked
#  so 720p/1080p/1440p/4K are actually reachable)
# ======================================================================

class Cancelled(Exception):
    pass


_last_tick = {"t": 0, "b": 0}


def progress_hook(d):
    if cancel_evt.is_set():
        raise Cancelled()
    if d.get("status") == "downloading":
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        downloaded = d.get("downloaded_bytes", 0)
        if total:
            frac = max(0, min(1, downloaded / total))
            ui(progress_bar.set, frac)
            ui(progress_pct_lbl.configure, text=f"{frac*100:.1f}%")
        ui(stats_labels["Speed"].configure, text=(d.get("_speed_str") or "—").strip())
        ui(stats_labels["ETA"].configure, text=(d.get("_eta_str") or "—").strip())
        ui(stats_labels["Downloaded"].configure, text=f"{fmt_bytes(downloaded)} / {fmt_bytes(total)}")
        ui(stats_labels["File"].configure, text=os.path.basename(d.get("filename", "") or ""))
    elif d.get("status") == "finished":
        ui(progress_bar.set, 1.0)
        ui(progress_pct_lbl.configure, text="100%")
        status("Processing / merging...", "busy")


def start_download(mode):
    global downloading
    if downloading:
        return
    url = url_entry.get().strip()
    if not url:
        messagebox.showerror("Error", "Enter a YouTube URL."); return
    downloading = True
    cancel_evt.clear()
    set_buttons(False)
    ui(progress_bar.set, 0)
    ui(progress_pct_lbl.configure, text="0%")
    for lbl in stats_labels.values():
        ui(lbl.configure, text="—")
    threading.Thread(target=_download_worker, args=(url, mode), daemon=True).start()


def _download_worker(url, mode):
    global downloading
    quality = quality_var.get()
    is_pl = bool(pl_switch.get())
    want_subs = bool(subs_switch.get())
    want_embed = bool(embed_switch.get()) and has_ffmpeg()

    opts = {
        **YDL_BASE,
        "outtmpl": os.path.join(folder, "%(playlist_index)s - %(title)s.%(ext)s" if is_pl else "%(title)s.%(ext)s"),
        "progress_hooks": [progress_hook],
        "noplaylist": not is_pl,
        "ignoreerrors": is_pl,
    }
    if want_subs:
        opts.update(writesubtitles=True, subtitleslangs=["en"], subtitlesformat="srt")

    if want_embed:
        opts["writethumbnail"] = True
        opts["postprocessors"] = opts.get("postprocessors", []) + [
            {"key": "FFmpegThumbnailsConvertor", "format": "jpg"},
        ]

    if mode == "video":
        height = quality.replace("p", "") if quality != "Best" else None
        if has_ffmpeg():
            # With ffmpeg present we can always grab the best available
            # video-only stream (which is where 1080p/1440p/4K actually
            # live on YouTube) and mux it with the best audio stream.
            # The height<= filters are only applied when the user picked
            # a specific resolution; "Best" pulls the true maximum.
            if height:
                fmt = (
                    f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
                    f"bestvideo[height<={height}]+bestaudio/"
                    f"best[height<={height}]"
                )
            else:
                fmt = (
                    "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                    "bestvideo+bestaudio/"
                    "best"
                )
            # Force a proper container so high-res video-only + audio-only
            # streams are merged correctly instead of silently falling
            # back to a low-res progressive format.
            opts["merge_output_format"] = "mp4"
        else:
            # No ffmpeg -> we're stuck with YouTube's progressive (audio
            # baked in) formats, which cap out well below 4K. Same as
            # before, just kept as an honest fallback.
            fmt = (f"best[vcodec!=none][acodec!=none][height<={height}]/best[vcodec!=none][acodec!=none]") if height else \
                  "best[vcodec!=none][acodec!=none]"
            status("ffmpeg not found — capped to a lower-quality progressive format, no thumbnail embedding.", "warn")
        opts["format"] = fmt
        if want_embed:
            opts["postprocessors"] = opts.get("postprocessors", []) + [{"key": "EmbedThumbnail"}]
        label = "Video"
        dtype = "Video"
    else:
        opts["format"] = "bestaudio/best"
        codec = audio_fmt_var.get().lower()
        opts["postprocessors"] = opts.get("postprocessors", []) + [
            {"key": "FFmpegExtractAudio", "preferredcodec": codec, "preferredquality": "192"},
        ]
        if want_embed:
            opts["postprocessors"].append({"key": "EmbedThumbnail"})
        label = f"Audio ({audio_fmt_var.get()})"
        dtype = "Audio (MP3)"

    title = info.get("title", url) if info else url
    try:
        status(f"Downloading {label}...", "busy")
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        status(f"{label} downloaded successfully!", "ok")
        add_history(title, f"{label} • saved to {folder}", "✅", COLORS["success"], dtype)
        ui(open_folder_btn.configure, state="normal")
        if autoopen_switch.get():
            ui(open_folder)
    except Cancelled:
        status("Download cancelled.", "warn")
        add_history(title, f"{label} • cancelled", "⏹", COLORS["warning"], dtype)
    except Exception as e:
        msg = str(e)
        friendly = "YouTube blocked this request (403). Run 'pip install -U yt-dlp'." if "403" in msg else "Download failed."
        status(friendly, "err")
        add_history(title, f"{label} • error: {e}", "❌", COLORS["error"], dtype)
        ui(messagebox.showerror, "Download Error", msg)
    finally:
        downloading = False
        set_buttons(True)


def cancel_download():
    if downloading:
        cancel_evt.set()
        status("Cancelling...", "warn")


def open_folder():
    try:
        if platform.system() == "Windows": os.startfile(folder)
        elif platform.system() == "Darwin": subprocess.Popen(["open", folder])
        else: subprocess.Popen(["xdg-open", folder])
    except Exception as e:
        messagebox.showerror("Error", str(e))


# ======================================================================
#  KEYBOARD SHORTCUTS
# ======================================================================

app.bind("<Control-v>", lambda e: paste_clip())
app.bind("<Control-Return>", lambda e: fetch_info())
app.bind("<Control-d>", lambda e: start_download("video"))
app.bind("<Escape>", lambda e: cancel_download())

# ======================================================================
#  BOOT
# ======================================================================

select_page("home")
render_history()

if not has_ffmpeg():
    status("ffmpeg not found — video downloads capped to formats with embedded audio.", "warn")

app.mainloop()
