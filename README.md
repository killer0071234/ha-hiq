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

## Prerequisites

The integration polls the HIQ controllers in the local network. It reaches a
controller in one of two ways, chosen per controller when it is added:

- **Direct connection** (recommended): Home Assistant talks to the controller
  over UDP port 8442 (A-bus), no scgi server needed.
- **Through the CybroScgiServer**: the way of the versions before 0.7.0. Still
  useful for controllers that Home Assistant can't reach directly (another
  site, behind NAT).

Home Assistant 2026.10 or newer is required. Install the integration from the
HACS store (or manually, see [Installation](#installation)):

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.][hacs-integration-badge]][hacs-integration]

### Direct connection

- Home Assistant and the controllers should be in the same network segment.
  The controllers are found by broadcast. For a controller in another segment
  or VLAN, enter its IP address when adding it.
- Home Assistant in Docker needs `network_mode: host`. With published ports
  only, broadcasts don't arrive: enter the IP address of every controller.
- If an A-bus password is set in the controller, enter it when adding the
  controller.
- **UDP port 8442 on the Home Assistant host.** The CybroScgiServer and the
  Cybro Edge Toolkit apps use this port too. While such an app runs, the
  integration leaves the port to it and uses another one: polling works, but
  the controllers can't send data to Home Assistant on their own. A repair
  under **Settings → System → Repairs** names the app and offers to stop it
  (and to turn off its start on boot). Entries that still use the scgi server
  of the app stop working then, so switch them to the direct connection first.
  If the port is freed in another way, it is taken within 15 minutes.

### Through the scgi server

The scgi server must be running before the controller is added. Use one of:

- Home Assistant app CybroScgiServer

  [![Open this app in your Home Assistant instance.][addon-badge]][addon]

- Own Docker container on own Docker host.

  [![dockerhub][scgi-docker-shield]][scgi-docker]

- Native manual install from source.

## Adding controllers

**Settings → Devices & services → Add integration → HIQ-Home**, then choose
the connection:

- **Directly over the network** searches the local network first and lists
  the HIQ controllers that aren't set up yet, with NAD, IP address and HIQ
  program version. Pick one, or choose to enter the address (NAD) manually.
- **Through the CybroScgiServer** asks for the host and port of the scgi
  server and the NAD.

Once one controller is set up, the integration searches the network after
Home Assistant started and every 15 minutes. New HIQ controllers appear under
**Settings → Devices & services → Discovered**. A controller that gets its IP
address by DHCP (Cybrotech MAC address `00:CB:00:…`) can also be found this
way when it connects to the network.

Only controllers running the HIQ program are offered. Other controllers can
still be added by entering their NAD.

### Switching an entry to the direct connection

When the search finds a controller that is set up through the scgi server, it
offers to connect it directly. The entities, custom sensors and custom selects
stay. The connection of an entry can also be changed with **Reconfigure** in
the menu of the entry (in both directions).

### IP address changes

Controllers added without IP address are found by broadcast and follow a new
IP address on their own. For a controller with a fixed IP address in the
entry, the new address is stored when the search, DHCP or a socket frame of
the controller shows it.

## Supported entities

During creation of the device it scans for supported device types and creates it in home assistant.
If the `general_error` of the HIQ expansion unit is set, the device will be ignored (Default behaviour of hiq software).

Currently supported are:

