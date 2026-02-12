#!/usr/bin/env python3
"""Sushi Scout Agent - CLI demo of the sushi-scout MCP toolkit.

This agent demonstrates the full sushi-scout workflow using our tools directly:
1. Search for nearby sushi restaurants (simulated or real)
2. Generate menus with tuna roll prices (calibrated to real price tiers)
3. Find the cheapest tuna roll across all results
4. Optionally place a simulated order

For the full MCP experience with Google OAuth:
    arcade mcp -p sushi_scout http --debug

Then connect via Claude Desktop, Cursor, or any MCP client.

Usage:
    # Demo mode (sample data, no API key needed - shows the full workflow)
    uv run python -m sushi_scout --demo
    uv run python -m sushi_scout --demo --order

    # Live mode (requires GOOGLE_PLACES_API_KEY in .env for testing without OAuth)
    uv run python -m sushi_scout --lat 37.7749 --lng -122.4194 --radius 2.0
"""

import argparse
import os
import sys
from typing import Any

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sushi_scout.tools.menu import generate_menu_for_restaurant
from sushi_scout.tools.ordering import _generate_order_id
from sushi_scout.tools.search import (
    PLACES_BASE_URL,
    SEARCH_FIELDS,
    _format_restaurant,
    _miles_to_meters,
)


# -- Sample data for demo mode --

DEMO_RESTAURANTS = [
    {
        "id": "demo_sf_sushi_1",
        "name": "Tokyo Express",
        "address": "123 Market St, San Francisco, CA",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "rating": 4.2,
        "review_count": 450,
        "price_level": "PRICE_LEVEL_INEXPENSIVE",
        "price_range_low": 12,
        "price_range_high": 20,
        "delivery": True,
        "types": ["sushi_restaurant", "japanese_restaurant"],
    },
    {
        "id": "demo_sf_sushi_2",
        "name": "Sushi Palace",
        "address": "456 Geary St, San Francisco, CA",
        "latitude": 37.7864,
        "longitude": -122.4134,
        "rating": 4.5,
        "review_count": 820,
        "price_level": "PRICE_LEVEL_MODERATE",
        "price_range_low": 20,
        "price_range_high": 35,
        "delivery": True,
        "types": ["sushi_restaurant", "japanese_restaurant"],
    },
    {
        "id": "demo_sf_sushi_3",
        "name": "Zen Omakase",
        "address": "789 Mission St, San Francisco, CA",
        "latitude": 37.7853,
        "longitude": -122.4000,
        "rating": 4.8,
        "review_count": 1200,
        "price_level": "PRICE_LEVEL_EXPENSIVE",
        "price_range_low": 60,
        "price_range_high": 120,
        "delivery": False,
        "types": ["sushi_restaurant", "japanese_restaurant"],
    },
    {
        "id": "demo_sf_sushi_4",
        "name": "Roll House",
        "address": "321 Valencia St, San Francisco, CA",
        "latitude": 37.7685,
        "longitude": -122.4218,
        "rating": 4.0,
        "review_count": 290,
        "price_level": "PRICE_LEVEL_INEXPENSIVE",
        "price_range_low": 10,
        "price_range_high": 18,
        "delivery": True,
        "types": ["sushi_restaurant"],
    },
    {
        "id": "demo_sf_sushi_5",
        "name": "Sakura Garden",
        "address": "555 Hayes St, San Francisco, CA",
        "latitude": 37.7763,
        "longitude": -122.4246,
        "rating": 4.3,
        "review_count": 650,
        "price_level": "PRICE_LEVEL_MODERATE",
        "price_range_low": 22,
        "price_range_high": 30,
        "delivery": True,
        "types": ["japanese_restaurant", "sushi_restaurant"],
    },
]


# -- Display helpers --


def print_header():
    print()
    print("=" * 60)
    print("  SUSHI SCOUT - Find the Cheapest Tuna Roll Nearby")
    print("=" * 60)
    print()


def print_restaurants(restaurants: list[dict[str, Any]]):
    print(f"Found {len(restaurants)} sushi restaurants:\n")
    for i, r in enumerate(restaurants, 1):
        delivery = "delivers" if r.get("delivery") else "no delivery"
        rating = r.get("rating", "N/A")
        price = r.get("price_level") or "N/A"
        if price != "N/A":
            price = price.replace("PRICE_LEVEL_", "").lower()
        print(f"  {i}. {r['name']:<30} rating={rating}  {price:<15} {delivery}")
    print()


def print_tuna_options(all_options: list[dict[str, Any]]):
    print(f"Found {len(all_options)} available tuna rolls:\n")
    print(f"  {'#':<4} {'Restaurant':<25} {'Item':<22} {'Price':>7} {'Delivery':>10} {'Total':>8}")
    print(f"  {'-'*4} {'-'*25} {'-'*22} {'-'*7} {'-'*10} {'-'*8}")
    for i, opt in enumerate(all_options, 1):
        delivery = f"${opt['delivery_fee']:.2f}" if opt["delivery_fee"] else "N/A"
        total = f"${opt['total_with_delivery']:.2f}" if opt["delivery_available"] else "N/A"
        print(
            f"  {i:<4} {opt['restaurant_name']:<25} "
            f"{opt['item_name']:<22} "
            f"${opt['price']:>6.2f} "
            f"{delivery:>10} "
            f"{total:>8}"
        )
    print()


