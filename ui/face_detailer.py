import customtkinter as ctk
from tkinter import filedialog
from PIL import Image

from app.job_runner import FaceJob, JobCallbacks
from ui.base import BaseScreen
from i18n import t

DEFAULT_NEG = "lowres, bad anatomy, bad hands, missing fingers, extra fingers"


class FaceDetailerScreen(BaseScreen):
    """Standalone Face Detailer (load an image, fix faces/eyes).

    The automated T2I -> Face Detail pipeline is owned by JobRunner now,
    so this screen no longer participates in any cross-screen handshake.
    """

    def __init__(self, parent, controller, image=None):
        super().__init__(parent, controller)
        self.input_image = image
        self.result_image = None
        self.result_raw = None

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Left: Controls ──────────────────────────────────
        self.left_panel = ctk.CTkScrollableFrame(self, width=380, fg_color=("#f5f5f5", "#0f0f0f"))
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        ctk.CTkLabel(self.left_panel, text=t("face_detailer_title"), font=("", 14, "bold"), text_color="#1f6aa5").pack(anchor="w", padx=10, pady=(10, 5))

        ctk.CTkButton(self.left_panel, text=t("load_image"), command=self.load_image).pack(fill="x", padx=10, pady=5)

        self.input_label = ctk.CTkLabel(self.left_panel, text=t("no_image"), height=200, fg_color=("#e0e0e0", "#151515"), corner_radius=10)
        self.input_label.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(self.left_panel, text=t("prompt"), font=("", 11, "bold")).pack(anchor="w", padx=10)
        self.prompt_txt = ctk.CTkTextbox(self.left_panel, height=100, border_width=1, border_color="gray30")
        self.prompt_txt.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(self.left_panel, text=t("strength"), font=("", 11, "bold")).pack(anchor="w", padx=10)
        self.strength_slider = ctk.CTkSlider(self.left_panel, from_=0.0, to=1.0)
        self.strength_slider.set(0.55)
        self.strength_slider.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(self.left_panel, text=t("bbox_thresh"), font=("", 11, "bold")).pack(anchor="w", padx=10)
        self.bbox_thresh = ctk.CTkEntry(self.left_panel)
        self.bbox_thresh.insert(0, "0.5")
        self.bbox_thresh.pack(fill="x", padx=10, pady=5)

        # ── Right: Result ───────────────────────────────────
        self.result_panel = ctk.CTkFrame(self, corner_radius=0, fg_color=("#e8e8e8", "#111111"))
        self.result_panel.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.result_panel.grid_rowconfigure(0, weight=1)
        self.result_panel.grid_columnconfigure(0, weight=1)

        self.img_label = ctk.CTkLabel(self.result_panel, text=t("waiting_result"))
        self.img_label.grid(row=0, column=0, sticky="nsew")

        r_btn_row = ctk.CTkFrame(self.result_panel, fg_color="transparent")
        r_btn_row.grid(row=1, column=0, sticky="ew", pady=10)
        self.save_btn = ctk.CTkButton(r_btn_row, text=t("save_short"), state="disabled", command=self.controller.save_result)
        self.save_btn.pack(side="left", expand=True, padx=5)

        if self.input_image:
            self.display_input(self.input_image)

    def set_params(self, image=None, **kwargs):
        if image is not None:
            self.input_image = image
            self.display_input(image)

    def load_image(self):
        path = filedialog.askopenfilename()
        if path:
            self.input_image = Image.open(path).convert("RGB")
            self.display_input(self.input_image)

    def display_input(self, pil_img):
        w, h = pil_img.size
        ratio = 360 / w
        nw, nh = int(w * ratio), int(h * ratio)
        if nh > 300:
            ratio = 300 / h
            nw, nh = int(w * ratio), int(h * ratio)
        img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(nw, nh))
        self.input_label.configure(image=img, text="")

    def display_result(self, pil_img, raw_bytes):
        self.result_image = pil_img
        self.result_raw = raw_bytes
        self.save_btn.configure(state="normal")
        self._render_image()

    def _render_image(self):
        if not self.result_image:
            return
        w, h = self.result_image.size
        pw = self.result_panel.winfo_width()
        ph = self.result_panel.winfo_height() - 60
        if pw < 10 or ph < 10:
            self.after(100, self._render_image)
            return
        ratio = min(pw / w, ph / h)
        img = ctk.CTkImage(light_image=self.result_image, dark_image=self.result_image, size=(int(w * ratio), int(h * ratio)))
        self.img_label.configure(image=img, text="")

    def _set_status(self, text):
        self.after(0, lambda: self.controller.status_label.configure(text=text))

    def _set_busy(self, busy):
        if busy:
            self.controller.set_gen_btn_state("disabled", t("running_detecting"))
        else:
            self.controller.set_gen_btn_state("normal")

    def generate(self):
        runner = self.controller.job_runner
        if runner.running:
            runner.stop()
            self._set_status("Stopping")
            return

        if not self.input_image:
            print("[FaceDetailer] No input image.")
            return
        token = self.config.get("nai_token")
        if not token:
            print("[FaceDetailer] No NAI token.")
            return

        shared = self.controller.shared
        try:
            seed = int(shared["seed_var"].get())
        except ValueError:
            seed = -1
        try:
            bbox_thresh = float(self.bbox_thresh.get())
        except ValueError:
            bbox_thresh = 0.5

        job = FaceJob(
            token=token,
            image=self.input_image.copy(),
            model=shared["face_model_var"].get(),
            prompt=self.prompt_txt.get("1.0", "end-1c"),
            neg_prompt=DEFAULT_NEG,
            steps=int(shared["steps_var"].get()),
            cfg=float(shared["cfg_var"].get()),
            seed=seed,
            sampler=shared["sampler_var"].get(),
            scheduler=shared["scheduler_var"].get(),
            cfg_rescale=float(shared["cfg_rescale_var"].get()),
            strength=self.strength_slider.get(),
            bbox_thresh=bbox_thresh,
        )

        cb = JobCallbacks(
            on_status=lambda text: self._set_status(text),
            on_result=lambda stage, pil, raw: self.after(
                0, lambda: self.controller.display_result(pil, raw)),
            on_error=lambda msg: self._set_status(f"Error: {msg[:30]}"),
            on_done=lambda: self.after(0, lambda: self._set_busy(False)),
        )

        self._set_busy(True)
        runner.start_face(job, cb)
