import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.job_runner as jr
from app.job_runner import (
    JobRunner, T2IJob, FaceJob, I2IJob, InpaintJob, JobCallbacks,
)
from core.tipo_engine import _filter_ban_tags


def _img():
    return Image.new("RGB", (64, 64), "white")


class _Recorder:
    def __init__(self):
        self.statuses = []
        self.results = []
        self.errors = []
        self.done = 0

    def callbacks(self):
        return JobCallbacks(
            on_status=self.statuses.append,
            on_expanded=lambda t: None,
            on_result=lambda stage, pil, raw: self.results.append(stage),
            on_error=self.errors.append,
            on_done=lambda: setattr(self, "done", self.done + 1),
        )


def _patch(monkeypatch_target):
    """Replace network + disk side effects with fakes. Returns originals."""
    orig = (jr.post_nai, jr.zip_to_pil, jr._autosave)
    jr.post_nai = lambda token, payload: b"zipbytes"
    jr.zip_to_pil = lambda zb: (_img(), b"rawpng")
    jr._autosave = lambda *a, **k: None
    return orig


def _restore(orig):
    jr.post_nai, jr.zip_to_pil, jr._autosave = orig


class _FakeTipo:
    def expand(self, prompt, **kw):
        return prompt + ", expanded"


def _base_job(**over):
    defaults = dict(
        token="tok", model="nai-diffusion-3", width=64, height=64,
        steps=28, cfg=6.0, seed=-1, sampler="k_euler_ancestral",
        scheduler="karras", cfg_rescale=0.0, prompt="1girl",
        neg_prompt="lowres", wildcard_dir="", use_tipo=False,
        rating="safe", tipo_temp=1.2, ban_tags="", style_name="None",
        style_mode="Append", art_presets=[], count=1,
    )
    defaults.update(over)
    return T2IJob(**defaults)


def test_t2i_single_no_face():
    orig = _patch(None)
    try:
        r = JobRunner()
        rec = _Recorder()
        r._run_t2i(_base_job(), _FakeTipo(), rec.callbacks())
        assert rec.results == ["t2i"]
        assert rec.done == 1
        assert "Ready" in rec.statuses
    finally:
        _restore(orig)


def test_t2i_with_face_detail():
    orig = _patch(None)
    try:
        r = JobRunner()
        r.face_pipeline.build_mask = lambda pil, conf=0.5: _img()
        rec = _Recorder()
        r._run_t2i(_base_job(face_detail=True), _FakeTipo(), rec.callbacks())
        assert rec.results == ["t2i", "face"]
    finally:
        _restore(orig)


def test_t2i_face_detail_no_detection():
    orig = _patch(None)
    try:
        r = JobRunner()
        r.face_pipeline.build_mask = lambda pil, conf=0.5: None
        rec = _Recorder()
        r._run_t2i(_base_job(face_detail=True), _FakeTipo(), rec.callbacks())
        assert rec.results == ["t2i"]
        assert "감지된 대상이 없습니다" in rec.statuses
    finally:
        _restore(orig)


def test_face_job_runs():
    orig = _patch(None)
    try:
        r = JobRunner()
        r.face_pipeline.build_mask = lambda pil, conf=0.5: _img()
        rec = _Recorder()
        job = FaceJob(
            token="t", image=_img(), model="nai-diffusion-3",
            prompt="p", neg_prompt="n", steps=28, cfg=6.0, seed=1,
            sampler="k_euler_ancestral", scheduler="karras", cfg_rescale=0.0,
        )
        r._run_face_job(job, rec.callbacks())
        assert rec.results == ["face"]
        assert rec.done == 1
    finally:
        _restore(orig)


def test_i2i_job_runs():
    orig = _patch(None)
    try:
        r = JobRunner()
        rec = _Recorder()
        job = I2IJob(
            token="t", image=_img(), model="nai-diffusion-3",
            prompt="p", neg_prompt="n", width=64, height=64, steps=28,
            cfg=6.0, seed=-1, sampler="k_euler_ancestral",
            scheduler="karras", cfg_rescale=0.0,
        )
        r._run_i2i_job(job, rec.callbacks())
        assert rec.results == ["i2i"]
        assert rec.done == 1
    finally:
        _restore(orig)


def test_inpaint_job_runs():
    orig = _patch(None)
    try:
        r = JobRunner()
        rec = _Recorder()
        job = InpaintJob(
            token="t", image=_img(), mask=_img().convert("L"),
            model="nai-diffusion-3", prompt="p", neg_prompt="n",
            width=64, height=64, steps=28, cfg=6.0, seed=1,
            sampler="k_euler_ancestral", scheduler="karras", cfg_rescale=0.0,
        )
        r._run_inpaint_job(job, rec.callbacks())
        assert rec.results == ["inpaint"]
        assert rec.done == 1
    finally:
        _restore(orig)


def test_tipo_ban_filter():
    assert _filter_ban_tags("a, bad, c", "bad") == "a, c"
    assert _filter_ban_tags("a, b", "") == "a, b"
    assert _filter_ban_tags("A, B", "a") == "B"
