import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageDraw, ImageTk
import numpy as np

from app.job_runner import InpaintJob, JobCallbacks
from ui.base import BaseScreen
from i18n import t


class InpaintScreen(BaseScreen):
    """Brush a mask over an image and regenerate the masked region."""

    def __init__(self, parent, controller, image=None):
        super().__init__(parent, controller)
        self.base_image = image
        self.mask_image = None
        self.overlay_image = None
        self.brush_size = 40
        self.display_w = 600
        self.display_h = 600
        self.tk_overlay_img = None
        self.is_busy = False

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Left: Controls ──────────────────────────────────
        left_panel = ctk.CTkScrollableFrame(self, width=380, fg_color=("#f5f5f5", "#0f0f0f"))
        left_panel.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        ctk.CTkButton(left_panel, text=t("load_image"), command=self.load_image).pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(left_panel, text=t("reset_mask"), command=self.reset_mask).pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(left_panel, text=t("brush_size")).pack(anchor="w", padx=10, pady=(10, 0))
        self.brush_slider = ctk.CTkSlider(left_panel, from_=1, to=100,
                                          command=lambda v: setattr(self, 'brush_size', int(v)))
        self.brush_slider.set(self.brush_size)
        self.brush_slider.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(left_panel, text=t("prompt")).pack(anchor="w", padx=10)
        self.prompt_txt = ctk.CTkTextbox(left_panel, height=80)
        self.prompt_txt.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(left_panel, text=t("neg_prompt")).pack(anchor="w", padx=10)
        self.neg_prompt_txt = ctk.CTkTextbox(left_panel, height=60)
        self.neg_prompt_txt.pack(fill="x", padx=10, pady=(0, 10))
        self.neg_prompt_txt.insert("1.0", "lowres, bad anatomy, error, fewer, extra, missing, worst quality, jpeg artifacts, blurry")

        ctk.CTkLabel(left_panel, text=t("strength")).pack(anchor="w", padx=10, pady=(10, 0))
        self.strength_slider = ctk.CTkSlider(left_panel, from_=0.0, to=1.0, number_of_steps=100)
        self.strength_slider.set(0.7)
        self.strength_slider.pack(fill="x", padx=10, pady=5)

        # ── Right: Paint canvas ─────────────────────────────
        self.canvas_frame = ctk.CTkFrame(self, fg_color=("#111111", "#111111"))
        self.canvas_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        self.canvas = tk.Canvas(self.canvas_frame, bg="#111111", cursor="cross", highlightthickness=0)
        self.canvas.pack(expand=True, fill="both")
        self.canvas.bind("<B1-Motion>", self.paint)
        self.canvas.bind("<Button-1>", self.paint)
        self.canvas_frame.bind("<Configure>", lambda e: self.setup_canvas() if self.base_image else None)

        if self.base_image:
            self.after(100, self.setup_canvas)

    def set_params(self, image=None, **kwargs):
        if image is not None:
            self.base_image = image
            self.after(50, self.setup_canvas)

    def load_image(self):
        path = filedialog.askopenfilename()
        if path:
            self.base_image = Image.open(path).convert("RGB")
            self.setup_canvas()

    def setup_canvas(self):
        if not self.base_image:
            return
        w, h = self.base_image.size
        frame_w = self.canvas.winfo_width()
        frame_h = self.canvas.winfo_height()
        if frame_w <= 1 or frame_h <= 1:
            self.after(100, self.setup_canvas)
            return
        ratio = min(frame_w / w, frame_h / h)
        self.display_w, self.display_h = int(w * ratio), int(h * ratio)
        self.mask_image = Image.new("L", (w, h), 0)
        self.draw = ImageDraw.Draw(self.mask_image)
        self.update_overlay()

    def paint(self, event):
        if not self.mask_image or not self.base_image:
            return
        x_ratio = self.base_image.width / self.display_w
        y_ratio = self.base_image.height / self.display_h
        cx = event.x * x_ratio
        cy = event.y * y_ratio
        r = max(16, self.brush_size * x_ratio)

        grid = 8
        bx1 = max(0, int((cx - r) // grid) * grid)
        by1 = max(0, int((cy - r) // grid) * grid)
        bx2 = min(self.base_image.width, (int((cx + r) // grid) + 1) * grid)
        by2 = min(self.base_image.height, (int((cy + r) // grid) + 1) * grid)

        for by in range(by1, by2, grid):
            for bx in range(bx1, bx2, grid):
                block_cx = bx + grid / 2
                block_cy = by + grid / 2
                if (block_cx - cx) ** 2 + (block_cy - cy) ** 2 <= r ** 2:
                    x_end = min(self.base_image.width, bx + grid)
                    y_end = min(self.base_image.height, by + grid)
                    self.draw.rectangle([bx, by, x_end - 1, y_end - 1], fill=255)
        self.update_overlay()

    def update_overlay(self):
        if not self.base_image or not self.mask_image:
            return
        display_base = self.base_image.resize((self.display_w, self.display_h), Image.LANCZOS)
        display_mask = self.mask_image.resize((self.display_w, self.display_h), Image.NEAREST)
        base_arr = np.array(display_base.convert("RGBA"), dtype=np.float32)
        mask_alpha = np.array(display_mask, dtype=np.float32) / 255.0

        overlay = base_arr.copy()
        overlay[:, :, 0] = np.clip(base_arr[:, :, 0] * (1 - mask_alpha * 0.5) + 255 * mask_alpha * 0.5, 0, 255)
        overlay[:, :, 1] = np.clip(base_arr[:, :, 1] * (1 - mask_alpha * 0.5), 0, 255)
        overlay[:, :, 2] = np.clip(base_arr[:, :, 2] * (1 - mask_alpha * 0.5), 0, 255)
        overlay[:, :, 3] = base_arr[:, :, 3]
        self.overlay_image = Image.fromarray(overlay.astype(np.uint8), "RGBA")
        self.display_canvas()

    def display_canvas(self):
        if not self.overlay_image:
            return
        self.tk_overlay_img = ImageTk.PhotoImage(self.overlay_image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_overlay_img)

    def reset_mask(self):
        if self.base_image:
            self.mask_image = Image.new("L", self.base_image.size, 0)
            self.draw = ImageDraw.Draw(self.mask_image)
            self.update_overlay()

    def prepare_mask_for_api(self, mask_img, grid=8, min_box=32):
        """Snap mask to 8px grid; ensure each masked region is at least 32px."""
        arr = np.array(mask_img)
        h, w = arr.shape
        result = np.zeros_like(arr)
        for y in range(0, h, grid):
            for x in range(0, w, grid):
                if arr[y:y + grid, x:x + grid].any():
                    result[y:y + grid, x:x + grid] = 255

        ys, xs = np.where(result > 0)
        if len(ys) == 0:
            return Image.fromarray(result, 'L')

        y1, y2 = int(ys.min()), int(ys.max())
        x1, x2 = int(xs.min()), int(xs.max())
        if (y2 - y1 + 1) < min_box:
            pad = (min_box - (y2 - y1 + 1) + 1) // 2
            y1 = max(0, y1 - pad)
            y2 = min(h - 1, y1 + min_box - 1)
        if (x2 - x1 + 1) < min_box:
            pad = (min_box - (x2 - x1 + 1) + 1) // 2
            x1 = max(0, x1 - pad)
            x2 = min(w - 1, x1 + min_box - 1)

        x1 = (x1 // grid) * grid
        y1 = (y1 // grid) * grid
        x2 = min(w, ((x2 + grid) // grid) * grid)
        y2 = min(h, ((y2 + grid) // grid) * grid)
        result[y1:y2, x1:x2] = np.maximum(result[y1:y2, x1:x2], 255)
        return Image.fromarray(result, 'L')

    def _set_status(self, text):
        self.after(0, lambda: self.controller.status_label.configure(text=text))

    def _set_busy(self, busy):
        self.is_busy = busy
        self.controller.set_gen_btn_state("disabled", t("generating")) if busy \
            else self.controller.set_gen_btn_state("normal")

    def generate(self):
        runner = self.controller.job_runner
        if runner.running:
            runner.stop()
            self._set_status("Stopping")
            return
        if not self.base_image or not self.mask_image:
            return
        token = self.config.get("nai_token")
        if not token:
            return

        shared = self.controller.shared
        w, h = self.base_image.size
        try:
            seed = int(shared["seed_var"].get())
        except ValueError:
            seed = -1

        job = InpaintJob(
            token=token,
            image=self.base_image,
            mask=self.prepare_mask_for_api(self.mask_image),
            model=shared["model_var"].get(),
            prompt=self.prompt_txt.get("1.0", "end-1c"),
            neg_prompt=self.neg_prompt_txt.get("1.0", "end-1c"),
            width=(w // 64) * 64,
            height=(h // 64) * 64,
            steps=int(shared["steps_var"].get()),
            cfg=float(shared["cfg_var"].get()),
            seed=seed,
            sampler=shared["sampler_var"].get(),
            scheduler=shared["scheduler_var"].get(),
            cfg_rescale=float(shared["cfg_rescale_var"].get()),
            wildcard_dir=self.config.get("wildcard_dir", ""),
            strength=self.strength_slider.get(),
        )

        cb = JobCallbacks(
            on_status=lambda text: self._set_status(text),
            on_result=lambda stage, pil, raw: self.after(
                0, lambda: self.show_result(pil, raw)),
            on_error=lambda msg: self._set_status(f"Error: {msg[:30]}"),
            on_done=lambda: self.after(0, lambda: self._set_busy(False)),
        )

        self._set_busy(True)
        runner.start_inpaint(job, cb)

    def show_result(self, pil_img, raw_bytes):
        self.controller.display_result(pil_img, raw_bytes)
        top = ctk.CTkToplevel(self)
        top.title(t("inpaint_result"))
        w, h = pil_img.size
        ratio = min(800 / w, 800 / h)
        img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img,
                           size=(int(w * ratio), int(h * ratio)))
        ctk.CTkLabel(top, image=img, text="").pack(padx=20, pady=20)
        ctk.CTkButton(top, text=t("save"),
                      command=lambda: self._save(top, raw_bytes)).pack(pady=10)

    def _save(self, window, raw_bytes):
        path = filedialog.asksaveasfilename(defaultextension=".png")
        if path and raw_bytes:
            with open(path, "wb") as f:
                f.write(raw_bytes)
            window.destroy()
