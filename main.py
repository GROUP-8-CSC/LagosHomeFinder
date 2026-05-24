import tkinter as tk
import os
import json
from PIL import Image, ImageTk

from screens.Landing import LandingScreen
from screens.Signup_login import AuthScreen
from screens.Dashboard import DashboardScreen

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Lagos Home Finder")
        self.geometry("900x600") 
        self.configure(bg="#FFFFFF")
        
        # --- GLOBAL SESSION STATE
        # This acts like browser cookies, remembering the user across screens
        self.session = {
            "name": "",
            "email": "",
            "is_verified": False,
            "theme": "light"
        }
        self.remember_file = os.path.join("db", "remember_me.json")
        self.start_page = "LandingScreen"
        self._load_remembered_session()
        
        try:
            for ext in [".png", ".jpg", ".ico"]:
                if os.path.exists("assets/logo_icon" + ext):
                    app_icn = tk.PhotoImage(file="assets/logo_icon" + ext)
                    self.iconphoto(False, app_icn)
                    break
        except: pass

        self.container = tk.Frame(self)
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        
        for F in (LandingScreen, AuthScreen, DashboardScreen):
            page_name = F.__name__
            frame = F(parent=self.container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        if self.session["name"]:
            dashboard = self.frames.get("DashboardScreen")
            if dashboard and hasattr(dashboard, "on_user_login"):
                dashboard.on_user_login()
            self.start_page = "DashboardScreen"

        self.run_loader()

    def _load_remembered_session(self):
        if not os.path.exists(self.remember_file):
            return

        try:
            with open(self.remember_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("remember") and data.get("name") and data.get("email"):
                self.session["name"] = data["name"]
                self.session["email"] = data["email"]
                self.session["is_verified"] = False
                self.start_page = "DashboardScreen"
        except Exception:
            self._clear_remembered_session()

    def _clear_remembered_session(self):
        try:
            if os.path.exists(self.remember_file):
                os.remove(self.remember_file)
        except Exception:
            pass

    def save_remembered_session(self, name, email):
        os.makedirs(os.path.dirname(self.remember_file), exist_ok=True)
        with open(self.remember_file, "w", encoding="utf-8") as f:
            json.dump({"remember": True, "name": name, "email": email}, f)

    def forget_session(self):
        self.session["name"] = ""
        self.session["email"] = ""
        self.session["is_verified"] = False
        self._clear_remembered_session()

    def show_frame(self, page_name):
        frame = self.frames[page_name]
        frame.tkraise()

    def run_loader(self):
        self.load_frm = tk.Frame(self, bg="#FFFFFF")
        self.load_frm.place(relwidth=1, relheight=1) 

        try:
            img = Image.open("assets/logo_icon.png").resize((90, 90), Image.Resampling.LANCZOS)
            self.load_img = ImageTk.PhotoImage(img)
            tk.Label(self.load_frm, image=self.load_img, bg="#FFFFFF").place(relx=0.5, rely=0.42, anchor="center")
        except: pass

        self.load_txt = tk.Label(self.load_frm, text="Loading Lagos Home Finder...", font=("Arial", 12, "bold"), fg="#00A859", bg="#FFFFFF")
        self.load_txt.place(relx=0.5, rely=0.55, anchor="center")

        self.pulse_anim(0)
        self.after(2500, self.kill_loader)

    def pulse_anim(self, step):
        if not hasattr(self, 'load_txt') or not self.load_txt.winfo_exists(): return
        colors = ["#00A859", "#11BA6A", "#22CC7B", "#44E299", "#22CC7B", "#11BA6A"]
        self.load_txt.config(fg=colors[step % len(colors)])
        self.after(150, lambda: self.pulse_anim(step + 1))

    def kill_loader(self):
        self.load_frm.destroy()
        self.show_frame(self.start_page)

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()