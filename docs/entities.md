# Entity reference

All entities the HIQ-Home integration creates, by platform. Back to the
[README](../README.md).

In the tables, `XXXX` is the NAD of the controller, `YY` the number of the
expansion unit or thermostat, `ZZ` the output of a unit, and `YYYY` the IEX
module prefix (e.g. `lc00`, `bc02`).

When the integration starts, it scans the controller for supported units and
creates their entities. A unit with `general_error` set is skipped (as the HIQ
software does).

Many diagnostic and parameter entities are **disabled by default**. Enable them
under **Settings → Devices & services → HIQ-Home → entities**.

> [!NOTE]
> Some `number`, `select`, `switch` and `button` entities are additions to the
> HIQ functionality and are not supported by the stock HIQ firmware.

- [light](#light)
- [cover](#cover)
- [scene](#scene)
- [climate](#climate)
- [weather](#weather)
- [binary_sensor](#binary_sensor)
- [sensor](#sensor)
- [number](#number)
- [select](#select)
- [switch](#switch)
- [button](#button)
- [Devices](#devices)
- [Common attributes](#common-attributes)

---

## light

| HIQ expansion unit | On / off | Brightness | RGB | White temperature |
| ------------------ | :------: | :--------: | :-: | :---------------: |
| LC-10-IQ           | ✓        |            |     |                   |
| LC-8-IQ            | ✓        |            |     |                   |
| LD-D10-IQ          | ✓        | ✓          | ✓   | ✓                 |
| LD-D8-IQ           | ✓        | ✓          |     |                   |
| LD-P4-IQ           | ✓        | ✓          | ✓   |                   |
| LD-V4-IQ           | ✓        | ✓          | ✓   |                   |
| Virtual LC         | ✓        |            |     |                   |

The color mode of each LD-D10-IQ output (`ldNN_color_mode_MM`: standard dimmer,
RGB or white temperature) is read when the integration starts. The color of an
output can only be written, not read back from the module, so the last color set
from Home Assistant is shown (and kept over a restart). White temperature 0..100 %
is shown as 2700..6500 K.

## cover

The blinds of the HIQ controller.

Supported HIQ expansion units: **BC-5-IQ**, **Virtual BC**.

Commands: open, close, stop, set position.

## scene

The scenes of lights and blinds (SC-4-IQ). A scene is created for every defined
scene of `cXXXX.scene_status[0..31]` (status is not `-1`) when the integration
starts. Activating a scene writes its number to `cXXXX.global_scene_request`.
The attribute `active` shows if the scene is active on the controller.

## climate

The TH (thermostat) units of the HIQ controller.

Supported HIQ expansion units: **TH-X-IQ**.

Commands:

- Turn heating / cooling on / off
- Set the setpoint temperature
- Set the presets eco (idle) / comfort (on) / boost (fan max)

## weather

Created when the controller has a weather station, i.e. at least one of the
variables below.

| Value          | Controller var                | Unit |
| -------------- | ----------------------------- | ---- |
| Temperature    | `cXXXX.weather_temperature`    | °C   |
| Humidity       | `cXXXX.weather_humidity`       | %    |
| Pressure       | `cXXXX.weather_pressure`       | hPa  |
| Wind speed     | `cXXXX.weather_wind_speed`     | km/h |
| Wind direction | `cXXXX.weather_wind_direction` | °    |

The weather station has no condition (sunny, rainy, ...).

---

## binary_sensor

### Controller

| Entity name            | Description                                                                        | Enabled |
| ---------------------- | ---------------------------------------------------------------------------------- | ------- |
| `cXXXX.general_error`  | Logical or of IEX general errors, indicates that at least one module has an error. | no      |
| `cXXXX.retentive_fail` | Indicates that retentive memory failed.                                            | no      |
| `cXXXX.scan_overrun`   | Too long scan execution caused scan overrun error.                                 | no      |

### Indicators of the controller

| Entity name                  | Description                              | Controller var              | Enabled |
| ---------------------------- | ---------------------------------------- | --------------------------- | ------- |
| `cXXXX diagnostic presence`  | Indicates that somebody is at home.      | `cXXXX.presence_indicator`  | yes     |
| `cXXXX diagnostic nighttime` | Indicates that the sun is below horizon. | `cXXXX.low_light_indicator` | yes     |

### Every IEX expansion unit

| Entity name                | Description                                                                  | Enabled |
| -------------------------- | ---------------------------------------------------------------------------- | ------- |
| `cXXXX.YYYY_general_error` | Combined system error (timeout or program error), module is not operational. | no      |

### Every TH (thermostat) expansion unit

| Entity name                    | Description                            | Controller var      | Enabled |
| ------------------------------ | -------------------------------------- | ------------------- | ------- |
| `cXXXX.thYY thermostat window` | Indicate state of window switch input. | `cXXXX.thYY_ix00`   | no      |
| `cXXXX.thYY thermostat output` | Radiator output.                       | `cXXXX.thYY_output` | no      |

---

## sensor

Custom sensors from any controller variable can be added too, see
[Custom entities](../README.md#custom-entities).

### Controller

| Entity name                | Description                                                         | Enabled |
| -------------------------- | ------------------------------------------------------------------- | ------- |
| `cXXXX.scan_time`          | Last scan execution time [ms].                                      | no      |
| `cXXXX.scan_time_max`      | Maximal scan execution time encountered since program started [ms]. | no      |
| `cXXXX.scan_frequency`     | Actual number of scans per second.                                  | no      |
| `cXXXX.cybro_power_supply` | Measured power supply voltage [V]. Measuring range is 0..40V.       | no      |
| `cXXXX.cybro_uptime`       | Number of operating hours since power-on [h].                       | no      |
| `cXXXX.operating_hours`    | Total number of operating hours [h].                                | no      |
| `cXXXX.sys.ip_port`        | IP address and UDP port of the controller.                          | no      |

### Every IEX expansion unit

| Entity name                   | Description                                                   | Enabled |
| ----------------------------- | ------------------------------------------------------------- | ------- |
| `cXXXX.YYYY_iex_power_supply` | Measured power supply voltage [V]. Measuring range is 0..40V. | no      |

### Power meter

| Entity name                 | Description                     | Enabled |
| --------------------------- | ------------------------------- | ------- |
| `cXXXX.power_meter_power`   | Measured power consumption [W]. | yes     |
| `cXXXX.power_meter_energy`  | Energy consumption total [kWh]. | yes     |
| `cXXXX.power_meter_voltage` | Measured AC voltage [V].        | no      |

### Temperature / humidity sensors of expansion units

| Entity name              | Description                             | Enabled                          |
| ------------------------ | --------------------------------------- | -------------------------------- |
| `cXXXX.YYYY_temperature` | Measured temperature [°C].              | if module has no `general_error` |
| `cXXXX.YYYY_humidity`    | Measured relative humidity (0..100%rh). | if module has no `general_error` |

### Every TH (thermostat) expansion unit

| Entity name                           | Description                                          | Controller var             | Enabled |
| ------------------------------------- | ---------------------------------------------------- | -------------------------- | ------- |
| `cXXXX.thYY thermostat temperature`   | Measured temperature (internal, external or remote). | `cXXXX.thYY_temperature`   | yes     |
| `cXXXX.thYY thermostat temperature 1` | Measured external temperature.                       | `cXXXX.thYY_temperature_1` | yes     |
| `cXXXX.thYY thermostat humidity`      | Measured relative humidity.                          | `cXXXX.thYY_humidity`      | yes     |

### HVAC (internal)

| Entity name                            | Description                                        | Controller var               | Enabled               |
| -------------------------------------- | -------------------------------------------------- | ---------------------------- | --------------------- |
| `cXXXX.thYY HVAC outdoor temperature`  | Measured outdoor temperature.                      | `cXXXX.outdoor_temperature`  | if `zz_enable` is set |
| `cXXXX.thYY HVAC wall temperature`     | Measured temperature within building construction. | `cXXXX.wall_temperature`     | if `zz_enable` is set |
| `cXXXX.thYY HVAC water temperature`    | Measured temperature of heating/cooling medium.    | `cXXXX.water_temperature`    | if `zz_enable` is set |
| `cXXXX.thYY HVAC auxilary temperature` | Measured temperature of auxilary sensor.           | `cXXXX.auxilary_temperature` | if `zz_enable` is set |

---

## number

All `number` entities are disabled by default.

### Every TH (thermostat) expansion unit

| Entity name                                                  | Description                                                                                      | Controller var                      |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ | ----------------------------------- |
| `cXXXX.thYY thermostat setpoint idle`                        | Secondary setpoint, used when thermostat is off. Zero means output is off.                       | `cXXXX.thYY_setpoint_idle`          |
| `cXXXX.thYY thermostat setpoint idle cooling`                | Secondary setpoint for cooling, used when thermostat is off. Zero means output is off.           | `cXXXX.thYY_setpoint_idle_c`        |
| `cXXXX.thYY thermostat setpoint idle heating`                | Secondary heating setpoint, used when thermostat is off. Zero means output is off.               | `cXXXX.thYY_setpoint_idle_h`        |
| `cXXXX.thYY thermostat setpoint offset`                      | Setpoint correction, used to affect regulated temperature without changing setpoint.             | `cXXXX.thYY_setpoint_offset`        |
| `cXXXX.thYY thermostat setpoint offset cooling`              | Setpoint correction for cooling, used to affect regulated temperature without changing setpoint. | `cXXXX.thYY_setpoint_offset_c`      |
| `cXXXX.thYY thermostat setpoint offset heating`              | Setpoint correction for heating, used to affect regulated temperature without changing setpoint. | `cXXXX.thYY_setpoint_offset_h`      |
| `cXXXX.thYY thermostat temperature offset`                   | Measurement correction of the thermostat temperature sensor.                                     | `cXXXX.thYY_temperature_offset`     |
| `cXXXX.thYY thermostat hystheresis`                          | Hysteresis for on/off regulation. Defined as distance between on and off points.                 | `cXXXX.thYY_setpoint_hystheresis`   |
| `cXXXX.thYY thermostat hystheresis cooling`                  | Hysteresis for on/off regulation in cooling mode. Defined as distance between on and off points. | `cXXXX.thYY_setpoint_hystheresis_c` |
| `cXXXX.thYY thermostat hystheresis heating`                  | Hysteresis for on/off regulation in heating mode. Defined as distance between on and off points. | `cXXXX.thYY_setpoint_hystheresis_h` |
| `cXXXX.thYY thermostat activation time max function`         | Activation period for max function [s].                                                          | `cXXXX.thYY_max_time`               |
| `cXXXX.thYY thermostat activation time max function cooling` | Activation period for max function in cooling [s].                                               | `cXXXX.thYY_max_time_c`             |
| `cXXXX.thYY thermostat activation time max function heating` | Activation period for max function in heating [s].                                               | `cXXXX.thYY_max_time_h`             |
| `cXXXX.thYY thermostat max temp external`                    | External sensor max temperature setpoint.                                                        | `cXXXX.thYY_max_temp`               |

### Every LC / LD / BC output (on the device of the light or blind)

| Entity name        | Description                                                       | Controller var                                            |
| ------------------ | ----------------------------------------------------------------- | --------------------------------------------------------- |
| `output timer`     | Timer that turns off the output automatically, 0 is no timer [s]. | `cXXXX.lcYY_output_mode_ZZ`, `cXXXX.ldYY_output_timer_ZZ` |
| `travel time up`   | Travel time of the blind from bottom to top [s].                  | `cXXXX.bcYY_blinds_time_up_ZZ`                            |
| `travel time down` | Travel time of the blind from top to bottom [s].                  | `cXXXX.bcYY_blinds_time_dn_ZZ`                            |

These are written through registers shared by all outputs of the module (index,
data and write request), as described by the module.

---

## select

All built-in `select` entities are disabled by default. Custom selects can be
added too, see [Custom entities](../README.md#custom-entities).

### Every TH (thermostat) expansion unit

| Entity name                                | Description                                                                                         | Controller var                  |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------- | ------------------------------- |
| `cXXXX.thYY thermostat temperature source` | Source of measured temperature: 0-internal sensor, 1-external sensor, 2-remote from another device. | `cXXXX.thYY_temperature_source` |
| `cXXXX.thYY thermostat display mode`       | Select what to display when thermostat is off: 0-nothing, 1- ---, 2-temperature.                    | `cXXXX.thYY_display_mode`       |

### HVAC (internal)

| Entity name                                       | Description                                                                  | Controller var                  |
| ------------------------------------------------- | ---------------------------------------------------------------------------- | ------------------------------- |
| `cXXXX HVAC mode`                                 | Hvac mode: 0-off, 1-heating, 2-cooling.                                      | `cXXXX.hvac_mode`               |
| `cXXXX HVAC thermostat config display mode`       | What to display when thermostat is off: 0-nothing, 1-dashes, 2-temperature.  | `cXXXX.hvac_display_mode`       |
| `cXXXX HVAC thermostat config temperature source` | Select temperature source: 0-internal, 1-external, 2-remote from controller. | `cXXXX.hvac_temperature_source` |

### Every LC / LD output (on the device of the light)

| Entity name  | Description                                                                                                                                                                  | Controller var                                         |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| `input mode` | How the input affects the output: toggle, staircase timer, motion sensor timer (also night only), inverse / door sensor (also night only), direct / doorbell or event only. | `cXXXX.lcYY_input_mode_ZZ`, `cXXXX.ldYY_input_mode_ZZ` |
| `color mode` | LD only: standard dimmer, RGB dimmer or white temperature. The light follows after a reload of the integration.                                                              | `cXXXX.ldYY_color_mode_ZZ`                             |

---

## switch

All `switch` entities are disabled by default.

### Every TH (thermostat) expansion unit

| Entity name                                  | Description                                                                                   | Controller var             |
| -------------------------------------------- | --------------------------------------------------------------------------------------------- | -------------------------- |
| `cXXXX.thYY thermostat window switch enable` | Select how window switch input is handled: 0-ignore input, 1-use input to disable thermostat. | `cXXXX.thYY_window_enable` |
| `cXXXX.thYY thermostat demand enable`        | Enable thermostat to control energy source: 0-off, 1-on.                                      | `cXXXX.thYY_demand_enable` |

### HVAC (internal)

| Entity name                                     | Description                                                                   | Controller var                      |
| ----------------------------------------------- | ----------------------------------------------------------------------------- | ----------------------------------- |
| `cXXXX HVAC outdoor temperature enable`         | Enable outdoor temperature measurement: 0-off, 1-on.                          | `cXXXX.outdoor_temperature_enable`  |
| `cXXXX HVAC wall temperature enable`            | Enable wall temperature measurement: 0-off, 1-on.                             | `cXXXX.wall_temperature_enable`     |
| `cXXXX HVAC water temperature enable`           | Enable water temperature measurement: 0-off, 1-on.                            | `cXXXX.water_temperature_enable`    |
| `cXXXX HVAC auxilary temperature enable`        | Enable auxilary temperature measurement: 0-off, 1-on.                         | `cXXXX.auxilary_temperature_enable` |
| `cXXXX HVAC automatic setpoint limits enable`   | Automatically set when operation mode is changed between heating and cooling. | `cXXXX.auto_limits_enable`          |
| `cXXXX HVAC thermostat fan option speed auto 1` | Enable fan speed auto 1.                                                      | `cXXXX.hvac_fan_option_b01`         |
| `cXXXX HVAC thermostat fan option speed auto 2` | Enable fan speed auto 2.                                                      | `cXXXX.hvac_fan_option_b02`         |
| `cXXXX HVAC thermostat fan option speed auto 3` | Enable fan speed auto 3.                                                      | `cXXXX.hvac_fan_option_b03`         |
| `cXXXX HVAC thermostat fan option speed max`    | Enable fan speed max.                                                         | `cXXXX.hvac_fan_option_b04`         |

---

## button

All `button` entities are disabled by default.

### Every TH (thermostat) expansion unit

| Entity name                                | Description                                                                        | Controller var                |
| ------------------------------------------ | ---------------------------------------------------------------------------------- | ----------------------------- |
| `cXXXX HVAC thYY config request`           | Set to update configuration parameters. It will reset automatically after sending. | `cXXXX.thYY_config1_req`      |
| `cXXXX HVAC thYY config read back request` | Request to read options back from thermostat.                                      | `cXXXX.thYY_options_back_req` |

### Every defined scene

| Entity name                   | Description                                      | Controller var                |
| ----------------------------- | ------------------------------------------------ | ----------------------------- |
| `cXXXX scenes store scene YY` | Store the current lights and blinds as scene YY. | `cXXXX.global_memory_request` |

---

## Devices

A device is created for each HIQ controller (diagnostics) and for every light,
blind, thermostat, HVAC and weather station.

Newer controllers report the card id and firmware of every IEX expansion unit
(`cXXXX.mmYY_iex_card_id` and `cXXXX.mmYY_firmware_version`). They are read once
when the integration starts, and shown on the light, blind and thermostat
devices of that unit:

| Device info | Taken from                                      | Example                                                                    |
| ----------- | ----------------------------------------------- | -------------------------------------------------------------------------- |
| Model       | card id                                         | `60` → `LC-10-IQ`, `63` → `BC-5-IQ`, `66` → `TH-2-IQ`, `72` → `LD-D10-IQ` |
| Firmware    | firmware version as `major.minor.build.release` | `1203` → `1.2.0.3`, `32767` → `32.7.6.7`                                   |

A card id without a known model is shown as `card <id>`. If one of both values
is missing or `0`, it is shown as `unknown`. If both are missing (older
controllers or an empty slot), the device shows `HIQ controller` and the
integration version. A firmware update of a unit is shown after the
integration is reloaded.

## Common attributes

| Attribute     | Value                                 |
| ------------- | ------------------------------------- |
| `description` | The description text from the PLC tag |
