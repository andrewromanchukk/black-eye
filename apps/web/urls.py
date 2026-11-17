from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("regulamin/", views.terms, name="terms"),
    path("polityka-prywatnosci/", views.privacy, name="privacy"),
    # auth
    path("rejestracja/", views.signup, name="signup"),
    path("logowanie/", auth_views.LoginView.as_view(template_name="web/auth/login.html"), name="login"),
    path("wyloguj/", auth_views.LogoutView.as_view(), name="logout"),
    path("haslo/reset/", auth_views.PasswordResetView.as_view(
        template_name="web/auth/password_reset.html", email_template_name="web/auth/password_reset_email.txt",
        success_url="/haslo/reset/wyslano/"), name="password_reset"),
    path("haslo/reset/wyslano/", auth_views.PasswordResetDoneView.as_view(
        template_name="web/auth/message.html", extra_context={"title": "Sprawdź skrzynkę",
        "text": "Jeśli konto istnieje, wysłaliśmy link do zmiany hasła."}), name="password_reset_done"),
    path("haslo/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="web/auth/password_reset_confirm.html", success_url="/haslo/reset/gotowe/"),
        name="password_reset_confirm"),
    path("haslo/reset/gotowe/", auth_views.PasswordResetCompleteView.as_view(
        template_name="web/auth/message.html", extra_context={"title": "Hasło zmienione",
        "text": "Możesz się teraz zalogować."}), name="password_reset_complete"),
    # owner panel
    path("panel/", views.dashboard, name="dashboard"),
    path("panel/grafik/", views.schedule, name="schedule"),
    path("panel/wizyty/nowa/", views.manual_booking, name="manual_booking"),
    path("panel/wizyty/<int:pk>/status/", views.booking_status, name="booking_status"),
    path("panel/ustawienia/", views.workshop_settings, name="settings"),
    path("panel/stanowiska/", views.bays, name="bays"),
    path("panel/stanowiska/<int:pk>/", views.bay_edit, name="bay_edit"),
    path("panel/uslugi/", views.services, name="services"),
    path("panel/uslugi/<int:pk>/", views.service_edit, name="service_edit"),
    path("panel/przechowalnia/", views.storage_list, name="storage"),
    path("panel/przechowalnia/<int:pk>/wydaj/", views.storage_return, name="storage_return"),
    path("panel/przypomnienia/", views.reminders, name="reminders"),
    path("panel/sms/", views.sms_log, name="sms_log"),
    path("panel/klienci/", views.customer_list, name="customers"),
    path("panel/klienci/<int:pk>/", views.customer_detail, name="customer_detail"),
    # customer booking
    path("w/<slug:slug>/", views.public_booking, name="public_booking"),
    path("w/<slug:slug>/<int:service_id>/", views.public_slots, name="public_slots"),
    path("w/<slug:slug>/<int:service_id>/rezerwuj/", views.public_book, name="public_book"),
    path("r/<str:token>/", views.cancel_booking, name="cancel_booking"),
]