- [light](#light)
- [cover](#cover)
- [scene](#scene)
- [climate](#climate)
- [binary_sensor](#binary_sensor)
- [sensor](#sensor)
- [number](#number)
- [select](#select)
- [switch](#switch)
- [button](#button)

---

### light<a name="light"></a>

Supported HIQ expansion units:

- LC-10-IQ (light on / off supported)
- LC-8-IQ (light on / off supported)
- LD-D10-IQ (light on / off, brightness, RGB and white temperature supported)
- LD-D8-IQ (light on / off and brightness supported)
- LD-P4-IQ (light on / off, brightness and RGB supported)
- LD-V4-IQ (light on / off, brightness and RGB supported)
- Virtual LC (light on / off supported)

The color mode of each LD-D10-IQ output (`ldNN_color_mode_MM`: standard dimmer,
RGB or white temperature) is read when the integration starts. The color of an
output can only be written, not read back from the module, so the last color set
from Home Assistant is shown (and kept over a restart). White temperature 0..100 %
is shown as 2700..6500 K.

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

### scene<a name="scene"></a>

The scenes of lights and blinds (SC-4-IQ) are [scene](#scene) devices in HA.
A scene is created for every defined scene of `cXXXX.scene_status[0..31]` (status is
not `-1`) when the integration starts. Activating a scene writes its number to
`cXXXX.global_scene_request`. The attribute `active` shows if the scene is active on
the controller.

---

### climate<a name="climate"></a>

TH (thermostat) devices in the HIQ controller are called [climate](#climate) devices in HA.

Supported HIQ expansion units:

- TH-X-IQ

Possible commands for the thermostats are:

- Turn heating / cooling on / off
- Set setpoint temperature
- Set presets eco (idle) / comfort (on) / boost (fan max)

---

### binary_sensor<a name="binary_sensor"></a>

To have a basic diagnostic, there are some `binary_sensor` Entities exposed.

#### For the controller:

| Entity name            | Description                                                                        | Enabled |
| ---------------------- | ---------------------------------------------------------------------------------- | ------- |
| `cXXXX.general_error`  | Logical or of IEX general errors, indicates that at least one module has an error. | no      |
| `cXXXX.retentive_fail` | Indicates that retentive memory failed.                                            | no      |
| `cXXXX.scan_overrun`   | Too long scan execution caused scan overrun error.                                 | no      |

#### Indicators of the controller:

| Entity name                  | Description                               | Controller var              | Enabled |
| ---------------------------- | ----------------------------------------- | --------------------------- | ------- |
| `cXXXX diagnostic presence`  | Indicates that somebody is at home.       | `cXXXX.presence_indicator`  | yes     |
| `cXXXX diagnostic nighttime` | Indicates that the sun is below horizon.  | `cXXXX.low_light_indicator` | yes     |

#### For every IEX expansion unit:

| Entity name                | Description                                                                  | Enabled |
| -------------------------- | ---------------------------------------------------------------------------- | ------- |
| `cXXXX.YYYY_general_error` | Combined system error (timeout or program error), module is not operational. | no      |

#### For TH (thermostat) expansion unit:

| Entity name                    | Description                            | Controller var     | Enabled       |
| ------------------------------ | -------------------------------------- | -------------------| ------------- |
| `cXXXX.thYY thermostat window` | Indicate state of window switch input. | `cXXXX.thYY_ix00`  | no            |
| `cXXXX.thYY thermostat output` | Radiator output.                       | `cXXXX.thYY_output`| no            |

XXXX is the NAD of the controller, and YYYY is the IEX module prefix

---

### sensor<a name="sensor"></a>

To have a basic diagnostic, there are some `sensor` Entities exposed.

It is also possible to add custom sensors from variables in the HIQ controller.
To add custom sensors, navigate to HIQ integration, click on `configure`, choose
`Add custom entity` and then `Sensor`.
Custom sensors are changed with `Configure custom entity` and deleted with
`Remove custom entities`.

[![Open your Home Assistant instance and show an integration.][integration-badge]][integration]

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

#### For every TH (thermostat) expansion unit:

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

#### For every TH (thermostat) expansion unit:

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

#### For every LC / LD / BC output (on the device of the light or blind):

| Entity name        | Description                                                  | Controller var                                          |
| ------------------ | ------------------------------------------------------------ | ------------------------------------------------------- |
| `output timer`     | Timer that turns off the output automatically, 0 is no timer [s]. | `cXXXX.lcYY_output_mode_ZZ`, `cXXXX.ldYY_output_timer_ZZ` |
| `travel time up`   | Travel time of the blind from bottom to top [s].             | `cXXXX.bcYY_blinds_time_up_ZZ`                          |
| `travel time down` | Travel time of the blind from top to bottom [s].             | `cXXXX.bcYY_blinds_time_dn_ZZ`                          |

These are written through registers shared by all outputs of the module (index, data and
write request), as described by the module.

By default all of the `number` entities are disabled.

Note: Not all entities are supported by stock HIQ firmware!
Some of them are additions to HIQ functionality.

---

### select<a name="select"></a>

To set some parameters in the controller, there are some `select` Entities exposed.

#### For every TH (thermostat) expansion unit:

| Entity name                                | Description                                                                                         | Controller var                  |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------- | ------------------------------- |
| `cXXXX.thYY thermostat temperature source` | Source of measured temperature: 0-internal sensor, 1-external sensor, 2-remote from another device. | `cXXXX.thYY_temperature_source` |
| `cXXXX.thYY thermostat display mode`       | Select what to display when thermostat is off: 0-nothing, 1- ---, 2-temperature.                    | `cXXXX.thYY_display_mode`       |

#### For hvac (internal):

| Entity name                                       | Description                                                                  | Controller var                  |
| ------------------------------------------------- | ---------------------------------------------------------------------------- | ------------------------------- |
| `cXXXX HVAC mode`                                 | Hvac mode: 0-off, 1-heating, 2-cooling.                                      | `cXXXX.hvac_mode`               |
| `cXXXX HVAC thermostat config display mode`       | What to display when thermostat is off: 0-nothing, 1-dashes, 2-temperature.  | `cXXXX.hvac_display_mode`       |
| `cXXXX HVAC thermostat config temperature source` | Select temperature source: 0-internal, 1-external, 2-remote from controller. | `cXXXX.hvac_temperature_source` |

#### For every LC / LD output (on the device of the light):

| Entity name  | Description                                                                                                                                                                   | Controller var                                          |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| `input mode` | How the input affects the output: toggle, staircase timer, motion sensor timer (also night only), inverse / door sensor (also night only), direct / doorbell or event only. | `cXXXX.lcYY_input_mode_ZZ`, `cXXXX.ldYY_input_mode_ZZ` |
| `color mode` | LD only: standard dimmer, RGB dimmer or white temperature. The light follows after a reload of the integration.                                                               | `cXXXX.ldYY_color_mode_ZZ`                              |

By default all of the `select` entities are disabled.

#### Custom selects:

Any integer variable of the HIQ controller can be exposed as a custom `select`.
Navigate to HIQ integration, click on `configure`, choose `Add custom entity`
and then `Select`, and pick the variable, a name and the options.

Each option is entered as `label=value`. The value is a whole number, negative
values are allowed. Choosing an option writes its value to the variable, and the
select shows the option of the current value of the variable (`unknown` if no
option has this value). Labels and values must be unique.

Example for a variable `cXXXX.heating_mode`:

| Option       | Written value |
| ------------ | ------------- |
| `off=0`      | `0`           |
| `eco=1`      | `1`           |
| `comfort=2`  | `2`           |
| `frost=-1`   | `-1`          |

Custom selects belong to the `cXXXX custom` device (together with custom
sensors) and are enabled by default. They are changed with
`Configure custom entity` (name and options, the variable is fixed) and deleted
with `Remove custom entities`.

Note: Not all entities are supported by stock HIQ firmware!
Some of them are additions to HIQ functionality.

---

### switch<a name="switch"></a>

To set some parameters in the controller, there are some `switch` Entities exposed.

#### For every TH (thermostat) expansion unit:

| Entity name                                  | Description                                                                                   | Controller var             |
| -------------------------------------------- | --------------------------------------------------------------------------------------------- | -------------------------- |
| `cXXXX.thYY thermostat window switch enable` | Select how window switch input is handled: 0-ignore input, 1-use input to disable thermostat. | `cXXXX.thYY_window_enable` |
| `cXXXX.thYY thermostat demand enable`        | Enable thermostat to control energy source: 0-off, 1-on.                                      | `cXXXX.thYY_demand_enable` |

#### For hvac (internal):

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

By default all of the `switch` entities are disabled.

Note: Not all entities are supported by stock HIQ firmware!
Some of them are additions to HIQ functionality.

---

### button<a name="button"></a>

To save / read parameters in the expansion units, there are some `button` Entities exposed.

#### For every TH (thermostat) expansion unit:

| Entity name                                | Description                                                                        | Controller var                |
| ------------------------------------------ | ---------------------------------------------------------------------------------- | ----------------------------- |
| `cXXXX HVAC thYY config request`           | Set to update configuration parameters. It will reset automatically after sending. | `cXXXX.thYY_config1_req`      |
| `cXXXX HVAC thYY config read back request` | Request to read options back from thermostat.                                      | `cXXXX.thYY_options_back_req` |

#### For every defined scene:

| Entity name                      | Description                                       | Controller var                |
| -------------------------------- | ------------------------------------------------- | ----------------------------- |
| `cXXXX scenes store scene YY`    | Store the current lights and blinds as scene YY.  | `cXXXX.global_memory_request` |

By default all of the `button` entities are disabled.

Note: Not all entities are supported by stock HIQ firmware!
Some of them are additions to HIQ functionality.

---

### Common Attributes

| Attribute   | Example Values (comma separated)      |
| ----------- | ------------------------------------- |
| description | the description text from the PLC tag |

### Devices

A device is created for each HIQ-controller (diagnostics) and for every light, blind, thermostat and HVAC.

Newer controllers report the card id and firmware of every IEX expansion unit
(`cXXXX.mmYY_iex_card_id` and `cXXXX.mmYY_firmware_version`). They are read once
when the integration starts, and shown on the light, blind and thermostat
devices of that unit:

| Device info | Taken from | Example |
| --- | --- | --- |
| Model | card id | `60` → `LC-10-IQ`, `63` → `BC-5-IQ`, `66` → `TH-2-IQ`, `72` → `LD-D10-IQ` |
| Firmware | firmware version as `major.minor.build.release` | `1203` → `1.2.0.3`, `32767` → `32.7.6.7` |

A card id without a known model is shown as `card <id>`. If one of both values
is missing or `0`, it is shown as `unknown`. If both are missing (older
controllers or an empty slot), the device shows `HIQ controller` and the
integration version. A firmware update of a unit is shown after the
integration is reloaded.

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
- HC-HIQ v6.1.1 Software on a Cybro-3 controller, direct connection, Home Assistant OS 2026.10.4

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
[integration-badge]: https://my.home-assistant.io/badges/integration.svg
[integration]: https://my.home-assistant.io/redirect/integration/?domain=hiq
[hacs-integration-badge]: https://my.home-assistant.io/badges/hacs_repository.svg
[hacs-integration]: https://my.home-assistant.io/redirect/hacs_repository/?owner=killer0071234&repository=ha-hiq
