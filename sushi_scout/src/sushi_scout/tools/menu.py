"""Synthetic menu data layer - generates realistic sushi menus calibrated to real price data."""

import hashlib
import json
import random
from typing import Annotated, Any

from arcade_mcp_server import tool


# Price calibration based on Google Places priceLevel
# Maps restaurant price tier to realistic tuna roll price ranges
PRICE_CALIBRATION = {
    "PRICE_LEVEL_FREE": (4.00, 6.00),
    "PRICE_LEVEL_INEXPENSIVE": (5.00, 8.00),
    "PRICE_LEVEL_MODERATE": (8.00, 13.00),
    "PRICE_LEVEL_EXPENSIVE": (14.00, 20.00),
    "PRICE_LEVEL_VERY_EXPENSIVE": (18.00, 28.00),
}
DEFAULT_PRICE_RANGE = (8.00, 14.00)

# Tuna roll variants that a sushi restaurant might offer
TUNA_ROLL_VARIANTS = [
    {"name": "Tuna Roll", "description": "Classic tuna roll with sushi rice and nori", "pieces": 6},
    {
        "name": "Spicy Tuna Roll",
        "description": "Tuna with spicy mayo, cucumber, and sesame seeds",
        "pieces": 8,
    },
    {
        "name": "Tuna Avocado Roll",
        "description": "Fresh tuna with avocado and sushi rice",
        "pieces": 8,
    },
]

# Additional menu items for realism
OTHER_SUSHI_ITEMS = [
    {"name": "California Roll", "category": "rolls"},
    {"name": "Salmon Roll", "category": "rolls"},
    {"name": "Rainbow Roll", "category": "specialty_rolls"},
    {"name": "Dragon Roll", "category": "specialty_rolls"},
    {"name": "Edamame", "category": "appetizers"},
    {"name": "Miso Soup", "category": "soup"},
]


def _seed_rng(place_id: str, variant_name: str) -> random.Random:
    """Create a seeded RNG for deterministic menu generation per restaurant+item."""
    seed = hashlib.md5(f"{place_id}:{variant_name}".encode()).hexdigest()
    return random.Random(seed)


def _generate_tuna_price(
    rng: random.Random, price_level: str | None, price_range_low: int | None
) -> float:
    """Generate a realistic tuna roll price based on restaurant's price tier."""
    low, high = PRICE_CALIBRATION.get(price_level or "", DEFAULT_PRICE_RANGE)

    # If we have a real price range from Google, use it to refine
    if price_range_low and price_range_low > 0:
        # Tuna roll is typically 30-50% of the per-person meal cost
        estimated_low = price_range_low * 0.30
        estimated_high = price_range_low * 0.55
        low = max(low, estimated_low)
        high = min(high, estimated_high) if estimated_high > low else high

    price = rng.uniform(low, high)
    # Round to nearest .49 or .99 (common restaurant pricing)
    return round(round(price * 2) / 2 - 0.01, 2)


def _generate_delivery_time(rng: random.Random) -> int:
    """Generate estimated delivery time in minutes."""
    return rng.choice([15, 20, 25, 30, 35, 40, 45])


