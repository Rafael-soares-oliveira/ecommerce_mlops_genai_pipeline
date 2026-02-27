import ibis
import pandas as pd
import pytest
from pytest_mock import MockerFixture

from thelook_ecommerce_analysis.pipelines.data_metrics.metrics.customer_metrics import (
    cohort_retention,
    customer_rfm_ltv,
)
from thelook_ecommerce_analysis.pipelines.data_metrics.metrics.product_360 import (
    product_360,
)
from thelook_ecommerce_analysis.pipelines.data_metrics.metrics.sales_daily import (
    daily_sales_and_revenue,
)
from thelook_ecommerce_analysis.pipelines.data_metrics.metrics.web_analytics import (
    sales_funnel,
    session_conversion,
    traffic_source_performance,
)


@pytest.fixture
def users_table() -> ibis.Table:
    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "country": ["BR", "US", "BR"],
            "traffic_source": ["Organic", "Facebook", "Organic"],
        }
    )
    return ibis.memtable(df)


@pytest.fixture
def order_items_table() -> ibis.Table:
    df = pd.DataFrame(
        {
            "order_id": [10, 11, 12, 13],
            "user_id": [1, 1, 2, 3],
            "product_id": [100, 101, 100, 102],
            "status": ["Complete", "Returned", "Complete", "Cancelled"],
            "sale_price": [50.0, 30.0, 100.0, 20.0],
            "created_at": pd.to_datetime(
                ["2023-01-01", "2023-01-15", "2023-02-01", "2023-03-01"]
            ),
            "shipped_at": pd.to_datetime(
                ["2023-01-02", "2023-01-16", "2023-02-02", pd.NaT]
            ),
        }
    )
    return ibis.memtable(df)


@pytest.fixture
def products_table() -> ibis.Table:
    df = pd.DataFrame(
        {
            "id": [100, 101, 102],
            "category": ["A", "B", "A"],
            "name": ["Prod1", "Prod2", "Prod3"],
            "cost": [20.0, 10.0, 5.0],
        }
    )
    return ibis.memtable(df)


@pytest.fixture
def inventory_items_table() -> ibis.Table:
    df = pd.DataFrame(
        {
            "id": [1, 2],
            "product_id": [100, 101],
            "created_at": pd.to_datetime(["2022-12-01", "2022-12-15"]),
            "sold_at": [pd.NaT, pd.NaT],  # Não vendidos
        }
    )
    return ibis.memtable(df)


@pytest.fixture
def events_table() -> ibis.Table:
    df = pd.DataFrame(
        {
            "session_id": ["s1", "s1", "s2"],
            "event_type": ["cart", "purchase", "view"],
            "extracted_product_id": [100, 100, 101],
            "created_at": pd.to_datetime(
                ["2023-01-01 10:00:00", "2023-01-01 10:05:00", "2023-01-02 11:00:00"]
            ),
        }
    )
    return ibis.memtable(df)


@pytest.fixture
def orders_table() -> ibis.Table:
    df = pd.DataFrame({"order_id": [10, 11, 12, 13], "user_id": [1, 1, 2, 3]})
    return ibis.memtable(df)


def test_customer_rfm_ltv(users_table: ibis.Table, order_items_table: ibis.Table):
    result = customer_rfm_ltv(users_table, order_items_table).execute()

    assert not result.empty
    assert "customer_segment" in result.columns
    assert "rfm_score" in result.columns
    # O usuário 3 tem item 'Cancelled', não deve entrar no cálculo válido
    assert len(result) == 2


def test_cohort_retention(users_table: ibis.Table, order_items_table: ibis.Table):
    result = cohort_retention(users_table, order_items_table, month_limit=12).execute()

    assert not result.empty
    assert "retention_rate" in result.columns
    assert result["month_number"].max() <= 12


def test_product_360(
    mocker: MockerFixture,
    order_items_table: ibis.Table,
    products_table: ibis.Table,
    inventory_items_table: ibis.Table,
):
    # Usando pytest-mock para congelar ibis.now() e garantir aging determinístico
    mock_now = mocker.patch(
        "thelook_ecommerce_analysis.pipelines.data_metrics.metrics.product_360.ibis.now"
    )
    mock_now.return_value = ibis.literal("2023-05-01 00:00:00").cast("timestamp")

    result = product_360(
        order_items_table, products_table, inventory_items_table
    ).execute()

    assert not result.empty
    assert "avg_margin_pct" in result.columns
    assert "stock_qt" in result.columns

    prod1 = result[result["product_name"] == "Prod1"].iloc[0]
    assert prod1["return_rate_pct"] >= 0


def test_daily_sales_and_revenue(
    order_items_table: ibis.Table, products_table: ibis.Table, users_table: ibis.Table
):
    result = daily_sales_and_revenue(
        order_items_table, products_table, users_table, returns_cost=0.10
    ).execute()

    assert not result.empty
    assert "gross_profit_realistic" in result.columns
    assert "logistic_loss" in result.columns


def test_session_conversion(events_table: ibis.Table):
    result = session_conversion(events_table).execute()

    assert not result.empty
    assert "session_duration_bucket" in result.columns
    assert result["total_sessions"].sum() == 2


def test_traffic_source_performance(
    users_table: ibis.Table, orders_table: ibis.Table, order_items_table: ibis.Table
):
    result = traffic_source_performance(
        users_table, orders_table, order_items_table
    ).execute()

    assert not result.empty
    assert "Organic" in result["traffic_source"].to_numpy()
    assert "avg_ticket" in result.columns


def test_sales_funnel(events_table: ibis.Table):
    result = sales_funnel(events_table).execute()

    assert not result.empty
    assert "abandon_cart" in result.columns
    assert "drop_off" in result.columns