def print_winner(cheapest: dict[str, Any]):
    print("=" * 60)
    print("  CHEAPEST TUNA ROLL FOUND!")
    print("=" * 60)
    print()
    print(f"  Restaurant:  {cheapest['restaurant_name']}")
    print(f"  Item:        {cheapest['item_name']}")
    print(f"  Price:       ${cheapest['price']:.2f}")
    print(f"  Pieces:      {cheapest['pieces']}")
    print(f"  Per piece:   ${cheapest['price_per_piece']:.2f}")
    if cheapest["delivery_available"] and cheapest.get("delivery_fee") is not None:
        print(f"  Delivery:    ${cheapest['delivery_fee']:.2f} fee, ~{cheapest['delivery_time_minutes']} min")
        print(f"  Total:       ${cheapest['total_with_delivery']:.2f} (with delivery)")
    else:
        print("  Delivery:    Not available (dine-in/pickup only)")
    print()


def simulate_order(cheapest: dict[str, Any], delivery_address: str):
    order_id = _generate_order_id(cheapest["restaurant_id"], cheapest["item_name"])
    tax = round(cheapest["price"] * 0.0875, 2)
    delivery_fee = cheapest["delivery_fee"] or 0
    total = round(cheapest["price"] + delivery_fee + tax, 2)

    print("=" * 60)
    print("  ORDER CONFIRMED (Simulated)")
    print("=" * 60)
    print()
    print(f"  Order ID:      {order_id}")
    print(f"  Restaurant:    {cheapest['restaurant_name']}")
    print(f"  Item:          {cheapest['item_name']}")
    print(f"  Subtotal:      ${cheapest['price']:.2f}")
    print(f"  Delivery fee:  ${delivery_fee:.2f}")
    print(f"  Tax:           ${tax:.2f}")
    print(f"  Total:         ${total:.2f}")
    print(f"  Deliver to:    {delivery_address}")
    print(f"  Est. delivery: ~{cheapest.get('delivery_time_minutes') or 30} minutes")
    print()
    print("  Note: This is a simulated order. No real order was placed.")
    print()


# -- Core workflow --


def find_all_tuna_options(restaurants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate menus for all restaurants and collect available tuna rolls."""
    all_options = []
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
                "total_with_delivery": round(item["price"] + (menu["delivery_fee"] or 0), 2),
            })
    all_options.sort(key=lambda x: x["price"])
    return all_options


async def search_live(latitude: float, longitude: float, radius_miles: float):
    """Search using Google Places API with API key (testing fallback)."""
    import httpx

    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        print("[ERROR] For live mode, set GOOGLE_PLACES_API_KEY in environment or .env")
        print()
        print("For the full OAuth experience, run the MCP server instead:")
        print("  cd sushi_scout && uv run arcade mcp -p sushi_scout http --debug")
        print()
        print("Or try demo mode: uv run python -m sushi_scout --demo")
        return None

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": ",".join(SEARCH_FIELDS),
    }
    payload = {
        "includedTypes": ["japanese_restaurant", "sushi_restaurant"],
        "maxResultCount": 10,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": _miles_to_meters(radius_miles),
            }
        },
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{PLACES_BASE_URL}:searchNearby", json=payload, headers=headers
        )
        response.raise_for_status()
        data = response.json()

    places = data.get("places", [])
    return [_format_restaurant(p, i) for i, p in enumerate(places)]


def run_workflow(restaurants: list[dict[str, Any]], order: bool = False, address: str = ""):
    """Execute the full sushi scout workflow."""
    # Step 1: Show restaurants
    print("STEP 1: Restaurant Discovery")
    print("-" * 40)
    print_restaurants(restaurants)

    # Step 2: Menu analysis
    print("STEP 2: Menu Analysis & Price Comparison")
    print("-" * 40)
    all_options = find_all_tuna_options(restaurants)
    print_tuna_options(all_options)

    # Step 3: Winner
    if not all_options:
        print("No available tuna rolls found. Try expanding your search radius.")
        return

    cheapest = all_options[0]
    print_winner(cheapest)

    # Step 4: Order
    if order:
        delivery_address = address or "123 Main St, San Francisco, CA 94102"
        if cheapest["delivery_available"]:
            simulate_order(cheapest, delivery_address)
        else:
            print("Cheapest option doesn't deliver. Checking next best...\n")
            for opt in all_options[1:]:
                if opt["delivery_available"]:
                    print(f"  Next cheapest with delivery: {opt['item_name']} "
                          f"at {opt['restaurant_name']} - ${opt['price']:.2f}\n")
                    simulate_order(opt, delivery_address)
                    return
            print("  No delivery options available in this area.")


def main():
    parser = argparse.ArgumentParser(
        description="Sushi Scout - Find the cheapest tuna roll nearby",
        epilog=(
            "For the full OAuth MCP experience:\n"
            "  cd sushi_scout && uv run arcade mcp -p sushi_scout http --debug\n"
            "Then connect via Claude Desktop, Cursor, or any MCP client."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Run with sample data (no API key or OAuth needed)",
    )
    parser.add_argument("--lat", type=float, default=37.7749, help="Latitude (default: SF)")
    parser.add_argument("--lng", type=float, default=-122.4194, help="Longitude (default: SF)")
    parser.add_argument("--radius", type=float, default=2.0, help="Search radius in miles")
    parser.add_argument("--order", action="store_true", help="Simulate placing an order")
    parser.add_argument("--address", type=str, default="", help="Delivery address")
    args = parser.parse_args()

    print_header()

    if args.demo:
        print("Running in DEMO mode (sample data, no API calls)\n")
        restaurants = DEMO_RESTAURANTS
    else:
        import asyncio

        print(f"Searching near ({args.lat}, {args.lng}), radius {args.radius} miles...")
        print("(Using API key fallback. For OAuth, run via: arcade mcp -p sushi_scout http)\n")
        restaurants = asyncio.run(search_live(args.lat, args.lng, args.radius))
        if not restaurants:
            return

    run_workflow(restaurants, order=args.order, address=args.address)


if __name__ == "__main__":
    main()
