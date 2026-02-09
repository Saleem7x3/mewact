
import ctypes
import numpy as np
import cv2
import mss
import time
import unicodedata
import io
from ctypes import wintypes
from typing import List, Dict
from colorama import Fore

from .config import (
    print, OCR_ENGINE, OCR_USE_GPU, OCR_SCAN_MODE, OCR_MONITOR_STRATEGY,
    OCR_ADAPTIVE_MODE, OCR_STRIP_THRESHOLD, OCR_STRIP_COUNT, OCR_STRIP_OVERLAP,
    DEBUG_OCR, TARGET_WINDOW_TITLE, TARGET_MONITORS
)

# --- 2. PERCEPTION ENGINE ---
class WindowCapture:
    def __init__(self):
        self.user32 = ctypes.windll.user32
        try:
            self.shcore = ctypes.windll.shcore
            self.shcore.SetProcessDpiAwareness(1)
        except:
            self.user32.SetProcessDPIAware() 

    def get_window_rect(self, title_keyword):
        found_hwnd = None
        def callback(hwnd, extra):
            nonlocal found_hwnd
            if not self.user32.IsWindowVisible(hwnd): return 1
            length = self.user32.GetWindowTextLengthW(hwnd)
            if length == 0: return 1
            buff = ctypes.create_unicode_buffer(length + 1)
            self.user32.GetWindowTextW(hwnd, buff, length + 1)
            if title_keyword.lower() in buff.value.lower():
                found_hwnd = hwnd
                return 0 
            return 1
        PROT_ENUM = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
        self.user32.EnumWindows(PROT_ENUM(callback), 0)

        if found_hwnd:
            rect = wintypes.RECT()
            self.user32.GetWindowRect(found_hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            return {"top": rect.top, "left": rect.left, "width": w, "height": h}
        return None

    
    def get_all_window_rects(self):
        """Return list of rects for all visible application windows."""
        window_rects = []
        def callback(hwnd, extra):
            if self.user32.IsWindowVisible(hwnd):
                length = self.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    # Get title to filter Program Manager/System stuff
                    buff = ctypes.create_unicode_buffer(length + 1)
                    self.user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    
                    if title and title != "Program Manager":
                        rect = wintypes.RECT()
                        self.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        w = rect.right - rect.left
                        h = rect.bottom - rect.top
                        
                        # Filter tiny windows (likely tooltips/hidden)
                        if w > 20 and h > 20:
                             window_rects.append({"top": rect.top, "left": rect.left, "width": w, "height": h, "title": title})
            return 1
        PROT_ENUM = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
        self.user32.EnumWindows(PROT_ENUM(callback), 0)
        # Sort by Z-order? EnumWindows usually enumerates in Z-order (top first).
        # We might want to capture top-down or bottom-up. Standard iteration is fine.
        return window_rects

    def list_windows(self):
        window_list = []
        def callback(hwnd, extra):
            if self.user32.IsWindowVisible(hwnd):
                length = self.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    self.user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    if title and title != "Program Manager": 
                         window_list.append((hwnd, title))
            return 1
        PROT_ENUM = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
        self.user32.EnumWindows(PROT_ENUM(callback), 0)
        return window_list

class PerceptionEngine:
    def __init__(self):
        self.ocr_engine = OCR_ENGINE.lower()
        gpu_status = "GPU" if OCR_USE_GPU else "CPU"
        print(f"{Fore.CYAN}[*] Initialization: {self.ocr_engine.upper()} Engine ({gpu_status})")
        
        # --- ENGINE INITIALIZATION ---
        if self.ocr_engine == "easyocr":
            try:
                import easyocr
                self.ocr = easyocr.Reader(['en'], gpu=OCR_USE_GPU)
            except ImportError:
                print(f"{Fore.YELLOW}[!] EasyOCR not installed. Falling back to RapidOCR.")
                self.ocr_engine = "rapidocr"
        
        elif self.ocr_engine == "paddleocr":
            try:
                from paddleocr import PaddleOCR
                self.ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False, use_gpu=OCR_USE_GPU)
            except ImportError:
                print(f"{Fore.YELLOW}[!] PaddleOCR not installed. Falling back to RapidOCR.")
                self.ocr_engine = "rapidocr"
        
        # Default / Fallback
        if self.ocr_engine == "rapidocr":
            from rapidocr_onnxruntime import RapidOCR
            self.ocr = RapidOCR(det_use_gpu=OCR_USE_GPU, cls_use_gpu=OCR_USE_GPU, rec_use_gpu=OCR_USE_GPU, intra_op_num_threads=4)
            
        self.win_cap = WindowCapture()
        # Active Vision is now separate (see active_vision.py)
        
        self.last_image = None  # DEPRECATED: Only used if we do full capture loop
        self.current_capture_regions = [] # Store regions for mew act command


        with mss.mss() as sct:
            self.monitors = sct.monitors[1:] if len(sct.monitors) > 2 else [sct.monitors[1]]

    def _get_capture_regions(self, sct):
        # 1. Target Window Override (Highest Priority)
        # Note: Imports from config for current values of globals
        from . import config
        
        if config.TARGET_WINDOW_TITLE:
            rect = self.win_cap.get_window_rect(config.TARGET_WINDOW_TITLE)
            if rect: return [rect]
            else:
                if DEBUG_OCR: print(f"{Fore.RED}[!] Target window '{config.TARGET_WINDOW_TITLE}' not found.")
                return []
        
        # 2. Window Scan Logic
        # Active if mode="window" OR (mode="monitor" AND strategy="window")
        use_window_logic = (config.OCR_SCAN_MODE == "window") or (config.OCR_SCAN_MODE == "monitor" and config.OCR_MONITOR_STRATEGY == "window")
        
        if use_window_logic:
            # Get all visible windows
            all_windows = self.win_cap.get_all_window_rects()
            
            # Determine relevant monitors (if filtered)
            target_indices = config.TARGET_MONITORS if config.TARGET_MONITORS else range(1, len(sct.monitors))
            valid_monitors = [sct.monitors[i] for i in target_indices if i < len(sct.monitors)]
            
            if not valid_monitors: return []
            
            filtered_windows = []
            for win in all_windows:
                # Check if window center is inside any valid monitor
                cx = win['left'] + win['width'] // 2
                cy = win['top'] + win['height'] // 2
                
                is_valid = False
                for mon in valid_monitors:
                     if (mon['left'] <= cx < mon['left'] + mon['width'] and 
                         mon['top'] <= cy < mon['top'] + mon['height']):
                         is_valid = True
                         break
                
                if is_valid:
                    filtered_windows.append(win)
            
            # Sort windows by coordinate (Top-Left -> Bottom-Right) for consistent reading order
            return filtered_windows

        # 3. Monitor Scan Logic (Full Screen) - Default
        target_indices = config.TARGET_MONITORS if config.TARGET_MONITORS else range(1, len(sct.monitors))
        regions = [sct.monitors[i] for i in target_indices if i < len(sct.monitors)]
        
        if not regions:
             return [sct.monitors[1]] if len(sct.monitors) > 1 else []
             
        return regions

    def _ocr_image(self, img, region_offset_x, region_offset_y):
        """Helper to run OCR on an image and return adjusted coordinates."""
        ui_data = []
        txt_parts = []
        try:
            if self.ocr_engine == "easyocr":
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
                results = self.ocr.readtext(img_rgb)
                for (bbox, text, prob) in results:
                    if prob < 0.2: continue
                    cx = int((bbox[0][0] + bbox[2][0]) / 2) + region_offset_x
                    cy = int((bbox[0][1] + bbox[2][1]) / 2) + region_offset_y
                    ui_data.append({"text": text, "x": cx, "y": cy})
                    txt_parts.append(text)
                    
            elif self.ocr_engine == "paddleocr":
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
                result = self.ocr.ocr(img_rgb, cls=True)
                if result and result[0]:
                    for line in result[0]:
                        box = line[0]
                        text, score = line[1]
                        if score < 0.5: continue
                        cx = int((box[0][0] + box[2][0]) / 2) + region_offset_x
                        cy = int((box[0][1] + box[2][1]) / 2) + region_offset_y
                        ui_data.append({"text": text, "x": cx, "y": cy})
                        txt_parts.append(text)
                        
            else: # RapidOCR
                result, _ = self.ocr(img)
                if result:
                    for line in result:
                        box = line[0]
                        text, score = line[1], line[2]
                        if score < 0.4: continue
                        cx = int((box[0][0] + box[2][0]) / 2) + region_offset_x
                        cy = int((box[0][1] + box[2][1]) / 2) + region_offset_y
                        ui_data.append({"text": text, "x": cx, "y": cy})
                        txt_parts.append(text)
        except Exception as e:
            if DEBUG_OCR: print(f"OCR Error: {e}")
        return ui_data, txt_parts

    def capture_and_scan(self):
        # Imports from config to catch updates
        from . import config
        
        time.sleep(0.1) 
        try:
            with mss.mss() as sct:
                all_ui_data = [] 
                all_txt_parts = []
                
                self.current_capture_regions = self._get_capture_regions(sct)
                if not self.current_capture_regions: return [], ""

                # Assume screen 0 for coverage calculation (simplification)
                screen_area = sct.monitors[0]['width'] * sct.monitors[0]['height']
                
                # Disable splitting for window-based modes (User request: "without cutting")
                is_window_mode = (config.OCR_SCAN_MODE == "window") or (config.OCR_SCAN_MODE == "monitor" and config.OCR_MONITOR_STRATEGY == "window")
                allow_splitting = config.OCR_ADAPTIVE_MODE and not is_window_mode

                for region in self.current_capture_regions:
                    region_area = region['width'] * region['height']
                    coverage = region_area / screen_area
                    
                    # ADAPTIVE OCR STRATEGY (Power Saver Mode - Full Monitor Only)
                    if allow_splitting and coverage > OCR_STRIP_THRESHOLD:
                        # Large window: Split into strips to reduce peak memory/CPU load
                        # print(f"[DEBUG] Adaptive OCR: Strip mode for large window ({coverage:.2f} coverage)")
                        strip_height = region['height'] // OCR_STRIP_COUNT
                        for i in range(OCR_STRIP_COUNT):
                            # Calculate base dimensions
                            base_top = region['top'] + (i * strip_height)
                            base_height = strip_height
                            # Adjust height for last strip to cover remainder
                            if i == OCR_STRIP_COUNT - 1:
                                base_height = region['height'] - (i * strip_height)
                            
                            # Add overlap: Extend strip DOWNWARDS to capture text on the cut line
                            # (Except for the very last strip which is bounded by window bottom)
                            final_height = base_height
                            if i < OCR_STRIP_COUNT - 1:
                                final_height += OCR_STRIP_OVERLAP
                                
                            strip_rect = {
                                'left': region['left'],
                                'top': base_top,
                                'width': region['width'],
                                'height': final_height
                            }
                            img = np.array(sct.grab(strip_rect))
                            s_data, s_txt = self._ocr_image(img, strip_rect['left'], strip_rect['top'])
                            all_ui_data.extend(s_data)
                            all_txt_parts.extend(s_txt)
                    else:
                        # Small window: Full capture
                        # print(f"[DEBUG] Adaptive OCR: Full mode for small window ({coverage:.2f} coverage)")
                        img = np.array(sct.grab(region))
                        s_data, s_txt = self._ocr_image(img, region['left'], region['top'])
                        all_ui_data.extend(s_data)
                        all_txt_parts.extend(s_txt)
                
                full_text = " ".join(all_txt_parts)
                # --- NORMALIZE "STYLISH" FONTS ---
                # Chatbots sometimes output mathematical bold/italic unicode (e.g. 𝐇𝐞𝐥𝐥𝐨)
                full_text = unicodedata.normalize('NFKD', full_text).encode('ascii', 'ignore').decode('utf-8')
                
                return all_ui_data, full_text
        except Exception as e:
            if DEBUG_OCR: print(f"Capture Error: {e}")
            return [], ""

    def copy_last_image_to_clipboard(self) -> bool:
        """Capture FRESH full-screen image (or relevant context) and copy to clipboard."""
        # Note: Imports from config for current globals
        from . import config
        
        try:
            with mss.mss() as sct:
                # Determine best region to capture for context
                # Prioritize explicit targets, otherwise default to Primary Monitor
                region = None
                
                if config.TARGET_WINDOW_TITLE:
                    rect = self.win_cap.get_window_rect(config.TARGET_WINDOW_TITLE)
                    if rect: region = rect
                elif config.TARGET_MONITORS:
                    # Capture the first targeted monitor
                    idx = config.TARGET_MONITORS[0]
                    if idx < len(sct.monitors):
                        region = sct.monitors[idx]
                
                # Fallback: Capture Primary Monitor (sct.monitors[1])
                # Note: sct.monitors[0] is 'All Monitors Combined' - good for context but maybe too big?
                # Sticking to Primary Monitor for consistency.
                if not region:
                    region = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                
                img = np.array(sct.grab(region))
            
            from PIL import Image
            import win32clipboard
            
            # Convert BGRA to RGB
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
            pil_img = Image.fromarray(img_rgb)
            
            # Convert to BMP format for clipboard
            output = io.BytesIO()
            pil_img.convert('RGB').save(output, 'BMP')
            data = output.getvalue()[14:]  # Remove BMP header
            output.close()
            
            # Copy to clipboard
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            
            print(f"{Fore.GREEN}[+] Fresh full-screen image copied to clipboard!")
            return True
        except ImportError as e:
            print(f"{Fore.RED}[!] Missing module: {e.name}. Install with: pip install pywin32 pillow")
            return False
        except Exception as e:
            print(f"{Fore.RED}[!] Failed to copy image: {e}")
            return False


    def wait_for_text(self, target_text, timeout=30):
        print(f"{Fore.YELLOW}[*] Waiting for text: '{target_text}' (Timeout: {timeout}s)...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            ui_data, txt = self.capture_and_scan()
            if target_text.lower() in txt.lower():
                print(f"{Fore.GREEN}[+] Text '{target_text}' detected!")
                return True
            time.sleep(1) # Poll every second
        print(f"{Fore.RED}[!] Timeout waiting for text.")
        return False

        print(f"{Fore.RED}[!] Timeout waiting for text.")
        return False


