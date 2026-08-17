from app.payment_service.service import should_fail_payment


def test_normal_customer_succeeds() -> None:
    assert not should_fail_payment("customer-123", 4999)


def test_fail_suffix_simulates_provider_decline() -> None:
    assert should_fail_payment("customer-fail", 4999)
