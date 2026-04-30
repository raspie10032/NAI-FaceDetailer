import sys
import os

# 앱 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import tipo
from config import load_config

def test_tipo():
    print("[TEST] Loading Config...")
    cfg = load_config()
    model_path = cfg.get("tipo_model_path", "./models")
    gpu_layers = cfg.get("tipo_gpu_layers", 0)
    
    print(f"[TEST] Model Path: {model_path}")
    print("[TEST] Initializing TIPO...")
    llm = tipo.load_tipo(model_path, gpu_layers)
    
    if not llm:
        print("[TEST] Failed to initialize TIPO.")
        return
        
    print("[TEST] Expanding prompt: '1girl, beach'...")
    result = tipo.expand_prompt(llm, "1girl, beach")
    
    print(f"[TEST] Result: {result}")
    if result and len(result) > 15:
        print("[TEST] SUCCESS: TIPO expansion works.")
    else:
        print("[TEST] FAILURE: TIPO expansion returned empty or original.")

if __name__ == "__main__":
    test_tipo()
