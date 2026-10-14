from io import BytesIO
from django.db import models
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from PIL import Image, ImageCms, ImageOps
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

def shrink_photo(upload, crop=None):
    """
    A PHOTO_SIZE square JPEG copy of an uploaded photo, named with a random
    UUID. Re-encoding it also drops its metadata, such as the location where
    it was taken.

    crop is the (x, y, size) square the user framed their face in, in pixels
    of the photo turned upright. Without one, the middle of the photo is used.
    """
    image = Image.open(upload)
    image = to_srgb(ImageOps.exif_transpose(image), image.info.get("icc_profile"))
    if crop:
        image = image.crop(crop_box(crop, image.size))
    image = ImageOps.fit(image, (PHOTO_SIZE, PHOTO_SIZE))
    output = BytesIO()
    image.save(output, "JPEG", quality=85)
    return ContentFile(output.getvalue(), name=f"{uuid.uuid4().hex}.jpg")

def crop_box(crop, image_size):
    """The crop square as a Pillow box, moved and shrunk to fit in the image."""
    x, y, size = crop
    width, height = image_size
    size = max(1, min(round(size), width, height))
    x = min(max(round(x), 0), width - size)
    y = min(max(round(y), 0), height - size)
    return (x, y, x + size, y + size)

PHOTO_FOLDER = "private_media/profile_photos/"

def delete_photo_file(name):
    """
    Deletes a photo the app stored. Older photos (static/images/...) are
    left alone, as they can be files kept in the repository.
    """
    if name and name.startswith(PHOTO_FOLDER):
        photo_storage.delete(name)

SRGB = ImageCms.createProfile("sRGB")

def to_srgb(image, icc_profile):
    """
    The image in RGB with sRGB colours. Phone and camera photos are often in
    a wider colour space (Display P3, Adobe RGB) given by their ICC profile;
    the saved photo has no profile, so browsers show it as sRGB, and without
    converting its colours look washed out.
    """
    if icc_profile:
        try:
            if image.mode not in ("RGB", "CMYK"):
                image = image.convert("RGB")
            return ImageCms.profileToProfile(
                image, ImageCms.ImageCmsProfile(BytesIO(icc_profile)), SRGB, outputMode="RGB",
            )
        except (ImageCms.PyCMSError, OSError):
            # A broken or unsupported profile: keep the colours as they are
            pass
    return image.convert("RGB")

class User(AbstractUser):
    class NameVisibility(models.TextChoices):
        FIRST = "first", _("First name only")
        INITIAL = "initial", _("First name and last initial")
        FULL = "full", _("Full name")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Remove username without actually removing it
    username = models.CharField(null=True, blank=True)
    email = models.EmailField(unique=True)

    pfp = models.ImageField(upload_to=PHOTO_FOLDER, storage=photo_storage, blank=True, null=True)
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
        # (pfp_crop: the square chosen in the photo framing dialog, if any)
        if self.pfp and not self.pfp._committed:
            self.pfp = shrink_photo(self.pfp, getattr(self, "pfp_crop", None))
            self.pfp_crop = None
        super().save(*args, **kwargs)

        old = str(getattr(self, "_saved_pfp", ""))
        if old != (self.pfp.name or ""):
            delete_photo_file(old)
        self._saved_pfp = self.pfp.name or ""

    def initials(self):
        return f"{self.first_name[:1]}{self.last_name[:1]}".upper() or "?"
