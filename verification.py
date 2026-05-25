import tkinter as tk
import random
import secrets
import time
import smtplib
import hashlib
import socket
import os
from email.mime.text import MIMEText

try:
    from services.msgbox import MessageBoxService
except ModuleNotFoundError:
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from services.msgbox import MessageBoxService


def _load_env():
    """Load SMTP credentials from a .env or _env file in this folder or project root."""
    env = {}
    candidates = [
        os.path.join(os.path.dirname(__file__), ".env"),
        os.path.join(os.path.dirname(__file__), "_env"),
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        os.path.join(os.path.dirname(__file__), "..", "_env"),
    ]
    for path in candidates:
        path = os.path.normpath(path)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            k, _, v = line.partition("=")
                            env[k.strip()] = v.strip()
            except Exception:
                pass
            break
    return env


def center_window(window, width, height, parent=None):
    """Centers a Tkinter window on the screen or relative to a parent."""
    if parent and parent.winfo_exists():
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        x = parent_x + (parent_w // 2) - (width // 2)
        y = parent_y + (parent_h // 2) - (height // 2)
    else:
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()
        x = (screen_w // 2) - (width // 2)
        y = (screen_h // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")

class VerificationService:
    def __init__(self, dashboard):
        self.dashboard = dashboard
        self.msgbox = dashboard.msgbox if hasattr(dashboard, 'msgbox') else MessageBoxService(dashboard)
        self.controller = dashboard.controller
        # Load SMTP credentials from .env / _env file
        _env = _load_env()
        self.smtp_email    = _env.get("GMAIL_SENDER_EMAIL") or getattr(dashboard, 'smtp_sender_email', '')
        self.smtp_password = _env.get("GMAIL_APP_PASSWORD")  or getattr(dashboard, 'smtp_app_password', '')

        self.verify_modal = None
        self.contact_modal = None
        self.verify_timer_id = None
        self.contact_timer_id = None
        self.verify_remaining = 0
        self.contact_remaining = 0
        self.current_otp_code = None
        self.target_email = ""

    # ---------- Database helpers (proxy to dashboard) ----------
    def _find_user(self, email):
        if hasattr(self.dashboard, '_find_user'):
            return self.dashboard._find_user(email)
        return None

    def _update_user(self, email, updater):
        if hasattr(self.dashboard, '_update_user'):
            return self.dashboard._update_user(email, updater)
        return None

    def _hash_otp(self, salt, code):
        return hashlib.sha256(f"{salt}:{code}".encode("utf-8")).hexdigest()

    def _refresh_verification_state(self):
        if hasattr(self.dashboard, 'refresh_verification_state'):
            self.dashboard.refresh_verification_state()

    # ---------- Email Verification for Property Alerts ----------
    def start_account_verification(self):
        email = self.controller.session.get("email", "")
        if not email:
            self.msgbox.error("Missing account", "Please log in before verifying your email.")
            return

        if self.verify_modal and self.verify_modal.winfo_exists():
            self.verify_modal.lift()
            return

        self.verify_modal = tk.Toplevel(self.dashboard)
        self.verify_modal.title("Get Property Alerts")
        self.verify_modal.configure(bg="#FFFFFF")
        self.verify_modal.resizable(False, False)
        self.verify_modal.transient(self.dashboard.winfo_toplevel())
        self.verify_modal.grab_set()
        
        # Ensure the app logo is applied
        if hasattr(self.dashboard, '_set_window_icon'):
            self.dashboard._set_window_icon(self.verify_modal)
            
        center_window(self.verify_modal, 450, 480, parent=self.dashboard)

        tk.Label(self.verify_modal, text="Verify Email for Property Alerts", font=("Arial", 16, "bold"), bg="#FFFFFF", fg="#0A1128").pack(pady=(20, 8))
        tk.Label(self.verify_modal, text="We want to ensure your email is real so we can send you exciting updates on future properties you might be interested in!",
                 font=("Arial", 10), bg="#FFFFFF", fg="#667085", wraplength=380, justify="center").pack(pady=(0, 14), padx=20)

        tk.Label(self.verify_modal, text="Registered email", font=("Arial", 10, "bold"), bg="#FFFFFF").pack(anchor="w", padx=40)
        self.verify_email_ent = tk.Entry(self.verify_modal, font=("Arial", 12), bg="#F4F6F8", relief="flat")
        self.verify_email_ent.pack(fill="x", padx=40, pady=(4, 10), ipady=5)
        self.verify_email_ent.insert(0, email)
        self.verify_email_ent.config(state="disabled")

        self.send_verify_btn = tk.Button(self.verify_modal, text="Send verification code", bg="#FFC107", fg="#212529",
                                         font=("Arial", 10, "bold"), relief="flat", cursor="hand2",
                                         command=self._send_account_verification_code)
        self.send_verify_btn.pack(fill="x", padx=40, pady=(4, 5), ipady=5)

        self.timer_label = tk.Label(self.verify_modal, text="", font=("Arial", 9), bg="#FFFFFF", fg="#D97706")
        self.timer_label.pack()
        self.verify_status_lbl = tk.Label(self.verify_modal, text="", font=("Arial", 9), bg="#FFFFFF")
        self.verify_status_lbl.pack()

        self.code_form = tk.Frame(self.verify_modal, bg="#FFFFFF")
        tk.Label(self.code_form, text="Enter 6-digit code", font=("Arial", 10, "bold"), bg="#FFFFFF").pack(anchor="w")
        self.verify_code_ent = tk.Entry(self.code_form, font=("Arial", 16, "bold"), bg="#F4F6F8", relief="flat", justify="center")
        self.verify_code_ent.pack(fill="x", pady=5, ipady=5)
        tk.Button(self.code_form, text="Verify email", bg="#00A859", fg="white", font=("Arial", 10, "bold"),
                  relief="flat", cursor="hand2", command=self.verify_account_code).pack(fill="x", pady=10, ipady=5)
        tk.Button(self.verify_modal, text="Maybe later", bg="#F3F4F6", fg="#0A1128", font=("Arial", 10),
                  relief="flat", cursor="hand2", command=self._close_verify_modal).pack(pady=(8, 12))

    def _send_account_verification_code(self):
        email = self.controller.session.get("email", "")
        if not email:
            self.verify_status_lbl.config(text="You must be logged in to verify.", fg="#E63946")
            return

        user = self._find_user(email)
        if not user:
            self.verify_status_lbl.config(text="Account record not found.", fg="#E63946")
            return

        if not self.smtp_email or "YOUR_EMAIL" in self.smtp_email:
            self.verify_status_lbl.config(text="Email settings not configured. Please contact support.", fg="#E63946")
            return

        self._cancel_verify_timer()

        code = f"{random.randint(100000, 999999)}"
        salt = secrets.token_hex(8)
        otp_hash = self._hash_otp(salt, code)
        issued_epoch = time.time()
        expiry_epoch = issued_epoch + 240

        self.current_otp_code = code
        self.target_email = email

        def updater(record):
            record["verified"] = False
            record["otp_salt"] = salt
            record["otp_hash"] = otp_hash
            record["otp_expiry"] = expiry_epoch
            record["otp_issued_epoch"] = issued_epoch
            record["otp_issued_mono"] = time.monotonic()
            record["otp_attempts"] = "0"
            return record
        self._update_user(email, updater)

        self.verify_status_lbl.config(text="Sending code...", fg="#0A1128")
        self.dashboard.update_idletasks()

        human_email = (f"Hello {user['name']},\n\n"
                       f"Use this one-time code to verify your email on Lagos Home Finder:\n\n"
                       f"{code}\n\n"
                       f"This ensures we can send you alerts on future properties you might be interested in. "
                       f"This code expires in 4 minutes. If you did not request this, you can safely ignore this email.")
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
                server.login(self.smtp_email, self.smtp_password)
                msg = MIMEText(human_email)
                msg["Subject"] = "Verify your email for property alerts"
                msg["From"] = self.smtp_email
                msg["To"] = email
                server.send_message(msg)

            self.verify_status_lbl.config(text="Code sent! Check your inbox or spam.", fg="#00A859")
            self.code_form.pack(fill="x", padx=40, pady=12)
            self.verify_remaining = 240
            self._update_verify_timer()
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPAuthenticationError, socket.timeout, ConnectionError, OSError):
            self.verify_status_lbl.config(text="Unable to send email. Check connection.", fg="#E63946")
        except Exception:
            self.verify_status_lbl.config(text="Unable to send email. Please try again later.", fg="#E63946")

    def _update_verify_timer(self):
        if self.verify_remaining <= 0:
            self.timer_label.config(text="Code expired. Click 'Send verification code' again.")
            self._cancel_verify_timer()
            return
        mins = self.verify_remaining // 60
        secs = self.verify_remaining % 60
        self.timer_label.config(text=f"Current code expires in: {mins:02d}:{secs:02d}")
        self.verify_remaining -= 1
        self.verify_timer_id = self.verify_modal.after(1000, self._update_verify_timer)

    def _cancel_verify_timer(self):
        if self.verify_timer_id:
            self.verify_modal.after_cancel(self.verify_timer_id)
            self.verify_timer_id = None

    def verify_account_code(self):
        email = self.controller.session.get("email", "")
        user = self._find_user(email) if email else None
        if not user:
            self.verify_status_lbl.config(text="Account record not found.", fg="#E63946")
            return

        entered = self.verify_code_ent.get().strip()
        if not entered:
            self.verify_status_lbl.config(text="Enter the 6-digit code.", fg="#E63946")
            return

        current_wall = time.time()
        expiry_epoch = float(user.get("otp_expiry", 0) or 0)
        if expiry_epoch and current_wall > expiry_epoch:
            self.verify_status_lbl.config(text="Code expired. Request a new one.", fg="#E63946")
            return

        expected_hash = self._hash_otp(user.get("otp_salt", ""), entered)
        if expected_hash != user.get("otp_hash", ""):
            attempts = int(user.get("otp_attempts", 0) or 0) + 1
            self._update_user(email, lambda record: {**record, "otp_attempts": str(attempts)})
            if attempts >= 5:
                self._update_user(email, lambda record: {**record, "otp_hash": "", "otp_salt": "", "otp_expiry": "", "otp_attempts": "0"})
                self.verify_status_lbl.config(text="Too many failed attempts. Send a new code.", fg="#E63946")
            else:
                self.verify_status_lbl.config(text="Invalid code.", fg="#E63946")
            return

        def mark_verified(record):
            record["verified"] = True
            record["otp_salt"] = record["otp_hash"] = record["otp_expiry"] = record["otp_issued_epoch"] = record["otp_issued_mono"] = ""
            record["otp_attempts"] = "0"
            return record
            
        self._update_user(email, mark_verified)
        self.controller.session["is_verified"] = True
        self.verify_status_lbl.config(text="Email verified successfully.", fg="#00A859")
        self.msgbox.success("Success!", "Your email has been verified.",
                            subtitle="You will now receive alerts on future properties.",
                            on_confirm=self._close_verify_modal)

    def _close_verify_modal(self):
        self._cancel_verify_timer()
        if self.verify_modal and self.verify_modal.winfo_exists():
            self.verify_modal.grab_release()
            self.verify_modal.destroy()
        self.verify_modal = None
        self._refresh_verification_state()

    # ---------- Contact agent verification ----------
    def open_contact_modal(self, property_name):
        if self.contact_modal and self.contact_modal.winfo_exists():
            self.contact_modal.lift()
            return

        self.contact_modal = tk.Toplevel(self.dashboard)
        self.contact_modal.title("Security Verification")
        self.contact_modal.configure(bg="#FFFFFF")
        self.contact_modal.resizable(False, False)
        self.contact_modal.grab_set()
        
        if hasattr(self.dashboard, '_set_window_icon'):
            self.dashboard._set_window_icon(self.contact_modal)
            
        center_window(self.contact_modal, 450, 520, parent=self.dashboard)

        tk.Label(self.contact_modal, text="Action Required", font=("Arial", 16, "bold"), bg="#FFFFFF").pack(pady=(20, 5))
        tk.Label(self.contact_modal, text=f"Verify your identity to contact the agent for\n{property_name}",
                 font=("Arial", 10), bg="#FFFFFF", fg="#7A7A7A", justify="center").pack(pady=(0, 20))

        tk.Label(self.contact_modal, text="Enter your registered email:", font=("Arial", 10, "bold"), bg="#FFFFFF").pack(anchor="w", padx=40)
        self.contact_email_ent = tk.Entry(self.contact_modal, font=("Arial", 12), bg="#F4F6F8", relief="flat")
        self.contact_email_ent.pack(fill="x", padx=40, pady=5, ipady=5)

        self.contact_send_btn = tk.Button(self.contact_modal, text="Send Verification Code", bg="#00A859", fg="white",
                                          font=("Arial", 10, "bold"), relief="flat", cursor="hand2",
                                          command=self._send_contact_code)
        self.contact_send_btn.pack(fill="x", padx=40, pady=(5, 0), ipady=5)

        self.contact_timer_label = tk.Label(self.contact_modal, text="", font=("Arial", 9), bg="#FFFFFF", fg="#D97706")
        self.contact_timer_label.pack()
        self.contact_msg_lbl = tk.Label(self.contact_modal, text="", font=("Arial", 9), bg="#FFFFFF")
        self.contact_msg_lbl.pack()

        self.contact_code_frame = tk.Frame(self.contact_modal, bg="#FFFFFF")
        tk.Label(self.contact_code_frame, text="Enter 6-digit code (expires in 4 minutes):", font=("Arial", 10, "bold"), bg="#FFFFFF").pack(anchor="w")
        self.contact_code_ent = tk.Entry(self.contact_code_frame, font=("Arial", 16, "bold"), bg="#F4F6F8", relief="flat", justify="center")
        self.contact_code_ent.pack(fill="x", pady=5, ipady=5)
        tk.Button(self.contact_code_frame, text="Verify & Proceed", bg="#0A1128", fg="white", font=("Arial", 10, "bold"),
                  relief="flat", cursor="hand2", command=self.verify_contact_code).pack(fill="x", pady=10, ipady=5)
        tk.Button(self.contact_modal, text="Cancel", bg="#F3F4F6", fg="#0A1128", font=("Arial", 10),
                  relief="flat", cursor="hand2", command=self._close_contact_modal).pack(pady=(6, 12))

    def _send_contact_code(self):
        email = self.contact_email_ent.get().strip()
        if not email or "@" not in email:
            self.contact_msg_lbl.config(text="Enter a valid email address!", fg="red")
            return

        user = self._find_user(email)
        if not user:
            self.contact_msg_lbl.config(text="Email not registered. Please sign up first.", fg="red")
            return

        if not self.smtp_email or "YOUR_EMAIL" in self.smtp_email:
            self.contact_msg_lbl.config(text="Email settings not configured. Please contact support.", fg="red")
            return

        self._cancel_contact_timer()

        code = str(random.randint(100000, 999999))
        salt = secrets.token_hex(8)
        otp_hash = self._hash_otp(salt, code)
        issued_epoch = time.time()
        expiry_epoch = issued_epoch + 240

        self.current_otp_code = code
        self.target_email = email

        def updater(record):
            record["otp_salt"] = salt
            record["otp_hash"] = otp_hash
            record["otp_expiry"] = expiry_epoch
            record["otp_issued_epoch"] = issued_epoch
            record["otp_issued_mono"] = time.monotonic()
            record["otp_attempts"] = "0"
            return record
        self._update_user(email, updater)

        self.contact_msg_lbl.config(text="Sending code...", fg="black")
        self.dashboard.update_idletasks()

        human_email = (f"Hello {user['name']},\n\n"
                       f"Use this one-time code to contact an agent on Lagos Home Finder:\n\n"
                       f"{code}\n\n"
                       f"This code expires in 4 minutes. Do not share it with anyone.")
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
                server.login(self.smtp_email, self.smtp_password)
                msg = MIMEText(human_email)
                msg["Subject"] = "Agent Contact Verification"
                msg["From"] = self.smtp_email
                msg["To"] = email
                server.send_message(msg)

            self.contact_msg_lbl.config(text="Code sent! Check your inbox.", fg="#00A859")
            self.contact_email_ent.config(state="disabled")
            self.contact_code_frame.pack(fill="x", padx=40, pady=10)
            self.contact_remaining = 240
            self._update_contact_timer()
        except Exception:
            self.contact_msg_lbl.config(text="Unable to send email. Please check connection.", fg="red")

    def _update_contact_timer(self):
        if self.contact_remaining <= 0:
            self.contact_timer_label.config(text="Code expired. Click 'Send Verification Code' again.")
            self._cancel_contact_timer()
            return
        mins = self.contact_remaining // 60
        secs = self.contact_remaining % 60
        self.contact_timer_label.config(text=f"Current code expires in: {mins:02d}:{secs:02d}")
        self.contact_remaining -= 1
        self.contact_timer_id = self.contact_modal.after(1000, self._update_contact_timer)

    def _cancel_contact_timer(self):
        if self.contact_timer_id:
            self.contact_modal.after_cancel(self.contact_timer_id)
            self.contact_timer_id = None

    def verify_contact_code(self):
        email = self.target_email
        if not email:
            self.contact_msg_lbl.config(text="Please request a code first.", fg="red")
            return

        user = self._find_user(email)
        if not user:
            self.contact_msg_lbl.config(text="User not found.", fg="red")
            return

        entered = self.contact_code_ent.get().strip()
        if not entered:
            self.contact_msg_lbl.config(text="Enter the 6-digit code.", fg="red")
            return

        current_wall = time.time()
        expiry_epoch = float(user.get("otp_expiry", 0) or 0)
        if expiry_epoch and current_wall > expiry_epoch:
            self.contact_msg_lbl.config(text="Code expired. Please request a new one.", fg="red")
            return

        expected_hash = self._hash_otp(user.get("otp_salt", ""), entered)
        if expected_hash != user.get("otp_hash", ""):
            attempts = int(user.get("otp_attempts", 0) or 0) + 1
            self._update_user(email, lambda record: {**record, "otp_attempts": str(attempts)})
            if attempts >= 5:
                self._update_user(email, lambda record: {**record, "otp_hash": "", "otp_salt": "", "otp_expiry": "", "otp_attempts": "0"})
                self.contact_msg_lbl.config(text="Too many failed attempts. Request a new code.", fg="red")
            else:
                self.contact_msg_lbl.config(text="Invalid code.", fg="red")
            return

        if hasattr(self.msgbox, 'success'):
            self.msgbox.success("Success", "Identity Verified! The agent has been notified.",
                                on_confirm=self._close_contact_modal)
        else:
            self._close_contact_modal()

    def _close_contact_modal(self):
        self._cancel_contact_timer()
        if self.contact_modal and self.contact_modal.winfo_exists():
            self.contact_modal.grab_release()
            self.contact_modal.destroy()
        self.contact_modal = None