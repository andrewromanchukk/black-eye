from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.db import connection, transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.booking import engine, notify
from apps.booking.models import Booking
from apps.storage import services as storage
from apps.storage.models import TireDeposit
from apps.workshops.models import Bay, Service, Workshop

from . import forms

User = get_user_model()


# ---------- helpers ----------

def owner_workshop(request) -> Workshop:
    try:
        return request.user.workshop
    except Workshop.DoesNotExist:
        raise Http404("Brak warsztatu")


def parse_day(value: str | None) -> date:
    try:
        return date.fromisoformat(value) if value else timezone.localdate()
    except ValueError:
        return timezone.localdate()


# ---------- public pages ----------

def healthz(request):
    with connection.cursor() as cur:
        cur.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")


def landing(request):
    return render(request, "web/landing.html")


def terms(request):
    return render(request, "web/legal/terms.html")


def privacy(request):
    return render(request, "web/legal/privacy.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("web:dashboard")
    form = forms.SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        with transaction.atomic():
            user = User.objects.create_user(username=d["email"], email=d["email"], password=d["password"])
            workshop = Workshop.objects.create(
                owner=user, name=d["workshop_name"], slug=Workshop.unique_slug_for(d["workshop_name"]),
                address=d["address"], phone=d["phone"])
            workshop.create_default_hours()
            Bay.objects.create(workshop=workshop, name="Stanowisko 1")
            Service.objects.create(workshop=workshop, name="Wymiana opon — 4 koła", duration_min=45, price=120)
        login(request, user)
        messages.success(request, "Warsztat utworzony. Sprawdź godziny, stanowiska i usługi.")
        return redirect("web:dashboard")
    return render(request, "web/auth/signup.html", {"form": form})


# ---------- customer booking flow ----------

def public_booking(request, slug):
    workshop = get_object_or_404(Workshop, slug=slug)
    services = workshop.services.filter(is_active=True)
    return render(request, "web/public/services.html", {"workshop": workshop, "services": services})


def public_slots(request, slug, service_id):
    workshop = get_object_or_404(Workshop, slug=slug)
    service = get_object_or_404(Service, pk=service_id, workshop=workshop, is_active=True)
    days = engine.bookable_days(workshop)
    if request.GET.get("d"):
        day = parse_day(request.GET["d"])
        slots = engine.available_slots(workshop, service, day)
    else:  # open the first day that still has free slots
        day, slots = (days[0] if days else timezone.localdate()), []
        for candidate in days:
            slots = engine.available_slots(workshop, service, candidate)
            if slots:
                day = candidate
                break
    return render(request, "web/public/slots.html", {
        "workshop": workshop, "service": service, "days": days, "day": day, "slots": slots})


def public_book(request, slug, service_id):
    workshop = get_object_or_404(Workshop, slug=slug)
    service = get_object_or_404(Service, pk=service_id, workshop=workshop, is_active=True)
    try:
        start = datetime.fromisoformat(request.GET.get("start") or request.POST.get("start", ""))
    except ValueError:
        return redirect("web:public_slots", slug=slug, service_id=service.pk)
    if timezone.is_naive(start):
        start = timezone.make_aware(start)
    slots_url = reverse("web:public_slots", args=[slug, service.pk]) + f"?d={timezone.localtime(start).date()}"
    if engine.find_slot(workshop, service, start) is None and request.method == "GET":
        messages.error(request, "Ten termin jest już zajęty. Wybierz inny.")
        return redirect(slots_url)

    form = forms.PublicBookingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            booking = engine.book(workshop, service, start, customer_name=d["name"], phone=d["phone"],
                                  plate=d["plate"], note=d["note"])
        except engine.SlotUnavailable:
            messages.error(request, "Ktoś właśnie zajął ten termin. Wybierz inny.")
            return redirect(slots_url)
        except engine.InvalidBooking as e:
            form.add_error(None, str(e))
        else:
            notify.booking_confirmed(booking)
            return redirect("web:cancel_booking", token=booking.cancel_token)
    return render(request, "web/public/book.html", {
        "workshop": workshop, "service": service, "start": timezone.localtime(start), "form": form,
        "slots_url": slots_url})


def cancel_booking(request, token):
    """Booking page for the customer: confirmation + self-service cancel."""
    booking = get_object_or_404(Booking.objects.select_related("workshop", "service"), cancel_token=token)
    can_cancel = engine.can_customer_cancel(booking)
    if request.method == "POST" and can_cancel:
        engine.cancel(booking)
        messages.success(request, "Rezerwacja anulowana.")
        return redirect("web:cancel_booking", token=token)
    return render(request, "web/public/booking_detail.html", {
        "booking": booking, "workshop": booking.workshop, "can_cancel": can_cancel,
        "start": timezone.localtime(booking.start)})


# ---------- owner panel ----------

@login_required
def dashboard(request):
    return redirect("web:schedule")


@login_required
def schedule(request):
    workshop = owner_workshop(request)
    day = parse_day(request.GET.get("d"))
    tz = timezone.get_current_timezone()
    start = datetime.combine(day, datetime.min.time(), tzinfo=tz)
    bookings = (Booking.objects.filter(workshop=workshop, start__gte=start, start__lt=start + timedelta(days=1))
                .exclude(status=Booking.Status.CANCELLED).select_related("customer", "service", "bay"))
    bays = list(workshop.bays.all())
    columns = [(bay, [b for b in bookings if b.bay_id == bay.pk]) for bay in bays]
    return render(request, "web/panel/schedule.html", {
        "day": day, "prev": day - timedelta(days=1), "next": day + timedelta(days=1),
        "today": timezone.localdate(), "columns": columns, "count": len(bookings),
        "public_url": request.build_absolute_uri(reverse("web:public_booking", args=[workshop.slug]))})


@login_required
@require_POST
def booking_status(request, pk):
    workshop = owner_workshop(request)
    booking = get_object_or_404(Booking, pk=pk, workshop=workshop)
    engine.set_status(booking, request.POST.get("status", ""))
    messages.success(request, f"Status: {booking.get_status_display()}")
    return redirect(reverse("web:schedule") + f"?d={timezone.localtime(booking.start).date()}")


@login_required
def manual_booking(request):
    workshop = owner_workshop(request)
    initial = {}
    if request.GET.get("d"):
        initial["start"] = datetime.combine(parse_day(request.GET["d"]), datetime.min.time().replace(hour=9))
    form = forms.ManualBookingForm(request.POST or None, workshop=workshop, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            booking = engine.book(workshop, d["service"], d["start"], customer_name=d["name"], phone=d["phone"],
                                  plate=d["plate"], note=d["note"], source=Booking.Source.MANUAL,
                                  enforce_rules=False)
        except (engine.SlotUnavailable, engine.InvalidBooking) as e:
            form.add_error(None, str(e))
        else:
            messages.success(request, "Wizyta dodana.")
            return redirect(reverse("web:schedule") + f"?d={timezone.localtime(booking.start).date()}")
    return render(request, "web/panel/manual_booking.html", {"form": form})


@login_required
def workshop_settings(request):
    workshop = owner_workshop(request)
    form = forms.WorkshopForm(request.POST or None, instance=workshop, prefix="w")
    hours = forms.OpeningHoursFormSet(request.POST or None, instance=workshop, prefix="h")
    if request.method == "POST" and form.is_valid() and hours.is_valid():
        form.save()
        hours.save()
        messages.success(request, "Zapisano ustawienia.")
        return redirect("web:settings")
    return render(request, "web/panel/settings.html", {"form": form, "hours": hours})


@login_required
def bays(request):
    workshop = owner_workshop(request)
    form = forms.BayForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        bay = form.save(commit=False)
        bay.workshop = workshop
        bay.position = workshop.bays.count()
        bay.save()
        messages.success(request, "Dodano stanowisko.")
        return redirect("web:bays")
    return render(request, "web/panel/bays.html", {"form": form, "bays": workshop.bays.all()})


@login_required
def bay_edit(request, pk):
    bay = get_object_or_404(Bay, pk=pk, workshop=owner_workshop(request))
    form = forms.BayForm(request.POST or None, instance=bay)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Zapisano stanowisko.")
        return redirect("web:bays")
    return render(request, "web/panel/edit.html", {"form": form, "title": "Edytuj stanowisko", "back": "web:bays"})


@login_required
def services(request):
    workshop = owner_workshop(request)
    form = forms.ServiceForm(request.POST or None, workshop=workshop)
    if request.method == "POST" and form.is_valid():
        service = form.save(commit=False)
        service.workshop = workshop
        service.position = workshop.services.count()
        service.save()
        form.save_m2m()
        messages.success(request, "Dodano usługę.")
        return redirect("web:services")
    return render(request, "web/panel/services.html", {
        "form": form, "services": workshop.services.prefetch_related("bays")})


@login_required
def service_edit(request, pk):
    workshop = owner_workshop(request)
    service = get_object_or_404(Service, pk=pk, workshop=workshop)
    form = forms.ServiceForm(request.POST or None, instance=service, workshop=workshop)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Zapisano usługę.")
        return redirect("web:services")
    return render(request, "web/panel/edit.html", {"form": form, "title": "Edytuj usługę", "back": "web:services"})


@login_required
def storage_list(request):
    workshop = owner_workshop(request)
    q = request.GET.get("q", "")
    status = request.GET.get("status", TireDeposit.Status.STORED)
    form = forms.TireDepositForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        storage.register_deposit(workshop, **form.cleaned_data)
        messages.success(request, "Przyjęto opony do przechowalni.")
        return redirect("web:storage")
    deposits = storage.search(workshop, q, status=status or None)
    return render(request, "web/panel/storage.html", {
        "form": form, "deposits": deposits, "q": q, "status": status, "statuses": TireDeposit.Status.choices})


@login_required
@require_POST
def storage_return(request, pk):
    deposit = get_object_or_404(TireDeposit, pk=pk, workshop=owner_workshop(request))
    storage.mark_returned(deposit)
    messages.success(request, f"Wydano opony {deposit.plate}.")
    return redirect("web:storage")


@login_required
def reminders(request):
    workshop = owner_workshop(request)
    season = request.GET.get("season") or request.POST.get("season") or TireDeposit.Season.SUMMER
    if request.method == "POST":
        sent = storage.send_reminders(workshop, request.POST.getlist("deposit"))
        messages.success(request, f"Wysłano przypomnienia: {sent}.")
        return redirect(reverse("web:reminders") + f"?season={season}")
    candidates = storage.reminder_candidates(workshop, season)
    return render(request, "web/panel/reminders.html", {
        "season": season, "seasons": TireDeposit.Season.choices, "candidates": candidates,
        "preview": storage.reminder_text(workshop, candidates[0]) if candidates else None})
