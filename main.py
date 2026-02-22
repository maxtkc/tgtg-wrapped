#!/usr/bin/env python3

import argparse
import json
import os
import sys
from datetime import datetime

from tgtg_client import TgtgClient

CRED_FILE = "tgtg_credentials.json"


# -----------------------------
# Authentication
# -----------------------------

def get_client(email: str = None) -> TgtgClient:
    """
    Get authenticated TgtgClient using cached tokens.
    Will refresh tokens if necessary.
    If email is provided and no cached credentials exist, performs first-time login.
    """
    # Try to load cached credentials
    if os.path.exists(CRED_FILE):
        with open(CRED_FILE, "r") as f:
            creds = json.load(f)

        client = TgtgClient(
            access_token=creds.get("access_token"),
            refresh_token=creds.get("refresh_token"),
        )

        # Restore cached datadome_cookie if available
        if "datadome_cookie" in creds:
            client.datadome_cookie = creds["datadome_cookie"]

        try:
            client.login()  # will refresh token if needed
            # Update credentials file with refreshed tokens
            updated_creds = client.get_credentials()
            with open(CRED_FILE, "w") as f:
                json.dump(updated_creds, f, indent=2)
            return client
        except Exception as e:
            print(f"Cached credentials invalid or expired: {e}")
            if not email:
                print("Please provide --email to login again")
                sys.exit(1)
            # Fall through to new login with email

    # First-time login or cached credentials failed
    if not email:
        print(f"No cached credentials found in {CRED_FILE}")
        print("Please provide --email for first-time login")
        sys.exit(1)

    print(f"Logging in with email: {email}")
    client = TgtgClient(email=email)

    try:
        client.login()
        # Save credentials for future use
        creds = client.get_credentials()
        with open(CRED_FILE, "w") as f:
            json.dump(creds, f, indent=2)
        print(f"Login successful! Credentials saved to {CRED_FILE}")
        return client
    except Exception as e:
        print(f"Login failed: {e}")
        sys.exit(1)


# -----------------------------
# Fetch all redeemed orders
# -----------------------------
def get_all_redeemed_orders(client: TgtgClient):
    """
    Fetch all redeemed orders using month-based pagination.
    TGTG API paginates orders by month, going backwards in time.
    """
    all_orders = []
    page_size = 50
    next_page_year = None
    next_page_month = None
    page_num = 1

    while True:
        print(f"Fetching page {page_num}...")
        response = client.get_order_history(
            page_size=page_size,
            next_page_year=next_page_year,
            next_page_month=next_page_month
        )

        # Extract orders from all months in this response
        for month_group in response.get("orders_per_month", []):
            orders = month_group.get("orders", [])
            all_orders.extend(orders)
            print(f"  Month {month_group['year']}-{month_group['month']:02d}: {len(orders)} orders")

        if not response.get("has_more", False):
            break

        # Get pagination params for next page
        next_page_year = response.get("next_page_year")
        next_page_month = response.get("next_page_month")
        page_num += 1

    # Filter to only redeemed orders
    redeemed = [o for o in all_orders if o.get("state") == "REDEEMED"]
    print(f"\nTotal orders: {len(all_orders)}, Redeemed: {len(redeemed)}")
    return redeemed


# -----------------------------
# Extract geo points
# -----------------------------
def extract_points(orders):
    """
    Extract coordinates and pickup times from order data.
    Location data is already included in the order response.
    """
    points = []

    for order in orders:
        # Get location from order (no need to fetch item details)
        loc = order.get("pickup_location", {}).get("location", {})
        lat = loc.get("latitude")
        lon = loc.get("longitude")

        if lat is None or lon is None:
            print(f"  Warning: Skipping order {order.get('order_id')} - no location data")
            continue

        # Get pickup time (use redeemed_at if available, otherwise pickup start)
        pickup_time_str = order.get("redeemed_at_utc")
        if not pickup_time_str:
            pickup_time_str = order.get("pickup_interval", {}).get("start")

        if pickup_time_str:
            time = datetime.fromisoformat(pickup_time_str.replace("Z", "+00:00"))
        else:
            print(f"  Warning: Skipping order {order.get('order_id')} - no time data")
            continue

        # Get store/item name
        name = order.get("store_name", order.get("item_name", "Unknown"))

        points.append(
            {
                "lat": lat,
                "lon": lon,
                "time": time,
                "name": name,
                "item_id": order.get("item_id"),
                "order_id": order.get("order_id"),
                "store_name": order.get("store_name"),
                "order": order,
            }
        )

    points.sort(key=lambda x: x["time"])
    return points


# -----------------------------
# GeoJSON Export
# -----------------------------
def export_geojson(points, output_file, metadata=False):
    features = []

    for p in points:
        props = {
            "name": p["name"],
            "item_id": p["item_id"],
            "time": p["time"].isoformat(),
        }
        if metadata:
            props.update(p["order"])

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
                "properties": props,
            }
        )

    line_coords = [[p["lon"], p["lat"]] for p in points]
    features.append(
        {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": line_coords},
            "properties": {"name": "TGTG Collection Route"},
        }
    )

    geojson = {"type": "FeatureCollection", "features": features}

    with open(output_file, "w") as f:
        json.dump(geojson, f, indent=2)

    print(f"GeoJSON exported to {output_file}")


# -----------------------------
# Main
# -----------------------------
def main():
    parser = argparse.ArgumentParser(description="Export TooGoodToGo pickup history as a map")
    parser.add_argument("--email", help="Email for first-time login")
    parser.add_argument("--output", default=None, help="Output file name")
    parser.add_argument("--metadata", action="store_true", help="Include full bag metadata (price, address, etc.) in output")
    args = parser.parse_args()

    output_file = args.output or "tgtg_history.geojson"

    client = get_client(args.email)

    print("Fetching redeemed orders...")
    orders = get_all_redeemed_orders(client)

    print(f"Found {len(orders)} redeemed orders")
    if not orders:
        print("No redeemed orders found")
        sys.exit(0)

    print("Extracting pickup locations...")
    points = extract_points(orders)

    export_geojson(points, output_file, metadata=args.metadata)


if __name__ == "__main__":
    main()
