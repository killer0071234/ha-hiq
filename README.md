# ha-hiq

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![pre-commit][pre-commit-shield]][pre-commit]
[![Black][black-shield]][black]

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]

[![Community Forum][forum-shield]][forum]

## Supported devices

This integration enables basic support for HIQ-Controllers (Cybro 2/3 PLC with HIQ software running on it from Robotina D.o.o or Cybrotech).

## Functionality

This integration is a local polling integration that connects to a running CybroScgiServer from Cybrotech.
To use this integration you need to have a running scgi server.
Please use one of the 3 methods to run the scgi server.
Without a running scgi server it is not possible to use this integration!

- Homeassistant Addon CybroScgiServer (Recommended)

  [![Open this add-on in your Home Assistant instance.][addon-badge]][addon]

- Own Docker container on own Docker host.

  [![dockerhub][scgi-docker-shield]][scgi-docker]

- Native manual install from source.

## Supported entities

During creation of the device it scans for supported device types and creates it in home assistant.
If the `general_error` of the HIQ expansion unit is set, the device will be ignored (Default behaviour of hiq software).
To add all possible entities there exists a option.

Currently supported are:

- [light](#light)
- [cover](#cover)
- [climate](#climate)
- [binary_sensor](#binary_sensor)
- [sensor](#sensor)
- [number](#number)
- [select](#select)
- [switch](#switch)

---

### light<a name="light"></a>

Supported HIQ expansion units:

- LC-10-IQ (light on / off supported)
- LC-8-IQ (light on / off supported)
- LD-D10-IQ (light on / off, brightness and RGB supported)
- LD-D8-IQ (light on / off and brightness supported)
- LD-P4-IQ (light on / off, brightness and RGB supported)
- LD-V4-IQ (light on / off, brightness and RGB supported)
- Virtual LC (light on / off supported)

---

### cover<a name="cover"></a>

Blinds in the HIQ controller are called [cover](#cover) devices in HA.

Supported HIQ expansion units:

- BC-5-IQ
- Virtual BC

Possible commands for the blinds are:

- open cover
- close cover
- stop cover
- set position

---

### climate<a name="climate"></a>

TH (thermostat) devices in the HIQ controller are called [climate](#climate) devices in HA.

Supported HIQ expansion units:

- TH-X-IQ

Possible commands for the thermostats are:

- Turn heating / cooling on / off
- Set setpoint temperature

---

### binary_sensor<a name="binary_sensor"></a>

To have a basic diagnostic, there are some `binary_sensor` Entities exposed.

#### For the controller:

| Entity name            | Description                                                                        | Enabled |
| ---------------------- | ---------------------------------------------------------------------------------- | ------- |
| `cXXXX.general_error`  | Logical or of IEX general errors, indicates that at least one module has an error. | yes     |
| `cXXXX.retentive_fail` | Indicates that retentive memory failed.                                            | yes     |
| `cXXXX.scan_overrun`   | Too long scan execution caused scan overrun error.                                 | yes     |

#### For every IEX expansion unit:

| Entity name                | Description                                                                  | Enabled |
| -------------------------- | ---------------------------------------------------------------------------- | ------- |
| `cXXXX.YYYY_general_error` | Combined system error (timeout or program error), module is not operational. | yes     |

#### For TH (thermostat) expansion unit:

| Entity name                    | Description                            | Controller var     | Enabled       |
| ------------------------------ | -------------------------------------- | -------------------| ------------- |
| `cXXXX.thYY thermostat window` | Indicate state of window switch input. | `cXXXX.thYY_ix00`  | if configured |
| `cXXXX.thYY thermostat output` | Radiator output.                       | `cXXXX.thYY_output`| yes           |

XXXX is the NAD of the controller, and YYYY is the IEX module prefix

---

### sensor<a name="sensor"></a>

To have a basic diagnostic, there are some `sensor` Entities exposed.

#### For the controller:

| Entity name                | Description                                                         | Enabled |
| -------------------------- | ------------------------------------------------------------------- | ------- |
| `cXXXX.scan_time`          | Last scan execution time [ms].                                      | no      |
| `cXXXX.scan_time_max`      | Maximal scan execution time encountered since program started [ms]. | no      |
| `cXXXX.scan_frequency`     | Actual number of scans per second.                                  | no      |
| `cXXXX.cybro_power_supply` | Measured power supply voltage [V]. Measuring range is 0..40V.       | no      |
| `cXXXX.cybro_uptime`       | Number of operating hours since power-on [h].                       | no      |
| `cXXXX.operating_hours`    | Total number of operating hours [h].                                | no      |
| `cXXXX.sys.ip_port`        | IP address and UDP port of the controller.                          | no      |

#### For every IEX expansion unit:

| Entity name                   | Description                                                   | Enabled |
| ----------------------------- | ------------------------------------------------------------- | ------- |
| `cXXXX.YYYY_iex_power_supply` | Measured power supply voltage [V]. Measuring range is 0..40V. | no      |

#### power meter:

In presence of a power meter, it will add the following Entities:

| Entity name                 | Description                     | Enabled |
| --------------------------- | ------------------------------- | ------- |
| `cXXXX.power_meter_power`   | Measured power consumption [W]. | yes     |
| `cXXXX.power_meter_energy`  | Energy consumption total [kWh]. | yes     |
| `cXXXX.power_meter_voltage` | Measured AC voltage [V].        | no      |

#### temperatures:

In presence of expansion units with temperature / humidity sensors, it will add the following Entities:

| Entity name              | Description                             | Enabled                          |
| ------------------------ | --------------------------------------- | -------------------------------- |
| `cXXXX.YYYY_temperature` | Measured temperature [°C].              | if module has no `general_error` |
| `cXXXX.YYYY_humidity`    | Measured relative humidity (0..100%rh). | if module has no `general_error` |

#### For TH (thermostat) expansion unit:

| Entity name                           | Description                                          | Controller var            | Enabled |
| ------------------------------------- | ---------------------------------------------------- | --------------------------| ------- |
| `cXXXX.thYY thermostat temperature`   | Measured temperature (internal, external or remote). | `cXXXX.thYY_temperature`  | yes     |
| `cXXXX.thYY thermostat temperature 1` | Measured external temperature.                       | `cXXXX.thYY_temperature_1`| yes     |
| `cXXXX.thYY thermostat humidity`      | Measured relative humidity.                          | `cXXXX.thYY_humidity`     | yes     |

#### For hvac (internal):

| Entity name                            | Description                                        | Controller var               | Enabled               |
| -------------------------------------- | -------------------------------------------------- | -----------------------------| --------------------- |
| `cXXXX.thYY HVAC outdoor temperature`  | Measured outdoor temperature.                      | `cXXXX.outdoor_temperature`  | if `zz_enable` is set |
| `cXXXX.thYY HVAC wall temperature`     | Measured temperature within building construction. | `cXXXX.wall_temperature`     | if `zz_enable` is set |
| `cXXXX.thYY HVAC water temperature`    | Measured temperature of heating/cooling medium.    | `cXXXX.water_temperature`    | if `zz_enable` is set |
| `cXXXX.thYY HVAC auxilary temperature` | Measured temperature of auxilary sensor.           | `cXXXX.auxilary_temperature` | if `zz_enable` is set |

XXXX is the NAD of the controller, and YYYY is the IEX module prefix (eg: lc00, bc02..)

---

### number<a name="number"></a>

To set some parameters in the controller, there are some `number` Entities exposed.

#### For TH (thermostat) expansion unit:

| Entity name                                                  | Description                                                                                      | Controller var                      |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ | ----------------------------------- |
| `cXXXX.thYY thermostat setpoint idle`                        | Secondary setpoint, used when thermostat is off. Zero means output is off.                       | `cXXXX.thYY_setpoint_idle`          |
| `cXXXX.thYY thermostat setpoint idle cooling`                | Secondary setpoint for cooling, used when thermostat is off. Zero means output is off.           | `cXXXX.thYY_setpoint_idle_c`        |
| `cXXXX.thYY thermostat setpoint idle heating`                | Secondary heating setpoint, used when thermostat is off. Zero means output is off.               | `cXXXX.thYY_setpoint_idle_h`        |
| `cXXXX.thYY thermostat setpoint offset`                      | Setpoint correction, used to affect regulated temperature without changing setpoint.             | `cXXXX.thYY_setpoint_offset`        |
| `cXXXX.thYY thermostat setpoint offset cooling`              | Setpoint correction for cooling, used to affect regulated temperature without changing setpoint. | `cXXXX.thYY_setpoint_offset_c`      |
| `cXXXX.thYY thermostat setpoint offset heating`              | Setpoint correction for heating, used to affect regulated temperature without changing setpoint. | `cXXXX.thYY_setpoint_offset_h`      |
| `cXXXX.thYY thermostat hystheresis`                          | Hysteresis for on/off regulation. Defined as distance between on and off points.                 | `cXXXX.thYY_setpoint_hystheresis`   |
| `cXXXX.thYY thermostat hystheresis cooling`                  | Hysteresis for on/off regulation in cooling mode. Defined as distance between on and off points. | `cXXXX.thYY_setpoint_hystheresis_c` |
| `cXXXX.thYY thermostat hystheresis heating`                  | Hysteresis for on/off regulation in heating mode. Defined as distance between on and off points. | `cXXXX.thYY_setpoint_hystheresis_h` |
| `cXXXX.thYY thermostat activation time max function`         | Activation period for max function [s].                                                          | `cXXXX.thYY_max_time`               |
| `cXXXX.thYY thermostat activation time max function cooling` | Activation period for max function in cooling [s].                                               | `cXXXX.thYY_max_time_c`             |
| `cXXXX.thYY thermostat activation time max function heating` | Activation period for max function in heating [s].                                               | `cXXXX.thYY_max_time_h`             |
| `cXXXX.thYY thermostat max temp external`                    | External sensor max temperature setpoint.                                                        | `cXXXX.thYY_max_temp`               |

By default all of the `number` entities are disabled.

Note: Not all entities are supported by stock HIQ firmware!
Some of them are additions to HIQ functionality.

---

### select<a name="select"></a>

To set some parameters in the controller, there are some `select` Entities exposed.

#### For TH (thermostat) expansion unit:

| Entity name                                | Description                                                                                         | Controller var                  |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------- | ------------------------------- |
| `cXXXX.thYY thermostat temperature source` | Source of measured temperature: 0-internal sensor, 1-external sensor, 2-remote from another device. | `cXXXX.thYY_temperature_source` |
| `cXXXX.thYY thermostat display mode`       | Select what to display when thermostat is off: 0-nothing, 1- ---, 2-temperature.                    | `cXXXX.thYY_display_mode`       |

#### For hvac (internal):

| Entity name            | Description                             | Controller var    |
| ---------------------- | --------------------------------------- | ----------------- |
| `cXXXX.thYY HVAC mode` | Hvac mode: 0-off, 1-heating, 2-cooling. | `cXXXX.hvac_mode` |

By default all of the `select` entities are disabled.

---

### switch<a name="switch"></a>

To set some parameters in the controller, there are some `switch` Entities exposed.

#### For TH (thermostat) expansion unit:

| Entity name                                  | Description                                                                                   | Controller var             |
| -------------------------------------------- | --------------------------------------------------------------------------------------------- | -------------------------- |
| `cXXXX.thYY thermostat window switch enable` | Select how window switch input is handled: 0-ignore input, 1-use input to disable thermostat. | `cXXXX.thYY_window_enable` |
| `cXXXX.thYY thermostat demand enable`        | Enable thermostat to control energy source: 0-off, 1-on.                                      | `cXXXX.thYY_demand_enable` |

#### For hvac (internal):

| Entity name                                        | Description                                                                   | Controller var                      |
| -------------------------------------------------- | ----------------------------------------------------------------------------- | ----------------------------------- |
| `cXXXX.thYY HVAC outdoor temperature enable`       | Enable outdoor temperature measurement: 0-off, 1-on.                          | `cXXXX.outdoor_temperature_enable`  |
| `cXXXX.thYY HVAC wall temperature enable`          | Enable wall temperature measurement: 0-off, 1-on.                             | `cXXXX.wall_temperature_enable`     |
| `cXXXX.thYY HVAC water temperature enable`         | Enable water temperature measurement: 0-off, 1-on.                            | `cXXXX.water_temperature_enable`    |
| `cXXXX.thYY HVAC auxilary temperature enable`      | Enable auxilary temperature measurement: 0-off, 1-on.                         | `cXXXX.auxilary_temperature_enable` |
| `cXXXX.thYY HVAC automatic setpoint limits enable` | Automatically set when operation mode is changed between heating and cooling. | `cXXXX.auto_limits_enable`          |

By default all of the `switch` entities are disabled.

---

### Common Attributes

| Attribute   | Example Values (comma separated)      |
| ----------- | ------------------------------------- |
| description | the description text from the PLC tag |

### Devices

A device is created for each HIQ-controller (diagnostics) and for every light, blind.

---

### Services

To forward some smartphone events directly to the HIQ-controller some services are exposed.

| Service          | Description                                                                                            |
| ---------------- | ------------------------------------------------------------------------------------------------------ |
| Presence signal  | Set the smartphone presence signal                                                                     |
| Charge on event  | Set the smartphone charge on (connect charger) event                                                   |
| Charge off event | Set the smartphone charge off (disconnect charger) event                                               |
| Home event       | Set the smartphone home event                                                                          |
| Precede event    | Set the smartphone Precede event (used in advance for triggering some actions before the alarm occurs) |
| Write tag        | Write a custom tag with a custom value in the controller (any accessible tag is allowed)               |

{% if not installed %}

## Installation

### HACS

1. Install [HACS](https://hacs.xyz/)
2. Go to HACS "Integrations >" section
3. In the lower right click "+ Explore & Download repositories"
4. Search for "HIQ" and add it
5. Restart Home Assistant
6. In the Home Assistant (HA) UI go to "Configuration"
7. Click "Integrations"
8. Click "+ Add Integration"
9. Search for "HIQ"

### Manual

1. Using the tool of choice open the directory (folder) for your [HA configuration](https://www.home-assistant.io/docs/configuration/) (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `hiq`.
4. Download _all_ the files from the `custom_components/hiq/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant
7. In the Home Assistant (HA) UI go to "Configuration"
8. Click "Integrations"
9. Click "+ Add Integration"
10. Search for "HIQ"

{% endif %}

## Configuration (Important! Please Read)

Config is done in the HA integrations UI.

### Disable new entities

If you prefer new entities to be disabled by default:

1. In the Home Assistant (HA) UI go to "Configuration"
2. Click "Integrations"
3. Click the three dots in the bottom right corner for the HIQ integration
4. Click "System options"
5. Disable "Enable newly added entities"

## Tested Devices

- HC-HIQ v3.0.3 Software running on a Cybro-3 controller with FW: 3.2.3, cybroscgiserver v3.1.3 running in a docker container

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](https://github.com/killer0071234/ha-hiq/blob/master/CONTRIBUTING.md)

## Credits

Code template was mainly taken from [@amosyuen](https://github.com/amosyuen)'s [ha-tplink-deco][ha_tplink_deco] integration

---

[addon-badge]: https://my.home-assistant.io/badges/supervisor_addon.svg
[addon]: https://my.home-assistant.io/redirect/supervisor_addon/?addon=85493909_cybroscgiserver&repository_url=https%3A%2F%2Fgithub.com%2Fkiller0071234%2Fha-addon-repository
[ha_tplink_deco]: https://github.com/amosyuen/ha-tplink-deco
[black]: https://github.com/psf/black
[black-shield]: https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/killer0071234/ha-hiq.svg?style=for-the-badge
[commits]: https://github.com/killer0071234/ha-hiq/commits/main
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[exampleimg]: example.png
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/killer0071234/ha-hiq.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-@killer0071234-blue.svg?style=for-the-badge
[pre-commit]: https://github.com/pre-commit/pre-commit
[pre-commit-shield]: https://img.shields.io/badge/pre--commit-enabled-brightgreen?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/killer0071234/ha-hiq.svg?style=for-the-badge
[releases]: https://github.com/killer0071234/ha-hiq/releases
[user_profile]: https://github.com/killer0071234
[scgi-docker-shield]: https://img.shields.io/badge/dockerhub-cybroscgiserver-brightgreen.svg?style=for-the-badge
[scgi-docker]: https://hub.docker.com/r/killer007/cybroscgiserver
