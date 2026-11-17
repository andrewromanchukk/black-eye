def current_workshop(request):
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return {"my_workshop": getattr(user, "workshop", None)}
    return {}
