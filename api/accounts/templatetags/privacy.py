from django import template
from django.urls import reverse

from accounts import privacy

register = template.Library()


@register.filter
def display_name(user, partner=False):
    """{{ user|display_name }}, or {{ user|display_name:True }} for ride partners."""
    return privacy.display_name(user, partner)


@register.inclusion_tag("_avatar.html", takes_context=True)
def avatar(context, user, size="w-9", text="text-sm"):
    """The user's photo if the viewer may see it, otherwise their initials."""
    photo_url = None
    if privacy.can_see_photo(user, context["request"].user):
        # The file name changes with each new photo, so the browser does not
        # keep showing an old one
        photo_url = f"{reverse('user_photo', args=[user.pk])}?v={user.pfp.name.rsplit('/', 1)[-1]}"
    return {"user": user, "photo_url": photo_url, "size": size, "text": text}
