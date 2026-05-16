import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import prompt_builder
from core.face_pipeline import align_mask_to_grid
from core.nai_client import build_t2i_payload, build_inpaint_payload


# ── prompt_builder.apply_style ──────────────────────────────────────

def test_apply_style_none_passthrough():
    p, n = prompt_builder.apply_style("1girl", "lowres", "None", "Append", [])
    assert p == "1girl"
    assert n == "lowres"


def test_apply_style_golden_recipe_wraps():
    p, n = prompt_builder.apply_style("1girl", "lowres", "Golden Recipe v3.1", "Append", [])
    assert p.startswith(prompt_builder.QUALITY_PREFIX)
    assert p.endswith(prompt_builder.QUALITY_SUFFIX)
    assert "1girl" in p
    assert n == f"{prompt_builder.GOLDEN_NEGATIVE}, lowres"


def test_apply_style_named_append_and_prepend():
    presets = [{"name": "MyStyle", "tags": "watercolor, pastel"}]
    p_app, _ = prompt_builder.apply_style("1girl", "neg", "MyStyle", "Append", presets)
    assert p_app == "1girl, watercolor, pastel"
    p_pre, _ = prompt_builder.apply_style("1girl", "neg", "MyStyle", "Prepend", presets)
    assert p_pre == "watercolor, pastel, 1girl"


def test_apply_style_unknown_preset_passthrough():
    p, n = prompt_builder.apply_style("1girl", "neg", "Ghost", "Append", [])
    assert p == "1girl" and n == "neg"


# ── face_pipeline.align_mask_to_grid ────────────────────────────────

def test_align_mask_empty_stays_empty():
    mask = np.zeros((64, 64), dtype=np.uint8)
    assert align_mask_to_grid(mask).sum() == 0


def test_align_mask_solid_block_fills_grid():
    mask = np.zeros((64, 64), dtype=np.uint8)
    mask[0:48, 0:48] = 255
    out = align_mask_to_grid(mask)
    assert out.max() == 255
    assert out[0:32, 0:32].mean() == 255


def test_align_mask_below_threshold_dropped():
    mask = np.zeros((64, 64), dtype=np.uint8)
    mask[0, 0] = 255  # single pixel, far below 30% of any 32px window
    assert align_mask_to_grid(mask).sum() == 0


# ── nai_client payload builders ─────────────────────────────────────

def test_build_t2i_payload_v4_uses_v4_prompt():
    pl = build_t2i_payload("nai-diffusion-4-5-full", "p", "n", 832, 1216, 28, 6.0, 42)
    assert pl["action"] == "generate"
    assert pl["parameters"]["v4_prompt"]["caption"]["base_caption"] == "p"
    assert pl["parameters"]["seed"] == 42


def test_build_t2i_payload_v3_uses_uc():
    pl = build_t2i_payload("nai-diffusion-3", "p", "n", 832, 1216, 28, 6.0, 7)
    assert pl["parameters"]["uc"] == "n"
    assert "v4_prompt" not in pl["parameters"]


def test_build_inpaint_payload_appends_inpainting_model():
    pl = build_inpaint_payload("nai-diffusion-3", "p", "n", 512, 512, 28, 6.0, 1,
                               0.5, "imgb64", "maskb64")
    assert pl["model"] == "nai-diffusion-3-inpainting"
    assert pl["action"] == "infill"
    assert pl["parameters"]["mask"] == "maskb64"
