from django.contrib import admin

from .models import Bay, OpeningHours, Service, Workshop


class OpeningHoursInline(admin.TabularInline):
    model = OpeningHours
    extra = 0


@admin.register(Workshop)
class WorkshopAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "owner", "phone", "created_at")
    search_fields = ("name", "slug", "owner__email")
    inlines = [OpeningHoursInline]


admin.site.register(Bay)
admin.site.register(Service)
