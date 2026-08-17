"""Add shared context to every rendered page."""

from apps.submission_queue.models import CartItem, QueueEntry


def cart(request):
    """Return the number of staged fastq samples for the navigation badge.

    Anonymous requests, including the login page and password reset, get no cart query,
        and the count is only taken for authenticated users so an unauthenticated 404 does not
        hit the database on the way out.
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {
        "cart_count": CartItem.objects.filter(user=user).count(),
        "failure_count": QueueEntry.objects.filter(
            requested_by=user,
            status__in=[QueueEntry.Status.FAILED, QueueEntry.Status.STRANDED],
        ).count(),
    }
