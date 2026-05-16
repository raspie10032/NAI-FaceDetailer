"""Face/eye detection + segmentation, decoupled from the UI.

Heavy deps (torch/ultralytics) are imported lazily so `import core.*`
works without them. Model handles are cached on the FacePipeline
instance instead of on a Tkinter widget.
"""

import os
import urllib.request

import numpy as np
from PIL import Image

MODEL_DIR = os.path.expanduser("~/.nai_studio/models")


def align_mask_to_grid(mask, box_size=32, grid_step=8, threshold=0.3):
    """Snap a 0/255 mask to NAI's inpaint grid.

    Any `box_size` window (stepped by `grid_step`) whose mean coverage
    exceeds `threshold` is filled solid. Pure numpy — unit testable.
    """
    h, w = mask.shape
    grid_mask = np.zeros_like(mask)
    for y in range(0, h - box_size + 1, grid_step):
        for x in range(0, w - box_size + 1, grid_step):
            window = mask[y:y + box_size, x:x + box_size]
            if window.size > 0 and np.mean(window) > (255 * threshold):
                grid_mask[y:y + box_size, x:x + box_size] = 255
    return grid_mask


def download_models():
    """Ensure detection/segmentation weights exist locally."""
    from huggingface_hub import hf_hub_download

    os.makedirs(MODEL_DIR, exist_ok=True)

    yolo_path = os.path.join(MODEL_DIR, "face_yolov8n.pt")
    if not os.path.exists(yolo_path):
        print("[FacePipeline] Downloading YOLO model...")
        hf_hub_download('Bingsu/adetailer', 'face_yolov8n.pt', local_dir=MODEL_DIR)

    eyes_path = os.path.join(MODEL_DIR, "full_eyes_detect_v1.pt")
    if not os.path.exists(eyes_path):
        print("[FacePipeline] Downloading Eyes model...")
        urllib.request.urlretrieve(
            "https://huggingface.co/guon/hand-eyes/resolve/main/full_eyes_detect_v1.pt",
            eyes_path,
        )

    sam_path = os.path.join(MODEL_DIR, "sam_b.pt")
    if not os.path.exists(sam_path):
        print("[FacePipeline] Downloading SAM model...")
        urllib.request.urlretrieve(
            "https://github.com/ultralytics/assets/releases/download/v8.3.0/sam_b.pt",
            sam_path,
        )

    return yolo_path, sam_path, eyes_path


class FacePipeline:
    """Detect faces + eyes, then build a grid-aligned inpaint mask.

    Caches model handles across calls. A single instance is meant to be
    reused for the lifetime of the app.
    """

    def __init__(self):
        self.yolo_model = None
        self.eyes_model = None
        self.sam_model = None
        self._yolo_path = None
        self._eyes_path = None
        self._sam_path = None

    @staticmethod
    def _select_device():
        import torch
        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def build_mask(self, pil_image, conf=0.5):
        """Return a grid-aligned mask PIL image, or None if no detections."""
        from ultralytics import YOLO, SAM

        yolo_path, sam_path, eyes_path = download_models()
        device = self._select_device()
        print(f"[FacePipeline] Using device: {device}")

        if not self.yolo_model or self._yolo_path != yolo_path:
            print(f"[FacePipeline] Loading YOLO: {yolo_path}")
            self.yolo_model = YOLO(yolo_path).to(device)
            self._yolo_path = yolo_path

        results = self.yolo_model(pil_image, conf=conf, verbose=False)
        if results and len(results[0].boxes) > 0:
            bboxes = results[0].boxes.xyxy.cpu().numpy()
        else:
            bboxes = np.empty((0, 4))

        if eyes_path:
            if not self.eyes_model or self._eyes_path != eyes_path:
                print(f"[FacePipeline] Loading Eyes YOLO: {eyes_path}")
                self.eyes_model = YOLO(eyes_path).to(device)
                self._eyes_path = eyes_path
            eyes_results = self.eyes_model(pil_image, conf=conf, verbose=False)
            if eyes_results and len(eyes_results[0].boxes) > 0:
                eyes_bboxes = eyes_results[0].boxes.xyxy.cpu().numpy()
                bboxes = np.concatenate([bboxes, eyes_bboxes], axis=0)

        if len(bboxes) == 0:
            print("[FacePipeline] No detections.")
            return None

        print(f"[FacePipeline] {len(bboxes)} detection(s) combined.")

        img_np = np.array(pil_image.convert("RGB"))
        combined_mask = np.zeros(img_np.shape[:2], dtype=np.uint8)

        if not self.sam_model or self._sam_path != sam_path:
            print(f"[FacePipeline] Loading SAM: {sam_path}")
            self.sam_model = SAM(sam_path).to(device)
            self._sam_path = sam_path

        bboxes_list = [b.tolist() for b in bboxes]
        try:
            sam_results = self.sam_model(img_np, bboxes=bboxes_list, verbose=False)
            if sam_results and sam_results[0].masks is not None:
                for mask_tensor in sam_results[0].masks.data:
                    mask_np = mask_tensor.cpu().numpy()
                    mask_img = Image.fromarray((mask_np * 255).astype(np.uint8)).resize(
                        pil_image.size, Image.NEAREST
                    )
                    combined_mask = np.maximum(combined_mask, np.array(mask_img))
        except Exception as sam_err:
            print(f"[FacePipeline] SAM Error (falling back to bboxes): {sam_err}")
            for box in bboxes:
                x1, y1, x2, y2 = map(int, box)
                combined_mask[y1:y2, x1:x2] = 255

        grid_mask = align_mask_to_grid(combined_mask)
        return Image.fromarray(grid_mask)
