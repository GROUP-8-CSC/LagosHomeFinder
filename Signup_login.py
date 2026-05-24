import tkinter as tk
import os
import csv
import json
import hashlib
import re
import secrets
import time
from PIL import Image, ImageTk, ImageDraw, ImageFilter

class AuthScreen(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#FFFFFF")
        self.controller = controller
        self.img_dict = {}
        self.parent = parent
        self.img_dict = {} 
        self.txt_wids = [] 
        self.inp_frms = [] 
        self.cur_tb_sz = 12 
        self.cur_pad = 20 
        self.pw_vis = False 
        # Overlay / visual tweakables
        self.overlay_color = (0, 168, 89)     # RGB for green tint
        self.overlay_alpha = 30               # alpha for main green overlay (0-255)
        self.overlay_blur = 6                 # gaussian blur radius for overlay
        self.overlay_top_frac = 1/3.8         # top line for overlay rectangle (fraction of height)

        # Transition tweakables
        self.transition_duration = 380        # milliseconds for slide animation
        self.transition_step_ms = 15          # ms per animation step
        # image counter to create unique keys so refs aren't overwritten
        self._img_counter = 0
        self.remember_file = os.path.join("db", "remember_me.json")
        
        self.chk_db() 
        
        # Setup split frames inside this screen
        self.lFrm = tk.Frame(self, bg="#0A1128")
        self.lFrm.place(relx=0, rely=0, relwidth=0.5, relheight=1)
        
        # Fake box shadow (Depth)
        self.shad = tk.Frame(self, bg="#E0E0E0", width=3)
        self.shad.place(relx=0.5, rely=0, relheight=1, anchor="nw")
        self.shad2 = tk.Frame(self, bg="#F0F0F0", width=2)
        self.shad2.place(relx=0.5, rely=0, relheight=1, x=3, anchor="nw")
        
        self.rFrm = tk.Frame(self, bg="#FFFFFF")
        self.rFrm.place(relx=0.5, rely=0, relwidth=0.5, relheight=1, x=5) 

        self.mk_l_pnl()
        self.mk_r_pnl()

        self.lFrm.bind("<Configure>", self.rsz_bg)
        self.rFrm.bind("<Configure>", self.rsz_r_pnl)

    def chk_db(self):
        self.db_file = "db/users.csv"
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        if not os.path.exists(self.db_file):
            with open(self.db_file, mode='w', newline='') as f:
                csv.writer(f).writerow(["Name", "Email", "Password", "Verified", "OTPSalt", "OTPHash", "OTPExpiry", "OTPIssuedEpoch", "OTPIssuedMono", "OTPAttempts"])

    def _user_headers(self):
        return ["Name", "Email", "Password", "Verified", "OTPSalt", "OTPHash", "OTPExpiry", "OTPIssuedEpoch", "OTPIssuedMono", "OTPAttempts"]

    def _row_to_user(self, row):
        row = list(row) + [""] * max(0, 10 - len(row))
        return {
            "name": row[0].strip(),
            "email": row[1].strip(),
            "password": row[2],
            "verified": str(row[3]).strip().lower() in ("1", "true", "yes", "y"),
            "otp_salt": row[4],
            "otp_hash": row[5],
            "otp_expiry": row[6],
            "otp_issued_epoch": row[7],
            "otp_issued_mono": row[8],
            "otp_attempts": row[9] or "0",
        }

    def _user_to_row(self, user):
        return [
            user.get("name", ""),
            user.get("email", ""),
            user.get("password", ""),
            "1" if user.get("verified") else "0",
            user.get("otp_salt", ""),
            user.get("otp_hash", ""),
            str(user.get("otp_expiry", "")),
            str(user.get("otp_issued_epoch", "")),
            str(user.get("otp_issued_mono", "")),
            str(user.get("otp_attempts", "0")),
        ]

    def _read_all_users(self):
        with open(self.db_file, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        if not rows:
            return []
        return rows[1:]

    def _write_all_users(self, rows):
        with open(self.db_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(self._user_headers())
            writer.writerows(rows)

    def _update_user_by_email(self, email, updater):
        rows = self._read_all_users()
        changed = False
        for idx, row in enumerate(rows):
            if len(row) >= 2 and row[1].strip().lower() == email.strip().lower():
                user = self._row_to_user(row)
                updated = updater(user)
                rows[idx] = self._user_to_row(updated)
                changed = True
                break
        if changed:
            self._write_all_users(rows)
        return changed

    def _find_user_by_email(self, email):
        try:
            for row in self._read_all_users():
                if len(row) >= 2 and row[1].strip().lower() == email.strip().lower():
                    return self._row_to_user(row)
        except Exception:
            pass
        return None

    def _hash_otp(self, salt, code):
        return hashlib.sha256(f"{salt}:{code}".encode("utf-8")).hexdigest()

    def load_pic(self, base_pth, size=None):
        # added .paint just in case you didn't rename it to .png
        exts = ['.png', '.jpg', '.jpeg', '.paint']
        for e in exts:
            if os.path.exists(base_pth + e):
                try: 
                    img = Image.open(base_pth + e)
                    if size:
                        img = img.resize(size, Image.Resampling.LANCZOS)
                    return img
                except: pass
        return None

    def mk_l_pnl(self):
        self.cnv = tk.Canvas(self.lFrm, highlightthickness=0, takefocus=0)
        self.cnv.pack(fill="both", expand=True)

        self.raw_bg = self.load_pic("assets/left_bg")
        self.bg_id = self.cnv.create_image(0, 0, anchor="nw")

        self.t1 = self.cnv.create_text(40, 240, text="Find Your", font=("Arial", 32, "bold"), fill="#FFFFFF", anchor="w")
        self.t2 = self.cnv.create_text(40, 290, text="Perfect", font=("Arial", 32, "bold"), fill="#FFFFFF", anchor="w")
        self.t3 = self.cnv.create_text(40, 340, text="Lagos Home", font=("Arial", 32, "bold"), fill="#00A859", anchor="w")

    def rsz_bg(self, evt):
        if not self.raw_bg: return
        cw, ch = evt.width, evt.height
        iw, ih = self.raw_bg.size
        
        r = max(cw/iw, ch/ih)
        new_w, new_h = int(iw * r), int(ih * r)
        
        rsz_img = self.raw_bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        lft = (new_w - cw) // 2
        top = (new_h - ch) // 2
        rht = (new_w + cw) // 2
        bot = (new_h + ch) // 2
        
        crp_img = rsz_img.crop((lft, top, rht, bot)).convert("RGBA")
        
        # Main green overlay — only from overlay_top_frac downwards, with optional blur
        overlay = Image.new('RGBA', crp_img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        top_y = int(ch * self.overlay_top_frac)
        draw.rectangle([(0, top_y), (cw, ch)], fill=(self.overlay_color[0], self.overlay_color[1], self.overlay_color[2], self.overlay_alpha))

        # Apply blur to the overlay if requested (creates a softer tint)
        if self.overlay_blur and self.overlay_blur > 0:
            overlay = overlay.filter(ImageFilter.GaussianBlur(radius=self.overlay_blur))

        crp_img = Image.alpha_composite(crp_img, overlay)

        # subtle white wash then a soft dark vignette to keep text readable
        wash = Image.new('RGBA', crp_img.size, (255, 255, 255, 10))
        crp_img = Image.alpha_composite(crp_img, wash)

        vign = Image.new('RGBA', crp_img.size, (0, 0, 0, 80))
        crp_img = Image.alpha_composite(crp_img, vign)
        
        self.fnl_bg = ImageTk.PhotoImage(crp_img)
        self.cnv.itemconfig(self.bg_id, image=self.fnl_bg)
        
        ratio = ch / 600.0
        new_fnt = max(14, int(32 * ratio))
        self.cnv.itemconfig(self.t1, font=("Arial", new_fnt, "bold"))
        self.cnv.itemconfig(self.t2, font=("Arial", new_fnt, "bold"))
        self.cnv.itemconfig(self.t3, font=("Arial", new_fnt, "bold"))
        
        self.cnv.coords(self.t1, 40, 240 * ratio)
        self.cnv.coords(self.t2, 40, 290 * ratio)
        self.cnv.coords(self.t3, 40, 340 * ratio)

    def mk_r_pnl(self):
        self.c_frm = tk.Frame(self.rFrm, bg="#FFFFFF")
        self.c_frm.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.75, relheight=0.85)

        # -- NEW LOGO & TEXT ASSEMBLY --
        lg_cont = tk.Frame(self.c_frm, bg="#FFFFFF")
        lg_cont.pack(pady=(0, 20))
        
        # Load the logo icon shrunk to 40x40
        lg_img = self.load_pic("assets/logo_icon", size=(40, 40))
        if lg_img:
            self.m_lg = ImageTk.PhotoImage(lg_img)
            tk.Label(lg_cont, image=self.m_lg, bg="#FFFFFF").pack(side="left", padx=(0, 10))
            
        # The text next to the logo
        txt_cont = tk.Frame(lg_cont, bg="#FFFFFF")
        txt_cont.pack(side="left")
        self.lg_t1 = tk.Label(txt_cont, text="LAGOS", font=("Arial", 16, "bold"), fg="#000000", bg="#FFFFFF")
        self.lg_t1.pack(anchor="w", pady=0)
        self.txt_wids.append((self.lg_t1, 16, "bold")) 
        
        self.lg_t2 = tk.Label(txt_cont, text="HOME FINDER", font=("Arial", 12, "bold"), fg="#00A859", bg="#FFFFFF")
        self.lg_t2.pack(anchor="w")
        self.txt_wids.append((self.lg_t2, 12, "bold")) 

        self.t_frm = tk.Frame(self.c_frm, bg="#FFFFFF")
        self.t_frm.pack(fill="x", pady=(0, 40)) 

        s_frm = tk.Frame(self.t_frm, bg="#FFFFFF")
        s_frm.pack(side="left", expand=True, fill="x")
        self.su_lbl = tk.Label(s_frm, text="Sign Up", font=("Arial", 12, "bold"), fg="#00A859", bg="#FFFFFF", cursor="hand2")
        self.su_lbl.pack(pady=(0, 5))
        self.txt_wids.append((self.su_lbl, 12, "bold")) 
        self.su_lin = tk.Frame(s_frm, bg="#00A859", height=2)
        self.su_lin.pack(fill="x") 

        l_frm = tk.Frame(self.t_frm, bg="#FFFFFF")
        l_frm.pack(side="right", expand=True, fill="x")
        self.li_lbl = tk.Label(l_frm, text="Log In", font=("Arial", 12), fg="#7A7A7A", bg="#FFFFFF", cursor="hand2")
        self.li_lbl.pack(pady=(0, 5))
        self.txt_wids.append((self.li_lbl, 12, ""))
        self.li_lin = tk.Frame(l_frm, bg="#E0E0E0", height=1)
        self.li_lin.pack(fill="x")

        self.su_lbl.bind("<Button-1>", lambda e: self.smth_sw("su"))
        self.li_lbl.bind("<Button-1>", lambda e: self.smth_sw("li"))

        # Create a dedicated container for the two forms so we can animate them
        self.forms_wrap = tk.Frame(self.c_frm, bg="#FFFFFF")
        self.forms_wrap.pack(fill="both", expand=True)

        # Sign-up form (placed initially at x=0)
        self.su_form = tk.Frame(self.forms_wrap, bg="#FFFFFF")
        self.su_form.place(x=0, y=0, relwidth=1, relheight=1)
        self.nm_frm, self.n_ent, _ = self.mk_inp(self.su_form, "assets/user_icon", "Full Name")
        self.em_frm, self.e_ent, _ = self.mk_inp(self.su_form, "assets/mail_icon", "Email Address")
        self.pw_frm, self.p_ent, self.pw_eye = self.mk_inp(self.su_form, "assets/lock_icon", "Password", True, "assets/eye_icon")
        # Enter key submits whichever form is active
        for _ent in (self.n_ent, self.e_ent, self.p_ent):
            _ent.bind("<Return>", lambda e: self.do_auth())

        # Log-in form (start off-screen to the right)
        self.li_form = tk.Frame(self.forms_wrap, bg="#FFFFFF")
        self.li_form.place(x=10000, y=0, relwidth=1, relheight=1)
        # Note: login only needs email + password
        self.li_em_frm, self.li_e_ent, _ = self.mk_inp(self.li_form, "assets/mail_icon", "Email Address")
        self.li_pw_frm, self.li_p_ent, self.li_pw_eye = self.mk_inp(self.li_form, "assets/lock_icon", "Password", True, "assets/eye_icon")
        # Enter key submits login form
        for _ent in (self.li_e_ent, self.li_p_ent):
            _ent.bind("<Return>", lambda e: self.do_auth())

        self.remember_row = tk.Frame(self.li_form, bg="#FFFFFF")
        self.remember_row.pack(fill="x", pady=(0, 10))
        self.remember_var = tk.BooleanVar(value=False)
        self.remember_chk = tk.Checkbutton(
            self.remember_row,
            text="Remember me",
            variable=self.remember_var,
            bg="#FFFFFF",
            fg="#7A7A7A",
            activebackground="#FFFFFF",
            activeforeground="#00A859",
            selectcolor="#FFFFFF",
            font=("Arial", 10),
            relief="flat",
            cursor="hand2",
            highlightthickness=0,
            highlightbackground="#FFFFFF",
            highlightcolor="#FFFFFF",
            bd=0,
            overrelief="flat",
            takefocus=0,
        )
        self.remember_chk.pack(anchor="w")

        self._prefill_remembered_login()

        self.msg_lbl = tk.Label(self.c_frm, text="", font=("Arial", 10), bg="#FFFFFF")
        self.msg_lbl.pack(fill="x")
        self.txt_wids.append((self.msg_lbl, 10, ""))

        # Buttons live in the main control column so they don't jump during the slide
        self.b1 = tk.Button(self.c_frm, text="Create Account", font=("Arial", 12, "bold"), bg="#00A859", fg="white", relief="flat", cursor="hand2", takefocus=0, activebackground="#007F43", activeforeground="white", command=self.do_auth)
        self.b1.pack(fill="x", pady=(10, 5))
        self.txt_wids.append((self.b1, 12, "bold"))

        f_frm = tk.Frame(self.c_frm, bg="#FFFFFF")
        f_frm.pack(pady=(5, 0)) 
        self.q_lbl = tk.Label(f_frm, text="Already have an account?", font=("Arial", 10), fg="#7A7A7A", bg="#FFFFFF")
        self.q_lbl.pack(side="left")
        self.txt_wids.append((self.q_lbl, 10, ""))
        
        self.a_lbl = tk.Label(f_frm, text="Log In", font=("Arial", 10, "bold"), fg="#00A859", bg="#FFFFFF", cursor="hand2")
        self.a_lbl.pack(side="left", padx=(5, 0))
        self.txt_wids.append((self.a_lbl, 10, "bold"))
        self.a_lbl.bind("<Button-1>", lambda e: self.smth_sw("li"))

    def smth_sw(self, tb):
        self.c_frm.update_idletasks()
        # start a smooth slide animation between forms
        self.start_form_slide(tb)

    def sw_tab(self, tb):
        self.set_msg("", "black")
        if tb == "su":
            self.su_lbl.config(fg="#00A859", font=("Arial", self.cur_tb_sz, "bold"))
            self.su_lin.config(bg="#00A859", height=2)
            self.li_lbl.config(fg="#7A7A7A", font=("Arial", self.cur_tb_sz, ""))
            self.li_lin.config(bg="#E0E0E0", height=1)
            self.b1.config(text="Create Account")
            self.q_lbl.config(text="Already have an account?")
            self.a_lbl.config(text="Log In")
            self.a_lbl.bind("<Button-1>", lambda e: self.smth_sw("li"))
            
            # ensure signup's name field is visible
            if not self.nm_frm.winfo_ismapped():
                self.nm_frm.pack(before=self.em_frm, fill="x", pady=(0, self.cur_pad))
        else:
            self.li_lbl.config(fg="#00A859", font=("Arial", self.cur_tb_sz, "bold"))
            self.li_lin.config(bg="#00A859", height=2)
            self.su_lbl.config(fg="#7A7A7A", font=("Arial", self.cur_tb_sz, ""))
            self.su_lin.config(bg="#E0E0E0", height=1)
            self.b1.config(text="Log In")
            self.q_lbl.config(text="Don't have an account?")
            self.a_lbl.config(text="Sign Up")
            self.a_lbl.bind("<Button-1>", lambda e: self.smth_sw("su"))
            
            if self.nm_frm.winfo_ismapped():
                self.nm_frm.pack_forget()

        # update the main button label
        self.b1.config(text=("Create Account" if tb == "su" else "Log In"))

        # update footer labels
        if tb == "su":
            self.q_lbl.config(text="Already have an account?")
            self.a_lbl.config(text="Log In")
        else:
            self.q_lbl.config(text="Don't have an account?")
            self.a_lbl.config(text="Sign Up")

    def start_form_slide(self, tb):
        """Animate sliding between signup and login forms over configured duration."""
        self.forms_wrap.update_idletasks()
        w = self.forms_wrap.winfo_width() or self.forms_wrap.winfo_reqwidth() or self.c_frm.winfo_width()
        if not w or w < 10:
            # fallback: immediately switch
            self.sw_tab(tb)
            if tb == 'li':
                self.su_form.place_configure(x=-w)
                self.li_form.place_configure(x=0)
            else:
                self.su_form.place_configure(x=0)
                self.li_form.place_configure(x=w)
            return

        steps = max(1, int(self.transition_duration / self.transition_step_ms))

        # animation functions
        if tb == 'li':
            # su -> left, li -> from right to 0
            def step_fn(i):
                prog = i / steps
                su_x = int(-prog * w)
                li_x = int(w - prog * w)
                self.su_form.place_configure(x=su_x)
                self.li_form.place_configure(x=li_x)
                if i >= steps:
                    self.su_form.place_configure(x=-w)
                    self.li_form.place_configure(x=0)
                    self.sw_tab('li')
                else:
                    self.after(self.transition_step_ms, lambda: step_fn(i + 1))

            # initialize positions
            self.su_form.place_configure(x=0)
            self.li_form.place_configure(x=w)
            self.after(1, lambda: step_fn(1))
        else:
            # li -> right, su -> from left to 0
            def step_fn(i):
                prog = i / steps
                su_x = int(-w + prog * w)
                li_x = int(prog * w)
                self.su_form.place_configure(x=su_x)
                self.li_form.place_configure(x=li_x)
                if i >= steps:
                    self.su_form.place_configure(x=0)
                    self.li_form.place_configure(x=w)
                    self.sw_tab('su')
                else:
                    self.after(self.transition_step_ms, lambda: step_fn(i + 1))

            # initialize positions
            self.su_form.place_configure(x=-w)
            self.li_form.place_configure(x=0)
            self.after(1, lambda: step_fn(1))


    def do_auth(self):
        self.set_msg("", "black")
        mde = self.b1.cget("text")
        # choose the correct fields depending on whether we're creating an account
        if mde == "Create Account":
            n = self.n_ent.get().strip()
            e = self.e_ent.get().strip()
            p = self.p_ent.get().strip()
        else:
            # login form uses separate fields
            n = ""
            e = self.li_e_ent.get().strip()
            p = self.li_p_ent.get().strip()
        
        if n == "Full Name": n = ""
        if e == "Email Address": e = ""
        if p == "Password": p = ""

        if not e or not p:
            self.set_msg("All fields are required!", "#E63946")
            return
            
        email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(email_regex, e):
            self.set_msg("Invalid email format!", "#E63946")
            return
            
        if len(p) < 4:
            self.set_msg("Password too short!", "#E63946")
            return

        if mde == "Create Account":
            if not n:
                self.set_msg("Full name is required!", "#E63946")
                return
            if not re.match(r"^[a-zA-Z\s]+$", n):
                self.set_msg("Name can only contain letters!", "#E63946")
                return

            try:
                with open(self.db_file, "r") as f:
                    for r in csv.reader(f):
                        if r and r[1] == e:
                            self.set_msg("Email already registered!", "#E63946")
                            return
            except: pass
            
            with open(self.db_file, "a", newline='', encoding="utf-8") as f:
                csv.writer(f).writerow([n, e, p, "0", "", "", "", "", "", "0"])
            
            self.set_msg("Account Created! Please Log In.", "#00A859")
            self.after(1000, lambda: self.smth_sw("li")) 
            
        else: # Log In Logic
            fnd = False
            try:
                with open(self.db_file, "r") as f:
                    for r in csv.reader(f):
                        if r and len(r) >= 3:
                            user = self._row_to_user(r)
                            if user["email"].lower() == e.lower():
                                fnd = True
                                if user["password"] == p:
                                    self.set_msg(f"Welcome back, {user['name']}!", "#00A859")

                                    if self.remember_var.get():
                                        self.controller.save_remembered_session(user["name"], user["email"])
                                    else:
                                        self.controller.forget_session()
                                    
                                    self.controller.session["name"] = user["name"]
                                    self.controller.session["email"] = user["email"]
                                    self.controller.session["is_verified"] = user["verified"]
                                    
                                    # Tell Dashboard to update its UI and verification state
                                    self.controller.frames["DashboardScreen"].on_user_login()
                                    
                                    # Switch screen
                                    self.after(800, lambda: self.controller.show_frame("DashboardScreen"))
                                    return
                                else:
                                    self.set_msg("Incorrect Password!", "#E63946")
                                    return
            except: pass
            if not fnd:
                self.set_msg("User not found!", "#E63946")

    def set_msg(self, txt, col):
        self.msg_lbl.config(text=txt, fg=col)

    def _prefill_remembered_login(self):
        if not os.path.exists(self.remember_file):
            return

        try:
            with open(self.remember_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("remember") and data.get("email"):
                self.li_e_ent.delete(0, tk.END)
                self.li_e_ent.insert(0, data["email"])
                self.remember_var.set(True)
        except Exception:
            pass

    def mk_inp(self, p, icn_base, plchld, is_pw=False, r_icn_base=None):
        b_frm = tk.Frame(p, bg="#FFFFFF", highlightbackground="#E0E0E0", highlightthickness=1, bd=0)
        b_frm.pack(fill="x", pady=(0, 20)) 
        self.inp_frms.append(b_frm) 

        i_img = self.load_pic(icn_base, size=(22, 22))
        if i_img:
            i_tk = ImageTk.PhotoImage(i_img)
            key = f"{icn_base}_{self._img_counter}"
            self._img_counter += 1
            self.img_dict[key] = i_tk
            lbl_i = tk.Label(b_frm, image=i_tk, bg="#FFFFFF")
            lbl_i.image = i_tk
            lbl_i.pack(side="left", padx=(15, 5))

        e = tk.Entry(b_frm, relief="flat", bg="#FFFFFF", fg="#333333", font=("Arial", 11), highlightthickness=0)
        e.insert(0, plchld)
        e.pack(side="left", fill="both", expand=True, padx=5, ipady=8)
        self.txt_wids.append((e, 11, "")) 

        def f_in(ev):
            if e.get() == plchld:
                e.delete(0, tk.END)
                if is_pw and not self.pw_vis: e.config(show="*")
                
        def f_out(ev):
            if not e.get():
                e.insert(0, plchld)
                if is_pw: e.config(show="")

        e.bind("<FocusIn>", f_in)
        e.bind("<FocusOut>", f_out)

        eye_lbl = None
        if r_icn_base:
            eye_lbl = tk.Label(b_frm, bg="#FFFFFF", cursor="hand2")
            eye_lbl.pack(side="right", padx=(5, 15))

            # load primary and alternate (unhidden) icons if available
            open_img = self.load_pic(r_icn_base, size=(22, 22))
            alt_base = r_icn_base.replace("eye_icon", "eye_unhid_icon")
            close_img = self.load_pic(alt_base, size=(22, 22))

            # store images with unique keys and attach to label to keep refs
            if open_img:
                open_tk = ImageTk.PhotoImage(open_img)
                k1 = f"{r_icn_base}_open_{self._img_counter}"
                self._img_counter += 1
                self.img_dict[k1] = open_tk
                eye_lbl.image = open_tk
                eye_lbl.config(image=open_tk)
            if close_img:
                close_tk = ImageTk.PhotoImage(close_img)
                k2 = f"{r_icn_base}_close_{self._img_counter}"
                self._img_counter += 1
                self.img_dict[k2] = close_tk

            # local toggle so each password field has its own eye control
            def local_toggle(ev, ent=e, lbl=eye_lbl, open_t=open_img, close_t=close_img):
                if ent.get() != "Password":
                    if ent.cget('show') == "*":
                        ent.config(show="")
                        if close_t:
                            tkimg = ImageTk.PhotoImage(close_t)
                            k = f"{r_icn_base}_close_{self._img_counter}"
                            self._img_counter += 1
                            self.img_dict[k] = tkimg
                            lbl.image = tkimg
                            lbl.config(image=tkimg)
                    else:
                        ent.config(show="*")
                        if open_img:
                            tkimg = ImageTk.PhotoImage(open_img)
                            k = f"{r_icn_base}_open_{self._img_counter}"
                            self._img_counter += 1
                            self.img_dict[k] = tkimg
                            lbl.image = tkimg
                            lbl.config(image=tkimg)

            eye_lbl.bind("<Button-1>", local_toggle)

        return b_frm, e, eye_lbl

    def tg_pw(self, e_widg):
        self.pw_vis = not self.pw_vis
        
        # Only mask/unmask the text if it is NOT the placeholder word
        if e_widg.get() != "Password":
            if self.pw_vis:
                e_widg.config(show="")
            else:
                e_widg.config(show="*")
                
        # Update the icon unconditionally
        self.upd_eye_icn()

    def upd_eye_icn(self):
        # Uses your new eye_unhid_icon file
        tgt_icn = "assets/eye_unhid_icon" if self.pw_vis else "assets/eye_icon"
        
        # force exact same 22x22 scale so it doesn't jump in size
        ri_img = self.load_pic(tgt_icn, size=(22, 22)) 
        
        if ri_img:
            ri_tk = ImageTk.PhotoImage(ri_img)
            self.img_dict["eye_curr"] = ri_tk 
            self.ey_lbl.config(image=ri_tk, text="")
        else:
            cur_sz = max(8, int(11 * (self.winfo_height() / 600.0))) if self.winfo_height() > 10 else 11
            txt = "[O]" if self.pw_vis else "[-]"
            self.ey_lbl.config(text=txt, font=("Arial", cur_sz), fg="#A0A0A0")

    def rsz_r_pnl(self, evt):
        if evt.widget != self.rFrm: return 
        
        ratio = evt.height / 600.0
        
        for widg, base_sz, weight in self.txt_wids:
            new_sz = max(8, int(base_sz * ratio)) 
            if widg in (self.su_lbl, self.li_lbl):
                self.cur_tb_sz = new_sz 
            
            if weight and (widg != self.li_lbl and widg != self.su_lbl):
                widg.config(font=("Arial", new_sz, weight))
            elif widg not in (self.li_lbl, self.su_lbl):
                widg.config(font=("Arial", new_sz))
                
        if self.b1.cget("text") == "Create Account":
            self.su_lbl.config(font=("Arial", self.cur_tb_sz, "bold"))
            self.li_lbl.config(font=("Arial", self.cur_tb_sz, ""))
        else:
            self.li_lbl.config(font=("Arial", self.cur_tb_sz, "bold"))
            self.su_lbl.config(font=("Arial", self.cur_tb_sz, ""))

        self.cur_pad = int(20 * ratio) 
        self.t_frm.pack_configure(pady=(0, self.cur_pad * 2))
        
        for f in self.inp_frms:
            if f.winfo_ismapped():
                f.pack_configure(pady=(0, self.cur_pad))
            
        self.b1.pack_configure(pady=(self.cur_pad, int(5 * ratio)))
        
        if hasattr(self, 'ey_lbl') and not self.ey_lbl.cget("image"):
            self.upd_eye_icn()