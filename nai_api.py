import os
import base64
import requests
import zipfile
import io
import time
import random
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

_session = requests.Session()

def _retry_after_seconds(response):
    retry_after = response.headers.get("Retry-After")
    if not retry_after:
        return None

    try:
        return max(0.0, float(retry_after))
    except (TypeError, ValueError):
        return None

def _backoff_delay(attempt, response=None, base_delay=2.0, max_delay=60.0):
    retry_after = _retry_after_seconds(response) if response is not None else None
    if retry_after is not None:
        return min(max_delay, retry_after)

    delay = min(max_delay, base_delay * (2 ** attempt))
    jitter = random.uniform(0, min(1.0, delay * 0.1))
    return delay + jitter

def post_nai(token, payload, url="https://image.novelai.net/ai/generate-image", max_retries=5):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            response = _session.post(url, headers=headers, json=payload, timeout=120)

            if response.status_code == 429:
                if attempt >= max_retries:
                    response.raise_for_status()

                delay = _backoff_delay(attempt, response=response)
                print(f"NAI API: 429 Too Many Requests. Retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
                last_error = requests.HTTPError("429 Too Many Requests", response=response)
                continue

            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            last_error = e
            response = getattr(e, "response", None)

            status_code = getattr(response, "status_code", None)
            retryable = status_code in {429, 500, 502, 503, 504} or response is None
            if not retryable or attempt >= max_retries:
                print(f"NAI API Error: {e}")
                if response is not None:
                    print(f"Response: {response.text}")
                raise

            delay = _backoff_delay(attempt, response=response)
            print(f"NAI API Error: {e}. Retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})...")
            time.sleep(delay)
        except Exception as e:
            print(f"NAI API Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            raise

    if last_error is not None:
        raise last_error
    raise RuntimeError("NAI API request failed without a captured exception")

def zip_to_pil(zip_bytes):
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zipped:
        image_bytes = zipped.read(zipped.infolist()[0])
        pil_img = Image.open(io.BytesIO(image_bytes))
        return pil_img, image_bytes

def pil_to_tensor(img):
    import torch
    import numpy as np
    img_np = np.array(img).astype(np.float32) / 255.0
    return torch.from_numpy(img_np).unsqueeze(0)

def tensor_to_pil(tensor, batch_index=0):
    import numpy as np
    img_np = tensor[batch_index].cpu().numpy()
    img_np = (img_np * 255.0).clip(0, 255).astype(np.uint8)
    return Image.fromarray(img_np)

def get_nai_token():
    token = os.getenv('NAI_ACCESS_TOKEN')
    if not token:
        print("Warning: NAI_ACCESS_TOKEN not found in environment variables.")
    return token

def build_t2i_payload(model, prompt, neg_prompt, width, height, steps, cfg, seed, sampler="k_euler_ancestral", scheduler="karras", cfg_rescale=0.0):
    is_v4 = "nai-diffusion-4" in model
    is_v45 = "4-5" in model
    
    # Ensure all inputs are correct types
    width, height = int(width), int(height)
    steps = int(steps)
    cfg = float(cfg)
    seed = int(seed)
    cfg_rescale = float(cfg_rescale)

    params = {
        "width": width, "height": height, "n_samples": 1, "seed": seed,
        "sampler": sampler, "steps": steps, "scale": cfg, "extra_noise_seed": seed,
    }
    if is_v4:
        params.update({
            "negative_prompt": neg_prompt, "cfg_rescale": cfg_rescale,
            "prefer_brownian": True, "noise_schedule": scheduler,
            "params_version": 3, "legacy": False,
            "skip_cfg_above_sigma": float(58 if is_v45 else 19),
            "v4_prompt": {"caption": {"base_caption": prompt, "char_captions": []}, "use_coords": False, "use_order": True},
            "v4_negative_prompt": {"caption": {"base_caption": neg_prompt, "char_captions": []}, "use_coords": False, "use_order": False}
        })
    else:
        params.update({"uc": neg_prompt, "ucPreset": 0, "qualityToggle": True, "sm": False, "sm_dyn": False})
    return {"input": prompt, "model": model, "action": "generate", "parameters": params}

def build_i2i_payload(model, prompt, neg_prompt, width, height, steps, cfg, seed, strength, image_b64, sampler="k_euler_ancestral", scheduler="karras", cfg_rescale=0.0):
    is_v4 = "nai-diffusion-4" in model
    is_v45 = "4-5" in model
    
    # Type conversion
    width, height = int(width), int(height)
    steps = int(steps)
    cfg = float(cfg)
    seed = int(seed)
    strength = float(strength)
    cfg_rescale = float(cfg_rescale)

    params = {
        "width": width, "height": height, "n_samples": 1, "seed": seed,
        "sampler": sampler, "steps": steps, "scale": cfg,
        "strength": strength, "noise": 0.0, "image": image_b64, "extra_noise_seed": seed,
    }
    if is_v4:
        params.update({
            "negative_prompt": neg_prompt, "cfg_rescale": cfg_rescale,
            "prefer_brownian": True, "noise_schedule": scheduler,
            "params_version": 3, "legacy": False,
            "skip_cfg_above_sigma": float(58 if is_v45 else 19),
            "v4_prompt": {"caption": {"base_caption": prompt, "char_captions": []}, "use_coords": False, "use_order": True},
            "v4_negative_prompt": {"caption": {"base_caption": neg_prompt, "char_captions": []}, "use_coords": False, "use_order": False}
        })
    else:
        params.update({"uc": neg_prompt, "ucPreset": 0, "qualityToggle": True})
    return {"input": prompt, "model": model, "action": "img2img", "parameters": params}

def build_inpaint_payload(model, prompt, neg_prompt, width, height, steps, cfg, seed, strength, image_b64, mask_b64, sampler="k_euler_ancestral", scheduler="karras", cfg_rescale=0.0):
    is_v4 = "nai-diffusion-4" in model
    is_v45 = "4-5" in model
    inpaint_model = model if model.endswith("-inpainting") else model + "-inpainting"
    params = {
        "width": width, "height": height, "n_samples": 1, "seed": seed,
        "sampler": sampler, "steps": steps, "scale": cfg,
        "image": image_b64, "mask": mask_b64,
        "add_original_image": True, "extra_noise_seed": seed,
        "inpaintImg2ImgStrength": strength,
        "noise": 0,
        "deliberate_euler_ancestral_bug": False,
        "controlnet_strength": 1,
        "request_type": "NativeInfillingRequest",
    }
    if is_v4:
        params.update({
            "negative_prompt": neg_prompt, "cfg_rescale": cfg_rescale,
            "prefer_brownian": True, "noise_schedule": scheduler,
            "params_version": 3, "legacy": False,
            "skip_cfg_above_sigma": 58 if is_v45 else 19,
            "v4_prompt": {"caption": {"base_caption": prompt, "char_captions": []}, "use_coords": False, "use_order": True},
            "v4_negative_prompt": {"caption": {"base_caption": neg_prompt, "char_captions": []}, "use_coords": False, "use_order": False}
        })
    else:
        params.update({"uc": neg_prompt, "ucPreset": 0})
    return {"input": prompt, "model": inpaint_model, "action": "infill", "parameters": params}
