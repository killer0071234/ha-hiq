# Entity reference

All entities the HIQ-Home integration creates, by platform. Back to the
[README](../README.md).

In the tables, `XXXX` is the NAD of the controller, `YY` the number of the
expansion unit or thermostat, `ZZ` the output of a unit, and `YYYY` the IEX
module prefix (e.g. `lc00`, `bc02`).

**Name** is the name of the entity as shown in Home Assistant, after the name of
its device (e.g. device `c1000.th00 thermostat`, entity `Setpoint eco`).

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

### Device `cXXXX diagnostic`

| Name                                 | Controller var             | Enabled by default |
| ------------------------------------ | -------------------------- | ------------------ |
| Presence                             | `cXXXX.presence_indicator`  | yes                |
| Nighttime                            | `cXXXX.low_light_indicator` | yes                |
| General error                        | `cXXXX.general_error`       | no                 |
| Controller program cycle overrun     | `cXXXX.scan_overrun`        | no                 |
| Controller retentive memory failure  | `cXXXX.retentive_fail`      | no                 |
| `YYYY` general error (per IEX unit)  | `cXXXX.YYYY_general_error`  | no                 |
| EnOcean general error                | `cXXXX.eno_general_error`   | no                 |

`General error` is the logical or of the IEX general errors: at least one unit
has an error. The error of a unit means timeout or program error, the unit is
not operational.

### Device `cXXXX.thYY thermostat`

| Name   | Controller var       | Enabled by default |
| ------ | -------------------- | ------------------ |
| Window | `cXXXX.thYY_ix00`    | no                 |
| Output | `cXXXX.thYY_output`  | no                 |

`Window` is the window switch input, on (open) when the input is `0`.
`Output` is the radiator output.

---

## sensor

