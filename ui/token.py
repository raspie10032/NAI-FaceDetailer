import customtkinter as ctk
from tkinter import filedialog
from core.settings import save_config
from ui.base import BaseScreen
from i18n import t

LANG_LABELS = {"ko": "한국어", "en": "English", "ja": "日本語", "zh": "中文"}
LANG_CODES = {v: k for k, v in LANG_LABELS.items()}

class TokenScreen(BaseScreen):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        current_lang = self.config.get("language", "ko")

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Title
        title = ctk.CTkLabel(self, text=t("settings"), font=ctk.CTkFont(size=24, weight="bold"))
        title.grid(row=0, column=0, pady=(20, 20))

        # Form container
        form = ctk.CTkScrollableFrame(self, fg_color="transparent")
        form.grid(row=1, column=0, sticky="nsew", padx=100, pady=(0, 5))

        # NAI Token
        ctk.CTkLabel(form, text=t("token_label")).pack(anchor="w")
        token_row = ctk.CTkFrame(form, fg_color="transparent")
        token_row.pack(fill="x", pady=(0, 15))
        self.token_entry = ctk.CTkEntry(token_row, placeholder_text=t("token_placeholder"))
        self.token_entry.pack(side="left", fill="x", expand=True)
        self.token_entry.insert(0, self.config.get("nai_token", ""))
        def paste_token():
            try:
                text = self.clipboard_get()
                self.token_entry.delete(0, "end")
                self.token_entry.insert(0, text)
            except Exception:
                pass
        ctk.CTkButton(token_row, text=t("paste"), width=80, command=paste_token).pack(side="right", padx=(5, 0))

        # Language
        ctk.CTkLabel(form, text=t("lang_label")).pack(anchor="w")
        self.lang_var = ctk.StringVar(value=LANG_LABELS.get(current_lang, "한국어"))
        self.lang_dropdown = ctk.CTkOptionMenu(
            form, 
            values=list(LANG_LABELS.values()), 
            variable=self.lang_var
        )
        self.lang_dropdown.pack(fill="x", pady=(0, 15))

        # GGUF Path
        ctk.CTkLabel(form, text=t("gguf_label")).pack(anchor="w")
        gguf_row = ctk.CTkFrame(form, fg_color="transparent")
        gguf_row.pack(fill="x", pady=(0, 15))
        self.gguf_entry = ctk.CTkEntry(gguf_row)
        self.gguf_entry.pack(side="left", fill="x", expand=True)
        self.gguf_entry.insert(0, self.config.get("gguf_path", ""))
        ctk.CTkButton(gguf_row, text=t("browse"), width=80, command=self.browse_gguf).pack(side="right", padx=(5, 0))

        # TIPO Model Path
        ctk.CTkLabel(form, text=t("tipo_label")).pack(anchor="w")
        tipo_row = ctk.CTkFrame(form, fg_color="transparent")
        tipo_row.pack(fill="x", pady=(0, 15))
        self.tipo_entry = ctk.CTkEntry(tipo_row)
        self.tipo_entry.pack(side="left", fill="x", expand=True)
        self.tipo_entry.insert(0, self.config.get("tipo_model_path", ""))
        ctk.CTkButton(tipo_row, text=t("browse"), width=80, command=self.browse_tipo).pack(side="right", padx=(5, 0))

        # TIPO GPU Layers
        ctk.CTkLabel(form, text=t("tipo_gpu_label")).pack(anchor="w")
        self.tipo_gpu_entry = ctk.CTkEntry(form)
        self.tipo_gpu_entry.pack(fill="x", pady=(0, 15))
        self.tipo_gpu_entry.insert(0, str(self.config.get("tipo_gpu_layers", 0)))

        # Wildcard Dir
        ctk.CTkLabel(form, text=t("wc_dir_label")).pack(anchor="w")
        wc_row = ctk.CTkFrame(form, fg_color="transparent")
        wc_row.pack(fill="x", pady=(0, 15))
        self.wc_entry = ctk.CTkEntry(wc_row)
        self.wc_entry.pack(side="left", fill="x", expand=True)
        self.wc_entry.insert(0, self.config.get("wildcard_dir", ""))
        ctk.CTkButton(wc_row, text=t("browse"), width=80, command=self.browse_wc).pack(side="right", padx=(5, 0))

        # Output Dir
        ctk.CTkLabel(form, text=t("out_dir_label")).pack(anchor="w")
        out_row = ctk.CTkFrame(form, fg_color="transparent")
        out_row.pack(fill="x", pady=(0, 15))
        self.out_entry = ctk.CTkEntry(out_row)
        self.out_entry.pack(side="left", fill="x", expand=True)
        self.out_entry.insert(0, self.config.get("output_dir", ""))
        ctk.CTkButton(out_row, text=t("browse"), width=80, command=self.browse_out).pack(side="right", padx=(5, 0))

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="ew", pady=(0, 20))

        # Info Label (Restart msg)
        self.info_label = ctk.CTkLabel(bottom, text="", text_color="orange")
        self.info_label.pack(pady=5)

        # Save Button
        save_btn = ctk.CTkButton(bottom, text=t("save_settings"), height=40, command=self.save)
        save_btn.pack(pady=(0, 5))

    def browse_gguf(self):
        path = filedialog.askopenfilename(filetypes=[("GGUF files", "*.gguf"), ("All files", "*.*")])
        if path:
            self.gguf_entry.delete(0, "end")
            self.gguf_entry.insert(0, path)

    def browse_tipo(self):
        import os
        models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
        path = filedialog.askopenfilename(
            initialdir=models_dir,
            filetypes=[("GGUF files", "*.gguf"), ("All files", "*.*")]
        )
        if path:
            self.tipo_entry.delete(0, "end")
            self.tipo_entry.insert(0, path)

    def browse_wc(self):
        path = filedialog.askdirectory()
        if path:
            self.wc_entry.delete(0, "end")
            self.wc_entry.insert(0, path)

    def browse_out(self):
        path = filedialog.askdirectory()
        if path:
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, path)

    def save(self):
        old_lang_code = self.config.get("language", "ko")
        
        lang_label = self.lang_var.get()
        new_lang_code = LANG_CODES.get(lang_label, "ko")

        self.config["nai_token"] = self.token_entry.get()
        self.config["language"] = new_lang_code
        self.config["gguf_path"] = self.gguf_entry.get()
        self.config["tipo_model_path"] = self.tipo_entry.get()
        try:
            self.config["tipo_gpu_layers"] = int(self.tipo_gpu_entry.get())
        except ValueError:
            self.config["tipo_gpu_layers"] = -1
        self.config["wildcard_dir"] = self.wc_entry.get()
        self.config["output_dir"] = self.out_entry.get()
        
        save_config(self.config)
        self.controller.config = self.config
        
        if old_lang_code != new_lang_code:
            self.info_label.configure(text=t("restart_msg"))
        else:
            self.info_label.configure(text=t("saved"))
        
        print("Settings saved.")
