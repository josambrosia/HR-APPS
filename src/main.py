"""HR Absensi App — entry point.

Initializes DB, shows splash screen for ~2s minimum while constructing
the main window in the background, then transitions to the main app.
"""
from src.config import DB_PATH
from src.db.schema import init_db
from src.ui.app import HRApp
from src.ui.splash import SplashScreen


SPLASH_MIN_MS = 2000  # minimum splash display duration


def main():
    init_db(DB_PATH)

    # Load the bundled display typeface (Space Grotesk) and repoint the theme's
    # display tokens at it BEFORE any screen is built. Falls back to Segoe UI.
    from src.ui.fonts import apply_display_font
    apply_display_font()

    # Construct main app first (it must be the tk root). Hide it so the
    # splash is the only thing visible during startup.
    app = HRApp()
    app.withdraw()

    splash = SplashScreen(parent=app)
    splash.lift()
    splash.update()

    def _reveal():
        splash.destroy()
        app.deiconify()
        app.state("zoomed")   # maximize after reveal
        # Re-apply icon after window state changes (some Windows builds drop
        # the iconbitmap setting through withdraw → deiconify → zoomed)
        app._apply_brand_icon()

    app.after(SPLASH_MIN_MS, _reveal)
    app.mainloop()


if __name__ == "__main__":
    main()
