from cryptography.hazmat.primitives import serialization
from django.core.management.base import BaseCommand
from py_vapid import Vapid01
from py_vapid.utils import b64urlencode


class Command(BaseCommand):
    help = "Makes the VAPID key pair for push notifications (notifications/push.py), as lines for .env."

    def handle(self, *args, **options):
        vapid = Vapid01()
        vapid.generate_keys()
        private = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
        public = vapid.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        self.stdout.write("# Push notifications. Keep the private key secret; changing the keys")
        self.stdout.write("# stops push notifications on every device until each one turns them on again.")
        self.stdout.write(f"VAPID_PUBLIC_KEY={b64urlencode(public)}")
        self.stdout.write(f"VAPID_PRIVATE_KEY={b64urlencode(private)}")
