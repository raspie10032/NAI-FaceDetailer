import customtkinter as ctk
import random
import threading
from core.settings import (
    load_art_presets, save_art_preset, delete_art_preset,
)
from core.tipo_engine import TipoExpander
from app.job_runner import T2IJob, JobCallbacks
from ui.base import BaseScreen
from i18n import t

class T2IScreen(BaseScreen):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)

        self.grid_columnconfigure(0, weight=0) # Controls
        self.grid_columnconfigure(1, weight=1) # Result Image
        self.grid_rowconfigure(0, weight=1)

        # ── Left: Controls Panel (Scrollable) ───────────────
        self.left_panel = ctk.CTkScrollableFrame(self, width=380, fg_color=("#f5f5f5", "#0f0f0f"))
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # ── SECTION 1: PROMPTS ──
        ctk.CTkLabel(self.left_panel, text=t("prompt_settings"), font=("", 14, "bold"), text_color="#1f6aa5").pack(anchor="w", padx=10, pady=(10, 5))
        
        prompt_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        prompt_frame.pack(fill="x", padx=5)

        ctk.CTkLabel(prompt_frame, text=t("positive_prompt"), font=("", 11, "bold")).pack(anchor="w", padx=5)
        self.prompt_txt = ctk.CTkTextbox(prompt_frame, height=100, border_width=1, border_color="gray30")
        self.prompt_txt.pack(fill="x", pady=(2, 8), padx=5)
        self.prompt_txt.insert("1.0", "1girl, solo, sundress, straw hat, barbara (genshin impact)")

        ctk.CTkLabel(prompt_frame, text=t("negative_prompt"), font=("", 11, "bold")).pack(anchor="w", padx=5)
        self.neg_prompt_txt = ctk.CTkTextbox(prompt_frame, height=60, border_width=1, border_color="gray30")
        self.neg_prompt_txt.pack(fill="x", pady=(2, 10), padx=5)
        self.neg_prompt_txt.insert("1.0", "lowres, bad anatomy, error, fewer, extra, missing, worst quality, jpeg artifacts, blurry")

        # ── SECTION 2: TIPO ENGINE ──
        ctk.CTkLabel(self.left_panel, text=t("tipo_engine"), font=("", 14, "bold"), text_color="#1f6aa5").pack(anchor="w", padx=10, pady=(15, 5))
        
        tipo_frame = ctk.CTkFrame(self.left_panel, fg_color=("gray90", "gray15"), corner_radius=10)
        tipo_frame.pack(fill="x", padx=10, pady=5)
        
        t_top_row = ctk.CTkFrame(tipo_frame, fg_color="transparent")
        t_top_row.pack(fill="x", pady=5, padx=5)
        
        self.tipo_switch = ctk.CTkSwitch(t_top_row, text=t("auto_expand"), font=("", 12, "bold"))
        self.tipo_switch.pack(side="left", padx=5)
        self.tipo_switch.select()

        self.rating_var = ctk.StringVar(value="safe")
        self.rating_menu = ctk.CTkOptionMenu(t_top_row, values=["safe", "sensitive", "questionable", "explicit"], 
                                             variable=self.rating_var, width=100, height=24)
        self.rating_menu.pack(side="right", padx=5)
        
        ctk.CTkLabel(tipo_frame, text=t("ban_tags_label"), font=("", 10)).pack(anchor="w", padx=10)
        self.ban_tags_entry = ctk.CTkEntry(tipo_frame, placeholder_text=t("ban_tags_placeholder"), height=24)
        self.ban_tags_entry.pack(fill="x", padx=10, pady=(0, 8))

        ctk.CTkLabel(tipo_frame, text=t("expansion_preview"), font=("", 10)).pack(anchor="w", padx=10)
        self.expanded_prompt_txt = ctk.CTkTextbox(tipo_frame, height=60, fg_color=("#e0e0e0", "#101010"), font=("", 10))
        self.expanded_prompt_txt.pack(fill="x", pady=(0, 10), padx=10)

        # ── SECTION 3: ART STYLE & ENHANCEMENT ──
        ctk.CTkLabel(self.left_panel, text=t("style_enhancement"), font=("", 14, "bold"), text_color="#1f6aa5").pack(anchor="w", padx=10, pady=(15, 5))
        
        enh_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        enh_frame.pack(fill="x", padx=5)

        # Art Presets
        style_row = ctk.CTkFrame(enh_frame, fg_color="transparent")
        style_row.pack(fill="x", pady=2)
        
        self.art_presets = load_art_presets()
        preset_names = ["None", "Golden Recipe v3.1"] + [p["name"] for p in self.art_presets]
        self.style_var = ctk.StringVar(value="Golden Recipe v3.1")
        self.style_menu = ctk.CTkOptionMenu(style_row, values=preset_names, 
                                            variable=self.style_var, height=28)
        self.style_menu.pack(side="left", fill="x", expand=True, padx=5)
        
        self.style_mode_var = ctk.StringVar(value="Append")
        self.style_mode_menu = ctk.CTkOptionMenu(style_row, values=[t("style_mode_prepend"), t("style_mode_append")], 
                                                 variable=self.style_mode_var, width=90, height=28)
        self.style_mode_menu.pack(side="right", padx=5)

        save_style_frame = ctk.CTkFrame(enh_frame, fg_color="transparent")
        save_style_frame.pack(fill="x", pady=(0, 10))
        self.new_style_entry = ctk.CTkEntry(save_style_frame, placeholder_text=t("new_style_placeholder"), height=24, font=("", 11))
        self.new_style_entry.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(save_style_frame, text=t("add"), width=40, height=24, command=self.add_art_preset).pack(side="right", padx=2)
        ctk.CTkButton(save_style_frame, text=t("delete_short"), width=40, height=24, fg_color="#a83232", hover_color="#8a2828", command=self.del_art_preset).pack(side="right", padx=5)

        # Switches
        sw_grid = ctk.CTkFrame(enh_frame, fg_color="transparent")
        sw_grid.pack(fill="x", padx=5)
        
        self.workflow_switch = ctk.CTkSwitch(sw_grid, text=t("workflow"), font=("", 12, "bold"))
        self.workflow_switch.pack(anchor="w", pady=(5, 2))
        self.workflow_switch.select() # 기본 활성화

        self.face_model_menu = ctk.CTkOptionMenu(
            sw_grid, 
            values=[
                "nai-diffusion-3", "nai-diffusion-4-5-curated", "nai-diffusion-4-5-full",
                "nai-diffusion-furry-3", "nai-diffusion-2"
            ],
            variable=self.controller.shared["face_model_var"],
            height=24, font=("", 11)
        )
        self.face_model_menu.pack(fill="x", padx=5, pady=(0, 10))

        # ── SECTION 4: AUTO GENERATION ──
        ctk.CTkLabel(self.left_panel, text=t("auto_gen"), font=("", 14, "bold"), text_color="#1f6aa5").pack(anchor="w", padx=10, pady=(15, 5))
        
        auto_frame = ctk.CTkFrame(self.left_panel, fg_color=("gray90", "gray15"), corner_radius=10)
        auto_frame.pack(fill="x", padx=10, pady=5)
        
        a_row = ctk.CTkFrame(auto_frame, fg_color="transparent")
        a_row.pack(fill="x", pady=8, padx=10)
        
        self.auto_gen_switch = ctk.CTkSwitch(a_row, text=t("infinite_loop"), font=("", 12, "bold"))
        self.auto_gen_switch.pack(side="left")
        
        self.auto_count_var = ctk.StringVar(value="∞")
        self.auto_count_menu = ctk.CTkOptionMenu(a_row, values=["∞", "10", "20", "50", "100"], 
                                                 variable=self.auto_count_var, width=60, height=24)
        self.auto_count_menu.pack(side="right", padx=5)
        
        d_row = ctk.CTkFrame(auto_frame, fg_color="transparent")
        d_row.pack(fill="x", pady=(0, 8), padx=10)
        ctk.CTkLabel(d_row, text=t("delay_sec"), font=("", 11)).pack(side="left")
        self.auto_delay_entry = ctk.CTkEntry(d_row, width=50, height=22)
        self.auto_delay_entry.insert(0, "2.0")
        self.auto_delay_entry.pack(side="right", padx=5)

        # ── SECTION 5: MODEL & CORE PARAMETERS ──
        ctk.CTkLabel(self.left_panel, text=t("core_parameters"), font=("", 14, "bold"), text_color="#1f6aa5").pack(anchor="w", padx=10, pady=(15, 5))
        
        shared = self.controller.shared
        core_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        core_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(core_frame, text=t("active_model"), font=("", 11, "bold")).pack(anchor="w", padx=5)
        models = [
            "nai-diffusion-4-5-curated", "nai-diffusion-4-5-full", 
            "nai-diffusion-4-full", "nai-diffusion-4-curated-preview", 
            "nai-diffusion-3", "nai-diffusion-furry-3", "nai-diffusion-2"
        ]
        ctk.CTkOptionMenu(core_frame, values=models, variable=shared["model_var"], height=28).pack(fill="x", padx=5, pady=(2, 10))

        param_grid = ctk.CTkFrame(core_frame, fg_color="transparent")
        param_grid.pack(fill="x", padx=5)
        param_grid.grid_columnconfigure((1, 3), weight=1)

        # Row 0: Res & Steps
        ctk.CTkLabel(param_grid, text=t("res_short"), font=("", 11)).grid(row=0, column=0, sticky="w", padx=2)
        res_list = ["832x1216", "1216x832", "1024x1024", "768x1344", "1344x768"]
        ctk.CTkOptionMenu(param_grid, values=res_list, variable=shared["res_var"], height=22, width=100, font=("", 11)).grid(row=0, column=1, sticky="ew", pady=2)
        
        ctk.CTkLabel(param_grid, text=t("steps_short"), font=("", 11)).grid(row=0, column=2, sticky="w", padx=5)
        ctk.CTkEntry(param_grid, textvariable=shared["steps_var"], height=22, width=50, font=("", 11)).grid(row=0, column=3, sticky="ew", pady=2)

        # Row 1: CFG & CFG Rescale
        ctk.CTkLabel(param_grid, text=t("cfg_short"), font=("", 11)).grid(row=1, column=0, sticky="w", padx=2)
        ctk.CTkEntry(param_grid, textvariable=shared["cfg_var"], height=22, font=("", 11)).grid(row=1, column=1, sticky="ew", pady=2)
        
        ctk.CTkLabel(param_grid, text=t("scale_short"), font=("", 11)).grid(row=1, column=2, sticky="w", padx=5)
        ctk.CTkEntry(param_grid, textvariable=shared["cfg_rescale_var"], height=22, font=("", 11)).grid(row=1, column=3, sticky="ew", pady=2)

        # Row 2: Sampler & Scheduler
        ctk.CTkLabel(param_grid, text=t("sampler_short"), font=("", 11)).grid(row=2, column=0, sticky="w", padx=2)
        samplers = ["k_euler_ancestral", "k_euler", "k_dpmpp_2s_ancestral", "k_dpmpp_2m", "ddim"]
        ctk.CTkOptionMenu(param_grid, values=samplers, variable=shared["sampler_var"], height=22, font=("", 11)).grid(row=2, column=1, sticky="ew", pady=2)

        ctk.CTkLabel(param_grid, text=t("scheduler_short"), font=("", 11)).grid(row=2, column=2, sticky="w", padx=5)
        schedulers = ["karras", "exponential", "native"]
        ctk.CTkOptionMenu(param_grid, values=schedulers, variable=shared["scheduler_var"], height=22, font=("", 11)).grid(row=2, column=3, sticky="ew", pady=2)

        # Row 3: Seed
        ctk.CTkLabel(param_grid, text=t("seed_short"), font=("", 11)).grid(row=3, column=0, sticky="w", padx=2)
        ctk.CTkEntry(param_grid, textvariable=shared["seed_var"], height=22, font=("", 11)).grid(row=3, column=1, columnspan=3, sticky="ew", pady=(2, 20))

        # ── Right: Result Display ──────────────────────────

        # ── Right: Result Display ──────────────────────────
        self.result_panel = ctk.CTkFrame(self, corner_radius=0, fg_color=("#e8e8e8", "#111111"))
        self.result_panel.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.result_panel.grid_rowconfigure(0, weight=1)
        self.result_panel.grid_columnconfigure(0, weight=1)

        self.img_label = ctk.CTkLabel(self.result_panel, text=t("waiting_image"))
        self.img_label.grid(row=0, column=0, sticky="nsew")

        # Result Buttons
        r_btn_row = ctk.CTkFrame(self.result_panel, fg_color="transparent")
        r_btn_row.grid(row=1, column=0, sticky="ew", pady=10)
        self.save_btn = ctk.CTkButton(r_btn_row, text=t("save_short"), state="disabled", command=self.controller.save_result)
        self.save_btn.pack(side="left", expand=True, padx=5)
        self.edit_btn = ctk.CTkButton(r_btn_row, text=t("send_to_edit"), state="disabled", command=self.send_to_i2i)
        self.edit_btn.pack(side="left", expand=True, padx=5)

        self.result_image = None
        self.result_raw = None
        self.is_busy = False
        self._tipo = None
        self._tipo_key = None

    def _ui(self, callback):
        self.after(0, callback)

    def _set_status(self, text):
        self._ui(lambda text=text: self.controller.status_label.configure(text=text))

    def _set_expanded_prompt(self, text):
        def update():
            self.expanded_prompt_txt.delete("1.0", "end")
            self.expanded_prompt_txt.insert("1.0", text)
        self._ui(update)

    def _set_generating(self, generating):
        self.is_busy = generating
        def update():
            if generating:
                self.controller.set_gen_btn_state("disabled", "GENERATING")
            else:
                self.controller.set_gen_btn_state("normal")
        self._ui(update)

    def _tipo_expander(self):
        model_path = self.config.get("tipo_model_path", "")
        gpu_layers = int(self.config.get("tipo_gpu_layers", -1))
        key = (model_path, gpu_layers)
        if self._tipo is None or self._tipo_key != key:
            self._tipo = TipoExpander(model_path, gpu_layers)
            self._tipo_key = key
        return self._tipo

    def display_result(self, pil_img, raw_bytes):
        self.result_image = pil_img
        self.result_raw = raw_bytes
        self.save_btn.configure(state="normal")
        self.edit_btn.configure(state="normal")
        self._render_image()

    def _render_result(self): # Compatibility
        self._render_image()

    def _render_image(self):
        if not self.result_image: return
        w, h = self.result_image.size
        pw = self.result_panel.winfo_width()
        ph = self.result_panel.winfo_height() - 60
        if pw < 10 or ph < 10: 
            self.after(100, self._render_image)
            return
        ratio = min(pw/w, ph/h)
        img = ctk.CTkImage(light_image=self.result_image, dark_image=self.result_image, size=(int(w*ratio), int(h*ratio)))
        self.img_label.configure(image=img, text="")

    def run_tipo_only(self):
        p = self.prompt_txt.get("1.0", "end-1c")
        rating = self.rating_var.get()
        ban_tags = self.ban_tags_entry.get()
        tipo_seed = random.randint(0, 2**31 - 1)
        expander = self._tipo_expander()

        def run():
            try:
                self._set_status("TIPO 추론 중")
                res = expander.expand(p, rating=rating, temperature=1.2,
                                      ban_tags=ban_tags, seed=tipo_seed)
                self._set_expanded_prompt(res)
            finally:
                self._set_status("Ready")
        threading.Thread(target=run, daemon=True).start()

    def generate(self):
        runner = self.controller.job_runner
        if runner.running:
            runner.stop()
            self._set_status("Stopping")
            return

        token = self.config.get("nai_token")
        if not token:
            return

        shared = self.controller.shared
        res = shared["res_var"].get().split('x')
        try:
            seed = int(shared["seed_var"].get())
        except ValueError:
            seed = -1
        auto_count_str = self.auto_count_var.get()
        auto_count = 999999 if auto_count_str == "∞" else int(auto_count_str)
        try:
            auto_delay = float(self.auto_delay_entry.get())
        except ValueError:
            auto_delay = 2.0

        job = T2IJob(
            token=token,
            model=shared["model_var"].get(),
            width=int(res[0]), height=int(res[1]),
            steps=int(shared["steps_var"].get()),
            cfg=float(shared["cfg_var"].get()),
            seed=seed,
            sampler=shared["sampler_var"].get(),
            scheduler=shared["scheduler_var"].get(),
            cfg_rescale=float(shared["cfg_rescale_var"].get()),
            prompt=self.prompt_txt.get("1.0", "end-1c"),
            neg_prompt=self.neg_prompt_txt.get("1.0", "end-1c"),
            wildcard_dir=self.config.get("wildcard_dir"),
            use_tipo=bool(self.tipo_switch.get()),
            rating=self.rating_var.get(),
            tipo_temp=1.2,
            ban_tags=self.ban_tags_entry.get(),
            style_name=self.style_var.get(),
            style_mode=self.style_mode_var.get(),
            art_presets=self.art_presets,
            face_detail=bool(self.workflow_switch.get()),
            face_model=shared["face_model_var"].get(),
            auto=bool(self.auto_gen_switch.get()),
            count=auto_count,
            delay=auto_delay,
        )

        cb = JobCallbacks(
            on_status=lambda text: self._set_status(text),
            on_expanded=lambda text: self._set_expanded_prompt(text),
            on_result=lambda stage, pil, raw: self._ui(
                lambda: self.display_result(pil, raw)),
            on_error=lambda msg: self._set_status(f"Error: {msg[:20]}"),
            on_done=lambda: self._set_generating(False),
        )

        self._set_generating(True)
        runner.start_t2i(job, self._tipo_expander(), cb)

    def send_to_i2i(self):
        self.controller.show_screen("I2I", image=self.result_image)

    def add_art_preset(self):
        name = self.new_style_entry.get().strip()
        tags = self.prompt_txt.get("1.0", "end-1c").strip()
        if name and tags:
            save_art_preset(name, tags)
            self.art_presets = load_art_presets()
            new_values = ["None", "Golden Recipe v3.1"] + [p["name"] for p in self.art_presets]
            self.style_menu.configure(values=new_values)
            self.new_style_entry.delete(0, "end")
            self._set_status(f"Saved style: {name}")

    def del_art_preset(self):
        name = self.style_var.get()
        if name not in ["None", "Golden Recipe v3.1"]:
            delete_art_preset(name)
            self.art_presets = load_art_presets()
            new_values = ["None", "Golden Recipe v3.1"] + [p["name"] for p in self.art_presets]
            self.style_menu.configure(values=new_values)
            self.style_var.set("Golden Recipe v3.1")
            self._set_status(f"Deleted style: {name}")
        else:
            self._set_status("기본 프리셋은 삭제할 수 없습니다.")
