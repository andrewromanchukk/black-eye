"""Tenancy seam: which Workshop does this request act for, and what may it see.

Every owner-facing view (web panel, REST API, future mobile endpoints) gets its
Workshop and its objects only through this module, so a new view cannot forget
to filter by workshop.

    current_workshop(request) -> Workshop          (raises NoWorkshop)
    scoped(model_or_queryset, request) -> QuerySet (only the current workshop's rows)
    get_owned(model_or_queryset, request, **lookup) -> object (raises Model.DoesNotExist)
"""
from django.db.models import Model, QuerySet

from .models import Workshop


class NoWorkshop(Exception):
    """Anonymous user or a user without a workshop (e.g. staff)."""


def current_workshop(request) -> Workshop:
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        raise NoWorkshop()
    try:
        return user.workshop
    except Workshop.DoesNotExist:
        raise NoWorkshop()


def scoped(model_or_qs, request) -> QuerySet:
    qs = model_or_qs._default_manager.all() if isinstance(model_or_qs, type) and issubclass(model_or_qs, Model) \
        else model_or_qs
    workshop = current_workshop(request)
    if qs.model is Workshop:
        return qs.filter(pk=workshop.pk)
    return qs.filter(workshop=workshop)


def get_owned(model_or_qs, request, **lookup):
    return scoped(model_or_qs, request).get(**lookup)
