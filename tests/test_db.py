import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import db


def test_search_products_by_keyword():
    results = db.search_products("honey")
    # 8 honey-category products, plus Organic Granola (honey in its description)
    assert len(results) == 9
    assert all("honey" in r["category"] or "honey" in r["description"].lower() for r in results)


def test_search_products_with_max_price():
    results = db.search_products("honey", max_price=15.00)
    names = {r["name"] for r in results}
    assert "Organic Manuka Honey" not in names
    assert all(r["price"] <= 15.00 for r in results)


def test_search_products_organic_only():
    results = db.search_products("honey", is_organic=True)
    assert all(r["is_organic"] == 1 for r in results)
    # 4 organic honeys, plus Organic Granola (honey in its description, also organic)
    assert len(results) == 5


def test_search_products_no_match():
    assert db.search_products("bicycle") == []


def test_get_product_found():
    product = db.get_product(1)
    assert product["name"] == "Organic Raw Honey"


def test_get_product_not_found():
    assert db.get_product(9999) is None


def test_place_order_and_get_orders():
    order = db.place_order(30)
    assert order["product_id"] == 30
    assert order["product_name"] == "Oat Milk"
    assert order["price"] == 4.49
    assert "id" in order and "ordered_at" in order

    orders = db.get_orders()
    assert any(o["id"] == order["id"] for o in orders)
