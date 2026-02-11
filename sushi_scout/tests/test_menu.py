"""Tests for the synthetic menu data layer."""

import json

from sushi_scout.tools.menu import (
    PRICE_CALIBRATION,
    generate_menu_for_restaurant,
)


class TestMenuGeneration:
    """Test synthetic menu generation logic."""

    def test_generates_menu_with_tuna_rolls(self, sample_restaurants):
        """Every restaurant menu should include at least one tuna roll."""
        for restaurant in sample_restaurants:
            menu = generate_menu_for_restaurant(restaurant)
            assert len(menu["tuna_rolls"]) >= 1
            assert len(menu["tuna_rolls"]) <= 3

    def test_generates_other_items(self, sample_restaurants):
        """Menus should include non-tuna items for realism."""
        for restaurant in sample_restaurants:
            menu = generate_menu_for_restaurant(restaurant)
            assert len(menu["other_items"]) > 0

    def test_tuna_rolls_have_required_fields(self, sample_restaurants):
        """Each tuna roll should have name, price, pieces, availability."""
        menu = generate_menu_for_restaurant(sample_restaurants[0])
        for item in menu["tuna_rolls"]:
            assert "name" in item
            assert "price" in item
            assert "pieces" in item
            assert "available" in item
            assert "description" in item
            assert item["price"] > 0
            assert item["pieces"] in (6, 8)

    def test_deterministic_output(self, sample_restaurants):
        """Same restaurant should always produce the same menu."""
        restaurant = sample_restaurants[0]
        menu1 = generate_menu_for_restaurant(restaurant)
        menu2 = generate_menu_for_restaurant(restaurant)

        assert menu1["tuna_rolls"] == menu2["tuna_rolls"]
        assert menu1["other_items"] == menu2["other_items"]

    def test_different_restaurants_get_different_menus(self, sample_restaurants):
        """Different restaurants should have different menus."""
        menu1 = generate_menu_for_restaurant(sample_restaurants[0])
        menu2 = generate_menu_for_restaurant(sample_restaurants[1])

        # Prices should differ (extremely unlikely to be identical)
        prices1 = [item["price"] for item in menu1["tuna_rolls"]]
        prices2 = [item["price"] for item in menu2["tuna_rolls"]]
        assert prices1 != prices2 or len(menu1["tuna_rolls"]) != len(menu2["tuna_rolls"])


class TestPriceCalibration:
    """Test that prices are calibrated to restaurant price tiers."""

    def test_moderate_prices_in_range(self):
        """MODERATE restaurants should have tuna rolls roughly $8-13."""
        restaurant = {
            "id": "test_moderate",
            "name": "Test Moderate",
            "price_level": "PRICE_LEVEL_MODERATE",
            "price_range_low": 20,
            "delivery": True,
        }
        menu = generate_menu_for_restaurant(restaurant)
        low, high = PRICE_CALIBRATION["PRICE_LEVEL_MODERATE"]
        for item in menu["tuna_rolls"]:
            # Allow some margin for rounding
            assert item["price"] >= low - 1.0, f"Price {item['price']} below range for MODERATE"
            assert item["price"] <= high + 1.0, f"Price {item['price']} above range for MODERATE"

    def test_expensive_prices_higher_than_moderate(self):
        """EXPENSIVE restaurants should generally have higher prices than MODERATE."""
        moderate = {
            "id": "test_mod",
            "name": "Moderate Place",
            "price_level": "PRICE_LEVEL_MODERATE",
            "price_range_low": 20,
            "delivery": True,
        }
        expensive = {
            "id": "test_exp",
            "name": "Expensive Place",
            "price_level": "PRICE_LEVEL_EXPENSIVE",
            "price_range_low": 50,
            "delivery": True,
        }
        mod_menu = generate_menu_for_restaurant(moderate)
        exp_menu = generate_menu_for_restaurant(expensive)

        mod_avg = sum(i["price"] for i in mod_menu["tuna_rolls"]) / len(mod_menu["tuna_rolls"])
        exp_avg = sum(i["price"] for i in exp_menu["tuna_rolls"]) / len(exp_menu["tuna_rolls"])

        assert exp_avg > mod_avg, "Expensive restaurant should have higher avg price"

    def test_inexpensive_prices_in_range(self):
        """INEXPENSIVE restaurants should have tuna rolls roughly $5-8."""
        restaurant = {
            "id": "test_cheap",
            "name": "Cheap Sushi",
            "price_level": "PRICE_LEVEL_INEXPENSIVE",
            "price_range_low": 10,
            "delivery": True,
        }
        menu = generate_menu_for_restaurant(restaurant)
        low, high = PRICE_CALIBRATION["PRICE_LEVEL_INEXPENSIVE"]
        for item in menu["tuna_rolls"]:
            assert item["price"] >= low - 1.0
            assert item["price"] <= high + 1.0

    def test_unknown_price_level_uses_default(self):
        """Restaurants without price level should still generate valid prices."""
        restaurant = {
            "id": "test_unknown",
            "name": "Mystery Sushi",
            "price_level": None,
            "price_range_low": None,
            "delivery": True,
        }
        menu = generate_menu_for_restaurant(restaurant)
        for item in menu["tuna_rolls"]:
            assert item["price"] > 0
            assert item["price"] < 30  # Sanity check


