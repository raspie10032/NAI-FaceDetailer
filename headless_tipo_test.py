import sys
import os
import re

# 앱 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core import tipo_engine as tipo
from core.settings import load_config

def test():
    cfg = load_config()
    model_path = cfg.get("tipo_model_path", "./models")
    llm = tipo.load_tipo(model_path, -1)
    
    if not llm:
        print("FAIL: LLM NOT LOADED")
        return

    test_prompt = "1girl, solo, in library"
    print(f"Testing expansion for: {test_prompt}")
    
    # 실제 추론 실행
    result = tipo.expand_prompt(llm, test_prompt)
    
    print("\n--- FINAL RESULT ---")
    print(result)
    print("--------------------")
    
    if result != test_prompt and "," in result:
        print("SUCCESS: TIPO EXPANDED AND EXTRACTED CORRECTLY")
    else:
        print("FAIL: TIPO RETURNED ORIGINAL OR EMPTY")

if __name__ == "__main__":
    test()
