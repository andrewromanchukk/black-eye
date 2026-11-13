from django.contrib import admin
from django.urls import include, path

from apps.web.views import healthz

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.api.urls")),
    path("", include("apps.web.urls")),
]
