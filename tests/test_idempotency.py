from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.order_service.models import Base
from app.order_service.schemas import CreateOrderRequest
from app.order_service.service import create_order


def test_same_key_returns_same_order() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    request = CreateOrderRequest(
        customer_id="test-user",
        item_id="SKU-CHAIR",
        quantity=1,
        amount_cents=4999,
    )

    first, first_created = create_order(session, request, "same-key")
    second, second_created = create_order(session, request, "same-key")

    assert first_created is True
    assert second_created is False
    assert first.id == second.id
