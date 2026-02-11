"""Mock ordering tool - simulates placing a delivery order."""

import hashlib
import time
from typing import Annotated



def _generate_order_id(restaurant_id: str, item_name: str) -> str:
    """Generate a deterministic order ID."""
    raw = f"{restaurant_id}:{item_name}:{int(time.time() / 60)}"
    return "SS-" + hashlib.md5(raw.encode()).hexdigest()[:8].upper()


def register_tools(app):
    """Register ordering tools with the MCP app."""

    @app.tool
    async def place_order(
        restaurant_id: Annotated[str, "Google Places ID of the restaurant"],
        restaurant_name: Annotated[str, "Name of the restaurant"],
        item_name: Annotated[str, "Name of the menu item to order"],
        item_price: Annotated[float, "Price of the item"],
        delivery_address: Annotated[str, "Delivery address for the order"],
        delivery_fee: Annotated[float, "Delivery fee"] = 0.0,
        special_instructions: Annotated[str, "Special instructions for the order"] = "",
    ) -> Annotated[dict, "Order confirmation with estimated delivery time"]:
        """Place a simulated delivery order for a menu item.

        This is a mock implementation that returns a realistic order confirmation.
        In production, this would integrate with a delivery platform API.

        Returns order ID, estimated delivery time, and cost breakdown.
        """
        order_id = _generate_order_id(restaurant_id, item_name)
        tax_rate = 0.0875  # SF tax rate
        tax = round(item_price * tax_rate, 2)
        total = round(item_price + delivery_fee + tax, 2)

        return {
            "status": "confirmed",
            "order_id": order_id,
            "restaurant": {
                "id": restaurant_id,
                "name": restaurant_name,
            },
            "item": {
                "name": item_name,
                "price": item_price,
                "special_instructions": special_instructions or None,
            },
            "delivery": {
                "address": delivery_address,
                "estimated_time_minutes": 30,
                "fee": delivery_fee,
            },
            "cost_breakdown": {
                "subtotal": item_price,
                "delivery_fee": delivery_fee,
                "tax": tax,
                "total": total,
            },
            "note": "This is a simulated order. No real order has been placed.",
        }

    @app.tool
    async def check_order_status(
        order_id: Annotated[str, "Order ID from place_order confirmation"],
    ) -> Annotated[dict, "Current status of the order"]:
        """Check the status of a simulated order.

        Returns mock status updates based on a typical delivery timeline.
        """
        return {
            "order_id": order_id,
            "status": "preparing",
            "timeline": [
                {"status": "confirmed", "time": "0 min ago", "complete": True},
                {"status": "preparing", "time": "now", "complete": True},
                {"status": "picked_up", "time": "~10 min", "complete": False},
                {"status": "delivered", "time": "~25 min", "complete": False},
            ],
            "estimated_delivery": "25-35 minutes",
            "note": "This is a simulated order status.",
        }
