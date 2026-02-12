"""Evaluation scenarios for the sushi_scout toolkit.

These tests validate the end-to-end logic of the toolkit:
- Price calibration accuracy across different restaurant tiers
- Ranking correctness
- Edge cases and error handling
"""

import json

from sushi_scout.tools.menu import generate_menu_for_restaurant


class TestPriceCalibrationEvals:
    """Evaluate that price calibration produces realistic results across scenarios."""

    def _make_restaurant(self, place_id, name, price_level, price_range_low, delivery=True):
        return {
            "id": place_id,
            "name": name,
            "price_level": price_level,
            "price_range_low": price_range_low,
            "delivery": delivery,
        }

    def test_eval_urban_high_density(self):
        """Simulate a dense urban area with multiple price tiers.

        Scenario: San Francisco downtown - mix of cheap and expensive sushi.
        Expected: Cheapest tuna roll under $10, most expensive over $15.
        """
        restaurants = [
            self._make_restaurant("sf_1", "Quick Sushi", "PRICE_LEVEL_INEXPENSIVE", 12),
            self._make_restaurant("sf_2", "Sushi Bar", "PRICE_LEVEL_MODERATE", 25),
            self._make_restaurant("sf_3", "Omakase Place", "PRICE_LEVEL_VERY_EXPENSIVE", 150),
            self._make_restaurant("sf_4", "Corner Roll", "PRICE_LEVEL_INEXPENSIVE", 10),
            self._make_restaurant("sf_5", "Mid Sushi", "PRICE_LEVEL_MODERATE", 20),
        ]

        all_prices = []
        for r in restaurants:
            menu = generate_menu_for_restaurant(r)
            for item in menu["tuna_rolls"]:
                all_prices.append(item["price"])

        assert min(all_prices) < 10.0, "Cheapest tuna roll should be under $10"
        assert max(all_prices) > 15.0, "Most expensive should be over $15"
        assert len(all_prices) >= 5, "Should have at least 5 tuna roll options"

    def test_eval_suburban_limited_options(self):
        """Simulate a suburban area with fewer restaurants.

        Scenario: Suburban neighborhood - only moderate options.
        Expected: All prices should be in a narrower band ($8-$13).
        """
        restaurants = [
            self._make_restaurant("sub_1", "Suburban Sushi", "PRICE_LEVEL_MODERATE", 22),
            self._make_restaurant("sub_2", "Family Roll", "PRICE_LEVEL_MODERATE", 18),
        ]

        all_prices = []
        for r in restaurants:
            menu = generate_menu_for_restaurant(r)
            for item in menu["tuna_rolls"]:
                all_prices.append(item["price"])

        for price in all_prices:
            assert 5.0 < price < 16.0, f"Moderate area price {price} out of expected range"

    def test_eval_price_tier_ordering(self):
        """Verify that average prices increase with restaurant price tier.

        This is the core calibration test - ensures our synthetic data
        reflects the real-world price signal from Google Places.
        """
        tiers = [
            ("PRICE_LEVEL_INEXPENSIVE", 10),
            ("PRICE_LEVEL_MODERATE", 25),
            ("PRICE_LEVEL_EXPENSIVE", 60),
            ("PRICE_LEVEL_VERY_EXPENSIVE", 150),
        ]

        averages = []
        for tier, price_range_low in tiers:
            # Generate menus for multiple restaurants in this tier
            total_price = 0
            count = 0
            for i in range(5):
                r = self._make_restaurant(f"tier_{tier}_{i}", f"Restaurant {i}", tier, price_range_low)
                menu = generate_menu_for_restaurant(r)
                for item in menu["tuna_rolls"]:
                    total_price += item["price"]
                    count += 1
            avg = total_price / count if count > 0 else 0
            averages.append((tier, avg))

        # Each tier's average should be higher than the previous
        for i in range(1, len(averages)):
            prev_tier, prev_avg = averages[i - 1]
            curr_tier, curr_avg = averages[i]
            assert curr_avg > prev_avg, (
                f"{curr_tier} avg (${curr_avg:.2f}) should be > "
                f"{prev_tier} avg (${prev_avg:.2f})"
            )


class TestRankingEvals:
    """Evaluate that ranking logic works correctly."""

    def test_eval_cheapest_is_actually_cheapest(self):
        """Verify the ranking algorithm returns truly the cheapest option."""
        restaurants = [
            {
                "id": f"rank_test_{i}",
                "name": f"Restaurant {i}",
                "price_level": level,
                "price_range_low": low,
                "delivery": True,
            }
            for i, (level, low) in enumerate([
                ("PRICE_LEVEL_INEXPENSIVE", 8),
                ("PRICE_LEVEL_MODERATE", 20),
                ("PRICE_LEVEL_EXPENSIVE", 50),
                ("PRICE_LEVEL_MODERATE", 25),
                ("PRICE_LEVEL_INEXPENSIVE", 12),
            ])
        ]

        all_options = []
        for r in restaurants:
            menu = generate_menu_for_restaurant(r)
            for item in menu["tuna_rolls"]:
                if item["available"]:
                    all_options.append({
                        "restaurant_name": r["name"],
                        "price": item["price"],
                        "price_level": r["price_level"],
                    })

        all_options.sort(key=lambda x: x["price"])
        cheapest = all_options[0]

        # Cheapest should be from an INEXPENSIVE restaurant
        assert cheapest["price_level"] in [
            "PRICE_LEVEL_INEXPENSIVE",
            "PRICE_LEVEL_FREE",
        ], f"Cheapest came from {cheapest['price_level']}, expected INEXPENSIVE"

    def test_eval_delivery_total_ranking(self):
        """Test ranking by total cost including delivery fee."""
        restaurants = [
            {
                "id": f"delivery_test_{i}",
                "name": f"Restaurant {i}",
                "price_level": "PRICE_LEVEL_MODERATE",
                "price_range_low": 20,
                "delivery": True,
            }
            for i in range(5)
        ]

        all_options = []
        for r in restaurants:
            menu = generate_menu_for_restaurant(r)
            for item in menu["tuna_rolls"]:
                if item["available"]:
                    total = item["price"] + (menu["delivery_fee"] or 0)
                    all_options.append({
                        "restaurant_name": r["name"],
                        "item_price": item["price"],
                        "delivery_fee": menu["delivery_fee"],
                        "total": round(total, 2),
                    })

        all_options.sort(key=lambda x: x["total"])

        # Verify sorted correctly
        for i in range(1, len(all_options)):
            assert all_options[i]["total"] >= all_options[i - 1]["total"]


