def theme_settings(request):
    preference = None
    if getattr(request, "user", None) and request.user.is_authenticated:
        preference = getattr(request.user, "preference", None)
    theme_preference = preference.theme_mode if preference else "system"
    if theme_preference not in {"light", "dark", "system"}:
        theme_preference = "system"
    theme = theme_preference if theme_preference in {"light", "dark"} else "system"
    return {
        "theme": theme,
        "theme_preference": theme_preference,
    }


def product_context(request):
    return {
        "app_name": "CodeArena",
        "tagline": "Compete, connect, and revise smarter.",
    }
