
import io
import time
import numpy as np
import cv2
import mss
from colorama import Fore
from . import config

# --- ACTIVE VISION ENGINE (VLM) ---
class VLM_Provider:
    def __init__(self):
        self.model = config.VLM_MODEL
        self.enabled = config.VLM_ENABLED or config.ACTIVE_MODE
        if self.enabled:
            print(f"{Fore.CYAN}[*] Active Vision Initialized ({self.model})")

    def describe_image(self, img_array, prompt="Describe this UI screen in detail."):
        if not self.enabled: return "Active Vision Disabled"
        try:
            import ollama
            from PIL import Image
            
            # Convert numpy array (BGRA) to PIL Image (RGB)
            img_rgb = cv2.cvtColor(img_array, cv2.COLOR_BGRA2RGB)
            pil_img = Image.fromarray(img_rgb)
            
            # Save to buffer for Ollama
            buffer = io.BytesIO()
            pil_img.save(buffer, format="PNG")
            buffer.seek(0)
            
            response = ollama.chat(
                model=self.model,
                messages=[{
                    'role': 'user',
                    'content': prompt,
                    'images': [buffer.getvalue()]
                }]
            )
            return response['message']['content']
        except ImportError:
            return "Error: 'ollama' python package not installed."
        except Exception as e:
            print(f"{Fore.RED}[!] Active Vision Error: {e}")
            return f"Error: {e}"

class ActiveVisionEngine:
    def __init__(self):
        self.vlm = VLM_Provider()

    def describe_screen(self):
        """Capture full screen and describe it via VLM."""
        if not self.vlm.enabled: return "Active Mode Disabled"
        with mss.mss() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            img = np.array(sct.grab(monitor))
            return self.vlm.describe_image(img)

    def describe_region(self, region):
        """Describe specific region (x, y, w, h)"""
        if not self.vlm.enabled: return "Active Mode Disabled"
        with mss.mss() as sct:
            img = np.array(sct.grab(region))
            return self.vlm.describe_image(img, prompt="Describe this specific UI element or region.")
