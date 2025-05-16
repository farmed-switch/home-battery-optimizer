import json
import time
import os
import requests
from .battery_optimizer import BatteryOptimizer
from .price_analysis import PriceAnalysis

HOME_ASSISTANT_URL = "http://localhost:8123"  # Ändra vid behov
LONG_LIVED_TOKEN = "DIN_LONG_LIVED_ACCESS_TOKEN"  # Skapa i Home Assistant

def get_battery_percentage(entity_id):
    url = f"{HOME_ASSISTANT_URL}/api/states/{entity_id}"
    headers = {
        "Authorization": f"Bearer {LONG_LIVED_TOKEN}",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        state = response.json().get("state")
        try:
            return float(state)
        except (TypeError, ValueError):
            return 0
    return 0

def load_battery_status():
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'battery_status.json')
    with open(os.path.abspath(path), 'r') as file:
        return json.load(file)

def load_price_data():
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'price_data.json')
    with open(os.path.abspath(path), 'r') as file:
        return json.load(file)

def main():
    battery_status = load_battery_status()
    price_data = load_price_data()

    battery_capacity = battery_status.get("battery_capacity", 100)
    charge_rate = battery_status.get("default_charge_rate", 10)
    discharge_rate = battery_status.get("default_discharge_rate", 10)
    battery_entity = battery_status.get("battery_entity", None)
    nordpool_entity = battery_status.get("nordpool_entity", None)

    # Hämta aktuell batteriprocent från Home Assistant
    battery_percentage = get_battery_percentage(battery_entity) if battery_entity else 0

    price_analysis = PriceAnalysis(price_data)
    optimizer = BatteryOptimizer(
        battery_capacity=battery_capacity,
        charge_rate=charge_rate,
        discharge_rate=discharge_rate,
        price_analysis=price_analysis
    )
    optimizer.current_charge = battery_percentage

    while True:
        optimizer.analyze_prices()
        optimizer.manage_battery()
        time.sleep(3600)  # Check every hour

if __name__ == "__main__":
    main()