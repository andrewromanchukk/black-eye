"""REST API v1 — the backend for the future owner mobile app.

Owner endpoints require `Authorization: Token <key>` (POST /api/v1/auth/token/).
Public endpoints (prefix /public/) need no auth and mirror the customer booking page.
"""
from datetime import date, datetime, timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from apps.booking import engine, reservations
from apps.booking.reservations import CustomerDetails
from apps.booking.models import Booking
from apps.storage import services as storage
from apps.storage.models import TireDeposit
from apps.workshops.models import Bay, Service, Workshop

from . import serializers as s


class ObtainToken(ObtainAuthToken):
    """POST {"username": "<email>", "password": "..."} -> {"token": "..."}"""


def owner_workshop(request) -> Workshop:
    try:
        return request.user.workshop
    except Workshop.DoesNotExist:
        raise NotFound("No workshop for this user.")


def parse_date(value) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError({"date": "Use YYYY-MM-DD."})


def _details(d) -> CustomerDetails:
    return CustomerDetails(name=d["name"], phone=d["phone"], plate=d["plate"], note=d.get("note", ""))


class WorkshopScoped:
    def get_workshop(self):
        return owner_workshop(self.request)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["workshop"] = self.get_workshop()
        return ctx

    def perform_create(self, serializer):
        serializer.save(workshop=self.get_workshop())


@api_view(["GET", "PATCH"])
def me_workshop(request):
    workshop = owner_workshop(request)
    if request.method == "PATCH":
        ser = s.WorkshopSerializer(workshop, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
    return Response(s.WorkshopSerializer(workshop).data)


class BayViewSet(WorkshopScoped, viewsets.ModelViewSet):
    serializer_class = s.BaySerializer

    def get_queryset(self):
        return Bay.objects.filter(workshop=self.get_workshop())


class ServiceViewSet(WorkshopScoped, viewsets.ModelViewSet):
    serializer_class = s.ServiceSerializer

    def get_queryset(self):
        return Service.objects.filter(workshop=self.get_workshop()).prefetch_related("bays")


class BookingViewSet(WorkshopScoped, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """GET ?date=YYYY-MM-DD — bookings of one day (default today). POST — manual booking."""

    serializer_class = s.BookingSerializer

    def get_queryset(self):
        qs = Booking.objects.filter(workshop=self.get_workshop()).select_related("customer", "service", "bay")
        if self.action == "list":
            day = parse_date(self.request.query_params["date"]) if "date" in self.request.query_params \
                else timezone.localdate()
            start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.get_current_timezone())
            qs = qs.filter(start__gte=start, start__lt=start + timedelta(days=1))
        return qs

    def create(self, request):
        workshop = self.get_workshop()
        ser = s.BookingCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        service = get_object_or_404(Service, pk=d["service"], workshop=workshop)
        try:
            booking = reservations.reserve_manual(workshop, service, d["start"], _details(d))
        except engine.SlotUnavailable as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        except engine.InvalidBooking as e:
            raise ValidationError({"detail": str(e)})
        return Response(s.BookingSerializer(booking).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def status(self, request, pk=None):
        booking = self.get_object()
        ser = s.BookingStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        engine.set_status(booking, ser.validated_data["status"])
        return Response(s.BookingSerializer(booking).data)


class TireDepositViewSet(WorkshopScoped, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                         viewsets.GenericViewSet):
    """GET ?q=<plate|phone>&status=stored|returned"""

    serializer_class = s.TireDepositSerializer

    def get_queryset(self):
        params = self.request.query_params
        return storage.search(self.get_workshop(), params.get("q", ""), status=params.get("status") or None)

    def create(self, request):
        ser = s.TireDepositCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        deposit = storage.register_deposit(self.get_workshop(), **ser.validated_data)
        return Response(s.TireDepositSerializer(deposit).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="return")
    def mark_returned(self, request, pk=None):
        return Response(s.TireDepositSerializer(storage.mark_returned(self.get_object())).data)

    @action(detail=False, methods=["post"])
    def remind(self, request):
        """POST {"ids": [1,2,3]} — send season reminders."""
        ids = request.data.get("ids") or []
        return Response({"sent": storage.send_reminders(self.get_workshop(), ids)})


# ---------- public (customer) ----------

class PublicThrottle(AnonRateThrottle):
    rate = "60/min"


@api_view(["GET"])
@permission_classes([AllowAny])
def public_workshop(request, slug):
    workshop = get_object_or_404(Workshop, slug=slug)
    return Response({**s.PublicWorkshopSerializer(workshop).data,
                     "services": s.PublicServiceSerializer(workshop.services.filter(is_active=True), many=True).data})


@api_view(["GET"])
@permission_classes([AllowAny])
def public_slots(request, slug, service_id):
    workshop = get_object_or_404(Workshop, slug=slug)
    service = get_object_or_404(Service, pk=service_id, workshop=workshop, is_active=True)
    slots = engine.available_slots(workshop, service, parse_date(request.query_params.get("date")))
    return Response(s.SlotSerializer(slots, many=True).data)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PublicThrottle])
def public_book(request, slug):
    workshop = get_object_or_404(Workshop, slug=slug)
    ser = s.BookingCreateSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    d = ser.validated_data
    service = get_object_or_404(Service, pk=d["service"], workshop=workshop, is_active=True)
    try:
        booking = reservations.reserve_online(workshop, service, d["start"], _details(d),
                                              consent=d.get("consent", False))
    except reservations.ConsentRequired as e:
        raise ValidationError({"consent": str(e)})
    except engine.SlotUnavailable as e:
        return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
    except engine.InvalidBooking as e:
        raise ValidationError({"detail": str(e)})
    return Response({"start": booking.start, "end": booking.end, "cancel_token": booking.cancel_token},
                    status=status.HTTP_201_CREATED)
