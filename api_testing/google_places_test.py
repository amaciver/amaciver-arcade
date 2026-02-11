"""
Google Places API Data Test Script

Tests what restaurant data Google Places API (New) actually provides.
Validates which fields are available for the sushi-scout project.

Setup:
1. Create .env file with: GOOGLE_PLACES_API_KEY=your_key_here
2. Run: uv run python google_places_test.py
"""

import os
import sys
import requests
import json
from pathlib import Path
from typing import Dict, List, Any

# Fix Windows console encoding for unicode output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Load .env file manually (avoid import issues)
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


class GooglePlacesTester:
    """Test Google Places API to understand available restaurant data."""

    BASE_URL = "https://places.googleapis.com/v1/places"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _headers(self, field_mask: str) -> dict:
        return {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": field_mask,
        }

    def search_nearby_sushi(
        self, location: Dict[str, float], radius_meters: int = 3000
    ) -> List[Dict[str, Any]]:
        """Search for sushi restaurants near a location."""
        url = f"{self.BASE_URL}:searchNearby"

        field_mask = ",".join(
            f"places.{f}"
            for f in [
                "id",
                "displayName",
                "formattedAddress",
                "rating",
                "userRatingCount",
                "priceLevel",
                "types",
                "location",
            ]
        )

        payload = {
            "includedTypes": ["japanese_restaurant", "sushi_restaurant"],
            "maxResultCount": 10,
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": location["latitude"],
                        "longitude": location["longitude"],
                    },
                    "radius": radius_meters,
                }
            },
        }

        print(
            f"[SEARCH] Sushi restaurants near ({location['latitude']}, {location['longitude']})"
        )
        print(f"         Radius: {radius_meters}m (~{radius_meters/1609:.1f} miles)\n")

        response = requests.post(url, json=payload, headers=self._headers(field_mask))

        if response.status_code == 200:
            data = response.json()
            places = data.get("places", [])
            print(f"[OK] Found {len(places)} restaurants\n")
            return places
        else:
            print(f"[ERROR] {response.status_code}: {response.text}\n")
            return []

    def get_place_details(self, place_id: str, place_name: str = "") -> Dict[str, Any]:
        """Get all available details for a place to understand data richness."""
        url = f"{self.BASE_URL}/{place_id}"

        # All potentially useful fields for sushi-scout
        fields = [
            "displayName",
            "formattedAddress",
            "location",
            "rating",
            "userRatingCount",
            "priceLevel",
            "priceRange",
            "websiteUri",
            "googleMapsUri",
            "currentOpeningHours",
            "delivery",
            "dineIn",
            "takeout",
            "curbsidePickup",
            "reservable",
            "servesLunch",
            "servesDinner",
            "servesBeer",
            "servesWine",
            "reviews",
            "types",
            "primaryType",
            "editorialSummary",
        ]

        field_mask = ",".join(fields)

        print(f"  [{place_name or place_id}]")

        response = requests.get(url, headers=self._headers(field_mask))

        if response.status_code == 200:
            return response.json()
        else:
            print(f"  [ERROR] {response.status_code}: {response.text}")
            return {}

    def print_place_summary(self, data: Dict[str, Any]) -> None:
        """Print a clean summary of what data we got for a place."""
        name = data.get("displayName", {}).get("text", "Unknown")
        addr = data.get("formattedAddress", "N/A")
        rating = data.get("rating", "N/A")
        count = data.get("userRatingCount", 0)
        price = data.get("priceLevel", "N/A")
        price_range = data.get("priceRange", None)
        website = data.get("websiteUri", "N/A")
        delivery = data.get("delivery", "N/A")
        takeout = data.get("takeout", "N/A")
        summary = data.get("editorialSummary", {}).get("text", "N/A")
        primary_type = data.get("primaryType", "N/A")

        print(f"  Name:          {name}")
        print(f"  Address:       {addr}")
        print(f"  Rating:        {rating} ({count} reviews)")
        print(f"  Price Level:   {price}")
        if price_range:
            print(f"  Price Range:   {json.dumps(price_range)}")
        print(f"  Primary Type:  {primary_type}")
        print(f"  Delivery:      {delivery}")
        print(f"  Takeout:       {takeout}")
        print(f"  Website:       {website}")
        print(f"  Summary:       {summary}")

        # Check reviews for menu/price mentions
        reviews = data.get("reviews", [])
        if reviews:
            print(f"  Reviews:       {len(reviews)} returned")
            tuna_mentions = []
            price_mentions = []
            for review in reviews:
                text = review.get("text", {}).get("text", "").lower()
                if "tuna" in text:
                    tuna_mentions.append(
                        review.get("text", {}).get("text", "")[:100]
                    )
                if "$" in text or "price" in text or "cheap" in text or "expensive" in text:
                    price_mentions.append(
                        review.get("text", {}).get("text", "")[:100]
                    )
            if tuna_mentions:
                print(f"  Tuna mentions: {len(tuna_mentions)}")
                for m in tuna_mentions[:2]:
                    print(f"    -> \"{m}...\"")
            if price_mentions:
                print(f"  Price mentions: {len(price_mentions)}")
                for m in price_mentions[:2]:
                    print(f"    -> \"{m}...\"")

        # Show which fields had data vs didn't
        available = [k for k in data.keys() if data[k] is not None]
        print(f"  Fields present: {', '.join(available)}")
        print()


