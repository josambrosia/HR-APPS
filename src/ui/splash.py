"""SplashScreen — animated GIF + tagline + version, shown during app startup."""
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from src.config import (
    BRAND_ANIMATION_GIF, APP_VERSION, APP_TAGLINE, APP_BRAND_NAME,
)


class SplashScreen(ctk.CTkToplevel):
    """Borderless Toplevel showing JTS brand animation + tagline + version.

    Auto-cycles through GIF frames at ~24fps. Caller is responsible for
    destroying the splash after a minimum visible duration (typically 2s)
    via `after(2000, splash.destroy)` from the main app.
    """

    WINDOW_W = 520
    WINDOW_H = 360
    GIF_SIZE = 256        # render GIF at this square size
    FRAME_DELAY_MS = 40   # ~24fps for the animation

    BG_COLOR = "#0A0A0A"          # brand black
    ACCENT_COLOR = "#EC4899"      # brand magenta — tagline cursor color
    TEXT_COLOR = "#FFFFFF"        # white text on dark
    DIM_COLOR = "#A3A3A3"         # subtle on dark

    def __init__(self, parent=None):
        super().__init__(parent)

        # Borderless, centered, on-top
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=self.BG_COLOR)

        # Center on screen
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - self.WINDOW_W) // 2
        y = (screen_h - self.WINDOW_H) // 2
        self.geometry(f"{self.WINDOW_W}x{self.WINDOW_H}+{x}+{y}")

        self._frames: list[ctk.CTkImage] = []
        self._after_id = None
        self._build_content()
        self._load_frames()
        if self._frames:
            self._animate(0)

    def _build_content(self):
        # Use a transparent inner frame to center content
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(expand=True, fill="both", padx=20, pady=20)

        # GIF placeholder (CTkLabel with image)
        self._gif_label = ctk.CTkLabel(container, text="", fg_color="transparent")
        self._gif_label.pack(pady=(20, 12))

        # Tagline
        ctk.CTkLabel(
            container,
            text=f"// {APP_TAGLINE.rstrip('.').lower()}",
            font=("Consolas", 14, "bold"),
            text_color=self.ACCENT_COLOR,
            fg_color="transparent",
        ).pack(pady=(0, 8))

        # App name + version
        ctk.CTkLabel(
            container,
            text=f"HR Absensi · v{APP_VERSION}",
            font=("Segoe UI", 12),
            text_color=self.TEXT_COLOR,
            fg_color="transparent",
        ).pack(pady=(0, 4))

        # Brand credit (small, dim)
        ctk.CTkLabel(
            container,
            text=APP_BRAND_NAME,
            font=("Segoe UI", 9),
            text_color=self.DIM_COLOR,
            fg_color="transparent",
        ).pack()

    def _load_frames(self):
        """Preload all GIF frames as CTkImage objects."""
        if not BRAND_ANIMATION_GIF.exists():
            return
        try:
            img = Image.open(str(BRAND_ANIMATION_GIF))
            while True:
                frame = img.copy().convert("RGBA")
                self._frames.append(ctk.CTkImage(
                    light_image=frame, dark_image=frame,
                    size=(self.GIF_SIZE, self.GIF_SIZE),
                ))
                img.seek(img.tell() + 1)
        except EOFError:
            pass  # End of frames
        except Exception:
            # Splash should not block app on GIF errors
            pass

    def _animate(self, idx: int):
        if not self._frames:
            return
        self._gif_label.configure(image=self._frames[idx % len(self._frames)])
        self._after_id = self.after(
            self.FRAME_DELAY_MS, self._animate, idx + 1,
        )

    def destroy(self):
        """Clean up animation timer before destroying window."""
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        super().destroy()
