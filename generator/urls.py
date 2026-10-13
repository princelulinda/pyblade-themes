from django.urls import path

from . import views

urlpatterns = [
    path("", views.editor, name="editor"),
    path("en/", views.editor, {"lang": "en"}, name="editor_en"),
    path("t/<str:slug>/", views.shared, name="shared"),
    path("en/t/<str:slug>/", views.shared, {"lang": "en"}, name="shared_en"),
    path("t/<str:slug>.css", views.shared_css, name="shared_css"),
    path("api/preset", views.api_preset, name="api_preset"),
    path("api/export", views.api_export, name="api_export"),
    path("api/themes", views.api_save, name="api_save"),
    path("theme/full.css", views.stylesheet, name="stylesheet"),
]
