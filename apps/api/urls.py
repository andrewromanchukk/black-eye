from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("bays", views.BayViewSet, basename="bay")
router.register("services", views.ServiceViewSet, basename="service")
router.register("bookings", views.BookingViewSet, basename="booking")
router.register("tire-deposits", views.TireDepositViewSet, basename="tire-deposit")
router.register("customers", views.CustomerViewSet, basename="customer")

urlpatterns = [
    path("auth/token/", views.ObtainToken.as_view(), name="api-token"),
    path("workshop/", views.me_workshop, name="api-workshop"),
    path("public/workshops/<slug:slug>/", views.public_workshop, name="api-public-workshop"),
    path("public/workshops/<slug:slug>/services/<int:service_id>/slots/", views.public_slots,
         name="api-public-slots"),
    path("public/workshops/<slug:slug>/bookings/", views.public_book, name="api-public-book"),
    path("", include(router.urls)),
]
