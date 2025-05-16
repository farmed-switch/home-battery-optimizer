import json
import time
import os
from .battery_optimizer import BatteryOptimizer
from .price_analysis import PriceAnalysis

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

    optimizer = BatteryOptimizer(battery_status, price_data)

    while True:
        optimizer.analyze_prices()
        optimizer.manage_battery()
        time.sleep(3600)  # Check every hour

if __name__ == "__main__":
    main()