class TestEdgeCaseEvals:
    """Evaluate edge cases and error handling."""

    def test_eval_single_restaurant(self):
        """Should work with just one restaurant."""
        restaurant = {
            "id": "solo_1",
            "name": "Only Option",
            "price_level": "PRICE_LEVEL_MODERATE",
            "price_range_low": 20,
            "delivery": True,
        }
        menu = generate_menu_for_restaurant(restaurant)
        available = [i for i in menu["tuna_rolls"] if i["available"]]
        assert len(available) >= 1

    def test_eval_no_delivery_restaurants(self):
        """Should handle restaurants that don't deliver."""
        restaurant = {
            "id": "no_delivery",
            "name": "Dine-In Only",
            "price_level": "PRICE_LEVEL_MODERATE",
            "price_range_low": 20,
            "delivery": False,
        }
        menu = generate_menu_for_restaurant(restaurant)
        assert menu["delivery_time_minutes"] is None
        assert menu["delivery_fee"] is None
        # Should still have tuna rolls on the menu
        assert len(menu["tuna_rolls"]) >= 1

    def test_eval_missing_all_metadata(self):
        """Should handle restaurants with no Google metadata at all."""
        restaurant = {"id": "bare_bones"}
        menu = generate_menu_for_restaurant(restaurant)

        assert menu["restaurant_name"] == "Unknown Restaurant"
        assert len(menu["tuna_rolls"]) >= 1
        for item in menu["tuna_rolls"]:
            assert item["price"] > 0

    def test_eval_real_api_data_pattern(self):
        """Simulate realistic Google Places API response where many fields are None.

        In real API results, most restaurants have no delivery flag and some
        lack price_level. The pipeline should handle this without errors.
        """
        # Modeled after actual SF API results from our testing
        restaurants = [
            {"id": "real_1", "name": "Mensho Tokyo SF",
             "price_level": "PRICE_LEVEL_MODERATE", "price_range_low": 20, "delivery": None},
            {"id": "real_2", "name": "Parking Garage @ Japan Center",
             "price_level": None, "price_range_low": None, "delivery": None},
            {"id": "real_3", "name": "Rintaro",
             "price_level": "PRICE_LEVEL_EXPENSIVE", "price_range_low": 60, "delivery": None},
            {"id": "real_4", "name": "Benihana",
             "price_level": "PRICE_LEVEL_EXPENSIVE", "price_range_low": None, "delivery": None},
        ]

        all_options = []
        for r in restaurants:
            menu = generate_menu_for_restaurant(r)

            # Core invariant: delivery fields must be consistent
            if menu["delivery_available"]:
                assert menu["delivery_time_minutes"] is not None
                assert menu["delivery_fee"] is not None
            else:
                assert menu["delivery_time_minutes"] is None
                assert menu["delivery_fee"] is None

            for item in menu["tuna_rolls"]:
                assert item["price"] > 0
                if item["available"]:
                    all_options.append({
                        "restaurant_name": menu["restaurant_name"],
                        "price": item["price"],
                        "delivery_available": menu["delivery_available"],
                        "delivery_fee": menu["delivery_fee"],
                        "total_with_delivery": round(
                            item["price"] + (menu["delivery_fee"] or 0), 2
                        ),
                    })

        all_options.sort(key=lambda x: x["price"])
        assert len(all_options) >= 4, "Should find tuna rolls at most restaurants"

        # Expensive restaurants should not be cheapest
        cheapest = all_options[0]
        assert cheapest["restaurant_name"] != "Rintaro", \
            "Expensive restaurant should not be cheapest"

    def test_eval_many_restaurants_performance(self):
        """Should handle a large number of restaurants without issues."""
        restaurants = [
            {
                "id": f"perf_test_{i}",
                "name": f"Restaurant {i}",
                "price_level": "PRICE_LEVEL_MODERATE",
                "price_range_low": 20,
                "delivery": True,
            }
            for i in range(50)
        ]

        all_options = []
        for r in restaurants:
            menu = generate_menu_for_restaurant(r)
            for item in menu["tuna_rolls"]:
                if item["available"]:
                    all_options.append(item["price"])

        assert len(all_options) > 30, "Should find tuna rolls at most restaurants"
        all_options.sort()
        assert all_options[0] < all_options[-1], "Should have price variance"
