import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import tools


def test_execute_search_products():
    result = tools.execute_tool("search_products", {"keyword": "honey", "is_organic": True})
    assert len(result["products"]) >= 4
    assert all(p["is_organic"] == 1 for p in result["products"])


def test_execute_get_rating():
    result = tools.execute_tool("get_rating", {"product_id": 1})
    assert result["product_id"] == 1
    assert result["average_rating"] > 0
    assert result["review_count"] > 0


def test_execute_get_order_history_empty_or_list():
    result = tools.execute_tool("get_order_history", {})
    assert "orders" in result
    assert isinstance(result["orders"], list)


def test_execute_checkout_places_order():
    result = tools.execute_tool("checkout", {"product_id": 32})
    assert result["order_id"] is not None
    assert result["product_name"] == "Soy Milk"


def test_execute_save_preference():
    result = tools.execute_tool("save_preference", {"key": "organic_only", "value": True})
    assert result["preferences"]["organic_only"] is True


def test_unknown_tool_raises():
    with pytest.raises(ValueError):
        tools.execute_tool("not_a_real_tool", {})