def generate_menu_for_restaurant(restaurant: dict[str, Any]) -> dict[str, Any]:
    """Generate a synthetic menu for a restaurant based on its real metadata.

    Uses the restaurant's place_id as a seed for deterministic output,
    and calibrates prices to the restaurant's actual priceLevel/priceRange.
    """
    place_id = restaurant.get("id", "unknown")
    price_level = restaurant.get("price_level")
    price_range_low = restaurant.get("price_range_low")
    name = restaurant.get("name", "Unknown Restaurant")
    delivery = restaurant.get("delivery")

    base_rng = _seed_rng(place_id, "base")

    # Determine which tuna roll variants this restaurant offers (1-3)
    num_variants = base_rng.randint(1, len(TUNA_ROLL_VARIANTS))
    offered_variants = base_rng.sample(TUNA_ROLL_VARIANTS, num_variants)

    tuna_items = []
    for variant in offered_variants:
        rng = _seed_rng(place_id, variant["name"])
        price = _generate_tuna_price(rng, price_level, price_range_low)
        available = rng.random() > 0.1  # 90% chance available

        tuna_items.append({
            "name": variant["name"],
            "description": variant["description"],
            "price": price,
            "pieces": variant["pieces"],
            "available": available,
            "category": "tuna_rolls",
        })

    # Generate a few other items for realism
    other_items = []
    for item in OTHER_SUSHI_ITEMS:
        rng = _seed_rng(place_id, item["name"])
        base_price = _generate_tuna_price(rng, price_level, price_range_low)
        # Vary price relative to tuna
        multiplier = rng.uniform(0.6, 1.4)
        price = round(base_price * multiplier * 2) / 2 - 0.01

        other_items.append({
            "name": item["name"],
            "price": round(price, 2),
            "category": item["category"],
            "available": rng.random() > 0.05,
        })

    delivers = delivery if delivery is not None else base_rng.random() > 0.3
    delivery_time = _generate_delivery_time(base_rng) if delivers else None

    return {
        "restaurant_id": place_id,
        "restaurant_name": name,
        "delivery_available": delivers,
        "delivery_time_minutes": delivery_time,
        "delivery_fee": round(base_rng.uniform(1.99, 5.99), 2) if delivers else None,
        "tuna_rolls": tuna_items,
        "other_items": other_items,
        "menu_note": "Menu data is synthetic, calibrated to restaurant price tier",
    }


@tool
async def get_restaurant_menu(
    restaurant_id: Annotated[str, "Google Places ID of the restaurant"],
    restaurant_name: Annotated[str, "Name of the restaurant"] = "",
    price_level: Annotated[str | None, "Price level from search results"] = None,
    price_range_low: Annotated[int | None, "Low end of price range in dollars"] = None,
    delivery: Annotated[bool | None, "Whether restaurant offers delivery"] = None,
) -> Annotated[dict, "Restaurant menu with tuna roll options and prices"]:
    """Get the menu for a restaurant, including tuna roll options with prices.

    Menu data is synthetically generated but calibrated to the restaurant's
    real price tier from Google Places. Prices are deterministic per restaurant.
    """
    restaurant = {
        "id": restaurant_id,
        "name": restaurant_name,
        "price_level": price_level,
        "price_range_low": price_range_low,
        "delivery": delivery,
    }
    return generate_menu_for_restaurant(restaurant)


@tool
async def find_cheapest_tuna_roll(
    restaurants_json: Annotated[
        str,
        "JSON string of restaurant list from search_nearby_restaurants "
        "(the 'restaurants' array from the response)",
    ],
) -> Annotated[dict, "Ranked list of cheapest tuna rolls across all restaurants"]:
    """Find the cheapest tuna roll across multiple restaurants.

    Takes the restaurant list from search_nearby_restaurants and generates
    menus for each, then ranks all available tuna rolls by price.

    Returns the cheapest options with restaurant details and delivery info.
    """
    try:
        restaurants = json.loads(restaurants_json)
    except (json.JSONDecodeError, TypeError):
        return {"error": "Invalid JSON. Pass the 'restaurants' array as a JSON string."}

    all_options: list[dict[str, Any]] = []

    for restaurant in restaurants:
        menu = generate_menu_for_restaurant(restaurant)

        for item in menu["tuna_rolls"]:
            if not item["available"]:
                continue

            all_options.append({
                "restaurant_name": menu["restaurant_name"],
                "restaurant_id": menu["restaurant_id"],
                "item_name": item["name"],
                "price": item["price"],
                "pieces": item["pieces"],
                "price_per_piece": round(item["price"] / item["pieces"], 2),
                "delivery_available": menu["delivery_available"],
                "delivery_time_minutes": menu["delivery_time_minutes"],
                "delivery_fee": menu["delivery_fee"],
                "total_with_delivery": round(
                    item["price"] + (menu["delivery_fee"] or 0), 2
                ),
            })

    # Sort by price (cheapest first)
    all_options.sort(key=lambda x: x["price"])

    cheapest = all_options[0] if all_options else None

    return {
        "cheapest": cheapest,
        "all_options": all_options,
        "total_restaurants_checked": len(restaurants),
        "total_options_found": len(all_options),
        "note": "Prices are synthetic but calibrated to each restaurant's real price tier",
    }
