# Home Battery Optimizer

## Overview
Home Battery Optimizer is a Home Assistant custom integration that automatically optimizes the charging and discharging of your home battery system. By analyzing real-time electricity prices and battery status, it schedules charging and discharging for maximum economic benefit.

## Features
- **Automatic Charging & Discharging**: Switches are controlled automatically based on your configured minimum profit and battery levels.
- **Dynamic Number Entities**: Adjust minimum profit (with 0.001–1000 step), charge percentage, discharge percentage, charge rate, and discharge rate at any time via Home Assistant sliders.
- **Price Analysis**: Finds the best hours to charge and discharge using Nordpool (or other) price data.
- **Schedule Sensor**: See the planned charge/discharge schedule as a sensor attribute.
- **Fully Configurable**: All logic and entity names are in English. Works with any currency/unit.
- **Home Assistant Native**: All configuration and control via the Home Assistant UI.

## Project Structure
```
custom_components/
└── home_battery_optimizer/
    ├── __init__.py              # Integration setup
    ├── manifest.json            # Integration metadata
    ├── config_flow.py           # UI configuration flow
    ├── sensor.py                # Battery status sensor
    ├── switch.py                # Charging/discharging switches
    ├── number.py                # Number entities for profit/charge/discharge/rate
    ├── schedule_sensor.py       # Schedule sensor
    ├── battery_optimizer.py     # Optimization logic
    ├── price_analysis.py        # Price analysis logic
    ├── services.yaml            # (Optional) Custom services
    ├── translations/
    │   └── en.json              # English translation
    └── ...
```

## Installation
1. Copy the `custom_components/home_battery_optimizer` folder to your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration via Home Assistant UI ("Add Integration" > "Home Battery Optimizer").
4. Select your Nordpool price entity and battery SoC entity.

## Usage
- Adjust **Minimum Profit**, **Charge Percentage**, **Discharge Percentage**, **Charge Rate**, and **Discharge Rate** via the number sliders in Home Assistant.
- The integration will automatically update the schedule and control the switches for charging/discharging.
- View the planned schedule in the "Battery Schedule" sensor's attributes.
- Switches for charging and discharging are controlled automatically, but can also be toggled manually if needed.
- Use the included services to force update the schedule, force charge, or force discharge if needed.

## Contributing
Contributions are welcome! Please open an issue or submit a pull request.

## License
MIT License. See LICENSE file for details.