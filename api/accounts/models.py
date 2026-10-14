from io import BytesIO
from django.db import models
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from PIL import Image, ImageOps
from django.utils.translation import gettext_lazy as _
import uuid
# from test_app.models import Address
from django.contrib.auth.models import AbstractUser

# Profile photos are kept out of the static files, which anyone can download,
# and are only served by accounts.views.photo to users allowed to see them.
# (Older photos named static/images/user_images/... resolve to the same place.)
photo_storage = FileSystemStorage(location=settings.BASE_DIR, base_url=None)

# Profile photos are stored as square JPEGs of this many pixels a side
PHOTO_SIZE = 512

def shrink_photo(upload):
    """
    A PHOTO_SIZE square JPEG copy of an uploaded photo, named with a random
    UUID. Re-encoding it also drops its metadata, such as the location where
    it was taken.
    """
    image = ImageOps.exif_transpose(Image.open(upload))
    image = ImageOps.fit(image.convert("RGB"), (PHOTO_SIZE, PHOTO_SIZE))
    output = BytesIO()
    image.save(output, "JPEG", quality=85)
    return ContentFile(output.getvalue(), name=f"{uuid.uuid4().hex}.jpg")

class User(AbstractUser):
    class NameVisibility(models.TextChoices):
        FIRST = "first", _("First name only")
        INITIAL = "initial", _("First name and last initial")
        FULL = "full", _("Full name")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Remove username without actually removing it
    username = models.CharField(null=True, blank=True)
    email = models.EmailField(unique=True)

    pfp = models.ImageField(upload_to='private_media/profile_photos/', storage=photo_storage, blank=True, null=True)
    address = models.ForeignKey('test_app.Address', on_delete=models.CASCADE, null=True, blank=True)
    phone = models.CharField(blank=True, null=True)

    # Privacy, see accounts/privacy.py. People sharing a ride (the driver and
    # its accepted passengers) always see each other's full names.
    name_visibility = models.CharField(max_length=10, choices=NameVisibility.choices, default=NameVisibility.INITIAL)
    show_photo = models.BooleanField(default=True, help_text="Show the profile photo to other members")
    share_email = models.BooleanField(default=True, help_text="Share the email address with people sharing a ride")
    share_phone = models.BooleanField(default=False, help_text="Share the phone number with people sharing a ride")

    # Notifications
    notify_ride_requests = models.BooleanField(default=True, help_text="Email about ride requests and responses")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @classmethod
    def from_db(cls, db, field_names, values):
        user = super().from_db(db, field_names, values)
        # Remembered so that a replaced or removed photo's file can be deleted
        user._saved_pfp = user.__dict__.get("pfp") or ""
        return user

    def save(self, *args, **kwargs):
        # A newly uploaded photo, from the profile page or the admin
        if self.pfp and not self.pfp._committed:
            self.pfp = shrink_photo(self.pfp)
        super().save(*args, **kwargs)

        old = str(getattr(self, "_saved_pfp", ""))
        if old and old != (self.pfp.name or ""):
            photo_storage.delete(old)
        self._saved_pfp = self.pfp.name or ""

    def initials(self):
        return f"{self.first_name[:1]}{self.last_name[:1]}".upper() or "?"
