import os
import re
import random
import threading
from pathlib import Path

# TIPO category tokens
TIPO_TOKENS = ["<|special|>", "<|rating|>", "<|artist|>", "<|characters|>",
               "<|copyrights|>", "<|general|>", "<|meta|>", "<|quality|>"]

SYSTEM_TIPO = (
    "You are a Danbooru tag expert. "
    "Given partial image tags, output a clean, concise, and high-impact Danbooru tag set. "
    "Focus on essential descriptive tags that define the scene, character, and atmosphere. "
    "Avoid redundant or meta tags. Keep the total count around 40-50 tags. "
    "Output ONLY comma-separated tags in order of importance. No explanation."
)

SYSTEM_TIPO_STRUCTURED = (
    "You are a Danbooru tag expert. "
    "Given partial image tags, output a complete Danbooru tag set organized by category. "
    "Use these category tokens: "
    "<|special|> for special quality tags, "
    "<|rating|> for content rating (safe/sensitive/nsfw), "
    "<|artist|> for artist tags, "
    "<|characters|> for character names, "
    "<|copyrights|> for series/copyright, "
    "<|general|> for general descriptive tags, "
    "<|meta|> for meta tags (resolution etc), "
    "<|quality|> for quality tags. "
    "Output format: <|category|>tag1, tag2<|category|>tag3, tag4 ... "
    "Only include requested categories. No explanation."
)

_model_cache = {}
_cache_lock = threading.Lock()

def _parse_weights(text: str) -> tuple:
    weight_map = {}
    def _replace(m):
        inner = m.group(1).strip()
        wm = re.match(r"^(.*):([0-9.]+)$", inner)
        if wm:
            tag, w = wm.group(1).strip(), float(wm.group(2))
        else:
            tag, w = inner, 1.1
        weight_map[tag.lower()] = w
        return tag
    cleaned = re.sub(r"\(([^()]+)\)", _replace, text)
    cleaned = re.sub(r"\[([^\[\]]+)\]", lambda m: m.group(1), cleaned)
    return cleaned, weight_map

def _apply_weights(tags: str, weight_map: dict) -> str:
    if not weight_map: return tags
    result = []
    for tag in tags.split(","):
        tag = tag.strip()
        w = weight_map.get(tag.lower())
        if w and abs(w - 1.0) > 0.05:
            result.append(f"({tag}:{w})")
        else:
            result.append(tag)
    return ", ".join(result)

def _consolidate_tags(tags: list, limit=50) -> list:
    """Consolidate redundant tags and filter junk for a KGen-like concise output."""
    # 1. Cleaning and Junk Filter
    junk_patterns = [
        r"^year \d{4}$", r"^absurdres$", r"^highres$", r"^ultra-detailed$",
        r"^resolution$", r"^quality$", r"^masterpiece$", r"^best quality$"
    ]
    
    clean_tags = []
    seen = set()
    for t in tags:
        # Lowercase, underscores to spaces, trim
        t = t.lower().replace("_", " ").strip()
        if not t or t in seen:
            continue
            
        # Filter junk
        if any(re.match(p, t) for p in junk_patterns):
            continue
            
        clean_tags.append(t)
        seen.add(t)
    
    # 2. Containment and Redundancy
    to_remove = set()
    
    # Hardcoded rules for character counts
    hard_rules = {
        "girl": ["1girl", "2girls", "3girls", "4girls", "5girls", "6+girls"],
        "girls": ["2girls", "3girls", "4girls", "5girls", "6+girls"],
        "boy": ["1boy", "2boys", "3boys", "4boys", "5boys", "6+boys"],
        "boys": ["2boys", "3boys", "4boys", "5boys", "6+boys"],
    }
    
    for general, specifics in hard_rules.items():
        if any(spec in seen for spec in specifics):
            to_remove.add(general)

    # Aggressive containment: if "in library" exists, remove "library"
    # We sort by length descending to catch longer phrases first
    sorted_tags = sorted(list(seen), key=len, reverse=True)
    for i, long_tag in enumerate(sorted_tags):
        if long_tag in to_remove: continue
        for short_tag in sorted_tags[i+1:]:
            if short_tag in to_remove: continue
            # If short_tag is a whole word inside long_tag (e.g. "library" in "in library")
            if re.search(rf"\b{re.escape(short_tag)}\b", long_tag) and long_tag != short_tag:
                to_remove.add(short_tag)

    # 3. Final selection with limit
    final = []
    for t in clean_tags:
        if t not in to_remove:
            final.append(t)
            if len(final) >= limit:
                break
                
    return final

