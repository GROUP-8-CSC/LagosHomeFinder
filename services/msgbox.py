import tkinter as tk

# A Simple module created for popups
class MessageBoxService:
    def __init__(self, master):
        self.master = master

    def _build_popup(self, title, message, accent="#00A859", subtitle=None, width=440,
                     buttons=None, on_close=None):
        window = tk.Toplevel(self.master)
        window.title(title)
        window.configure(bg="#FFFFFF")
        window.resizable(False, False)
        window.transient(self.master.winfo_toplevel())
        window.grab_set()

        # Center on screen
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()
        x = (screen_w // 2) - (width // 2)
        y = (screen_h // 2) - 160
        window.geometry(f"{width}x280+{x}+{y}")

        # Accent bar
        top_bar = tk.Frame(window, bg=accent, height=6)
        top_bar.pack(fill="x", side="top")

        # Body
        body = tk.Frame(window, bg="#FFFFFF")
        body.pack(fill="both", expand=True, padx=24, pady=24)

        tk.Label(body, text=title, font=("Arial", 16, "bold"), fg="#0A1128", bg="#FFFFFF", anchor="w").pack(fill="x", pady=(0, 10))
        tk.Label(body, text=message, font=("Arial", 11), fg="#333333", bg="#FFFFFF", justify="left", wraplength=width - 48).pack(anchor="w", fill="x")
        if subtitle:
            tk.Label(body, text=subtitle, font=("Arial", 10), fg="#7A7A7A", bg="#FFFFFF", justify="left", wraplength=width - 48).pack(anchor="w", fill="x", pady=(8, 0))

        # Footer with buttons
        footer = tk.Frame(window, bg="#F4F6F8", height=60)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        btn_frame = tk.Frame(footer, bg="#F4F6F8")
        btn_frame.pack(side="right", padx=16, pady=12)

        def close_and_run(callback):
            window.grab_release()
            window.destroy()
            if callable(callback):
                callback()

        # Create buttons from provided list or default
        if not buttons:
            buttons = [{"text": "OK", "callback": None, "bg": accent, "fg": "#FFFFFF"}]

        for btn in buttons:
            cb = btn.get("callback")
            tk.Button(
                btn_frame,
                text=btn["text"],
                font=("Arial", 10, "bold"),
                bg=btn.get("bg", accent),
                fg=btn.get("fg", "#FFFFFF"),
                activebackground=btn.get("bg", accent),
                relief="flat",
                cursor="hand2",
                command=lambda c=cb: close_and_run(c),
                padx=16,
                pady=6
            ).pack(side="left", padx=(0, 10) if btn != buttons[-1] else 0)

        # Close on X
        window.protocol("WM_DELETE_WINDOW", lambda: close_and_run(on_close))
        return window

    # Convenience methods (backward compatible)
    def info(self, title, message, subtitle=None, confirm_label="OK", on_confirm=None, show_cancel=False, cancel_label="Cancel", on_cancel=None):
        buttons = [{"text": confirm_label, "callback": on_confirm, "bg": "#00A859"}]
        if show_cancel:
            buttons.insert(0, {"text": cancel_label, "callback": on_cancel, "bg": "#E0E0E0", "fg": "#333333"})
        return self._build_popup(title, message, accent="#00A859", subtitle=subtitle, buttons=buttons, on_close=on_cancel)

    def success(self, title, message, subtitle=None, confirm_label="Great", on_confirm=None, show_cancel=False, cancel_label="Close", on_cancel=None):
        buttons = [{"text": confirm_label, "callback": on_confirm, "bg": "#00A859"}]
        if show_cancel:
            buttons.insert(0, {"text": cancel_label, "callback": on_cancel, "bg": "#E0E0E0", "fg": "#333333"})
        return self._build_popup(title, message, accent="#00A859", subtitle=subtitle, buttons=buttons, on_close=on_cancel)

    def warning(self, title, message, subtitle=None, confirm_label="Understood", on_confirm=None, show_cancel=False, cancel_label="Cancel", on_cancel=None):
        buttons = [{"text": confirm_label, "callback": on_confirm, "bg": "#D97706"}]
        if show_cancel:
            buttons.insert(0, {"text": cancel_label, "callback": on_cancel, "bg": "#E0E0E0", "fg": "#333333"})
        return self._build_popup(title, message, accent="#D97706", subtitle=subtitle, buttons=buttons, on_close=on_cancel)

    def error(self, title, message, subtitle=None, confirm_label="Close", on_confirm=None, show_cancel=False, cancel_label="Cancel", on_cancel=None):
        buttons = [{"text": confirm_label, "callback": on_confirm, "bg": "#E63946"}]
        if show_cancel:
            buttons.insert(0, {"text": cancel_label, "callback": on_cancel, "bg": "#E0E0E0", "fg": "#333333"})
        return self._build_popup(title, message, accent="#E63946", subtitle=subtitle, buttons=buttons, on_close=on_cancel)

    # New flexible custom dialog
    def custom(self, title, message, accent="#00A859", subtitle=None, width=440, buttons=None, on_close=None):
        """
        buttons: list of dicts, e.g. [{"text": "Yes", "callback": yes_func}, {"text": "No", "callback": no_func}]
        """
        return self._build_popup(title, message, accent, subtitle, width, buttons, on_close)