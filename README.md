# Home Battery Optimizer

[![hacs][hacsbadge]][hacs]

![Icon](custom_components/home_battery_optimizer/icon.svg)

Home Battery Optimizer is a Home Assistant custom integration that automatically optimizes the charging and discharging of your home battery system. By analyzing real-time electricity prices and battery status, it schedules charging and discharging for maximum economic benefit and self-sufficiency.

## Features
- **Automatic Charging & Discharging**: Controls battery charging/discharging based on price and your settings.
- **Dynamic Number & Switch Entities**: Adjust minimum profit, charge/discharge percent, and rates directly in Home Assistant.
- **Price Analysis**: Finds the best hours to charge/discharge using Nordpool (or other) price data.
- **Schedule & Status Sensors**: See the planned charge/discharge schedule and current status as sensors.
- **ApexCharts Support**: Visualize price, charge, discharge, and SoC with a ready-to-use ApexCharts card.
- **Fully Configurable**: All logic and entity names in English and Swedish. Works with any currency/unit.
- **Native Home Assistant UI**: All configuration and control via the Home Assistant UI.

## Installation
1. Copy the `custom_components/home_battery_optimizer` folder to your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration via Home Assistant UI ("Add Integration" > "Home Battery Optimizer").
4. Select your price entity and battery SoC entity.

## Usage
- Adjust **Minimum Profit**, **Charge Percentage**, **Discharge Percentage**, **Charge Rate**, and **Discharge Rate** via the number sliders in Home Assistant.
- The integration will automatically update the schedule and control the switches for charging/discharging.
- View the planned schedule in the "Battery Schedule" sensor's attributes.
- Switches for charging and discharging are controlled automatically, but can also be toggled manually if needed.
- Use the included services to force update the schedule, force charge, or force discharge if needed.

## Entities

Entity | Type | Description
-- | -- | --
`sensor.home_battery_optimizer_soc` | Sensor | Current battery state of charge (SoC).
`sensor.home_battery_optimizer_estimated_soc` | Sensor | Estimated SoC curve for the next 48h.
`sensor.home_battery_optimizer_battery_price_raw_two_days` | Sensor | Price data for today and tomorrow.
`sensor.home_battery_optimizer_battery_charge_raw_two_days` | Sensor | Charge schedule for today and tomorrow.
`sensor.home_battery_optimizer_battery_discharge_raw_two_days` | Sensor | Discharge schedule for today and tomorrow.
`sensor.home_battery_optimizer_battery_schedule` | Sensor | Current planned schedule.
`sensor.home_battery_optimizer_batteristatus` | Sensor | Current battery status (Idle, Charge, Discharge, Self Usage).
`switch.home_battery_optimizer_charge` | Switch | Controls battery charging.
`switch.home_battery_optimizer_discharge` | Switch | Controls battery discharging.
`number.home_battery_optimizer_minimum_profit` | Number | Minimum profit required for action.
`number.home_battery_optimizer_charge_percentage` | Number | Maximum SoC for charging.
`number.home_battery_optimizer_discharge_percentage` | Number | Minimum SoC for discharging.
`number.home_battery_optimizer_charge_rate` | Number | Charge rate (%/h).
`number.home_battery_optimizer_discharge_rate` | Number | Discharge rate (%/h).

## ApexCharts Example

![Chart](assets/battery_optimizer_apex_example.png)

```yaml
# Example Lovelace card for Battery Optimizer
# Requires ApexCharts Card (https://github.com/RomRider/apexcharts-card)
type: custom:apexcharts-card
now:
  show: true
  label: Now
  color: "#ffc0cb"
locale: en
header:
  show: true
  title: Battery Optimizer
graph_span: 2d
span:
  start: day
yaxis:
  - id: price
    min: 0
    apex_config:
      forceNiceScale: true
  - id: action
    min: -1
    max: 1
    show: false
  - id: soc
    min: 0
    max: 100
    opposite: true
    decimals: 0
    show: true
apex_config:
  legend:
    show: true
    showForSingleSeries: true
    showForNullSeries: true
  xaxis:
    labels:
      show: true
      format: HH
      rotate: -45
      rotateAlways: true
      hideOverlappingLabels: true
      style:
        fontSize: 10
        fontWeight: 400
series:
  - entity: sensor.home_battery_optimizer_battery_schedule
    name: Electricity price
    unit: " öre/kWh"
    yaxis_id: price
    data_generator: |
      return entity.attributes.data
        ? entity.attributes.data.map(entry => [new Date(entry.start), entry.price])
        : [];
    type: line
    float_precision: 0
    color: "#2196f3"
    show:
      in_header: false
      legend_value: false
    extend_to: false
    color_threshold:
      - value: -100
        color: cyan
      - value: 0
        color: green
      - value: 40
        color: orange
      - value: 100
        color: red
      - value: 200
        color: magenta
      - value: 500
        color: black
  - entity: sensor.home_battery_optimizer_battery_schedule
    name: Charge
    yaxis_id: action
    data_generator: |
      return entity.attributes.data
        ? entity.attributes.data.map(entry => [new Date(entry.start), entry.charge === 1 ? 1 : 0])
        : [];
    type: area
    curve: stepline
    color: "#4caf50"
    opacity: 0.5
    show:
      in_header: false
      legend_value: false
    extend_to: false
  - entity: sensor.home_battery_optimizer_battery_schedule
    name: Discharge
    yaxis_id: action
    data_generator: |
      return entity.attributes.data
        ? entity.attributes.data.map(entry => [new Date(entry.start), entry.discharge === 1 ? -1 : 0])
        : [];
    type: area
    curve: stepline
    color: "#f44336"
    opacity: 0.5
    show:
      in_header: false
      legend_value: false
    extend_to: false
  - entity: sensor.home_battery_optimizer_battery_schedule
    name: Estimated SoC
    yaxis_id: soc
    data_generator: |
      return entity.attributes.data
        ? entity.attributes.data.map(entry => [new Date(entry.start), entry.soc])
        : [];
    type: line
    color: "#ffd600"
    stroke_width: 2
    show:
      in_header: false
      legend_value: false
    extend_to: false
experimental:
  color_threshold: true

```

## License
MIT License. See LICENSE file for details.