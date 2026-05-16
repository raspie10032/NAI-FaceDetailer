"""Single-threaded job orchestration.

Replaces the old cross-screen handshake (controller.pipeline_event +
time.sleep + show_screen) with one worker thread that runs the whole
T2I -> (optional) Face Detail pipeline sequentially and reports progress
through callbacks. No customtkinter here.
"""

import base64
import io
import os
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

from PIL import Image

from core import prompt_builder
from core.face_pipeline import FacePipeline
from core.nai_client import (
    post_nai, zip_to_pil, build_t2i_payload, build_inpaint_payload,
)
from core.settings import resolve_wildcards, get_output_dir

RAND_MAX = 2 ** 31 - 1


def _b64(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _autosave(raw, subfolder=None, prefix="NAI"):
    if not raw:
        return
    base = get_output_dir()
    parts = [base]
    if subfolder:
        parts.append(subfolder)
    parts.append(datetime.now().strftime("%Y-%m-%d"))
    d = os.path.join(*parts)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{prefix}_{int(time.time())}.png"), "wb") as f:
        f.write(raw)


@dataclass
class T2IJob:
    token: str
    model: str
    width: int
    height: int
    steps: int
    cfg: float
    seed: int            # -1 => fresh random per iteration
    sampler: str
    scheduler: str
    cfg_rescale: float
    prompt: str
    neg_prompt: str
    wildcard_dir: str
    use_tipo: bool
    rating: str
    tipo_temp: float
    ban_tags: str
    style_name: str
    style_mode: str
    art_presets: list
    # Face Detail stage
    face_detail: bool = False
    face_model: str = "nai-diffusion-3"
    face_strength: float = 0.55
    face_bbox_thresh: float = 0.5
    # Loop
    auto: bool = False
    count: int = 1
    delay: float = 2.0


@dataclass
class FaceJob:
    token: str
    image: Image.Image
    model: str
    prompt: str
    neg_prompt: str
    steps: int
    cfg: float
    seed: int
    sampler: str
    scheduler: str
    cfg_rescale: float
    strength: float = 0.55
    bbox_thresh: float = 0.5


@dataclass
class JobCallbacks:
    """Hooks invoked from the worker thread. UI implementations must
    marshal back onto the Tk main thread themselves."""
    on_status: callable = lambda text: None
    on_expanded: callable = lambda text: None
    on_result: callable = lambda stage, pil, raw: None  # stage: "t2i"|"face"
    on_error: callable = lambda msg: None
    on_done: callable = lambda: None


class JobRunner:
    def __init__(self):
        self._thread = None
        self._stop = threading.Event()
        self.face_pipeline = FacePipeline()

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def stop(self):
        self._stop.set()

    def _start(self, target, *args):
        if self.running:
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=target, args=args, daemon=True)
        self._thread.start()
        return True

    def start_t2i(self, job: T2IJob, tipo_expander, cb: JobCallbacks):
        return self._start(self._run_t2i, job, tipo_expander, cb)

    def start_face(self, job: FaceJob, cb: JobCallbacks):
        return self._start(self._run_face_job, job, cb)

    # ── internals ──────────────────────────────────────────────────

    def _seed(self, configured):
        return configured if configured != -1 else random.randint(0, RAND_MAX)

    def _inpaint(self, token, model, prompt, neg, image, mask, job):
        seed = self._seed(job.seed)
        payload = build_inpaint_payload(
            model, prompt, neg, image.width, image.height,
            job.steps, job.cfg, seed, job.face_strength if isinstance(job, T2IJob) else job.strength,
            _b64(image), _b64(mask),
            sampler=job.sampler, scheduler=job.scheduler, cfg_rescale=job.cfg_rescale,
        )
        if "parameters" in payload and "v4_prompt" in payload["parameters"]:
            payload["parameters"]["v4_prompt"]["caption"]["base_caption"] = prompt
        return zip_to_pil(post_nai(token, payload))

    def _run_t2i(self, job: T2IJob, tipo, cb: JobCallbacks):
        count = 0
        total = "∞" if job.count >= 1000 else job.count
        try:
            while not self._stop.is_set() and count < job.count:
                count += 1
                seed = self._seed(job.seed)
                tipo_seed = random.randint(0, RAND_MAX)

                working = resolve_wildcards(job.prompt, job.wildcard_dir)

                if job.use_tipo:
                    cb.on_status(f"TIPO 추론 중 ({count}/{total})")
                    working = tipo.expand(
                        working, rating=job.rating, temperature=job.tipo_temp,
                        ban_tags=job.ban_tags, seed=tipo_seed,
                    )
                    cb.on_expanded(working)

                final_p, final_neg = prompt_builder.apply_style(
                    working, job.neg_prompt, job.style_name,
                    job.style_mode, job.art_presets,
                )

                cb.on_status(f"NAI API 호출 중 ({count}/{total})")
                payload = build_t2i_payload(
                    job.model, final_p, final_neg, job.width, job.height,
                    job.steps, job.cfg, seed,
                    sampler=job.sampler, scheduler=job.scheduler,
                    cfg_rescale=job.cfg_rescale,
                )
                if "parameters" in payload and "v4_prompt" in payload["parameters"]:
                    payload["parameters"]["v4_prompt"]["caption"]["base_caption"] = final_p

                pil, raw = zip_to_pil(post_nai(job.token, payload))
                cb.on_result("t2i", pil, raw)
                _autosave(raw, prefix="NAI")

                if job.face_detail and not self._stop.is_set():
                    cb.on_status(f"얼굴 보정 중 ({count}/{total})")
                    mask = self.face_pipeline.build_mask(pil, conf=job.face_bbox_thresh)
                    if mask is None:
                        cb.on_status("감지된 대상이 없습니다")
                    else:
                        # Reuse the styled prompt for stylistic consistency.
                        fpil, fraw = self._inpaint(
                            job.token, job.face_model, final_p, final_neg,
                            pil, mask, job,
                        )
                        cb.on_result("face", fpil, fraw)
                        _autosave(fraw, subfolder="FaceDetailer", prefix="FaceDetailer")

                if not job.auto:
                    break
                if count < job.count and not self._stop.is_set():
                    cb.on_status(f"대기 중 ({int(job.delay)}초)")
                    self._stop.wait(job.delay)
        except Exception as e:
            print(f"[JobRunner] T2I error: {e}")
            cb.on_error(str(e))
        finally:
            cb.on_status("Ready")
            cb.on_done()

    def _run_face_job(self, job: FaceJob, cb: JobCallbacks):
        try:
            cb.on_status("얼굴 감지 중")
            mask = self.face_pipeline.build_mask(job.image, conf=job.bbox_thresh)
            if mask is None:
                cb.on_status("감지된 대상이 없습니다")
                return
            cb.on_status("NAI API 호출 중")
            fpil, fraw = self._inpaint(
                job.token, job.model, job.prompt, job.neg_prompt,
                job.image, mask, job,
            )
            cb.on_result("face", fpil, fraw)
            _autosave(fraw, subfolder="FaceDetailer", prefix="FaceDetailer")
            cb.on_status("완료")
        except Exception as e:
            print(f"[JobRunner] Face error: {e}")
            cb.on_error(str(e))
        finally:
            cb.on_done()
