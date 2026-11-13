from django.contrib import admin

from .models import Booking, Customer


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("start", "workshop", "bay", "service", "customer", "plate", "status", "source")
    list_filter = ("status", "source", "workshop")
    search_fields = ("plate", "customer__phone", "customer__name")


admin.site.register(Customer)
