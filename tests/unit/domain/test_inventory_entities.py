"""Unit tests for InventoryLevel aggregate root."""

from __future__ import annotations

import pytest

from app.domain.errors import DomainError
from app.domain.inventory.entities import InsufficientStockError, InventoryLevel
from app.domain.products.entities import SKU


def _level(on_hand: int, reserved: int = 0) -> InventoryLevel:
    return InventoryLevel(sku=SKU("TEST-SKU"), on_hand=on_hand, reserved=reserved)


# ---------------------------------------------------------------------------
# available() derived value
# ---------------------------------------------------------------------------


def test_available_is_on_hand_minus_reserved() -> None:
    level = _level(on_hand=10, reserved=3)
    assert level.available() == 7


def test_available_is_zero_when_fully_reserved() -> None:
    level = _level(on_hand=5, reserved=5)
    assert level.available() == 0


# ---------------------------------------------------------------------------
# reserve()
# ---------------------------------------------------------------------------


def test_reserve_increments_reserved() -> None:
    level = _level(on_hand=10, reserved=0)
    level.reserve(4)
    assert level.reserved == 4
    assert level.on_hand == 10  # on_hand unchanged


def test_reserve_raises_when_quantity_exceeds_available() -> None:
    level = _level(on_hand=2, reserved=1)
    with pytest.raises(InsufficientStockError) as exc_info:
        level.reserve(2)
    assert exc_info.value.requested == 2
    assert exc_info.value.available == 1


def test_reserve_raises_for_zero_quantity() -> None:
    level = _level(on_hand=10, reserved=0)
    with pytest.raises(DomainError):
        level.reserve(0)


def test_reserve_raises_for_negative_quantity() -> None:
    level = _level(on_hand=10, reserved=0)
    with pytest.raises(DomainError):
        level.reserve(-1)


def test_reserve_exact_available_succeeds() -> None:
    """Reserving exactly the available quantity must succeed."""
    level = _level(on_hand=3, reserved=0)
    level.reserve(3)
    assert level.reserved == 3
    assert level.available() == 0


# ---------------------------------------------------------------------------
# release()
# ---------------------------------------------------------------------------


def test_release_decrements_reserved() -> None:
    level = _level(on_hand=10, reserved=5)
    level.release(3)
    assert level.reserved == 2


def test_release_raises_when_more_than_reserved() -> None:
    level = _level(on_hand=5, reserved=2)
    with pytest.raises(DomainError):
        level.release(3)


def test_release_raises_for_zero_quantity() -> None:
    level = _level(on_hand=5, reserved=2)
    with pytest.raises(DomainError):
        level.release(0)


# ---------------------------------------------------------------------------
# commit()
# ---------------------------------------------------------------------------


def test_commit_decrements_both_on_hand_and_reserved() -> None:
    level = _level(on_hand=10, reserved=5)
    level.commit(5)
    assert level.reserved == 0
    assert level.on_hand == 5


def test_commit_raises_when_more_than_reserved() -> None:
    level = _level(on_hand=10, reserved=3)
    with pytest.raises(DomainError):
        level.commit(4)


def test_commit_raises_for_zero_quantity() -> None:
    level = _level(on_hand=10, reserved=5)
    with pytest.raises(DomainError):
        level.commit(0)
