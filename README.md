# Home Battery Optimizer

## Overview
The Home Battery Optimizer is a Python-based application designed to optimize the charging and discharging of a home battery system. By analyzing electricity prices and battery status, the program determines the most economical times to charge and discharge the battery, ensuring cost-effective energy management. This project also includes integration with Home Assistant, allowing users to manage the battery optimizer through the Home Assistant frontend.

## Features
- **Dynamic Charging and Discharging**: Automatically adjusts charging and discharging based on real-time price data.
- **Price Analysis**: Identifies the best hours for charging and discharging by analyzing price fluctuations.
- **Battery Management**: Calculates the time required to charge and discharge the battery based on its current percentage level.
- **Multiple Cycles**: Supports multiple charging and discharging cycles throughout the day for optimal energy usage.
- **Home Assistant Integration**: Manage the battery optimizer through Home Assistant, including controls for starting and stopping charging and discharging, and viewing the planned schedule.

## Project Structure
```
home-battery-optimizer
├── custom_components
│   └── home_battery_optimizer
│       ├── __init__.py            # Initializes the Home Assistant integration
│       ├── manifest.json           # Metadata about the integration
│       ├── config_flow.py          # Configuration flow for user input
│       ├── sensor.py               # Defines sensor entities for battery status
│       ├── switch.py               # Defines switch entities for control
│       ├── services.yaml           # Defines services for controlling the optimizer
│       └── translations
│           └── en.json             # Translations for localization
├── src
│   ├── main.py                     # Entry point for the application
│   ├── battery_optimizer.py         # Contains the BatteryOptimizer class
│   ├── price_analysis.py            # Contains the PriceAnalysis class
│   └── utils
│       ├── time_utils.py           # Utility functions for time operations
│       └── price_utils.py          # Utility functions for price data processing
├── data
│   ├── price_data.json              # Stores hourly price data
│   └── battery_status.json           # Contains current battery status
├── tests
│   ├── test_battery_optimizer.py     # Unit tests for BatteryOptimizer
│   ├── test_price_analysis.py        # Unit tests for PriceAnalysis
│   └── test_utils.py                 # Unit tests for utility functions
├── requirements.txt                  # Project dependencies
└── README.md                         # Project documentation
```

## Installation
1. Clone the repository:
   ```
   git clone <repository-url>
   ```
2. Navigate to the project directory:
   ```
   cd home-battery-optimizer
   ```
3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage
To run the Home Battery Optimizer, execute the following command:
```
python src/main.py
```

### Home Assistant Integration
1. Install the Home Battery Optimizer integration via HACS (Home Assistant Community Store).
2. Configure the integration by selecting it in Home Assistant and providing the necessary details:
   - Nordpool integration entity
   - Battery percentage
3. Use the Home Assistant frontend to control the battery optimizer:
   - Start and stop charging and discharging
   - View the planned schedule

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for details.