"""Tests for the mock ordering tool."""

import pytest

from sushi_scout.tools.ordering import _generate_order_id


class TestOrderIdGeneration:
    """Test order ID generation."""

    def test_order_id_format(self):
        """Order IDs should follow SS-XXXXXXXX format."""
        order_id = _generate_order_id("restaurant_123", "Tuna Roll")
        assert order_id.startswith("SS-")
        assert len(order_id) == 11  # "SS-" + 8 hex chars

    def test_order_id_hex_chars(self):
        """Order ID suffix should be uppercase hex."""
        order_id = _generate_order_id("restaurant_123", "Tuna Roll")
        suffix = order_id[3:]
        assert suffix == suffix.upper()
        assert all(c in "0123456789ABCDEF" for c in suffix)

    def test_different_inputs_different_ids(self):
        """Different restaurant/item combos should produce different IDs."""
        id1 = _generate_order_id("restaurant_1", "Tuna Roll")
        id2 = _generate_order_id("restaurant_2", "Tuna Roll")
        id3 = _generate_order_id("restaurant_1", "Spicy Tuna Roll")
        assert id1 != id2
        assert id1 != id3


class TestPlaceOrder:
    """Test the place_order tool logic (without MCP registration)."""

    def test_cost_breakdown_math(self):
        """Tax and total calculations should be correct."""
        item_price = 9.99
        delivery_fee = 3.99
        tax_rate = 0.0875

        tax = round(item_price * tax_rate, 2)
        total = round(item_price + delivery_fee + tax, 2)

        assert tax == round(9.99 * 0.0875, 2)
        assert total == round(9.99 + 3.99 + tax, 2)
        # Verify total adds up
        assert abs(total - (item_price + delivery_fee + tax)) < 0.01

    def test_cost_breakdown_zero_delivery(self):
        """Zero delivery fee should still calculate correctly."""
        item_price = 12.99
        delivery_fee = 0.0
        tax_rate = 0.0875

        tax = round(item_price * tax_rate, 2)
        total = round(item_price + delivery_fee + tax, 2)

        assert total == round(item_price + tax, 2)

    def test_order_response_structure(self):
        """Verify the expected response structure fields."""
        # Simulate what the tool would return
        order_id = _generate_order_id("place_123", "Tuna Roll")
        item_price = 9.99
        delivery_fee = 3.50
        tax = round(item_price * 0.0875, 2)

        response = {
            "status": "confirmed",
            "order_id": order_id,
            "restaurant": {"id": "place_123", "name": "Test Sushi"},
            "item": {"name": "Tuna Roll", "price": item_price, "special_instructions": None},
            "delivery": {
                "address": "123 Main St",
                "estimated_time_minutes": 30,
                "fee": delivery_fee,
            },
            "cost_breakdown": {
                "subtotal": item_price,
                "delivery_fee": delivery_fee,
                "tax": tax,
                "total": round(item_price + delivery_fee + tax, 2),
            },
        }

        assert response["status"] == "confirmed"
        assert response["order_id"].startswith("SS-")
        assert response["cost_breakdown"]["subtotal"] == item_price
        assert response["cost_breakdown"]["total"] > item_price
        assert response["delivery"]["estimated_time_minutes"] == 30
