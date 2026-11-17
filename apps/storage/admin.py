from django.contrib import admin

from .models import TireDeposit


@admin.register(TireDeposit)
class TireDepositAdmin(admin.ModelAdmin):
    list_display = ("plate", "workshop", "customer", "season", "status", "location", "stored_at")
    list_filter = ("status", "season", "workshop")
    search_fields = ("plate", "customer__phone")
