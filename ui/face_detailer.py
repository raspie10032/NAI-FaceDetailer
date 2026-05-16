import customtkinter as ctk
import os
import io
import base64
import random
import threading
import time
from PIL import Image
from datetime import datetime
from tkinter import filedialog
from config import get_output_dir
from nai_api import post_nai, zip_to_pil, build_inpaint_payload
from ui.base import BaseScreen
from i18n import t

def pil_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

class FaceDetailerScreen(BaseScreen):
    def __init__(self, parent, controller, image=None, auto_run=False, prompt=None, neg_prompt=None):
        super().__init__(parent, controller)
        self.input_image = image
        self.auto_run = auto_run
        self._auto_neg = neg_prompt or "lowres, bad anatomy, bad hands, missing fingers, extra fingers"
        self._initial_prompt = prompt
        
        self.yolo_model = None
        self.eyes_model = None
        self.sam_model = None
        self.result_image = None
        self.result_raw = None
        self.is_busy = False

        self.grid_columnconfigure(0, weight=0) # Controls
        self.grid_columnconfigure(1, weight=1) # Result
        self.grid_rowconfigure(0, weight=1)

        # ── Left: Controls Panel ──────────────────────────
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

        # ── Right: Result Panel ──────────────────────────
        self.result_panel = ctk.CTkFrame(self, corner_radius=0, fg_color=("#e8e8e8", "#111111"))
        self.result_panel.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.result_panel.grid_rowconfigure(0, weight=1)
        self.result_panel.grid_columnconfigure(0, weight=1)

        self.img_label = ctk.CTkLabel(self.result_panel, text=t("waiting_result"))
        self.img_label.grid(row=0, column=0, sticky="nsew")

        # Result Buttons
        r_btn_row = ctk.CTkFrame(self.result_panel, fg_color="transparent")
        r_btn_row.grid(row=1, column=0, sticky="ew", pady=10)
        self.save_btn = ctk.CTkButton(r_btn_row, text=t("save_short"), state="disabled", command=self.controller.save_result)
        self.save_btn.pack(side="left", expand=True, padx=5)
        
        if self.input_image: 
            self.display_input(self.input_image)
        if self._initial_prompt:
            self.prompt_txt.insert("1.0", self._initial_prompt)

    def set_params(self, image=None, auto_run=False, prompt=None, neg_prompt=None):
        if image is not None:
            self.input_image = image
            self.display_input(image)
        if prompt is not None:
            self.prompt_txt.delete("1.0", "end")
            self.prompt_txt.insert("1.0", prompt)
        if neg_prompt is not None:
            self._auto_neg = neg_prompt
        if auto_run:
            self.auto_run = True

    def on_show(self):
        if getattr(self, "auto_run", False):
            self.auto_run = False
            self._active_auto_run = True # Set flag for generate()
            # Give a small delay for UI to update
            self.after(500, self.generate)

    def load_image(self):
        path = filedialog.askopenfilename()
        if path:
            self.input_image = Image.open(path).convert("RGB")
            self.display_input(self.input_image)

    def display_input(self, pil_img):
        w, h = pil_img.size
        pw = 360 # Fixed width for left panel minus padding
        ratio = pw / w
        nw, nh = int(w*ratio), int(h*ratio)
        if nh > 300: # Max height
            ratio = 300 / h
            nw, nh = int(w*ratio), int(h*ratio)
        img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(nw, nh))
        self.input_label.configure(image=img, text="")

    def display_result(self, pil_img, raw_bytes):
        self.result_image = pil_img
        self.result_raw = raw_bytes
        self.save_btn.configure(state="normal")
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

    def download_models(self):
        from huggingface_hub import hf_hub_download
        import urllib.request
        cache_dir = os.path.expanduser("~/.nai_studio/models")
        os.makedirs(cache_dir, exist_ok=True)

        yolo_path = os.path.join(cache_dir, "face_yolov8n.pt")
        if not os.path.exists(yolo_path):
            print("[FaceDetailer] Downloading YOLO model...")
            hf_hub_download('Bingsu/adetailer', 'face_yolov8n.pt', local_dir=cache_dir)

        eyes_path = os.path.join(cache_dir, "full_eyes_detect_v1.pt")
        if not os.path.exists(eyes_path):
            print("[FaceDetailer] Downloading Eyes model...")
            eyes_url = "https://huggingface.co/guon/hand-eyes/resolve/main/full_eyes_detect_v1.pt"
            urllib.request.urlretrieve(eyes_url, eyes_path)

        sam_path = os.path.join(cache_dir, "sam_b.pt")
        if not os.path.exists(sam_path):
            print("[FaceDetailer] Downloading SAM model...")
            sam_url = "https://github.com/ultralytics/assets/releases/download/v8.3.0/sam_b.pt"
            urllib.request.urlretrieve(sam_url, sam_path)

        return yolo_path, sam_path, eyes_path

    def _set_status(self, text):
        self.after(0, lambda: self.controller.status_label.configure(text=text))

    def generate(self):
        if not self.input_image: 
            print("[FaceDetailer] No input image.")
            return

        token = self.config.get("nai_token")
        if not token: 
            print("[FaceDetailer] No NAI token.")
            return

        # Collect params
        shared = self.controller.shared
        try:
            steps = int(shared["steps_var"].get())
            cfg = float(shared["cfg_var"].get())
            seed = int(shared["seed_var"].get())
            if seed == -1: seed = random.randint(0, 2**31 - 1)
            sampler = shared["sampler_var"].get()
            scheduler = shared["scheduler_var"].get()
            cfg_rescale = float(shared["cfg_rescale_var"].get())
            model = shared["face_model_var"].get()
        except Exception as e:
            print(f"[FaceDetailer] Error getting shared params: {e}")
            steps, cfg, seed = 28, 6.0, random.randint(0, 2**31 - 1)
            sampler, scheduler, cfg_rescale = "k_euler_ancestral", "karras", 0.0
            model = "nai-diffusion-3"

        # Fixed internal models
        det_model, seg_model = "face_yolov8n.pt", "sam_b.pt"

        prompt_text = self.prompt_txt.get("1.0", "end-1c")
        neg_text = getattr(self, "_auto_neg", "lowres, bad anatomy, bad hands, missing fingers, extra fingers")
        strength = self.strength_slider.get()
        try:
            bbox_thresh = float(self.bbox_thresh.get())
        except:
            bbox_thresh = 0.5
        input_image = self.input_image.copy()

        # Keep track if this was an auto-run to avoid re-enabling button prematurely
        is_auto = getattr(self, "_active_auto_run", False)
        # Reset the internal flag for next time
        self._active_auto_run = False

        self.is_busy = True
        if not is_auto:
            self.controller.set_gen_btn_state("disabled", t("running_detecting"))
        self._set_status("얼굴 감지 중")

        def worker():
            import traceback as _tb
            try:
                import numpy as np
                import torch
                from ultralytics import YOLO, SAM
                yolo_path, sam_path, eyes_path = self.download_models()

                # Device selection
                device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
                print(f"[FaceDetailer] Using device: {device}")

                if not self.yolo_model or getattr(self, "_current_yolo_path", "") != yolo_path:
                    print(f"[FaceDetailer] Loading YOLO: {yolo_path}")
                    self.yolo_model = YOLO(yolo_path).to(device)
                    self._current_yolo_path = yolo_path

                # Detect faces (Primary)
                results = self.yolo_model(input_image, conf=bbox_thresh, verbose=False)
                bboxes = results[0].boxes.xyxy.cpu().numpy() if (results and len(results[0].boxes) > 0) else np.empty((0, 4))
                
                # Detect eyes (Secondary)
                if eyes_path:
                    if not self.eyes_model or getattr(self, "_current_eyes_path", "") != eyes_path:
                        print(f"[FaceDetailer] Loading Eyes YOLO: {eyes_path}")
                        self.eyes_model = YOLO(eyes_path).to(device)
                        self._current_eyes_path = eyes_path
                    
                    eyes_results = self.eyes_model(input_image, conf=bbox_thresh, verbose=False)
                    if eyes_results and len(eyes_results[0].boxes) > 0:
                        eyes_bboxes = eyes_results[0].boxes.xyxy.cpu().numpy()
                        bboxes = np.concatenate([bboxes, eyes_bboxes], axis=0)

                if len(bboxes) == 0:
                    print("[FaceDetailer] No detections.")
                    self._set_status("감지된 대상이 없습니다")
                    return

                print(f"[FaceDetailer] {len(bboxes)} detection(s) combined.")

                if not is_auto:
                    self.after(0, lambda: self.controller.set_gen_btn_state("disabled", t("running_segmenting")))
                self._set_status(f"{len(bboxes)}개 영역 분할 중")

                img_np = np.array(input_image.convert("RGB"))
                combined_mask = np.zeros(img_np.shape[:2], dtype=np.uint8)

                if not self.sam_model or getattr(self, "_current_sam_path", "") != sam_path:
                    print(f"[FaceDetailer] Loading SAM: {sam_path}")
                    self.sam_model = SAM(sam_path).to(device)
                    self._current_sam_path = sam_path
                
                bboxes_list = [b.tolist() for b in bboxes]
                
                try:
                    sam_results = self.sam_model(img_np, bboxes=bboxes_list, verbose=False)
                    if sam_results and sam_results[0].masks is not None:
                        for mask_tensor in sam_results[0].masks.data:
                            mask_np = mask_tensor.cpu().numpy()
                            mask_img = Image.fromarray((mask_np * 255).astype(np.uint8)).resize(
                                input_image.size, Image.NEAREST
                            )
                            combined_mask = np.maximum(combined_mask, np.array(mask_img))
                except Exception as sam_err:
                    print(f"[FaceDetailer] SAM Error (falling back to bboxes): {sam_err}")
                    for box in bboxes:
                        x1, y1, x2, y2 = map(int, box)
                        combined_mask[y1:y2, x1:x2] = 255

                # NAI inpaint grid alignment (32px box, 8px step)
                BOX_SIZE, GRID_STEP = 32, 8
                h_m, w_m = combined_mask.shape
                grid_mask = np.zeros_like(combined_mask)
                
                for y in range(0, h_m - BOX_SIZE + 1, GRID_STEP):
                    for x in range(0, w_m - BOX_SIZE + 1, GRID_STEP):
                        window = combined_mask[y:y + BOX_SIZE, x:x + BOX_SIZE]
                        if window.size > 0 and np.mean(window) > (255 * 0.3):
                            grid_mask[y:y + BOX_SIZE, x:x + BOX_SIZE] = 255

                mask_pil = Image.fromarray(grid_mask)

                if not is_auto:
                    self.after(0, lambda: self.controller.set_gen_btn_state("disabled", t("running_api")))
                self._set_status("NAI API 호출 중")

                img_b64 = pil_to_base64(input_image)
                mask_b64 = pil_to_base64(mask_pil)
                w, h = input_image.width, input_image.height

                payload = build_inpaint_payload(
                    model, prompt_text, neg_text,
                    w, h, steps, cfg, seed,
                    strength=strength,
                    image_b64=img_b64, mask_b64=mask_b64,
                    sampler=sampler, scheduler=scheduler, cfg_rescale=cfg_rescale
                )
                
                # V4 prompt fix
                if "parameters" in payload and "v4_prompt" in payload["parameters"]:
                    payload["parameters"]["v4_prompt"]["caption"]["base_caption"] = prompt_text

                print(f"[FaceDetailer] Calling NAI API (model={payload.get('model')})...")
                zip_bytes = post_nai(token, payload)
                pil_img, raw_bytes = zip_to_pil(zip_bytes)
                
                print("[FaceDetailer] Successfully received result.")
                self.after(0, lambda: self.controller.display_result(pil_img, raw_bytes))
                self.after(0, lambda: self.auto_save(raw_bytes))
                self._set_status("완료")

            except Exception as e:
                print(f"[FaceDetailer] Failed: {e}")
                _tb.print_exc()
                self._set_status(f"Error: {str(e)[:30]}")
            finally:
                self.is_busy = False
                # Only re-enable button if this was NOT part of an automated pipeline
                if not is_auto:
                    self.after(0, lambda: self.controller.set_gen_btn_state("normal"))
                else:
                    print("[FaceDetailer] Auto-run finished, signaling T2I loop.")
                    self.controller.pipeline_event.set()

        threading.Thread(target=worker, daemon=True).start()

    def auto_save(self, raw_bytes):
        if not raw_bytes: return
        base_dir = get_output_dir("FaceDetailer")
        date_str = datetime.now().strftime("%Y-%m-%d")
        full_path = os.path.join(base_dir, date_str)
        os.makedirs(full_path, exist_ok=True)
        
        filename = f"FaceDetailer_{int(time.time())}.png"
        save_path = os.path.join(full_path, filename)
        with open(save_path, "wb") as f:
            f.write(raw_bytes)
        print(f"[FaceDetailer] Saved to {save_path}")
