"""
Draws the iOS launch images listed in settings.PWA_APP_SPLASH_SCREEN: the LUT
logo of templates/_splash_logo.html, PWA_SPLASH_LOGO_WIDTH CSS px wide, in the middle
of the screen on PWA_APP_BACKGROUND_COLOR. Needs rsvg-convert (librsvg).

    python manage.py make_splash

iOS loads the launch images when the app is added to the home screen, so a
phone shows new ones only after the app is removed and added again.
"""
import io
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from PIL import Image


class Command(BaseCommand):
    help = "Draws the iOS launch images (PWA_SPLASH_SCREENS in settings)"

    def handle(self, *args, **options):
        folder = Path(settings.BASE_DIR) / "static/images/splash"
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("splash-*.png"):
            old.unlink()

        for width, height, ratio in settings.PWA_SPLASH_SCREENS:
            size = settings.PWA_SPLASH_LOGO_WIDTH * ratio
            svg = render_to_string("_splash_logo.html", {"width": f"{size}px"})
            png = subprocess.run(
                ["rsvg-convert", "--width", str(size), "--height", str(size)],
                input=svg.encode(), capture_output=True, check=True,
            ).stdout
            logo = Image.open(io.BytesIO(png)).convert("RGBA")

            screen = Image.new("RGBA", (width * ratio, height * ratio), settings.PWA_APP_BACKGROUND_COLOR)
            # Same rounding as the browser's centring in _splash.html
            screen.alpha_composite(logo, ((width * ratio - size) // 2, (height * ratio - size) // 2))
            name = folder / f"splash-{width * ratio}x{height * ratio}.png"
            screen.convert("RGB").save(name, optimize=True)
            self.stdout.write(f"{name.relative_to(settings.BASE_DIR)}")
