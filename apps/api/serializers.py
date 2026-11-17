from rest_framework import serializers

from apps.booking.models import Booking, Customer
from apps.storage.models import TireDeposit
from apps.workshops.models import Bay, OpeningHours, Service, Workshop


class OpeningHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = OpeningHours
        fields = ["weekday", "is_closed", "opens", "closes"]


class WorkshopSerializer(serializers.ModelSerializer):
    opening_hours = OpeningHoursSerializer(many=True, read_only=True)

    class Meta:
        model = Workshop
        fields = ["id", "name", "slug", "address", "phone", "slot_step_min", "booking_horizon_days",
                  "min_notice_min", "visit_reminders", "opening_hours"]
        read_only_fields = ["id"]


class PublicWorkshopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workshop
        fields = ["name", "slug", "address", "phone"]


class BaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Bay
        fields = ["id", "name", "is_active", "position"]


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "name", "duration_min", "price", "is_active", "bays", "position"]

    def validate_bays(self, bays):
        workshop = self.context["workshop"]
        if any(b.workshop_id != workshop.pk for b in bays):
            raise serializers.ValidationError("Bay belongs to another workshop.")
        return bays


class PublicServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "name", "duration_min", "price"]


class SlotSerializer(serializers.Serializer):
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()


class BookingSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_phone = serializers.CharField(source="customer.phone", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    bay_name = serializers.CharField(source="bay.name", read_only=True)

    class Meta:
        model = Booking
        fields = ["id", "start", "end", "status", "source", "plate", "note", "service", "service_name",
                  "bay", "bay_name", "customer_name", "customer_phone"]
        read_only_fields = fields


class BookingCreateSerializer(serializers.Serializer):
    service = serializers.IntegerField()
    start = serializers.DateTimeField()
    name = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=20)
    plate = serializers.CharField(max_length=16)
    note = serializers.CharField(max_length=300, required=False, allow_blank=True)
    consent = serializers.BooleanField(required=False)


class BookingStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Booking.Status.choices)


class TireDepositSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    phone = serializers.CharField(source="customer.phone", read_only=True)

    class Meta:
        model = TireDeposit
        fields = ["id", "plate", "season", "description", "location", "status", "stored_at", "returned_at",
                  "reminded_at", "customer_name", "phone"]
        read_only_fields = ["id", "status", "returned_at", "reminded_at", "customer_name", "phone"]


class TireDepositCreateSerializer(serializers.Serializer):
    customer_name = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=20)
    plate = serializers.CharField(max_length=16)
    season = serializers.ChoiceField(choices=TireDeposit.Season.choices)
    description = serializers.CharField(max_length=200)
    location = serializers.CharField(max_length=40, required=False, allow_blank=True)


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "name", "phone", "created_at"]


def customer_history_data(h) -> dict:
    return {
        **CustomerSerializer(h.customer).data,
        "plates": h.plates,
        "visits_done": h.visits_done,
        "no_shows": h.no_shows,
        "bookings": BookingSerializer(h.bookings, many=True).data,
        "tire_deposits": TireDepositSerializer(h.deposits, many=True).data,
    }
