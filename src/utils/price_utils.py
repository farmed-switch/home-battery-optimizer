def fetch_price_data(api_url):
    import requests
    response = requests.get(api_url)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception("Failed to fetch price data")

def parse_price_data(price_data):
    parsed_data = {}
    for entry in price_data:
        hour = entry['hour']
        price = entry['price']
        parsed_data[hour] = price
    return parsed_data

def get_best_hours_for_charging(parsed_data, price_difference=0.30):
    sorted_prices = sorted(parsed_data.items(), key=lambda x: x[1])
    best_hours = []
    for i in range(len(sorted_prices) - 1):
        current_hour, current_price = sorted_prices[i]
        next_hour, next_price = sorted_prices[i + 1]
        if (next_price - current_price) >= price_difference:
            best_hours.append(current_hour)
    return best_hours

def get_best_hours_for_discharging(parsed_data):
    sorted_prices = sorted(parsed_data.items(), key=lambda x: x[1], reverse=True)
    best_hours = [hour for hour, price in sorted_prices[:2]]  # Get the top 2 most expensive hours
    return best_hours