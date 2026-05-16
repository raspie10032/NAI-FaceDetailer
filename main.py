import customtkinter as ctk
import os
import threading
from core.settings import load_config, load_last_settings, save_last_settings
from i18n import t
from tkinter import filedialog
from ui.token import TokenScreen
from ui.t2i import T2IScreen
from ui.face_detailer import FaceDetailerScreen

class NAIStudioApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(t("title"))
        self.minsize(1200, 850)
        self.geometry("1400x960")
        self.configure(fg_color=("#f0f0f0", "#0f0f0f"))

        self.config = load_config()
        self.pipeline_event = threading.Event()

        # Layout: Sidebar (fixed), Main (expanded)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0) # Status bar
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        # ── Sidebar ──────────────────────────────────────────────
        self.sidebar = ctk.CTkFrame(self, width=400, corner_radius=0, fg_color=("#e0e0e0", "#171717"))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        ctk.CTkLabel(self.sidebar, text="NAI FaceDetailer", font=ctk.CTkFont(size=32, weight="bold")).pack(pady=(60, 50))

        self.nav_buttons = {}
        for label, name in [("T2I", "T2I"), ("Face Detailer", "FaceDetailer")]:
            btn = ctk.CTkButton(self.sidebar, text=label, anchor="w", fg_color="transparent", 
                                hover_color=("gray75", "gray30"), height=60, corner_radius=10,
                                font=ctk.CTkFont(size=18, weight="bold"),
                                command=lambda n=name: self.show_screen(n))
            btn.pack(fill="x", padx=30, pady=6)
            self.nav_buttons[name] = btn

        # Sidebar Bottom Section
        self.sidebar_bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sidebar_bottom.pack(side="bottom", fill="x", pady=20)

        self.settings_btn = ctk.CTkButton(self.sidebar_bottom, text="Settings", anchor="w", fg_color="transparent",
                                          command=lambda: self.show_screen("Token"))
        self.settings_btn.pack(fill="x", padx=20, pady=2)
        self.nav_buttons["Token"] = self.settings_btn

        self.open_out_btn = ctk.CTkButton(self.sidebar_bottom, text="Open Output", anchor="w", fg_color="transparent",
                                          hover_color=("gray75", "gray30"), height=40, corner_radius=8,
                                          command=self.open_output_dir)
        self.open_out_btn.pack(fill="x", padx=20, pady=2)

        # ── GENERATE Button (Fixed in Sidebar) ──────────────────
        self.gen_btn = ctk.CTkButton(
            self.sidebar, text="GENERATE", height=80,
            font=ctk.CTkFont(size=22, weight="bold"),
            fg_color="#1f6aa5", hover_color="#144870",
            border_width=2, border_color=("#144870", "#1f6aa5"),
            corner_radius=15,
            command=lambda: self.current_frame.generate() if hasattr(self.current_frame, "generate") else None
        )
        # Position the button at the bottom of the navigation list but above the settings
        self.gen_btn.pack(side="bottom", fill="x", padx=20, pady=(10, 20))

        # ── Main Content Area ────────────────────────────────────
        self.main_container = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew")
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        # ── Status Bar ──────────────────────────────────────────
        self.bottom_bar = ctk.CTkFrame(self, height=30, corner_radius=0, fg_color=("gray90", "gray12"))
        self.bottom_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.bottom_bar.grid_propagate(False)

        self.status_label = ctk.CTkLabel(self.bottom_bar, text="Ready", font=ctk.CTkFont(size=11))
        self.status_label.pack(side="left", padx=20)

        # Shared variables
        self.shared = {
            "model_var": ctk.StringVar(value="nai-diffusion-4-5-full"),
            "res_var": ctk.StringVar(value="832x1216"),
            "steps_var": ctk.StringVar(value="28"),
            "cfg_var": ctk.StringVar(value="6.0"),
            "seed_var": ctk.StringVar(value="-1"),
            "cfg_rescale_var": ctk.StringVar(value="0.0"),
            "sampler_var": ctk.StringVar(value="k_euler_ancestral"),
            "scheduler_var": ctk.StringVar(value="karras"),
            "face_model_var": ctk.StringVar(value="nai-diffusion-3"),
            "det_model_var": ctk.StringVar(value="face_yolov8n.pt"),
            "seg_model_var": ctk.StringVar(value="sam_b.pt"),
        }

        # Load last settings
        last_settings = load_last_settings()
        for k, v in last_settings.items():
            if k in self.shared:
                self.shared[k].set(v)

        # Screens
        self.frames = {}
        self.current_frame = None
        self.result_image = None
        self.result_raw = None
        self._pipeline_done_callback = None

        self.show_screen("T2I")

    def set_gen_btn_state(self, state, text=None):
        """Centralized method to control the Generate button state and text."""
        self.gen_btn.configure(state=state)
        if text:
            self.gen_btn.configure(text=text)
        elif state == "normal":
            self.gen_btn.configure(text="GENERATE")
        
        # Save settings when generation starts
        if state == "disabled" and text != "Token": # Avoid saving when switching to Token screen
            self.save_current_settings()

    def save_current_settings(self):
        """Saves current shared variables to last_settings.json"""
        settings = {k: v.get() for k, v in self.shared.items()}
        save_last_settings(settings)

    def show_screen(self, name, **kwargs):
        for k, v in self.nav_buttons.items():
            v.configure(fg_color=("gray85", "gray35") if k == name else "transparent")

        if name not in self.frames:
            cls = {"Token": TokenScreen, "T2I": T2IScreen, "FaceDetailer": FaceDetailerScreen}.get(name)
            if not cls: return
            frame = cls(parent=self.main_container, controller=self, **kwargs)
            self.frames[name] = frame
            frame.grid(row=0, column=0, sticky="nsew")
        else:
            frame = self.frames[name]
            if kwargs and hasattr(frame, "set_params"):
                frame.set_params(**kwargs)
        
        if self.current_frame: self.current_frame.grid_remove()
        self.current_frame = frame
        frame.grid()
        frame.tkraise()
        if hasattr(frame, 'on_show'): frame.on_show()
        
        # UI Element Management
        if name == "Token":
            self.gen_btn.configure(state="disabled")
            self.gen_btn.pack_forget()
        else:
            if not self.gen_btn.winfo_ismapped():
                self.gen_btn.pack(side="bottom", fill="x", padx=20, pady=(10, 20))
                self.sidebar_bottom.pack_forget() # Re-pack settings below
                self.sidebar_bottom.pack(side="bottom", fill="x", pady=10)
            
            # Sync button state with screen's busy status
            if hasattr(frame, "is_busy") and frame.is_busy:
                self.set_gen_btn_state("disabled", t("generating"))
            else:
                self.set_gen_btn_state("normal")

    def display_result(self, pil_img, raw_bytes):
        self.result_raw = raw_bytes
        self.result_image = pil_img
        if hasattr(self.current_frame, "display_result"):
             self.current_frame.display_result(pil_img, raw_bytes)

    def open_output_dir(self):
        import subprocess
        import platform
        path = self.config.get("output_dir", "./output")
        path = os.path.abspath(path)
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def save_result(self):
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
        if path and self.result_raw:
            with open(path, "wb") as f: f.write(self.result_raw)

if __name__ == "__main__":
    ctk.set_appearance_mode("dark") # Default to dark as seen in screenshot
    app = NAIStudioApp()
    app.mainloop()