def main():
    """Run the Places API data exploration."""

    api_key = os.getenv("GOOGLE_PLACES_API_KEY")

    if not api_key:
        print("[ERROR] GOOGLE_PLACES_API_KEY not found.")
        print("")
        print("Create a .env file in this directory:")
        print("  echo GOOGLE_PLACES_API_KEY=your_key_here > .env")
        print("")
        print("Or set the environment variable directly:")
        print("  $env:GOOGLE_PLACES_API_KEY='your_key_here'  (PowerShell)")
        return

    print("=" * 70)
    print("GOOGLE PLACES API - DATA AVAILABILITY TEST")
    print("=" * 70)
    print()

    tester = GooglePlacesTester(api_key)

    # San Francisco - known sushi hub
    sf_location = {"latitude": 37.7749, "longitude": -122.4194}

    places = tester.search_nearby_sushi(sf_location, radius_meters=2000)

    if not places:
        print("[WARN] No restaurants found. Check API key and enabled APIs.")
        return

    # Print search results overview
    print("-" * 70)
    print("SEARCH RESULTS OVERVIEW")
    print("-" * 70)
    for i, p in enumerate(places, 1):
        name = p.get("displayName", {}).get("text", "Unknown")
        rating = p.get("rating", "N/A")
        price = p.get("priceLevel", "N/A")
        types = p.get("types", [])
        sushi_related = [t for t in types if "sushi" in t or "japanese" in t]
        print(f"  {i:2}. {name:<35} rating={rating}  price={price}  types={sushi_related}")
    print()

    # Detailed analysis of first 5 restaurants
    print("=" * 70)
    print("DETAILED DATA FOR TOP 5 RESTAURANTS")
    print("=" * 70)
    print()

    has_delivery = 0
    has_website = 0
    has_reviews = 0
    has_price_level = 0
    has_price_range = 0

    for i, place in enumerate(places[:5], 1):
        place_id = place.get("id")
        place_name = place.get("displayName", {}).get("text", "Unknown")

        print(f"--- Restaurant {i}/5 ---")
        details = tester.get_place_details(place_id, place_name)

        if details:
            tester.print_place_summary(details)
            if details.get("delivery"):
                has_delivery += 1
            if details.get("websiteUri"):
                has_website += 1
            if details.get("reviews"):
                has_reviews += 1
            if details.get("priceLevel"):
                has_price_level += 1
            if details.get("priceRange"):
                has_price_range += 1

    # Final summary
    tested = min(5, len(places))
    print("=" * 70)
    print("DATA AVAILABILITY SUMMARY")
    print("=" * 70)
    print(f"  Restaurants found:       {len(places)}")
    print(f"  Restaurants tested:      {tested}")
    print(f"  Have delivery flag:      {has_delivery}/{tested}")
    print(f"  Have website URL:        {has_website}/{tested}")
    print(f"  Have reviews:            {has_reviews}/{tested}")
    print(f"  Have price level:        {has_price_level}/{tested}")
    print(f"  Have price range:        {has_price_range}/{tested}")
    print(f"  Have structured menus:   0/{tested} (field does not exist in API)")
    print()
    print("=" * 70)
    print("CONCLUSIONS FOR SUSHI-SCOUT")
    print("=" * 70)
    print()
    print("Google Places API (New) provides:")
    print("  [YES] Restaurant search by location + radius + cuisine type")
    print("  [YES] Ratings, review count, price level ($-$$$$)")
    print("  [YES] Delivery/takeout/dine-in availability flags")
    print("  [YES] Opening hours, website URL, Google Maps link")
    print("  [YES] User reviews (may mention specific items/prices)")
    print("  [YES] Lat/lng for distance calculations")
    print()
    print("  [NO]  Structured menu items with prices")
    print("  [NO]  Individual dish names or descriptions")
    print("  [NO]  Real-time ordering capability")
    print()
    print("RECOMMENDED STRATEGY:")
    print("  -> Use Google Places for restaurant discovery + metadata")
    print("  -> Use synthetic/seeded menu data for item-level pricing")
    print("  -> This is the best approach given API limitations")
    print()


if __name__ == "__main__":
    main()
