"""Prompt composition logic, decoupled from the UI.

Pure functions: given prompt text and style settings, produce the final
positive/negative prompts. No customtkinter / no threading here.
"""

from core.settings import resolve_wildcards

QUALITY_PREFIX = '2.0:: no lineart :: , 1.2:: artist:musouzuki :: , 0.9:: artist:chen_bin, artist:ciloranko :: , 0.85:: artist:kedama milk, artist:momoco, artist:zuizi :: , 0.8:: artist:pottsness :: , 0.85:: artist:ningen mame, artist:sho (sho lwlw) :: , 0.45:: artist:alt (ctrldel) :: , 0.9:: artist:quasarcake :: , 0.95:: artist:torino aqua :: , 0.85:: tianliang duohe fangdongye :: , 0.5:: artist:mika pikazo :: , 0.85:: artist:rhasta :: , 0.85:: artist:shacho (ko no ha) :: , cute, prism color, volumetric lighting, year 2023, year 2024, -2.0:: line art, straight-on :: , -3.0:: simple background, original, realistic, hat, fat, curvy, thick, buttons :: , -2.0:: multiple views, split screen, pale, letterbox, furry, :> :: , -1.0:: artist:bb (baalbuddy), artist:bkub (style) :: , -5.0:: artist collaboration :: , -1.0:: muscular ::'
QUALITY_SUFFIX = 'masterpiece, best quality, amazing quality, very aesthetic, absurdres, newest, scenery'
GOLDEN_NEGATIVE = 'upper teeth only, teeth, pink face, people, breast ptosis, text, copyright name, weibo logo, logo, jpeg artifacts, bad anatomy, missing fingers, extra digit, bad hands, fewer digits, deformed hand, fused fingers, extra fingers, mutated hands, poorly drawn hands, extra arms, extra legs, missing leg, missing arms, long neck, Humpbacked, mutation, deformed, multiple views, duplicate, error, signature, watermark, username, collage, poorly drawn face, printed shirt, ugly, morbid, mutilated, worst quality, low quality, normal quality, lowres'

GOLDEN_RECIPE_NAME = "Golden Recipe v3.1"


def apply_style(prompt, neg_prompt, style_name, style_mode, art_presets):
    """Apply an art-style preset (or the Golden Recipe) to a prompt.

    Returns (final_prompt, final_neg_prompt). Behavior matches the original
    inline logic in T2IScreen.generate():
      - Golden Recipe: wrap with quality prefix/suffix + boost negative
      - Named preset: prepend or append the preset's tags
      - "None": pass through unchanged
    """
    if style_name == GOLDEN_RECIPE_NAME:
        final_p = f"{QUALITY_PREFIX}, {prompt}, {QUALITY_SUFFIX}"
        final_neg = f"{GOLDEN_NEGATIVE}, {neg_prompt}"
        return final_p, final_neg

    if style_name and style_name != "None":
        style_tags = next(
            (p["tags"] for p in art_presets if p["name"] == style_name), ""
        )
        if style_tags:
            if style_mode == "Prepend":
                prompt = f"{style_tags}, {prompt}"
            else:
                prompt = f"{prompt}, {style_tags}"

    return prompt, neg_prompt


def compose(raw_prompt, neg_prompt, wildcard_dir, style_name, style_mode,
            art_presets, tipo_fn=None):
    """Full prompt pipeline: wildcards -> optional TIPO -> style.

    `tipo_fn` is an optional callable(str) -> str applied after wildcard
    resolution. Kept injectable so the TIPO engine (stateful) stays out of
    this pure module.
    """
    working = resolve_wildcards(raw_prompt, wildcard_dir)
    if tipo_fn is not None:
        working = tipo_fn(working)
    return apply_style(working, neg_prompt, style_name, style_mode, art_presets)
