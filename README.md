# ha-hiq

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![pre-commit][pre-commit-shield]][pre-commit]
[![Black][black-shield]][black]

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]

[![Community Forum][forum-shield]][forum]

## Functionality

This integration is a local polling integration that connects to a running cybro-scgi-server from Cybrotech.
To use this integration you need to have a running scgi server (it could be a docker container or native installed).
Further informations of the docker container can be found here: [![dockerhub][scgi-docker-shield]][scgi-docker]

### binary_sensor

There are some diagnostic binary sensors exposed:

| entity name              | Description                                                                        |
| ------------------------ | ---------------------------------------------------------------------------------- |
| cXXXX.general_error      | Logical or of IEX general errors, indicates that at least one module has an error. |
| cXXXX.retentive_fail     | Indicates that retentive memory failed.                                            |
| cXXXX.scan_overrun       | Too long scan execution caused scan overrun error.                                 |
| cXXXX.YYYY_general_error | Combined system error (timeout or program error), module is not operational.       |

XXXX is the NAD of the controller, and YYYY is the IEX module prefix

### sensor

There are some diagnostic sensors exposed:

| entity name                 | Description                                                         |
| --------------------------- | ------------------------------------------------------------------- |
| cXXXX.scan_time             | Last scan execution time [ms].                                      |
| cXXXX.scan_time_max         | Maximal scan execution time encountered since program started [ms]. |
| cXXXX.scan_frequency        | Actual number of scans per second.                                  |
| cXXXX.sys.ip_port           | IP address and UDP port of the controller.                          |
| cXXXX.YYYY_iex_power_supply | Measured power supply voltage [V]. Measuring range is 0..40V.       |

XXXX is the NAD of the controller, and YYYY is the IEX module prefix

In addition to the diagnostic sensors, it will check if there are some more sensors:

- temperature devices (eg: op00_temperature, ..)
- humidity devices (eg: ts00_humidity)
- energy meter device (eg: power_meter_power, power_meter_energy)

### cover

during creation of the device it scans for blind modules (eg: HIQ BC-5-IQ).

#### Common Attributes

| Attribute   | Example Values (comma separated)  |
| ----------- | --------------------------------- |
| description | the description text from the PLC |

### Devices

A device is created for each PLC (diagnostics) and for every light, blind.

{% if not installed %}

## Installation

### HACS

1. Install [HACS](https://hacs.xyz/)
2. Go to HACS "Integrations >" section
3. In the lower right click "+ Explore & Download repositories"
4. Search for "HIQ" and add it
   - HA Restart is not needed since it is configured in UI config flow
5. In the Home Assistant (HA) UI go to "Configuration"
6. Click "Integrations"
7. Click "+ Add Integration"
8. Search for "HIQ"

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

- HIQ v1 Software (on a Cybro-2 controller)

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](https://github.com/killer0071234/ha-hiq/blob/master/CONTRIBUTING.md)

## Credits

Code template was mainly taken from [@amosyuen](https://github.com/amosyuen)'s [ha-tplink-deco][ha_tplink_deco] integration

---

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
