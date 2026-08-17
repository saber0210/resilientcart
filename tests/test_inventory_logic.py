from app.inventory_service.logic import can_reserve


def test_can_reserve_exact_stock() -> None:
    assert can_reserve(100, 100)


def test_cannot_oversell() -> None:
    assert not can_reserve(99, 100)


def test_rejects_non_positive_quantity() -> None:
    assert not can_reserve(10, 0)
