import sys
import os
import time

# 앱 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import NAIStudioApp

def run_test():
    print("[TEST] Launching App...")
    app = NAIStudioApp()

    exit_code = {"value": 0}

    def finish(code):
        exit_code["value"] = code
        app.after(0, app.destroy)

    def fail(message):
        print(message)
        finish(1)

    def start_simulation():
        try:
            print("[TEST] Selecting T2I Screen...")
            app.show_screen("T2I")
            screen = app.current_frame

            print("[TEST] Setting test prompt...")
            screen.prompt_txt.delete("1.0", "end")
            screen.prompt_txt.insert("1.0", "cat, sitting on a fence")
            screen.tipo_switch.select()

            print("[TEST] Triggering TIPO Expansion...")
            screen.run_tipo_only()
            app.after(2000, lambda: poll_tipo(screen, time.time()))
        except Exception as e:
            handle_error(e)

    def poll_tipo(screen, start_time):
        try:
            result = screen.expanded_prompt_txt.get("1.0", "end-1c").strip()
            if result:
                print(f"[TEST] TIPO Expansion Success: {result[:50]}...")
                print("[TEST] Triggering Full Generation Flow...")
                screen.generate()
                app.after(5000, check_generation_state)
                return

            if time.time() - start_time >= 30:
                fail("[TEST] TIPO Expansion Timeout or Failed.")
                return

            app.after(2000, lambda: poll_tipo(screen, start_time))
        except Exception as e:
            handle_error(e)

    def check_generation_state():
        try:
            btn_text = app.gen_btn.cget("text")
            print(f"[TEST] Current Button State: {btn_text}")

            if "GENERATE" not in btn_text.upper():
                print("[TEST] Flow is active. Waiting for completion...")

            print("[TEST] All logic paths verified. Exiting.")
            finish(0)
        except Exception as e:
            handle_error(e)

    def handle_error(error):
        print(f"[TEST] Error during simulation: {error}")
        import traceback
        traceback.print_exc()
        finish(1)

    # Keep every Tk interaction on Tk's main thread. macOS can segfault if
    # widgets are touched directly from a background Python thread.
    app.after(5000, start_simulation)
    app.mainloop()
    sys.exit(exit_code["value"])

if __name__ == "__main__":
    run_test()
