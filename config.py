import json
import os
import re
import random
from pathlib import Path

CONFIG_DIR = Path.home() / 'nai_studio'
CONFIG_FILE = str(CONFIG_DIR / 'config.json')
PRESETS_FILE = str(CONFIG_DIR / 'presets.json')
ART_PRESETS_FILE = str(CONFIG_DIR / 'art_presets.json')
LAST_SETTINGS_FILE = str(CONFIG_DIR / 'last_settings.json')

DEFAULT_CONFIG = {
    "nai_token": "",
    "gguf_path": "",
    "tipo_model_path": str(Path(__file__).parent / "models"),
    "tipo_gpu_layers": 0,
    "wildcard_dir": str(Path(__file__).parent / "wildcards"),
    "output_dir": str(Path.home() / "Downloads" / "NAI"),
    "language": "ko"
}

DEFAULT_PRESETS = {
    "Golden Recipe v3.1": {
        "prompt": "2.0:: no lineart :: , 1.2:: artist:musouzuki :: , 0.9:: artist:chen_bin, artist:ciloranko :: , 0.85:: artist:kedama milk, artist:momoco, artist:zuizi :: , 0.8:: artist:pottsness :: , 0.85:: artist:ningen mame, artist:sho (sho lwlw) :: , 0.45:: artist:alt (ctrldel) :: , 0.9:: artist:quasarcake :: , 0.95:: artist:torino aqua :: , 0.85:: tianliang duohe fangdongye :: , 0.5:: artist:mika pikazo :: , 0.85:: artist:rhasta :: , 0.85:: artist:shacho (ko no ha) :: , cute, prism color, volumetric lighting, year 2023, year 2024, -2.0:: line art, straight-on :: , -3.0:: simple background, original, realistic, hat, fat, curvy, thick, buttons :: , -2.0:: multiple views, split screen, pale, letterbox, furry, :> :: , -1.0:: artist:bb (baalbuddy), artist:bkub (style) :: , -5.0:: artist collaboration :: , -1.0:: muscular :: , masterpiece, best quality, amazing quality, very aesthetic, absurdres, newest",
        "neg_prompt": "upper teeth only, teeth, pink face, people, breast ptosis, text, copyright name, weibo logo, logo, jpeg artifacts, bad anatomy, missing fingers, extra digit, bad hands, fewer digits, deformed hand, fused fingers, extra fingers, mutated hands, poorly drawn hands, extra arms, extra legs, missing leg, missing arms, long neck, Humpbacked, mutation, deformed, multiple views, duplicate, error, signature, watermark, username, collage, poorly drawn face, printed shirt, ugly, morbid, mutilated, worst quality, low quality, normal quality, lowres",
        "model": "nai-diffusion-4-5-full",
        "res": "768x1344",
        "steps": "28",
        "cfg": "6.0",
        "seed": "-1",
        "cfg_rescale": "0.0",
        "sampler": "k_euler_ancestral",
        "scheduler": "karras",
        "use_tipo": False
    },
    "Golden Recipe (Simple)": {
        "prompt": "masterpiece, best quality, amazing quality, very aesthetic, absurdres, newest",
        "neg_prompt": "upper teeth only, teeth, pink face, people, breast ptosis, text, copyright name, weibo logo, logo, jpeg artifacts, bad anatomy, missing fingers, extra digit, bad hands, fewer digits, deformed hand, fused fingers, extra fingers, mutated hands, poorly drawn hands, extra arms, extra legs, missing leg, missing arms, long neck, Humpbacked, mutation, deformed, multiple views, duplicate, error, signature, watermark, username, collage, poorly drawn face, printed shirt, ugly, morbid, mutilated, worst quality, low quality, normal quality, lowres",
        "model": "nai-diffusion-4-5-full",
        "res": "832x1216",
        "steps": "28",
        "cfg": "6.0",
        "seed": "-1",
        "cfg_rescale": "0.0",
        "sampler": "k_euler_ancestral",
        "scheduler": "karras",
        "use_tipo": True
    }
}

def get_output_dir(subfolder=None):
    base = os.path.join(os.path.expanduser("~"), "Downloads", "NAI")
    if subfolder:
        return os.path.join(base, subfolder)
    return base

def load_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # Ensure all default keys exist
                for k, v in DEFAULT_CONFIG.items():
                    if k not in config:
                        config[k] = v
                return config
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def resolve_wildcards(text, wildcard_dir, depth=0, max_depth=5):
    if depth >= max_depth:
        return text
    
    # Pattern to match {wildcard} or {folder/wildcard}
    pattern = re.compile(r'\{([^{}]+)\}')
    
    def replace(m):
        name = m.group(1)
        path = Path(wildcard_dir) / (name + ".txt")
        if not path.exists():
            return m.group(0)
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f.readlines() 
                         if l.strip() and not l.startswith('#')]
            if not lines:
                return m.group(0)
            return random.choice(lines)
        except Exception:
            return m.group(0)

    new_text = pattern.sub(replace, text)
    if new_text != text:
        return resolve_wildcards(new_text, wildcard_dir, depth + 1, max_depth)
    return new_text

def load_presets():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DEFAULT_PRESETS.copy()
    # 최초 실행 시 기본 프리셋 저장
    with open(PRESETS_FILE, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_PRESETS, f, indent=4, ensure_ascii=False)
    return DEFAULT_PRESETS.copy()

def save_preset(name, settings: dict):
    presets = load_presets()
    presets[name] = settings
    with open(PRESETS_FILE, "w", encoding="utf-8") as f:
        json.dump(presets, f, indent=4, ensure_ascii=False)

def delete_preset(name):
    presets = load_presets()
    if name in presets:
        del presets[name]
        with open(PRESETS_FILE, "w", encoding="utf-8") as f:
            json.dump(presets, f, indent=4, ensure_ascii=False)

def load_art_presets():
    if os.path.exists(ART_PRESETS_FILE):
        try:
            with open(ART_PRESETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_art_preset(name, tags):
    presets = load_art_presets()
    for p in presets:
        if p["name"] == name:
            p["tags"] = tags
            break
    else:
        if len(presets) >= 100:
            presets.pop(0)
        presets.append({"name": name, "tags": tags})
    with open(ART_PRESETS_FILE, "w", encoding="utf-8") as f:
        json.dump(presets, f, indent=4, ensure_ascii=False)

def delete_art_preset(name):
    presets = [p for p in load_art_presets() if p["name"] != name]
    with open(ART_PRESETS_FILE, "w", encoding="utf-8") as f:
        json.dump(presets, f, indent=4, ensure_ascii=False)

def load_last_settings():
    if os.path.exists(LAST_SETTINGS_FILE):
        try:
            with open(LAST_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_last_settings(settings: dict):
    with open(LAST_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)
