import customtkinter as ctk
import tkinter as tk
import os
import threading
from tkinter import filedialog
from PIL import Image, ImageDraw, ImageTk
import io
import base64
import random
from datetime import datetime
from core.nai_client import post_nai, zip_to_pil, build_inpaint_payload
from ui.base import BaseScreen
from i18n import t
import numpy as np

def pil_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

class InpaintScreen(BaseScreen):
    def __init__(self, parent, controller, image=None):
        super().__init__(parent, controller)
        self.base_image = image
        self.mask_image = None
        self.overlay_image = None
        self.brush_size = 40
        self.display_w = 600
        self.display_h = 600
        self.tk_base_img = None
        self.tk_overlay_img = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Controls panel (left side, inside the 300px left_panel)
        left_panel = ctk.CTkScrollableFrame(self, fg_color=("#f5f5f5", "#0f0f0f"))
        left_panel.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        ctk.CTkButton(left_panel, text=t("load_image"), command=self.load_image).pack(fill="x", pady=5)
        ctk.CTkButton(left_panel, text=t("reset_mask"), command=self.reset_mask).pack(fill="x", pady=5)

        ctk.CTkLabel(left_panel, text=t("brush_size")).pack(anchor="w", pady=(10, 0))
        self.brush_slider = ctk.CTkSlider(left_panel, from_=1, to=100, command=lambda v: setattr(self, 'brush_size', int(v)))
        self.brush_slider.set(self.brush_size)
        self.brush_slider.pack(fill="x", pady=5)

        ctk.CTkLabel(left_panel, text=t("prompt")).pack(anchor="w")
        self.prompt_txt = ctk.CTkTextbox(left_panel, height=80)
        self.prompt_txt.pack(fill="x", pady=5)

        ctk.CTkLabel(left_panel, text=t("neg_prompt")).pack(anchor="w")
        self.neg_prompt_txt = ctk.CTkTextbox(left_panel, height=60)
        self.neg_prompt_txt.pack(fill="x", pady=(0, 10))
        self.neg_prompt_txt.insert("1.0", "lowres, {bad}, error, fewer, extra, missing, worst quality, jpeg artifacts, blurry")

        ctk.CTkLabel(left_panel, text=t("strength")).pack(anchor="w", pady=(10, 0))
        self.strength_slider = ctk.CTkSlider(left_panel, from_=0.0, to=1.0, number_of_steps=100)
        self.strength_slider.set(0.7)
        self.strength_slider.pack(fill="x", pady=5)

        # Canvas goes in controller.image_panel (the large right area)
        ip = controller.image_panel
        self.canvas_frame = ctk.CTkFrame(ip, fg_color=("#111111", "#111111"))
        self.canvas_frame.grid(row=0, column=0, sticky="nsew")
        self.canvas_frame.grid_remove()  # hidden until on_show

        self.canvas = tk.Canvas(self.canvas_frame, bg="#111111", cursor="cross", highlightthickness=0)
        self.canvas.pack(expand=True, fill="both")

        self.canvas.bind("<B1-Motion>", self.paint)
        self.canvas.bind("<Button-1>", self.paint)
        self.canvas_frame.bind("<Configure>", lambda e: self.setup_canvas() if self.base_image else None)

        if self.base_image:
            self.after(100, self.setup_canvas)

    def on_show(self):
        self.controller.result_label.grid_remove()
        self.controller.btn_row.grid_remove()
        self.canvas_frame.grid()
        if self.base_image:
            self.after(50, self.setup_canvas)

    def on_hide(self):
        self.canvas_frame.grid_remove()
        self.controller.result_label.grid()
        self.controller.btn_row.grid()

    def load_image(self):
        path = filedialog.askopenfilename()
        if path:
            self.base_image = Image.open(path).convert("RGB")
            self.setup_canvas()

    def setup_canvas(self):
        if not self.base_image: return

        w, h = self.base_image.size
        frame_w = self.canvas.winfo_width()
        frame_h = self.canvas.winfo_height()
        if frame_w <= 1 or frame_h <= 1:
            self.after(100, self.setup_canvas)
            return

        ratio = min(frame_w/w, frame_h/h)
        self.display_w, self.display_h = int(w * ratio), int(h * ratio)
        
        resized_img = self.base_image.resize((self.display_w, self.display_h), Image.LANCZOS)
        self.tk_base_img = ImageTk.PhotoImage(resized_img)
        
        self.canvas.config(width=self.display_w, height=self.display_h)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_base_img)
        
        self.mask_image = Image.new("L", (w, h), 0)
        self.draw = ImageDraw.Draw(self.mask_image)
        
        self.update_overlay()

    def paint(self, event):
        if not self.mask_image or not self.base_image: return

        x_ratio = self.base_image.width / self.display_w
        y_ratio = self.base_image.height / self.display_h

        # Center in image coordinates
        cx = event.x * x_ratio
        cy = event.y * y_ratio
        # Brush radius in image coords, minimum 16 so diameter >= 32px
        r = max(16, self.brush_size * x_ratio)

        grid = 8
        bx1 = max(0, int((cx - r) // grid) * grid)
        by1 = max(0, int((cy - r) // grid) * grid)
        bx2 = min(self.base_image.width, (int((cx + r) // grid) + 1) * grid)
        by2 = min(self.base_image.height, (int((cy + r) // grid) + 1) * grid)

        # Paint each 8px block whose center falls within brush radius
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

        base_rgba = display_base.convert("RGBA")
        base_arr = np.array(base_rgba, dtype=np.float32)
        mask_alpha = np.array(display_mask, dtype=np.float32) / 255.0

        overlay = base_arr.copy()
        overlay[:, :, 0] = np.clip(base_arr[:, :, 0] * (1 - mask_alpha * 0.5) + 255 * mask_alpha * 0.5, 0, 255)
        overlay[:, :, 1] = np.clip(base_arr[:, :, 1] * (1 - mask_alpha * 0.5), 0, 255)
        overlay[:, :, 2] = np.clip(base_arr[:, :, 2] * (1 - mask_alpha * 0.5), 0, 255)
        overlay[:, :, 3] = base_arr[:, :, 3]
        
        self.overlay_image = Image.fromarray(overlay.astype(np.uint8), "RGBA")
        self.display_canvas()

    def display_canvas(self):
        if not self.overlay_image: return
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

        # Step 1: quantize — any 8×8 block with a masked pixel → fill entire block
        result = np.zeros_like(arr)
        for y in range(0, h, grid):
            for x in range(0, w, grid):
                if arr[y:y + grid, x:x + grid].any():
                    result[y:y + grid, x:x + grid] = 255

        # Step 2: ensure minimum bounding box per masked region is 32px
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

        # Snap expanded bbox back to 8px grid
        x1 = (x1 // grid) * grid
        y1 = (y1 // grid) * grid
        x2 = min(w, ((x2 + grid) // grid) * grid)
        y2 = min(h, ((y2 + grid) // grid) * grid)

        # Fill expanded area into result so small regions meet minimum size
        result[y1:y2, x1:x2] = np.maximum(result[y1:y2, x1:x2], 255)

        return Image.fromarray(result, 'L')

    def generate(self):
        if not self.base_image or not self.mask_image: return
        token = self.config.get("nai_token")
        if not token: return

        self.controller.gen_btn.configure(state="disabled", text=t("generating"))
        
        try:
            prompt = self.prompt_txt.get("1.0", "end-1c")
            neg_prompt = self.neg_prompt_txt.get("1.0", "end-1c")
            w, h = self.base_image.size
            width = (w // 64) * 64
            height = (h // 64) * 64

            steps = int(self.controller.shared["steps_var"].get())
            cfg = float(self.controller.shared["cfg_var"].get())
            seed = int(self.controller.shared["seed_var"].get())
            if seed == -1:
                seed = random.randint(0, 2**31 - 1)
            strength = self.strength_slider.get()
            sampler = self.controller.shared["sampler_var"].get()
            scheduler = self.controller.shared["scheduler_var"].get()
            cfg_rescale = float(self.controller.shared["cfg_rescale_var"].get())
            model = self.controller.shared["model_var"].get()
            
            # force inpainting model if available? or just let the API use selected
            # but usually for NAI inpaint, we might want to override to nai-diffusion-3-inpainting. 
            # I will just use shared model as requested, but standard is nai-diffusion-3-inpainting. 
            # Actually, user spec: "제거: model... 위젯, ... inpaint: 기존 방식 유지 가능" Wait, I removed the model widget so I'll use the shared one.

            image_b64 = pil_to_base64(self.base_image)
            
            # Preprocess mask for NAI API
            processed_mask = self.prepare_mask_for_api(self.mask_image)
            mask_b64 = pil_to_base64(processed_mask)

            # Resolve Wildcards
            final_p = resolve_wildcards(prompt, self.config.get("wildcard_dir"))

            payload = build_inpaint_payload(
                model, final_p, neg_prompt,
                width, height, steps, cfg, seed, strength, image_b64, mask_b64,
                sampler=sampler, scheduler=scheduler, cfg_rescale=cfg_rescale
            )
            payload["parameters"]["extra_noise_seed"] = seed

        except ValueError as e:
            print(f"Invalid input: {e}")
            self.controller.gen_btn.configure(state="normal", text="Generate")
            return

        def worker():
            try:
                zip_bytes = post_nai(token, payload)
                pil_img, raw_bytes = zip_to_pil(zip_bytes)
                self.after(0, lambda: self.show_result(pil_img, raw_bytes))
                self.after(0, lambda: self.auto_save(raw_bytes))
            except Exception as e:
                print(f"Inpaint failed: {e}")
            finally:
                self.after(0, lambda: self.controller.gen_btn.configure(state="normal", text="Generate"))

        threading.Thread(target=worker, daemon=True).start()

    def show_result(self, pil_img, raw_bytes):
        top = ctk.CTkToplevel(self)
        top.title(t("inpaint_result"))
        
        w, h = pil_img.size
        ratio = min(800/w, 800/h)
        nw, nh = int(w*ratio), int(h*ratio)
        
        img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(nw, nh))
        label = ctk.CTkLabel(top, image=img, text="")
        label.pack(padx=20, pady=20)
        
        ctk.CTkButton(top, text=t("save"), command=lambda: self.save_result(top, raw_bytes)).pack(pady=10)

    def auto_save(self, raw_bytes):
        if not raw_bytes: return
        base_dir = os.path.join(os.path.expanduser("~"), "Downloads", "NAI")
        date_str = datetime.now().strftime("%Y-%m-%d")
        full_path = os.path.join(base_dir, date_str)
        os.makedirs(full_path, exist_ok=True)
        
        time_str = datetime.now().strftime("%y%m%d_%H%M%S")
        filename = f"NAI_inpaint_{time_str}.png"
        save_path = os.path.join(full_path, filename)
        with open(save_path, "wb") as f:
            f.write(raw_bytes)
        print(f"Saved to {save_path}")

    def save_result(self, window, raw_bytes):
        path = filedialog.asksaveasfilename(defaultextension=".png")
        if path and raw_bytes:
            with open(path, "wb") as f:
                f.write(raw_bytes)
            window.destroy()
