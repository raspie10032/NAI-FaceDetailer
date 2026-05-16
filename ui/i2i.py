import customtkinter as ctk
import os
import base64
import io
import random
import threading
from PIL import Image
from datetime import datetime
from tkinter import filedialog
from core.nai_client import post_nai, zip_to_pil, build_i2i_payload
from ui.base import BaseScreen
from i18n import t

def pil_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

class I2IScreen(BaseScreen):
    def __init__(self, parent, controller, image=None):
        super().__init__(parent, controller)
        self.input_image = image

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        left_panel = ctk.CTkScrollableFrame(self, fg_color=("#f5f5f5", "#0f0f0f"))
        left_panel.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        self.load_btn = ctk.CTkButton(left_panel, text=t("load_image"), command=self.load_image)
        self.load_btn.pack(fill="x", pady=10)

        self.input_label = ctk.CTkLabel(left_panel, text=t("no_input_image"), height=200)
        self.input_label.pack(fill="x", pady=10)
        if self.input_image:
            self.display_input_image(self.input_image)

        ctk.CTkLabel(left_panel, text=t("prompt")).pack(anchor="w")
        self.prompt_txt = ctk.CTkTextbox(left_panel, height=80)
        self.prompt_txt.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(left_panel, text=t("neg_prompt")).pack(anchor="w")
        self.neg_prompt_txt = ctk.CTkTextbox(left_panel, height=60)
        self.neg_prompt_txt.pack(fill="x", pady=(0, 10))
        self.neg_prompt_txt.insert("1.0", "lowres, {bad}, error, fewer, extra, missing, worst quality, jpeg artifacts, blurry")

        ctk.CTkLabel(left_panel, text=t("strength")).pack(anchor="w", pady=(10,0))
        self.strength_slider = ctk.CTkSlider(left_panel, from_=0.0, to=1.0, number_of_steps=100)
        self.strength_slider.pack(fill="x", pady=(0, 10))
        self.strength_slider.set(0.7)

    def load_image(self):
        path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp")])
        if path:
            self.input_image = Image.open(path).convert("RGB")
            self.display_input_image(self.input_image)

    def display_input_image(self, pil_img):
        w, h = pil_img.size
        ratio = min(200/w, 200/h)
        new_w, new_h = int(w * ratio), int(h * ratio)
        self._input_ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(new_w, new_h))
        self.input_label.configure(image=self._input_ctk_img, text="")

    def generate(self):
        if not self.input_image:
            print("Error: Load an image first.")
            return
        
        token = self.config.get("nai_token")
        if not token: return

        self.controller.gen_btn.configure(state="disabled", text=t("generating"))
        
        try:
            prompt = self.prompt_txt.get("1.0", "end-1c")
            neg_prompt = self.neg_prompt_txt.get("1.0", "end-1c")
            
            w, h = self.input_image.size
            width = (w // 64) * 64
            height = (h // 64) * 64

            steps = int(self.controller.shared["steps_var"].get())
            cfg = float(self.controller.shared["cfg_var"].get())
            seed = int(self.controller.shared["seed_var"].get())
            if seed == -1:
                seed = random.randint(0, 2**31 - 1)
            cfg_rescale = float(self.controller.shared["cfg_rescale_var"].get())
            sampler = self.controller.shared["sampler_var"].get()
            scheduler = self.controller.shared["scheduler_var"].get()
            model = self.controller.shared["model_var"].get()
            strength = self.strength_slider.get()

            image_b64 = pil_to_base64(self.input_image)
            
            payload = build_i2i_payload(
                model, prompt, neg_prompt,
                width, height, steps, cfg, seed, strength, image_b64,
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
                self.after(0, lambda: self.controller.display_result(pil_img, raw_bytes))
                self.after(0, lambda: self.auto_save(raw_bytes))
            except Exception as e:
                print(f"I2I failed: {e}")
            finally:
                self.after(0, lambda: self.controller.gen_btn.configure(state="normal", text="Generate"))

        threading.Thread(target=worker, daemon=True).start()

    def auto_save(self, raw_bytes):
        if not raw_bytes: return
        base_dir = os.path.join(os.path.expanduser("~"), "Downloads", "NAI")
        date_str = datetime.now().strftime("%Y-%m-%d")
        full_path = os.path.join(base_dir, date_str)
        os.makedirs(full_path, exist_ok=True)
        
        time_str = datetime.now().strftime("%y%m%d_%H%M%S")
        filename = f"NAI_{time_str}.png"
        save_path = os.path.join(full_path, filename)
        with open(save_path, "wb") as f:
            f.write(raw_bytes)
        print(f"Saved to {save_path}")
