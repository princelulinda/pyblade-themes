import secrets

from django.db import models
from django.urls import reverse

from .themes import EditorTheme


def new_slug() -> str:
    return secrets.token_urlsafe(6)[:8].replace("-", "x").replace("_", "y")


class SavedTheme(models.Model):
    """A theme saved from the editor, shared by its short link: /t/<slug>/."""

    slug = models.CharField(max_length=12, unique=True, default=new_slug, editable=False)
    name = models.CharField(max_length=60, blank=True)
    base = models.CharField(max_length=20)
    color = models.CharField(max_length=20)
    radius = models.CharField(max_length=12)
    light = models.JSONField()
    dark = models.JSONField()
    shadow = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name or self.slug

    @property
    def theme(self) -> EditorTheme:
        return EditorTheme.from_payload({"base": self.base, "color": self.color, "radius": self.radius,
                                         "light": self.light, "dark": self.dark, "shadow": self.shadow})

    def get_absolute_url(self):
        return reverse("shared", args=[self.slug])