def _dedup(tags: str) -> str:
    seen, out = set(), []
    for t in tags.split(","):
        t = t.strip()
        key = re.sub(r"[():\d.]", "", t).strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(t)
    return ", ".join(out)

def _clean_special_tokens(raw: str) -> str:
    return re.sub(r"<[^|][^>]*>", "", raw)

def load_tipo(model_path, gpu_layers=0):
    if not model_path: return None
    
    if os.path.isdir(model_path):
        gguf_files = [f for f in os.listdir(model_path) if f.endswith(".gguf")]
        if not gguf_files: return None
        # Prefer Q4 or Q2 depending on preference, but here we'll just take the first or a "ko" one
        selected = next((f for f in gguf_files if "q4" in f.lower()), gguf_files[0])
        model_path = os.path.join(model_path, selected)

    if not os.path.exists(model_path): return None

    with _cache_lock:
        if model_path in _model_cache:
            return _model_cache[model_path]
        
        try:
            from llama_cpp import Llama
            # Force CPU (n_gpu_layers=0) on macOS to prevent Metal assertion conflicts with SAM/Torch
            # Increase n_ctx to 2048 to prevent llama_decode error -3 with long outputs
            llm = Llama(model_path=model_path, n_gpu_layers=0, n_ctx=2048, verbose=False)
            _model_cache[model_path] = llm
            return llm
        except Exception as e:
            print(f"[TIPO] Load error: {e}")
            return None

def expand_prompt(llm, prompt: str, rating="safe", max_tokens=384, temperature=0.7, seed=None) -> str:
    if not llm: return prompt
    
    clean_input, weight_map = _parse_weights(prompt.strip())
    
    # Check if input is likely Korean
    is_korean = bool(re.search("[가-힣]", clean_input))
    
    if is_korean:
        user_msg = f"Rating: {rating}\nDescription (Korean): {clean_input}"
    else:
        user_msg = f"Rating: {rating}\nPartial tags: {clean_input}"

    try:
        # Use provided seed or random for diversity
        target_seed = seed if seed is not None else random.randint(0, 1000000)
        
        resp = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_TIPO},
                {"role": "user",   "content": user_msg},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=0.9,
            repeat_penalty=1.2,
            seed=target_seed,
            stop=None,
        )
        raw = resp["choices"][0]["message"]["content"]
        
        tags_raw = _clean_special_tokens(raw).strip()
        # Collect all lines that look like tags to avoid stopping at first newline
        parsed_tags = []
        for line in tags_raw.splitlines():
            line = line.strip()
            if "," in line or len(line.split()) > 2:
                parsed_tags.append(line)
        
        if parsed_tags:
            tags = ", ".join(parsed_tags)
        else:
            tags = tags_raw
        
        tags = _dedup(tags)
        if not is_korean:
            tags = _apply_weights(tags, weight_map)
            
        # Merge with original tags to ensure core prompt is kept
        orig_tags = [t.strip() for t in clean_input.split(",")]
        combined_tags = list(dict.fromkeys(orig_tags + [t.strip() for t in tags.split(",")]))
        
        # Consolidate redundant tags
        final_tags = _consolidate_tags(combined_tags)
        
        return ", ".join(final_tags)

    except Exception as e:
        print(f"[TIPO] Expansion error: {e}")
        return prompt