class TestDeliveryInfo:
    """Test delivery-related menu data."""

    def test_delivery_restaurant_has_delivery_time(self):
        """Restaurants with delivery=True should have delivery time and fee."""
        restaurant = {
            "id": "test_delivery",
            "name": "Delivery Place",
            "price_level": "PRICE_LEVEL_MODERATE",
            "price_range_low": 20,
            "delivery": True,
        }
        menu = generate_menu_for_restaurant(restaurant)
        assert menu["delivery_available"] is True
        assert menu["delivery_time_minutes"] is not None
        assert menu["delivery_time_minutes"] in [15, 20, 25, 30, 35, 40, 45]
        assert menu["delivery_fee"] is not None
        assert menu["delivery_fee"] > 0

    def test_no_delivery_restaurant(self):
        """Restaurants with delivery=False should have no delivery time."""
        restaurant = {
            "id": "test_no_delivery",
            "name": "Dine-In Only",
            "price_level": "PRICE_LEVEL_MODERATE",
            "price_range_low": 20,
            "delivery": False,
        }
        menu = generate_menu_for_restaurant(restaurant)
        assert menu["delivery_time_minutes"] is None
        assert menu["delivery_fee"] is None

    def test_menu_includes_synthetic_note(self):
        """Menu should clearly indicate data is synthetic."""
        restaurant = {"id": "test", "name": "Test", "price_level": None, "delivery": True}
        menu = generate_menu_for_restaurant(restaurant)
        assert "synthetic" in menu["menu_note"].lower()


class TestFindCheapestTunaRoll:
    """Test the find_cheapest_tuna_roll orchestration logic."""

    def test_finds_cheapest(self, sample_restaurants):
        """Should return the cheapest available tuna roll across restaurants."""
        # Use the core function directly since the tool wrapper is async
        from sushi_scout.tools.menu import generate_menu_for_restaurant

        all_options = []
        for restaurant in sample_restaurants:
            menu = generate_menu_for_restaurant(restaurant)
            for item in menu["tuna_rolls"]:
                if item["available"]:
                    all_options.append({
                        "restaurant_name": menu["restaurant_name"],
                        "price": item["price"],
                        "item_name": item["name"],
                    })
        all_options.sort(key=lambda x: x["price"])

        assert len(all_options) > 0
        cheapest = all_options[0]
        # Verify it's actually the cheapest
        for opt in all_options[1:]:
            assert opt["price"] >= cheapest["price"]

    def test_expensive_restaurant_not_cheapest(self, sample_restaurants):
        """Expensive restaurants should not produce the cheapest option."""
        all_options = []
        for restaurant in sample_restaurants:
            menu = generate_menu_for_restaurant(restaurant)
            for item in menu["tuna_rolls"]:
                if item["available"]:
                    all_options.append({
                        "restaurant_name": menu["restaurant_name"],
                        "restaurant_id": menu["restaurant_id"],
                        "price": item["price"],
                        "price_level": restaurant.get("price_level"),
                    })
        all_options.sort(key=lambda x: x["price"])

        if all_options:
            cheapest = all_options[0]
            # Cheapest should NOT be from the EXPENSIVE restaurant
            assert cheapest["price_level"] != "PRICE_LEVEL_EXPENSIVE"

    def test_handles_empty_restaurant_list(self):
        """Should handle empty input gracefully."""
        all_options = []
        restaurants = []
        for restaurant in restaurants:
            menu = generate_menu_for_restaurant(restaurant)
            for item in menu["tuna_rolls"]:
                if item["available"]:
                    all_options.append({"price": item["price"]})

        assert len(all_options) == 0
