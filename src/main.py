import json
import time
from battery_optimizer import BatteryOptimizer
from price_analysis import PriceAnalysis

def load_battery_status():
    with open('../data/battery_status.json', 'r') as file:
        return json.load(file)

def load_price_data():
    with open('../data/price_data.json', 'r') as file:
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