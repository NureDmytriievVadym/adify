"""FR-124 (ADY-056): work starts only with a validated creative when the order needs one.

The rule is complete; only its data is pending. Uploading and validating creatives against
the requirements snapshot is ADY-055, which will mark snapshots that need customer
creatives and store creatives with their validation result. Until then no snapshot asks
for creatives and no order has one, so nothing is blocked.
"""

from adify_api.orders.models import Order

NO_VALIDATED_CREATIVE = "No validated creative"


def requires_creatives(order: Order) -> bool:
    """Whether the order's requirements snapshot asks the customer for creatives."""
    return bool(order.requirements.get("requires_creatives", False))


def has_validated_creative(order: Order) -> bool:
    """Whether a creative attached to the order passed validation.

    Stub until ADY-055 stores creatives: it then becomes a check that at least one of the
    order's creatives has a passed validation result.
    """
    return False


def work_start_blocker(order: Order) -> str | None:
    """Why the provider cannot start work yet because of creatives, or ``None``."""
    if requires_creatives(order) and not has_validated_creative(order):
        return NO_VALIDATED_CREATIVE
    return None
