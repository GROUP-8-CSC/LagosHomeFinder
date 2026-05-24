"""
Dashboard.py  —  Lagos Home Finder
Screens module: property grid with search, filter, favourites, detail popup.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import csv
import os
import re
import json
import threading
import webbrowser
from PIL import Image, ImageTk, ImageFile

try:
    from services.msgbox import MessageBoxService
    from services.verification import VerificationService
except ModuleNotFoundError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from services.msgbox import MessageBoxService
    from services.verification import VerificationService

ImageFile.LOAD_TRUNCATED_IMAGES = True

# ── SMTP config — fill in your Gmail + App Password here ──────────────────
SMTP_SENDER_EMAIL    = "YOUR_EMAIL@gmail.com"
SMTP_APP_PASSWORD    = "YOUR_APP_PASSWORD"

# ── Layout constants ───────────────────────────────────────────────────────
BATCH_SIZE  = 20
CARD_W      = 300
CARD_IMG_H  = 200
PLACEHOLDER = "Neighbourhood, title, price…"

# ── Property-type keyword map ──────────────────────────────────────────────
TYPE_KEYWORDS = {
    "Flat / Apartment": ["flat", "apartment", "mini flat", "studio"],
    "Duplex":           ["duplex"],
    "Bungalow":         ["bungalow"],
    "Terrace":          ["terrace"],
    "Self Contain":     ["self contain", "single room"],
    "Land / Plot":      ["land", "plot"],
    "Mansion / Villa":  ["mansion", "villa", "penthouse"],
    "Commercial":       ["commercial", "office", "warehouse", "shop"],
}


# ── Utility functions ──────────────────────────────────────────────────────
def _infer_type(title):
    t = title.lower()
    for ptype, kws in TYPE_KEYWORDS.items():
        if any(k in t for k in kws):
            return ptype
    return "Other"


def _parse_price_int(text):
    try:
        digits = re.sub(r"[^\d]", "", text)
        val = int(digits) if digits else 0
        return val * 1500 if "$" in text else val
    except Exception:
        return 0


def _infer_bedrooms(title, desc, ptype):
    m = re.search(r"(\d+)\s*bed", (title + " " + desc).lower())
    if m:
        return int(m.group(1))
    defaults = {"Flat / Apartment": 2, "Duplex": 4, "Bungalow": 3,
                "Terrace": 3, "Self Contain": 1, "Mansion / Villa": 5,
                "Commercial": 0, "Land / Plot": 0, "Other": 2}
    return defaults.get(ptype, 2)


def _infer_bathrooms(title, desc, beds):
    m = re.search(r"(\d+)\s*bath", (title + " " + desc).lower())
    return int(m.group(1)) if m else (max(1, beds - 1) if beds > 0 else 1)


def _split_agent_phone(raw):
    """Split 'Agent Name  +234...' into (name, phone)."""
    raw = raw.replace("\xa0", " ").strip()
    m = re.search(r"(\+?\d[\d\s\-]{7,})", raw)
    if m:
        phone = m.group(1).strip()
        name  = raw[:m.start()].strip()
        return name, phone
    return raw, ""


def _make_white_icon(path, size):
    """Load an RGBA image and recolour every opaque pixel to white."""
    img = Image.open(path).convert("RGBA")
    r, g, b, a = img.split()
    white = Image.new("L", img.size, 255)
    img   = Image.merge("RGBA", (white, white, white, a))
    img   = img.resize(size, Image.LANCZOS)
    return ImageTk.PhotoImage(img)


# ══════════════════════════════════════════════════════════════════════════════
class DashboardScreen(ttk.Frame):

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Runtime state
        self.all_properties = []
        self.filtered_list  = []
        self.loaded_until   = 0
        self.card_widgets   = {}   # pid -> card Frame
        self.card_images    = {}   # pid -> PhotoImage (kept alive)
        self._load_lock     = False
        self._scroll_job    = None
        self._resize_job    = None
        self.current_cols   = 3
        self.collections    = {"Favorites": []}
        self.current_user   = None

        self.icons = self._load_icons()

        # ── Services ──
        self.msgbox = MessageBoxService(self)
        self.smtp_sender_email = SMTP_SENDER_EMAIL
        self.smtp_app_password = SMTP_APP_PASSWORD

        self._build_topbar()
        self._build_verify_banner()        # yellow banner (hidden by default)
        self._build_sidebar_and_grid()
        self._load_data()
        self._populate_type_filter()
        self._load_user_collections()
        self._apply_filters()

        # init verification service (needs topbar + banner to exist)
        self.verification = VerificationService(self)

    # ── Icon loading ────────────────────────────────────────────────────────
    def _load_icons(self):
        base  = os.path.join(os.path.dirname(__file__), "..", "assets")
        icons = {}

        def _load(key, fname, size=(20, 20)):
            path = os.path.join(base, fname)
            if os.path.exists(path):
                try:
                    img = Image.open(path).resize(size, Image.LANCZOS)
                    icons[key] = ImageTk.PhotoImage(img)
                except Exception:
                    icons[key] = None
            else:
                icons[key] = None

        _load("bed",       "bed.png")
        _load("bath",      "bath.png")
        _load("location",  "location.png")
        _load("star_card_empty",  "star_open.png",   (20, 20))
        _load("star_card_filled", "star_closed.png", (20, 20))
        _load("phone_icon", "phone-call.png", (18, 18))
        _load("search_icon", "search.png",   (18, 18))

        # Navbar star → white version of star_closed
        star_path = os.path.join(base, "star_closed.png")
        if os.path.exists(star_path):
            try:
                icons["star_nav"] = _make_white_icon(star_path, (20, 20))
            except Exception:
                icons["star_nav"] = None
        else:
            icons["star_nav"] = None

        # User icon → white version for navbar
        user_path = os.path.join(base, "user_icon.png")
        if os.path.exists(user_path):
            try:
                icons["user_nav"] = _make_white_icon(user_path, (20, 20))
            except Exception:
                icons["user_nav"] = None
        else:
            icons["user_nav"] = None

        # User icon (original colours) for detail popup agent row
        if os.path.exists(user_path):
            try:
                img = Image.open(user_path).resize((18, 18), Image.LANCZOS)
                icons["user_agent"] = ImageTk.PhotoImage(img)
            except Exception:
                icons["user_agent"] = None
        else:
            icons["user_agent"] = None

        # App logo for popup window icon
        logo_path = os.path.join(base, "logo_icon.png")
        if os.path.exists(logo_path):
            try:
                img = Image.open(logo_path).resize((32, 32), Image.LANCZOS)
                icons["app_logo"] = ImageTk.PhotoImage(img)
            except Exception:
                icons["app_logo"] = None
        else:
            icons["app_logo"] = None

        return icons

    def _set_window_icon(self, window):
        """Apply the app logo to any Toplevel window."""
        logo = self.icons.get("app_logo")
        if logo:
            try:
                window.iconphoto(False, logo)
            except Exception:
                pass

    # ── Favourites persistence ──────────────────────────────────────────────
    def _favorites_file(self):
        if not self.current_user:
            return None
        db_dir = os.path.join(os.path.dirname(__file__), "..", "db")
        os.makedirs(db_dir, exist_ok=True)
        safe = re.sub(r"[^a-zA-Z0-9]", "_", self.current_user)
        return os.path.join(db_dir, f"favorites_{safe}.json")

    def _load_user_collections(self):
        sess = getattr(self.controller, "session", {}) or {}
        self.current_user = sess.get("email")
        fpath = self._favorites_file()
        if fpath and os.path.exists(fpath):
            try:
                with open(fpath) as f:
                    self.collections = {"Favorites": json.load(f).get("Favorites", [])}
                return
            except Exception:
                pass
        self.collections = {"Favorites": []}

    def _save_collections(self):
        fpath = self._favorites_file()
        if fpath:
            try:
                with open(fpath, "w") as f:
                    json.dump(self.collections, f, indent=2)
            except Exception as e:
                print(f"Favourites save error: {e}")

    def _is_favorite(self, pid):
        return pid in self.collections.get("Favorites", [])

    def _toggle_favorite(self, prop):
        if not self.current_user:
            messagebox.showwarning("Not Logged In", "Please log in to save properties.")
            return
        pid  = prop["id"]
        favs = self.collections.setdefault("Favorites", [])
        if pid in favs:
            favs.remove(pid)
        else:
            favs.append(pid)
        self._save_collections()
        self._refresh_star_on_card(pid, pid in favs)

    def _refresh_star_on_card(self, pid, is_saved):
        card = self.card_widgets.get(pid)
        if not card:
            return
        # Walk info > title_row > buttons looking for _is_star flag
        for child in card.winfo_children():
            if not isinstance(child, tk.Frame):
                continue
            for sub in child.winfo_children():
                if not isinstance(sub, tk.Frame):
                    continue
                for widget in sub.winfo_children():
                    if not getattr(widget, "_is_star", False):
                        continue
                    filled = self.icons.get("star_card_filled")
                    empty  = self.icons.get("star_card_empty")
                    if is_saved:
                        widget.config(image=filled or "", text="" if filled else "★", fg="#F5A623")
                    else:
                        widget.config(image=empty or "",  text="" if empty  else "☆", fg="#9AA5B4")

    # ── Data loading ────────────────────────────────────────────────────────
    def _load_data(self):
        base = os.path.dirname(__file__)
        csv_candidates = [
            os.path.join(base, "..", "db", "lagos_home_finder_seed.csv"),
            os.path.join(base, "..", "lagos_home_finder_seed.csv"),
        ]
        csv_path = next((p for p in csv_candidates if os.path.exists(p)), None)
        if not csv_path:
            return

        img_dir = os.path.join(base, "..", "assets", "property_images")

        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pid      = row.get("property_id", "").strip()
                img_path = os.path.join(img_dir, f"{pid}.jpg")
                if not os.path.exists(img_path):
                    continue

                title     = row.get("title", "No Title").strip().title()
                desc      = row.get("generated_description", "")
                ptype     = _infer_type(title)
                price_str = row.get("price", "").strip()
                if price_str and "₦" not in price_str:
                    price_str = f"₦{price_str}"

                beds  = self._safe_int(row.get("bedrooms",  "")) or _infer_bedrooms(title, desc, ptype)
                baths = self._safe_int(row.get("bathrooms", "")) or _infer_bathrooms(title, desc, beds)

                raw_agent         = row.get("agent", "")
                agent_name, phone = _split_agent_phone(raw_agent)

                # Support both 'property_url' and 'link' column names
                link = (row.get("property_url") or row.get("link") or "#").strip()

                self.all_properties.append({
                    "id":        pid,
                    "title":     title,
                    "price":     price_str,
                    "price_int": _parse_price_int(price_str),
                    "location":  row.get("location", "Unknown").strip(),
                    "agent":     agent_name,
                    "phone":     phone,
                    "desc":      desc,
                    "type":      ptype,
                    "bedrooms":  beds,
                    "bathrooms": baths,
                    "img_path":  img_path,
                    "link":      link,
                })

    def _safe_int(self, val):
        try:
            return int(str(val).strip()) if str(val).strip() else None
        except ValueError:
            return None

    def _populate_type_filter(self):
        types = sorted({p["type"] for p in self.all_properties})
        self.type_combo.configure(values=["All Types"] + types)

    # ── Filter & sort pipeline ──────────────────────────────────────────────
    def _apply_filters(self, *_):
        raw = self.search_var.get().strip()
        q   = "" if raw == PLACEHOLDER else raw.lower()

        sel_type  = self.type_var.get()
        sort_mode = self.sort_var.get()
        bed_filt  = self.bed_var.get()
        bath_filt = self.bath_var.get()

        min_p_raw = self.min_price_var.get().strip()
        max_p_raw = self.max_price_var.get().strip()
        min_price = _parse_price_int(min_p_raw) if min_p_raw not in ("", "Min") else 0
        max_price = _parse_price_int(max_p_raw) if max_p_raw not in ("", "Max") else 0

        result = []
        for p in self.all_properties:
            # Text / price search
            price_hit = self._fuzzy_price_match(q, p["price_int"])
            text_ok   = (not q
                         or q in p["title"].lower()
                         or q in p["location"].lower()
                         or q in p["type"].lower()
                         or price_hit)
            # Dropdown filters
            type_ok  = sel_type in ("All Types", "") or p["type"] == sel_type
            bed_ok   = True
            if bed_filt != "Any":
                bed_ok = p["bedrooms"] >= int(bed_filt.rstrip("+"))
            bath_ok  = True
            if bath_filt != "Any":
                bath_ok = p["bathrooms"] >= int(bath_filt.rstrip("+"))
            # Price range
            range_ok = True
            if min_price:
                range_ok = p["price_int"] >= min_price
            if max_price and range_ok:
                range_ok = p["price_int"] <= max_price

            if text_ok and type_ok and bed_ok and bath_ok and range_ok:
                result.append(p)

        if sort_mode == "Price: Low → High":
            result.sort(key=lambda x: x["price_int"])
        elif sort_mode == "Price: High → Low":
            result.sort(key=lambda x: x["price_int"], reverse=True)

        self.filtered_list = result
        self.loaded_until  = 0
        self._clear_grid()
        self._load_batch()

    def _fuzzy_price_match(self, query, price_int):
        digits = re.sub(r"[^\d]", "", query)
        if not digits or price_int == 0:
            return False
        typed = int(digits)
        if typed == 0:
            return False
        return abs(price_int - typed) / max(price_int, typed) <= 0.20

    def _reset_filters(self):
        self.search_var.set("")
        self.type_var.set("All Types")
        self.bed_var.set("Any")
        self.bath_var.set("Any")
        self.sort_var.set("Default")
        self.min_price_var.set("")
        self.max_price_var.set("")
        self._apply_filters()

    # ── Lazy / infinite scroll loading ─────────────────────────────────────
    def _clear_grid(self):
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self.card_widgets.clear()
        self.card_images.clear()

    def _load_batch(self):
        if self._load_lock:
            return
        self._load_lock = True
        try:
            start = self.loaded_until
            end   = min(start + BATCH_SIZE, len(self.filtered_list))
            if start >= end:
                self._show_empty_state()
                return
            cols = max(1, self.current_cols)
            for i in range(cols):
                self.grid_frame.columnconfigure(i, weight=1)
            for idx in range(start, end):
                prop = self.filtered_list[idx]
                card = self._make_card(prop)
                card.grid(row=idx // cols, column=idx % cols,
                          padx=16, pady=16, sticky="n")
                self.card_widgets[prop["id"]] = card
            self.loaded_until = end
            n = len(self.filtered_list)
            self.count_var.set(f"{n} propert{'y' if n == 1 else 'ies'} found")
        finally:
            self._load_lock = False

    def _show_empty_state(self):
        if self.grid_frame.winfo_children():
            return
        f = tk.Frame(self.grid_frame, bg="#F2F4F8")
        f.grid(row=0, column=0, padx=30, pady=60)
        tk.Label(f, text="🏠", font=("Arial", 36), bg="#F2F4F8", fg="#9AA5B4").pack()
        tk.Label(f, text="No properties match your search.",
                 font=("Arial", 13), fg="#4A5568", bg="#F2F4F8").pack(pady=(8, 4))
        tk.Label(f, text="Try adjusting your filters.",
                 font=("Arial", 10), fg="#9AA5B4", bg="#F2F4F8").pack()

    def _on_scroll(self, event):
        self.cards_canvas.yview_scroll(-1 * (event.delta // 120), "units")
        if self._scroll_job:
            self.after_cancel(self._scroll_job)
        self._scroll_job = self.after(200, self._maybe_load_more)

    def _maybe_load_more(self):
        if self.loaded_until >= len(self.filtered_list):
            return
        bbox = self.cards_canvas.bbox("all")
        if not bbox:
            return
        visible_bottom = self.cards_canvas.canvasy(self.cards_canvas.winfo_height())
        if bbox[3] - visible_bottom < 400:
            self._load_batch()

    # ── Property card ───────────────────────────────────────────────────────
    def _make_card(self, prop):
        card = tk.Frame(self.grid_frame, bg="#FFFFFF",
                        highlightthickness=1, highlightbackground="#DDE3EC",
                        cursor="hand2")

        # ── Image area ──
        img_frame = tk.Frame(card, bg="#DDE3EC", width=CARD_W, height=CARD_IMG_H)
        img_frame.pack(fill="x")
        img_frame.pack_propagate(False)
        thumb = tk.Label(img_frame, bg="#DDE3EC", text="Loading…", fg="#9AA5B4")
        thumb.place(relx=0.5, rely=0.5, anchor="center")
        self._async_load_image(prop, thumb, CARD_W, CARD_IMG_H)

        tk.Label(img_frame, text=prop["price"], font=("Arial", 10, "bold"),
                 fg="white", bg="#00A859", padx=8, pady=3)\
            .place(relx=0, rely=1, anchor="sw", x=8, y=-8)

        # ── Info area ──
        info = tk.Frame(card, bg="white", padx=12, pady=10)
        info.pack(fill="x")

        # Title row + favourite star
        title_row = tk.Frame(info, bg="white")
        title_row.pack(fill="x")
        tk.Label(title_row, text=prop["title"], font=("Arial", 11, "bold"),
                 fg="#0A1128", bg="white", wraplength=230,
                 justify="left", anchor="w").pack(side="left", fill="x", expand=True)

        is_fav   = self._is_favorite(prop["id"])
        star_img = self.icons.get("star_card_filled" if is_fav else "star_card_empty")
        star_btn = tk.Button(title_row,
                             image=star_img or "",
                             text="" if star_img else ("★" if is_fav else "☆"),
                             fg="#F5A623" if is_fav else "#9AA5B4",
                             font=("Arial", 14), bg="white",
                             relief="flat", cursor="hand2", bd=0,
                             command=lambda p=prop: self._toggle_favorite(p))
        star_btn._is_star = True
        star_btn.pack(side="right", padx=(5, 0))

        # Location
        loc_row = tk.Frame(info, bg="white")
        loc_row.pack(fill="x", pady=(2, 0))
        loc_icon = self.icons.get("location")
        tk.Label(loc_row, image=loc_icon or "", text="" if loc_icon else "📍",
                 font=("Arial", 9), bg="white").pack(side="left")
        tk.Label(loc_row, text=prop["location"], font=("Arial", 9),
                 fg="#4A5568", bg="white", wraplength=230,
                 justify="left", anchor="w").pack(side="left")

        # Bed / bath stats
        stats = tk.Frame(info, bg="white")
        stats.pack(anchor="w", pady=(4, 0))
        bed_ic  = self.icons.get("bed")
        bath_ic = self.icons.get("bath")
        tk.Label(stats, image=bed_ic  or "", text="" if bed_ic  else "🛏️",
                 font=("Arial", 9), bg="white").pack(side="left")
        tk.Label(stats, text=f" {prop['bedrooms']}  ",
                 font=("Arial", 9), fg="#4A5568", bg="white").pack(side="left")
        tk.Label(stats, image=bath_ic or "", text="" if bath_ic else "🛁",
                 font=("Arial", 9), bg="white").pack(side="left")
        tk.Label(stats, text=f" {prop['bathrooms']}",
                 font=("Arial", 9), fg="#4A5568", bg="white").pack(side="left")

        # Type chip
        tk.Label(info, text=prop["type"], font=("Arial", 8),
                 fg="#00A859", bg="#E8F8F0", padx=6, pady=2)\
            .pack(anchor="w", pady=(6, 0))

        # View details button
        btn_row = tk.Frame(card, bg="white", pady=8)
        btn_row.pack(fill="x", padx=12)
        tk.Button(btn_row, text="View Details →", font=("Arial", 9, "bold"),
                  bg="white", fg="#00A859", relief="flat", cursor="hand2", bd=0,
                  command=lambda p=prop: self._show_details(p)).pack(side="left")

        # Card hover border
        card.bind("<Enter>",    lambda e: card.configure(highlightbackground="#00A859"))
        card.bind("<Leave>",    lambda e: card.configure(highlightbackground="#DDE3EC"))
        card.bind("<Button-1>", lambda e, p=prop: self._show_details(p))
        return card

    def _async_load_image(self, prop, label, w, h):
        def task():
            try:
                img = Image.open(prop["img_path"])
                img.thumbnail((w, h))
                photo = ImageTk.PhotoImage(img)
                self.card_images[prop["id"]] = photo
                def update():
                    if label.winfo_exists():
                        label.config(image=photo, text="")
                self.after(0, update)
            except Exception:
                self.after(0, lambda: label.config(text="No Image"))
        threading.Thread(target=task, daemon=True).start()

    # ── Detail popup ─────────────────────────────────────────────────────────
    def _show_details(self, prop):
        popup = tk.Toplevel(self)
        try:
            popup.transient(self.winfo_toplevel())
        except Exception:
            pass
        popup.title(prop["title"])
        popup.geometry("1000x640")
        popup.minsize(820, 520)
        popup.configure(bg="white")
        popup.grab_set()
        self._set_window_icon(popup)

        # Header
        hdr = tk.Frame(popup, bg="#0A1128", height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Button(hdr, text="← Back", font=("Arial", 10),
                  bg="#0A1128", fg="#9AA5B4", relief="flat",
                  cursor="hand2", bd=0, command=popup.destroy)\
            .pack(side="left", padx=20, pady=10)
        tk.Label(hdr, text=prop["title"][:72], font=("Arial", 11, "bold"),
                 fg="white", bg="#0A1128").pack(side="left", padx=10)

        # Body
        body = tk.Frame(popup, bg="white")
        body.pack(fill="both", expand=True, padx=24, pady=20)

        # Left: property image
        img_frame = tk.Frame(body, bg="#DDE3EC", width=440, height=320)
        img_frame.pack(side="left", fill="none", padx=(0, 24))
        img_frame.pack_propagate(False)
        img_lbl = tk.Label(img_frame, bg="#DDE3EC", text="Loading…")
        img_lbl.place(relx=0.5, rely=0.5, anchor="center")

        def load_detail_img():
            try:
                img = Image.open(prop["img_path"])
                img.thumbnail((440, 320))
                photo = ImageTk.PhotoImage(img)
                popup._detail_photo = photo
                def upd():
                    if img_lbl.winfo_exists():
                        img_lbl.config(image=photo, text="")
                popup.after(0, upd)
            except Exception:
                popup.after(0, lambda: img_lbl.config(text="Image unavailable"))
        threading.Thread(target=load_detail_img, daemon=True).start()

        # Right: details panel
        right = tk.Frame(body, bg="white")
        right.pack(side="left", fill="both", expand=True)

        tk.Label(right, text=prop["title"], font=("Arial", 17, "bold"),
                 fg="#0A1128", bg="white", wraplength=420, justify="left").pack(anchor="w")
        tk.Label(right, text=prop["price"], font=("Arial", 24, "bold"),
                 fg="#00A859", bg="white").pack(anchor="w", pady=(6, 12))
        tk.Label(right, text=prop["type"], font=("Arial", 9),
                 fg="#00A859", bg="#E8F8F0", padx=8, pady=3).pack(anchor="w", pady=(0, 14))

        # Location / bed / bath row
        meta = tk.Frame(right, bg="white")
        meta.pack(anchor="w", pady=2)
        loc_ic  = self.icons.get("location")
        bed_ic  = self.icons.get("bed")
        bath_ic = self.icons.get("bath")
        for icon, emoji, value in [
            (loc_ic,  "📍", prop["location"] + "   "),
            (bed_ic,  "🛏️", str(prop["bedrooms"]) + "   "),
            (bath_ic, "🛁", str(prop["bathrooms"])),
        ]:
            tk.Label(meta, image=icon or "", text="" if icon else emoji,
                     font=("Arial", 10), bg="white").pack(side="left")
            tk.Label(meta, text=value, font=("Arial", 10),
                     fg="#4A5568", bg="white").pack(side="left")

        # Agent row with user_icon
        agent_row = tk.Frame(right, bg="white")
        agent_row.pack(anchor="w", pady=(8, 2))
        user_ic = self.icons.get("user_agent")
        tk.Label(agent_row, image=user_ic or "", text="" if user_ic else "👤",
                 bg="white").pack(side="left")
        tk.Label(agent_row, text=f"  {prop['agent']}", font=("Arial", 10),
                 fg="#4A5568", bg="white").pack(side="left")

        # Phone row with phone icon
        if prop.get("phone"):
            phone_row = tk.Frame(right, bg="white")
            phone_row.pack(anchor="w", pady=(2, 6))
            ph_ic = self.icons.get("phone_icon")
            tk.Label(phone_row, image=ph_ic or "", text="" if ph_ic else "📞",
                     bg="white").pack(side="left")
            tk.Label(phone_row, text=f"  {prop['phone']}", font=("Arial", 10),
                     fg="#4A5568", bg="white").pack(side="left")

        # Description
        tk.Label(right, text="About this property", font=("Arial", 10, "bold"),
                 fg="#0A1128", bg="white").pack(anchor="w", pady=(12, 4))
        desc_box = tk.Text(right, wrap="word", height=6, font=("Arial", 10),
                           fg="#4A5568", bg="#FAFAFA", relief="flat", bd=0,
                           highlightthickness=1, highlightbackground="#DDE3EC")
        desc_box.insert("1.0", prop["desc"])
        desc_box.configure(state="disabled")
        desc_box.pack(fill="both", expand=True, pady=(0, 14))

        # Action buttons
        btn_row = tk.Frame(right, bg="white")
        btn_row.pack(fill="x", pady=(0, 8))

        if prop.get("link") and prop["link"] not in ("#", ""):
            visit_btn = tk.Button(btn_row, text="🌐 Visit Listing",
                                  font=("Arial", 10, "bold"),
                                  bg="#00A859", fg="white", relief="flat",
                                  cursor="hand2", padx=16, pady=7,
                                  command=lambda: webbrowser.open(prop["link"]))
            visit_btn.pack(side="left", padx=(0, 10))
            visit_btn.bind("<Enter>", lambda e: visit_btn.config(bg="#007A40"))
            visit_btn.bind("<Leave>", lambda e: visit_btn.config(bg="#00A859"))

        if prop.get("phone"):
            phone_btn = tk.Button(btn_row, text="📞 Call Agent",
                                  font=("Arial", 10, "bold"),
                                  bg="#0A1128", fg="white", relief="flat",
                                  cursor="hand2", padx=16, pady=7,
                                  command=lambda: self._show_phone_popup(prop))
            phone_btn.pack(side="left", padx=(0, 10))
            phone_btn.bind("<Enter>", lambda e: phone_btn.config(bg="#1C2E5E"))
            phone_btn.bind("<Leave>", lambda e: phone_btn.config(bg="#0A1128"))

        close_btn = tk.Button(btn_row, text="Close", font=("Arial", 10),
                              bg="#F2F4F8", fg="#4A5568", relief="flat",
                              cursor="hand2", padx=16, pady=7,
                              command=popup.destroy)
        close_btn.pack(side="left")
        close_btn.bind("<Enter>", lambda e: close_btn.config(bg="#DDE3EC"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(bg="#F2F4F8"))

    def _show_phone_popup(self, prop):
        """Small popup showing agent phone number, with app logo."""
        win = tk.Toplevel(self)
        try:
            win.transient(self.winfo_toplevel())
        except Exception:
            pass
        win.title("Agent Contact")
        win.geometry("340x160")
        win.resizable(False, False)
        win.configure(bg="white")
        win.grab_set()
        self._set_window_icon(win)

        tk.Label(win, text="Agent Phone Number", font=("Arial", 11, "bold"),
                 fg="#0A1128", bg="white").pack(pady=(22, 6))

        ph_frame = tk.Frame(win, bg="white")
        ph_frame.pack()
        ph_ic = self.icons.get("phone_icon")
        tk.Label(ph_frame, image=ph_ic or "", text="" if ph_ic else "📞",
                 bg="white").pack(side="left", padx=(0, 6))
        tk.Label(ph_frame, text=prop["phone"], font=("Arial", 14, "bold"),
                 fg="#00A859", bg="white").pack(side="left")

        tk.Label(win, text=f"Agent: {prop['agent']}", font=("Arial", 9),
                 fg="#9AA5B4", bg="white").pack(pady=(4, 0))

        tk.Button(win, text="Close", font=("Arial", 9), bg="#F2F4F8",
                  fg="#4A5568", relief="flat", cursor="hand2",
                  padx=14, pady=5, command=win.destroy).pack(pady=(14, 0))

    # ── Navbar ───────────────────────────────────────────────────────────────
    def _build_topbar(self):
        bar = tk.Frame(self, bg="#0A1128", height=62)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # Logo + app name
        tk.Label(bar, text="LAGOS ", font=("Arial", 15, "bold"),
                 fg="white", bg="#0A1128").pack(side="left", padx=(20, 0), pady=16)
        tk.Label(bar, text="HOME FINDER", font=("Arial", 15, "bold"),
                 fg="#00A859", bg="#0A1128").pack(side="left", pady=16)

        # ── Right-side nav items (packed right-to-left) ──

        # Logout — outlined red border, fills on hover
        logout_btn = tk.Button(bar, text="Logout", font=("Arial", 10, "bold"),
                               bg="#0A1128", fg="#E63946",
                               relief="solid", bd=1,
                               highlightbackground="#E63946",
                               highlightthickness=1,
                               cursor="hand2", padx=14, pady=5,
                               command=self._logout)
        logout_btn.pack(side="right", padx=(0, 18), pady=16)
        logout_btn.bind("<Enter>", lambda e: logout_btn.config(bg="#E63946", fg="white"))
        logout_btn.bind("<Leave>", lambda e: logout_btn.config(bg="#0A1128", fg="#E63946"))

        # Separator between logout and other nav items
        tk.Frame(bar, bg="#2A3550", width=1).pack(side="right", fill="y", pady=14)

        # Favourites button
        star_nav = self.icons.get("star_nav")
        fav_btn  = tk.Button(bar,
                             image=star_nav or "",
                             text="  Favourites" if star_nav else "★  Favourites",
                             compound="left",
                             font=("Arial", 10),
                             bg="#0A1128", fg="#9AA5B4",
                             relief="flat", cursor="hand2",
                             bd=0, padx=12, pady=6,
                             command=self._open_favorites_window)
        fav_btn.pack(side="right", padx=(0, 8), pady=16)
        fav_btn.bind("<Enter>", lambda e: fav_btn.config(fg="white"))
        fav_btn.bind("<Leave>", lambda e: fav_btn.config(fg="#9AA5B4"))

        # Separator
        tk.Frame(bar, bg="#2A3550", width=1).pack(side="right", fill="y", pady=14)

        # User welcome chip (icon + name) — shown prominently
        user_chip = tk.Frame(bar, bg="#0A1128")
        user_chip.pack(side="right", padx=(0, 8), pady=16)

        user_nav = self.icons.get("user_nav")
        tk.Label(user_chip, image=user_nav or "",
                 text="" if user_nav else "👤",
                 font=("Arial", 11), bg="#0A1128").pack(side="left")

        self.welcome_var = tk.StringVar(value="Welcome!")
        tk.Label(user_chip, textvariable=self.welcome_var,
                 font=("Arial", 10, "bold"), fg="white",
                 bg="#0A1128").pack(side="left", padx=(6, 0))

    # ── Favourites window ────────────────────────────────────────────────────
    def _open_favorites_window(self):
        if not self.current_user:
            messagebox.showwarning("Not Logged In", "Please log in to view favourites.")
            return

        win = tk.Toplevel(self)
        try:
            win.transient(self.winfo_toplevel())
        except Exception:
            pass
        win.title("My Favourites")
        win.geometry("560x440")
        win.configure(bg="#F2F4F8")
        win.grab_set()
        self._set_window_icon(win)

        tk.Label(win, text="My Favourites", font=("Arial", 16, "bold"),
                 bg="#F2F4F8", fg="#0A1128").pack(pady=14)

        canvas = tk.Canvas(win, bg="#F2F4F8", highlightthickness=0)
        sb     = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner  = tk.Frame(canvas, bg="#F2F4F8")
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        sb.pack(side="right", fill="y")

        self._refresh_favorites_list(inner, canvas)

    def _refresh_favorites_list(self, inner, canvas):
        for w in inner.winfo_children():
            w.destroy()
        ids = self.collections.get("Favorites", [])
        if not ids:
            tk.Label(inner, text="No favourites yet.", font=("Arial", 11),
                     bg="#F2F4F8", fg="#9AA5B4").pack(pady=30)
        else:
            for pid in ids:
                prop = next((p for p in self.all_properties if p["id"] == pid), None)
                if not prop:
                    continue
                row = tk.Frame(inner, bg="white", highlightthickness=1,
                               highlightbackground="#DDE3EC")
                row.pack(fill="x", pady=4, padx=4)
                tk.Label(row, text=prop["title"], font=("Arial", 10),
                         bg="white", fg="#0A1128").pack(side="left", padx=10, pady=8)

                remove_btn = tk.Button(row, text="Remove", bg="#E63946", fg="white",
                                       relief="flat", font=("Arial", 9), cursor="hand2",
                                       command=lambda p=prop: [
                                           self._toggle_favorite(p),
                                           self._refresh_favorites_list(inner, canvas)])
                remove_btn.pack(side="right", padx=6, pady=6)
                remove_btn.bind("<Enter>", lambda e, b=remove_btn: b.config(bg="#C0272D"))
                remove_btn.bind("<Leave>", lambda e, b=remove_btn: b.config(bg="#E63946"))

                view_btn = tk.Button(row, text="View", bg="#00A859", fg="white",
                                     relief="flat", font=("Arial", 9), cursor="hand2",
                                     command=lambda p=prop: self._show_details(p))
                view_btn.pack(side="right", padx=4, pady=6)
                view_btn.bind("<Enter>", lambda e, b=view_btn: b.config(bg="#007A40"))
                view_btn.bind("<Leave>", lambda e, b=view_btn: b.config(bg="#00A859"))

        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    # ── Sidebar + property grid ──────────────────────────────────────────────
    def _build_sidebar_and_grid(self):
        body = tk.Frame(self, bg="#F2F4F8")
        body.pack(fill="both", expand=True)

        # ── Sidebar ──
        sidebar = tk.Frame(body, bg="white", width=248,
                           highlightthickness=1, highlightbackground="#DDE3EC")
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        def section_lbl(text):
            tk.Label(sidebar, text=text, font=("Arial", 8, "bold"),
                     fg="#9AA5B4", bg="white").pack(anchor="w", padx=20, pady=(14, 5))

        tk.Label(sidebar, text="Search & Filter", font=("Arial", 12, "bold"),
                 fg="#0A1128", bg="white").pack(anchor="w", padx=20, pady=(22, 12))
        tk.Frame(sidebar, bg="#DDE3EC", height=1).pack(fill="x", padx=20)

        # Search box
        section_lbl("SEARCH")
        srch_box = tk.Frame(sidebar, bg="white",
                            highlightthickness=1, highlightbackground="#DDE3EC")
        srch_box.pack(fill="x", padx=20, pady=(0, 10))

        search_ic = self.icons.get("search_icon")
        tk.Label(srch_box, image=search_ic or "",
                 text="" if search_ic else "🔍",
                 bg="white", fg="#9AA5B4",
                 font=("Arial", 10)).pack(side="left", padx=(8, 0))

        self.search_var = tk.StringVar()
        srch_ent = tk.Entry(srch_box, textvariable=self.search_var, relief="flat",
                            bg="white", fg="#9AA5B4", font=("Arial", 10),
                            highlightthickness=0)
        srch_ent.pack(side="left", fill="both", expand=True, ipady=8, padx=6)
        srch_ent.insert(0, PLACEHOLDER)

        def focus_in(e):
            if srch_ent.get() == PLACEHOLDER:
                srch_ent.delete(0, tk.END)
                srch_ent.config(fg="#0A1128")
        def focus_out(e):
            if not srch_ent.get():
                srch_ent.insert(0, PLACEHOLDER)
                srch_ent.config(fg="#9AA5B4")
        srch_ent.bind("<FocusIn>",  focus_in)
        srch_ent.bind("<FocusOut>", focus_out)
        self.search_var.trace_add("write", self._apply_filters)

        # Price range
        section_lbl("PRICE RANGE (₦)")
        price_row = tk.Frame(sidebar, bg="white")
        price_row.pack(fill="x", padx=20, pady=(0, 10))
        self.min_price_var = tk.StringVar()
        self.max_price_var = tk.StringVar()

        def placeholder_entry(parent, var, hint):
            e = tk.Entry(parent, textvariable=var, relief="flat",
                         bg="white", fg="#9AA5B4", font=("Arial", 9),
                         highlightthickness=1, highlightbackground="#DDE3EC", width=10)
            e.insert(0, hint)
            e.bind("<FocusIn>",  lambda ev: (e.delete(0, tk.END), e.config(fg="#0A1128"))
                                 if e.get() == hint else None)
            e.bind("<FocusOut>", lambda ev: (e.insert(0, hint), e.config(fg="#9AA5B4"))
                                 if not e.get() else None)
            return e

        min_e = placeholder_entry(price_row, self.min_price_var, "Min")
        min_e.pack(side="left", ipady=6, padx=(0, 4))
        tk.Label(price_row, text="–", bg="white", fg="#9AA5B4").pack(side="left")
        max_e = placeholder_entry(price_row, self.max_price_var, "Max")
        max_e.pack(side="left", ipady=6, padx=(4, 0))
        self.min_price_var.trace_add("write", self._apply_filters)
        self.max_price_var.trace_add("write", self._apply_filters)

        # Type
        section_lbl("PROPERTY TYPE")
        self.type_var   = tk.StringVar(value="All Types")
        self.type_combo = ttk.Combobox(sidebar, textvariable=self.type_var,
                                       state="readonly", font=("Arial", 10))
        self.type_combo.pack(fill="x", padx=20, pady=(0, 10), ipady=4)
        self.type_combo.bind("<<ComboboxSelected>>", self._apply_filters)

        # Bedrooms
        section_lbl("BEDROOMS")
        self.bed_var = tk.StringVar(value="Any")
        bed_combo = ttk.Combobox(sidebar, textvariable=self.bed_var,
                                 state="readonly", font=("Arial", 10),
                                 values=["Any", "1+", "2+", "3+", "4+", "5+"])
        bed_combo.pack(fill="x", padx=20, pady=(0, 10), ipady=4)
        bed_combo.bind("<<ComboboxSelected>>", self._apply_filters)

        # Bathrooms
        section_lbl("BATHROOMS")
        self.bath_var = tk.StringVar(value="Any")
        bath_combo = ttk.Combobox(sidebar, textvariable=self.bath_var,
                                  state="readonly", font=("Arial", 10),
                                  values=["Any", "1+", "2+", "3+", "4+"])
        bath_combo.pack(fill="x", padx=20, pady=(0, 10), ipady=4)
        bath_combo.bind("<<ComboboxSelected>>", self._apply_filters)

        # Sort
        section_lbl("SORT BY PRICE")
        self.sort_var = tk.StringVar(value="Default")
        sort_combo = ttk.Combobox(sidebar, textvariable=self.sort_var,
                                  state="readonly", font=("Arial", 10),
                                  values=["Default", "Price: Low → High", "Price: High → Low"])
        sort_combo.pack(fill="x", padx=20, pady=(0, 14), ipady=4)
        sort_combo.bind("<<ComboboxSelected>>", self._apply_filters)

        tk.Frame(sidebar, bg="#DDE3EC", height=1).pack(fill="x", padx=20, pady=(4, 14))
        reset_btn = tk.Button(sidebar, text="Reset Filters", font=("Arial", 10),
                              bg="#F2F4F8", fg="#4A5568", relief="flat",
                              cursor="hand2", bd=0, pady=8,
                              command=self._reset_filters)
        reset_btn.pack(fill="x", padx=20)
        reset_btn.bind("<Enter>", lambda e: reset_btn.config(bg="#DDE3EC"))
        reset_btn.bind("<Leave>", lambda e: reset_btn.config(bg="#F2F4F8"))

        self.count_var = tk.StringVar(value="")
        tk.Label(sidebar, textvariable=self.count_var, font=("Arial", 9, "italic"),
                 fg="#9AA5B4", bg="white", wraplength=200)\
            .pack(anchor="w", padx=20, pady=(14, 0))

        # ── Right / grid area ──
        right = tk.Frame(body, bg="#F2F4F8")
        right.pack(side="left", fill="both", expand=True)

        hdr = tk.Frame(right, bg="white", height=48,
                       highlightthickness=1, highlightbackground="#DDE3EC")
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="All Properties", font=("Arial", 11, "bold"),
                 fg="#0A1128", bg="white").pack(side="left", padx=20, pady=12)

        wrap = tk.Frame(right, bg="#F2F4F8")
        wrap.pack(fill="both", expand=True)

        self.cards_canvas = tk.Canvas(wrap, bg="#F2F4F8", highlightthickness=0)
        vscroll = ttk.Scrollbar(wrap, orient="vertical", command=self.cards_canvas.yview)
        self.grid_frame = tk.Frame(self.cards_canvas, bg="#F2F4F8")
        self._grid_win  = self.cards_canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")

        self.cards_canvas.configure(yscrollcommand=vscroll.set)
        self.cards_canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        self.grid_frame.bind("<Configure>",
            lambda e: self.cards_canvas.configure(scrollregion=self.cards_canvas.bbox("all")))
        self.cards_canvas.bind("<Configure>", self._on_canvas_resize)
        self.cards_canvas.bind("<MouseWheel>", self._on_scroll)
        self.cards_canvas.bind("<Button-4>", lambda e: self.cards_canvas.yview_scroll(-1, "units"))
        self.cards_canvas.bind("<Button-5>", lambda e: self.cards_canvas.yview_scroll(1,  "units"))

    def _on_canvas_resize(self, event):
        new_cols = max(1, event.width // (CARD_W + 32))
        self.cards_canvas.itemconfig(self._grid_win, width=event.width)
        if new_cols != self.current_cols:
            self.current_cols = new_cols
            if self._resize_job:
                self.after_cancel(self._resize_job)
            self._resize_job = self.after(150, self._reflow_grid)

    def _reflow_grid(self):
        widgets = list(self.grid_frame.winfo_children())
        if not widgets:
            return
        cols = self.current_cols
        for i in range(cols):
            self.grid_frame.columnconfigure(i, weight=1)
        for idx, widget in enumerate(widgets):
            widget.grid(row=idx // cols, column=idx % cols,
                        padx=16, pady=16, sticky="n")
        self._load_batch()

    # ── Verification banner ───────────────────────────────────────────────────
    def _build_verify_banner(self):
        """Yellow banner shown only to unverified users. Hidden by default."""
        self._verify_banner = tk.Frame(self, bg="#FFF8E1", pady=0)
        # Not packed yet — shown/hidden via refresh_verification_state

        inner = tk.Frame(self._verify_banner, bg="#FFF8E1")
        inner.pack(fill="x", padx=16, pady=6)

        tk.Label(inner,
                 text="⚠  Your email is not verified.",
                 font=("Arial", 9, "bold"),
                 fg="#92400E", bg="#FFF8E1").pack(side="left")
        tk.Label(inner,
                 text="  Verify now to receive alerts on new properties you might love.",
                 font=("Arial", 9),
                 fg="#92400E", bg="#FFF8E1").pack(side="left")

        verify_link = tk.Label(inner,
                               text="  Verify email →",
                               font=("Arial", 9, "bold", "underline"),
                               fg="#B45309", bg="#FFF8E1",
                               cursor="hand2")
        verify_link.pack(side="left")
        verify_link.bind("<Button-1>", lambda e: self.verification.start_account_verification())

        # thin amber bottom border
        tk.Frame(self._verify_banner, bg="#F59E0B", height=1).pack(fill="x", side="bottom")

    # ── Database helpers (used by VerificationService) ────────────────────────
    def _find_user(self, email):
        """Return a user dict from the CSV, or None."""
        db_path = os.path.join(os.path.dirname(__file__), "..", "db", "users.csv")
        try:
            with open(db_path, "r", newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))
            if len(rows) < 2:
                return None
            for row in rows[1:]:
                row = list(row) + [""] * max(0, 10 - len(row))
                if row[1].strip().lower() == email.strip().lower():
                    return {
                        "name":             row[0].strip(),
                        "email":            row[1].strip(),
                        "password":         row[2],
                        "verified":         str(row[3]).strip().lower() in ("1","true","yes","y"),
                        "otp_salt":         row[4],
                        "otp_hash":         row[5],
                        "otp_expiry":       row[6],
                        "otp_issued_epoch": row[7],
                        "otp_issued_mono":  row[8],
                        "otp_attempts":     row[9] or "0",
                    }
        except Exception:
            pass
        return None

    def _update_user(self, email, updater):
        """Apply updater(record) -> record to the matching CSV row."""
        db_path = os.path.join(os.path.dirname(__file__), "..", "db", "users.csv")
        headers = ["Name","Email","Password","Verified","OTPSalt","OTPHash",
                   "OTPExpiry","OTPIssuedEpoch","OTPIssuedMono","OTPAttempts"]
        try:
            with open(db_path, "r", newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))
            if len(rows) < 2:
                return False
            changed = False
            for idx, row in enumerate(rows[1:], start=1):
                row = list(row) + [""] * max(0, 10 - len(row))
                if row[1].strip().lower() == email.strip().lower():
                    user = {
                        "name":             row[0].strip(),
                        "email":            row[1].strip(),
                        "password":         row[2],
                        "verified":         str(row[3]).strip().lower() in ("1","true","yes","y"),
                        "otp_salt":         row[4],
                        "otp_hash":         row[5],
                        "otp_expiry":       row[6],
                        "otp_issued_epoch": row[7],
                        "otp_issued_mono":  row[8],
                        "otp_attempts":     row[9] or "0",
                    }
                    updated = updater(user)
                    rows[idx] = [
                        updated.get("name",""),
                        updated.get("email",""),
                        updated.get("password",""),
                        "1" if updated.get("verified") else "0",
                        updated.get("otp_salt",""),
                        updated.get("otp_hash",""),
                        str(updated.get("otp_expiry","")),
                        str(updated.get("otp_issued_epoch","")),
                        str(updated.get("otp_issued_mono","")),
                        str(updated.get("otp_attempts","0")),
                    ]
                    changed = True
                    break
            if changed:
                with open(db_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    writer.writerows(rows[1:])
            return changed
        except Exception:
            return False

    # ── Auth hooks ────────────────────────────────────────────────────────────
    def on_user_login(self):
        name = (getattr(self.controller, "session", {}) or {}).get("name", "")
        self.welcome_var.set(f"  {name}" if name else "  Welcome!")
        self._load_user_collections()
        self._apply_filters()
        self.refresh_verification_state()

    def refresh_verification_state(self):
        """Show the yellow banner only if the logged-in user is not verified."""
        sess       = getattr(self.controller, "session", {}) or {}
        is_verified = sess.get("is_verified", False)
        email      = sess.get("email", "")

        # If session says verified, double-check against the CSV (just in case)
        if is_verified and email:
            user = self._find_user(email)
            if user:
                is_verified = user.get("verified", False)
                # Keep session in sync
                self.controller.session["is_verified"] = is_verified

        show_banner = bool(email) and not is_verified

        if show_banner:
            # Insert banner between topbar and the body — only once
            if not self._verify_banner.winfo_ismapped():
                self._verify_banner.pack(fill="x", after=self.winfo_children()[0])
        else:
            if self._verify_banner.winfo_ismapped():
                self._verify_banner.pack_forget()

    def _logout(self):
        self.card_images.clear()
        self.refresh_verification_state()   # hides banner on logout
        self.controller.forget_session()
        self.controller.title("Lagos Home Finder")
        self.controller.show_frame("AuthScreen")