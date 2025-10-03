# autofish_bar_clicker_autoloop.py
# Requirements: pyautogui, mss, numpy, keyboard
# Install: python -m pip install pyautogui mss numpy keyboard

import time
import sys
import numpy as np
import pyautogui
from mss import mss

try:
    import keyboard
except ImportError:
    keyboard = None
    print("[!] 'keyboard' package not found. Install with: python -m pip install keyboard")
    print("    Hotkey will be disabled; script will run continuously.\n")

# -------- CONFIG ADJUST IF NEEDED --------
REGION = {"left": 1786, "top": 499, "width": 163, "height": 432}

RED = {"r_min": 170, "g_max": 90, "b_max": 90}
GREEN = {"g_min": 170, "r_max": 90, "b_max": 90}

MIN_CLICK_INTERVAL_SEC = 0.15
POLL_DELAY_SEC = 0.01

# Presence confirm (to avoid flicker false positives)
APPEAR_CONFIRM_FRAMES = 4
DISAPPEAR_CONFIRM_FRAMES = 4
RED_MIN_PIXELS_PRESENT = 60  # tune if needed

# ------------------------

def find_vertical_span(mask: np.ndarray):
    rows = np.where(mask.any(axis=1))[0]
    if rows.size == 0:
        return None, None
    return int(rows.min()), int(rows.max())

def detect_masks(bgr: np.ndarray):
    B, G, R = bgr[:, :, 0], bgr[:, :, 1], bgr[:, :, 2]
    red_mask = (R >= RED["r_min"]) & (G <= RED["g_max"]) & (B <= RED["b_max"])
    green_mask = (G >= GREEN["g_min"]) & (R <= GREEN["r_max"]) & (B <= GREEN["b_max"])

    # Trim noise for thin bars
    row_red_counts = red_mask.sum(axis=1)
    red_rows_keep = row_red_counts >= 3
    red_mask = red_mask & red_rows_keep[:, None]
    return red_mask, green_mask

def is_bar_present(red_mask: np.ndarray) -> bool:
    return red_mask.sum() >= RED_MIN_PIXELS_PRESENT

def main():
    pyautogui.FAILSAFE = False
    sct = mss()

    running = True if keyboard is None else False
    was_overlapping = False
    last_click_time = 0.0

    appear_hits, disappear_hits = 0, 0
    fishing = False

    if keyboard is not None:
        print("Hotkey: Press Alt+V to toggle ON/OFF.")
        running = False

        def toggle():
            nonlocal running, was_overlapping, fishing, appear_hits, disappear_hits
            running = not running
            was_overlapping = False
            fishing = False
            appear_hits = disappear_hits = 0
            print(f"[Toggle] Running = {running}")

        keyboard.add_hotkey("alt+v", toggle)

    print("Region:", REGION)
    print("Starting loop...")

    try:
        while True:
            if not running:
                time.sleep(POLL_DELAY_SEC)
                continue

            frame = np.array(sct.grab(REGION))[:, :, :3]
            red_mask, green_mask = detect_masks(frame)
            present = is_bar_present(red_mask)

            if not fishing:
                # Wait for bar to appear
                appear_hits = appear_hits + 1 if present else 0
                if appear_hits >= APPEAR_CONFIRM_FRAMES:
                    fishing = True
                    was_overlapping = False
                    disappear_hits = 0
                time.sleep(POLL_DELAY_SEC)
                continue

            # Fishing phase
            r_ymin, r_ymax = find_vertical_span(red_mask)
            g_ymin, g_ymax = find_vertical_span(green_mask)

            overlapping = False
            if (r_ymin is not None) and (g_ymin is not None):
                overlapping = not (r_ymax < g_ymin or r_ymin > g_ymax)

            now = time.time()
            if overlapping and not was_overlapping and (now - last_click_time) >= MIN_CLICK_INTERVAL_SEC:
                pyautogui.click()
                last_click_time = now

            was_overlapping = overlapping

            # Check for disappearance
            disappear_hits = disappear_hits + 1 if not present else 0
            if disappear_hits >= DISAPPEAR_CONFIRM_FRAMES:
                fishing = False
                disappear_hits = 0
                # --- NEW: 1 sec wait then M1 click ---
                time.sleep(1.0)
                pyautogui.click()
                # Wait for bar to reappear
                appear_hits = 0
                while True:
                    frame2 = np.array(sct.grab(REGION))[:, :, :3]
                    red_mask2, _ = detect_masks(frame2)
                    if is_bar_present(red_mask2):
                        appear_hits += 1
                        if appear_hits >= APPEAR_CONFIRM_FRAMES:
                            fishing = True
                            was_overlapping = False
                            break
                    else:
                        appear_hits = 0
                    time.sleep(POLL_DELAY_SEC)

            time.sleep(POLL_DELAY_SEC)

    except KeyboardInterrupt:
        print("\nExiting.")
    finally:
        if keyboard is not None:
            keyboard.clear_all_hotkeys()

if __name__ == "__main__":
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW("AutoFish M1-after-bar-disappears")
        except Exception:
            pass
    main()