Custom sensors from any controller variable can be added too, see
[Custom entities](../README.md#custom-entities).

### Device `cXXXX diagnostic`

| Name                       | Controller var                | Unit | Enabled by default |
| -------------------------- | ----------------------------- | ---- | ------------------ |
| Controller address         | `cXXXX.sys.ip_port`           |      | no                 |
| Scan time                  | `cXXXX.scan_time`             | ms   | no                 |
| Scan time maximum          | `cXXXX.scan_time_max`         | ms   | no                 |
| Controller program cycles  | `cXXXX.scan_frequency`        | Hz   | no                 |
| Controller uptime          | `cXXXX.cybro_uptime`          | h    | no                 |
| Controller operation hours | `cXXXX.operating_hours`       | h    | no                 |
| Controller supply voltage  | `cXXXX.cybro_power_supply`    | V    | no                 |
| IEX voltage                | `cXXXX.iex_power_supply`      | V    | no                 |
| `YYYY` IEX voltage         | `cXXXX.YYYY_iex_power_supply` | V    | no                 |

`Controller address` is the IP address and UDP port of the controller.
`Scan time maximum` is the longest scan since the program started. The supply
voltages are measured in the range 0..40 V.

### Device `cXXXX temperatures`

For the temperature / humidity units (`opYY`, `tsYY`, `fcYY`). Units with
`general_error` set are skipped.

| Name                          | Controller var             | Unit | Enabled by default |
| ----------------------------- | -------------------------- | ---- | ------------------ |
| `YYYY` temperature            | `cXXXX.YYYY_temperature`   | °C   | yes                |
| `YYYY` internal temperature   | `cXXXX.YYYY_temperature_0` | °C   | yes                |
| `YYYY` external temperature   | `cXXXX.YYYY_temperature_1` | °C   | yes                |
| `YYYY` humidity               | `cXXXX.YYYY_humidity`      | %    | yes                |

### Device `cXXXX power meter`

Created only while `cXXXX.power_meter_error` is `0`. `N` is the phase (1, 2, 3).

| Name          | Controller var                     | Unit | Enabled by default |
| ------------- | ---------------------------------- | ---- | ------------------ |
| Power         | `cXXXX.power_meter_power`          | W    | yes                |
| Power LN      | `cXXXX.power_meter_powerN`         | W    | yes                |
| Energy        | `cXXXX.power_meter_energy`         | kWh  | yes                |
| Energy real   | `cXXXX.power_meter_energy_real`    | kWh  | no                 |
| Energy (Wh)   | `cXXXX.power_meter_energy_watthours` | Wh | no                 |
| Voltage       | `cXXXX.power_meter_voltage`        | V    | no                 |
| Voltage LN    | `cXXXX.power_meter_voltageN`       | V    | no                 |
| Current LN    | `cXXXX.power_meter_currentN`       | mA   | no                 |

A voltage above 300 is taken as 0.1 V steps (some meters report it so).

### Device `cXXXX.thYY thermostat`

Thermostats with `general_error` set are skipped.

| Name                       | Controller var             | Unit | Enabled by default |
| -------------------------- | -------------------------- | ---- | ------------------ |
| Temperature                | `cXXXX.thYY_temperature`   | °C   | yes                |
| External temperature       | `cXXXX.thYY_temperature_1` | °C   | yes                |
| Humidity                   | `cXXXX.thYY_humidity`      | %    | yes                |
| Light sensor               | `cXXXX.thYY_light_sensor`  | %    | no                 |
| Max function remain timer  | `cXXXX.thYY_max_timer`     | s    | no                 |

`Temperature` is the regulated temperature (internal, external or remote,
see `Temperature source sensor`).

### Device `cXXXX HVAC`

| Name                  | Controller var               | Unit | Enabled by default                         |
| --------------------- | ---------------------------- | ---- | ------------------------------------------ |
| Outdoor temperature   | `cXXXX.outdoor_temperature`  | °C   | if `cXXXX.outdoor_temperature_enable` is 1   |
| Wall temperature      | `cXXXX.wall_temperature`     | °C   | if `cXXXX.wall_temperature_enable` is 1      |
| Water temperature     | `cXXXX.water_temperature`    | °C   | if `cXXXX.water_temperature_enable` is 1     |
| Auxiliary temperature | `cXXXX.auxilary_temperature` | °C   | if `cXXXX.auxilary_temperature_enable` is 1  |

The wall temperature is measured within the building construction, the water
temperature is the one of the heating / cooling medium.

---

## number

All `number` entities are disabled by default.

### Device `cXXXX.thYY thermostat`

Most values exist in three variants: plain, for cooling (`_c`) and for heating
(`_h`), e.g. `Setpoint eco`, `Setpoint eco cooling` and `Setpoint eco heating`.

| Name                          | Controller var                         | Unit | Range      |
| ----------------------------- | -------------------------------------- | ---- | ---------- |
| Setpoint eco                  | `cXXXX.thYY_setpoint_idle[_c\|_h]`     | °C   | 0..40      |
| Setpoint offset               | `cXXXX.thYY_setpoint_offset[_c\|_h]`   | °C   | -5..5      |
| Setpoint min                  | `cXXXX.thYY_setpoint_lo[_c\|_h]`       | °C   | 0..40      |
| Setpoint max                  | `cXXXX.thYY_setpoint_hi[_c\|_h]`       | °C   | 0..40      |
| Hysteresis                    | `cXXXX.thYY_hysteresis[_c\|_h]`        | °C   | 0.1..10    |
| Activation time max function  | `cXXXX.thYY_max_time[_c\|_h]`          | s    | 0..3600    |
| Temperature offset            | `cXXXX.thYY_temperature_offset`        | °C   | -5..5      |
| Max temperature external      | `cXXXX.thYY_max_temp`                  | °C   | 0..40      |

- **Setpoint eco**: secondary setpoint, used when the thermostat is off. Zero
  means the output is off.
- **Setpoint offset**: correction of the regulated temperature without changing
  the setpoint.
- **Hysteresis**: distance between the on and off points of the on / off
  regulation.
- **Temperature offset**: measurement correction of the thermostat sensor. It is
  sent to the thermostat with `cXXXX.thYY_config1_req`.
- **Max temperature external**: max temperature of the external sensor.

### Device `cXXXX HVAC`

| Name                  | Controller var                  | Unit | Range |
| --------------------- | ------------------------------- | ---- | ----- |
| Setpoint eco heating  | `cXXXX.setpoint_idle_heating`   | °C   | 0..40 |
| Setpoint min heating  | `cXXXX.setpoint_lo_heating`     | °C   | 0..40 |
| Setpoint max heating  | `cXXXX.setpoint_hi_heating`     | °C   | 0..40 |
| Setpoint eco cooling  | `cXXXX.setpoint_idle_cooling`   | °C   | 0..40 |
| Setpoint min cooling  | `cXXXX.setpoint_lo_cooling`     | °C   | 0..40 |
| Setpoint max cooling  | `cXXXX.setpoint_hi_cooling`     | °C   | 0..40 |

### Device of every LC / LD / BC output (light or blind)

| Name             | Controller var                                            | Unit | Range    |
| ---------------- | --------------------------------------------------------- | ---- | -------- |
| Output timer     | `cXXXX.lcYY_output_mode_ZZ`, `cXXXX.ldYY_output_timer_ZZ` | s    | 0..9999  |
| Travel time up   | `cXXXX.bcYY_blinds_time_up_ZZ`                            | s    | 0..999.9 |
| Travel time down | `cXXXX.bcYY_blinds_time_dn_ZZ`                            | s    | 0..999.9 |

`Output timer` turns off the output automatically, 0 is no timer. The travel
times are the ones of the blind from bottom to top and back. These values are
written through registers shared by all outputs of the module (index, data and
write request), as described by the module.

---

## select

All built-in `select` entities are disabled by default. Custom selects can be
added too, see [Custom entities](../README.md#custom-entities).

### Device `cXXXX.thYY thermostat`

| Name                      | Controller var                  | Options                                                   |
| ------------------------- | ------------------------------- | --------------------------------------------------------- |
| Temperature source sensor | `cXXXX.thYY_temperature_source` | 0 internal, 1 external, 2 remote from another device      |
| Display mode              | `cXXXX.thYY_display_mode`       | what is shown when off: 0 nothing, 1 `---`, 2 temperature |
| Fan mode limit            | `cXXXX.thYY_fan_limit`          | 0 off, 1 fan 1, 2 fan 2, 3 fan 3, 4 max                   |

### Device `cXXXX HVAC`

| Name                      | Controller var                  | Options                                                   |
| ------------------------- | ------------------------------- | --------------------------------------------------------- |
| Operation mode HVAC       | `cXXXX.hvac_mode`               | 0 off, 1 heating, 2 cooling                               |
| Temperature source sensor | `cXXXX.hvac_temperature_source` | 0 internal, 1 external, 2 remote from the controller      |
| Display mode              | `cXXXX.hvac_display_mode`       | what is shown when off: 0 nothing, 1 `---`, 2 temperature |

### Device of every LC / LD output (light)

| Name       | Controller var                                         | Options                                                                                                                                        |
| ---------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Input mode | `cXXXX.lcYY_input_mode_ZZ`, `cXXXX.ldYY_input_mode_ZZ` | 0 toggle, 1 staircase timer, 2 motion sensor timer, 3 motion night only, 4 inverse / door sensor, 5 inverse night only, 6 direct / doorbell, 7 event only |
| Color mode | `cXXXX.ldYY_color_mode_ZZ` (LD only)                   | 0 standard dimmer, 1 RGB, 2 white temperature                                                                                                  |

The light follows a changed color mode after a reload of the integration.

---

## switch

All `switch` entities are disabled by default.

### Device `cXXXX.thYY thermostat`

| Name                 | Controller var             | When on                                    |
| -------------------- | -------------------------- | ------------------------------------------ |
| Window switch enable | `cXXXX.thYY_window_enable` | an open window input disables the thermostat |
| Demand enable        | `cXXXX.thYY_demand_enable` | the thermostat controls the energy source  |

### Device `cXXXX HVAC`

| Name                             | Controller var                      | When on                                                       |
| -------------------------------- | ----------------------------------- | ------------------------------------------------------------- |
| Enable outdoor temperature       | `cXXXX.outdoor_temperature_enable`  | outdoor temperature is measured                               |
| Enable wall temperature          | `cXXXX.wall_temperature_enable`     | wall temperature is measured                                  |
| Enable water temperature         | `cXXXX.water_temperature_enable`    | water temperature is measured                                 |
| Enable auxiliary temperature     | `cXXXX.auxilary_temperature_enable` | auxiliary temperature is measured                             |
| Enable automatic setpoint limits | `cXXXX.auto_limits_enable`          | setpoint limits are set when switching heating / cooling      |
| Fan auto speed limit 1           | `cXXXX.hvac_fan_option_b01`         | fan speed auto 1 is allowed                                   |
| Fan auto speed limit 2           | `cXXXX.hvac_fan_option_b02`         | fan speed auto 2 is allowed                                   |
| Fan auto speed limit 3           | `cXXXX.hvac_fan_option_b03`         | fan speed auto 3 is allowed                                   |
| Fan speed limit max              | `cXXXX.hvac_fan_option_b04`         | fan speed max is allowed                                      |

---

## button

All `button` entities are disabled by default.

### Device `cXXXX.thYY thermostat`

Only when the controller has the HVAC parameters (e.g.
`cXXXX.hvac_display_mode`).

| Name                 | Controller var                | What it does                                        |
| -------------------- | ----------------------------- | --------------------------------------------------- |
| Config write request | `cXXXX.thYY_config1_req`      | Sends the configuration parameters to the thermostat |
| Config read request  | `cXXXX.thYY_options_back_req` | Reads the options back from the thermostat          |

### Device `cXXXX scenes`

| Name           | Controller var                | What it does                                          |
| -------------- | ----------------------------- | ----------------------------------------------------- |
| Store scene YY | `cXXXX.global_memory_request` | Stores the current lights and blinds as scene YY       |

One button for every defined scene.

---

## Devices

| Device                  | Holds                                                               |
| ----------------------- | ------------------------------------------------------------------- |
| `cXXXX diagnostic`      | Diagnostics of the controller and the error flags of the IEX units |
| `cXXXX temperatures`    | Temperature / humidity units                                        |
| `cXXXX power meter`     | Power meter                                                         |
| `cXXXX HVAC`            | HVAC parameters and temperatures                                    |
| `cXXXX.thYY thermostat` | Climate entity and parameters of a thermostat                       |
| `cXXXX scenes`          | Scenes and their store buttons                                      |
| `cXXXX weather`         | Weather station                                                     |
| `cXXXX custom`          | Custom sensors and selects                                          |
| light / blind           | One per LC / LD / BC output, with its parameters                    |

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

| Attribute     | Value                                       |
| ------------- | ------------------------------------------- |
| `description` | The description text from the PLC tag       |
| `variable`    | The controller variable behind the entity   |
