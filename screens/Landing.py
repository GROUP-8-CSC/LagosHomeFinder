import tkinter as tk
import os
from PIL import Image, ImageTk, ImageDraw

class LandingScreen(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="#0A1128")
        self.controller = controller
        
        self.cnv = tk.Canvas(self, highlightthickness=0)
        self.cnv.pack(fill="both", expand=True)

        # --- CAROUSEL SETUP ---
        self.bg_list = []
        self.bg_idx = 0
        self.cur_w = 900 
        self.cur_h = 600
        
        # Auto-create the carousel folder so it doesn't crash on startup
        car_dir = "assets/Bg_carousel"
        os.makedirs(car_dir, exist_ok=True)
        
        # Grab all images in the folder regardless of their names
        for f in os.listdir(car_dir):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                self.bg_list.append(os.path.join(car_dir, f))
        
        # Fallback if folder is empty (uses your left panel image)
        if not self.bg_list:
            for ext in ['.png', '.jpg', '.jpeg']:
                if os.path.exists("assets/left_bg" + ext):
                    self.bg_list.append("assets/left_bg" + ext)
                    break

        if self.bg_list:
            try: self.raw_bg = Image.open(self.bg_list[self.bg_idx])
            except: self.raw_bg = None
        else:
            self.raw_bg = None

        self.bg_id = self.cnv.create_image(0, 0, anchor="nw")

        # Landing Page Text
        self.t1 = self.cnv.create_text(450, 250, text="Welcome to Lagos Home Finder", font=("Arial", 38, "bold"), fill="#FFFFFF", justify="center")
        self.t2 = self.cnv.create_text(450, 310, text="Discover the most exclusive properties in the heart of the city.", font=("Arial", 16), fill="#E0E0E0", justify="center")

        self.btn = tk.Button(
            self, text="Get Started", font=("Arial", 14, "bold"), 
            bg="#00A859", fg="white", activebackground="#007F43", activeforeground="white", 
            relief="flat", bd=0, highlightthickness=0, highlightbackground="#00A859",
            highlightcolor="#00A859", overrelief="flat",
            takefocus=0, cursor="hand2", padx=30, pady=10,
            command=lambda: controller.show_frame("AuthScreen") 
        )
        self.btn_win = self.cnv.create_window(450, 400, window=self.btn)

        # Button Hover Animation
        self.btn.bind("<Enter>", lambda e: self.btn.config(bg="#00D16F"))
        self.btn.bind("<Leave>", lambda e: self.btn.config(bg="#00A859"))

        self.bind("<Configure>", self.on_rsz)
        
        # Start the 3-second (3000ms) carousel loop
        self.after(3000, self.cyc_bg)

    def cyc_bg(self):
        # Only cycle if there is more than 1 image
        if len(self.bg_list) > 1:
            self.bg_idx = (self.bg_idx + 1) % len(self.bg_list)
            try:
                self.raw_bg = Image.open(self.bg_list[self.bg_idx])
                self.upd_bg(self.cur_w, self.cur_h) # resize new image to fit window
            except: pass
        
        # loop it again
        self.after(3000, self.cyc_bg)

    def on_rsz(self, evt):
        # Save current window size so the carousel knows how big to make the next image
        self.cur_w, self.cur_h = evt.width, evt.height
        self.upd_bg(self.cur_w, self.cur_h)

    def upd_bg(self, cw, ch):
        if not self.raw_bg or cw <= 1 or ch <= 1: return
        
        iw, ih = self.raw_bg.size
        r = max(cw/iw, ch/ih)
        new_w, new_h = int(iw * r), int(ih * r)
        rsz_img = self.raw_bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        lft, top = (new_w - cw) // 2, (new_h - ch) // 2
        crp_img = rsz_img.crop((lft, top, lft + cw, top + ch)).convert("RGBA")
        
        # Dark overlay to keep text readable regardless of the image
        overlay = Image.new('RGBA', crp_img.size, (0, 0, 0, 140))
        crp_img = Image.alpha_composite(crp_img, overlay)
        
        self.fnl_bg = ImageTk.PhotoImage(crp_img)
        self.cnv.itemconfig(self.bg_id, image=self.fnl_bg)
        
        # Dynamic responsive layout
        ratio = ch / 600.0
        self.cnv.itemconfig(self.t1, font=("Arial", max(20, int(38 * ratio)), "bold"))
        self.cnv.itemconfig(self.t2, font=("Arial", max(10, int(16 * ratio))))
        
        self.cnv.coords(self.t1, cw/2, ch * 0.4)
        self.cnv.coords(self.t2, cw/2, ch * 0.5)
        self.cnv.coords(self.btn_win, cw/2, ch * 0.65)