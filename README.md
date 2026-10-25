# HIQ-Home for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![hacs][hacsbadge]][hacs]
[![License][license-shield]](LICENSE)
[![Project Maintenance][maintenance-shield]][user_profile]

Control your **HIQ home automation** from Home Assistant: lights, blinds,
thermostats, scenes and the diagnostics of HIQ controllers (Cybro-2 / Cybro-3
PLCs running the HIQ software from Robotina d.o.o. / Cybrotech).

- **Local only.** Talks to the controllers in your network, no cloud.
- **Set up in the UI.** Controllers in the network are found automatically.
- **No extra server needed.** Connects to the controllers directly over A-bus
  (UDP 8442). The CybroScgiServer is still supported.
- **Lights** with brightness, RGB and white temperature, **blinds** with
  position, **thermostats**, **scenes**, a **weather station**, a power meter
  and diagnostics.
- **Custom sensors and selects** for any variable of the controller.
- **Actions** to send smartphone events (presence, alarm clock, charger, ...)
  to the controller.

**Requires Home Assistant 2026.10 or newer.**

---

{% if not installed %}

## Installation

### HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.][hacs-integration-badge]][hacs-integration]

1. Install [HACS](https://hacs.xyz/) if you don't have it yet.
2. Click the button above, or search for **HIQ-Home** in HACS.
3. Click **Download**, then restart Home Assistant.

### Manual

[![Download the latest release][download-shield]][download]

1. Download [`hiq.zip`][download] of the latest release (or of an
   [older release][releases]).
2. Unpack it to `custom_components/hiq/` in your Home Assistant configuration
   directory (where `configuration.yaml` is).
3. Restart Home Assistant.

{% endif %}

## Adding a controller

[![Open your Home Assistant instance and start setting up a new integration.][config-flow-badge]][config-flow]

**Settings → Devices & services → Add integration → HIQ-Home**, then choose how
Home Assistant reaches the controller:

|                  | Directly over the network (recommended)                 | Through the CybroScgiServer                                |
| ---------------- | ------------------------------------------------------- | ---------------------------------------------------------- |
| How              | Home Assistant talks A-bus to the controller (UDP 8442) | Home Assistant asks a CybroScgiServer, which talks A-bus   |
| Extra software   | none                                                     | a running scgi server                                      |
| Setup            | Pick the controller from the list of found controllers  | Enter host and port of the scgi server and the NAD         |
| Controller pushes changes | yes                                            | no                                                         |
| Use when         | Home Assistant is in the same network as the controllers | The controller can't be reached directly (other site, NAT) |

Only controllers running the HIQ program are listed. Any other controller can
still be added by entering its address (NAD).

### Direct connection

What the network needs:

- Home Assistant and the controllers in the **same network segment**. The
  controllers are found by broadcast. For a controller in another segment or
  VLAN, enter its IP address when adding it.
- In **Docker**, Home Assistant needs `network_mode: host`. With published ports
  only, broadcasts don't arrive: enter the IP address of every controller.
- If an **A-bus password** is set in the controller, enter it when adding it.
- **UDP port 8442** free on the Home Assistant host, see
  [Troubleshooting](#port-8442-is-used-by-another-app).

### Through the CybroScgiServer

The scgi server must run before the controller is added. Use one of:

- the Home Assistant app CybroScgiServer
  [![Open this app in your Home Assistant instance.][addon-badge]][addon]
- the Docker image [![dockerhub][scgi-docker-shield]][scgi-docker]
- a manual install from source.

### After setup

- **New controllers are found on their own.** Once one controller is set up,
  the integration searches the network after Home Assistant starts and every
  15 minutes. New controllers show up under **Settings → Devices & services →
  Discovered**. A controller that gets its IP address by DHCP (Cybrotech MAC
  address `00:CB:00:…`) is also found when it connects to the network.
- **Moving from the scgi server to the direct connection.** When the search
  finds a controller that is set up through the scgi server, it offers to
  connect it directly. Entities, custom sensors and custom selects stay. The
  connection can also be changed with **Reconfigure** in the menu of the entry,
  in both directions.
- **IP address changes are followed.** Controllers added without an IP address
  are found by broadcast. For a controller with a fixed IP address, the new
  address is stored when the search, DHCP or a frame from the controller shows
  it.

## Entities

The integration scans the controller when it starts and creates entities for
the supported expansion units. A unit with `general_error` set is skipped.

| Platform        | What                                                               | Units                                                   |
| --------------- | ------------------------------------------------------------------ | ------------------------------------------------------- |
| `light`         | On / off, brightness, RGB, white temperature (depending on unit)   | LC-10-IQ, LC-8-IQ, LD-D10-IQ, LD-D8-IQ, LD-P4-IQ, LD-V4-IQ, Virtual LC |
| `cover`         | Open, close, stop, position                                        | BC-5-IQ, Virtual BC                                     |
| `scene`         | Scenes of lights and blinds                                        | SC-4-IQ                                                 |
| `climate`       | Heating / cooling, setpoint, presets eco / comfort / boost         | TH-X-IQ                                                 |
| `weather`       | Temperature, humidity, pressure, wind                              | weather station of the controller                       |
| `sensor`        | Temperatures, humidity, power meter, diagnostics                   | controller, expansion units, TH                         |
| `binary_sensor` | Presence, nighttime, error flags                                   | controller, expansion units, TH                         |
| `number`, `select`, `switch`, `button` | Parameters of thermostats, HVAC and outputs | TH, HVAC, LC / LD / BC outputs                         |

Diagnostic and parameter entities are **disabled by default**. Enable the ones
you need on the entities page of the integration.

**→ [Full entity reference][entities-doc]** with every entity, its controller
variable and its default.

## Custom entities

Any variable of the controller can become a sensor or a select.

[![Open your Home Assistant instance and show an integration.][integration-badge]][integration]

On the HIQ-Home integration, click **Configure → Add custom entity**, then:

- **Sensor**: pick the variable and a name.
- **Select**: pick an integer variable, a name and the options. Each option is
  `label=value`, e.g. for `cXXXX.heating_mode`:

  ```text
  off=0
  eco=1
  comfort=2
  frost=-1
  ```

  Choosing an option writes its value to the variable. The select shows the
  option of the current value (`unknown` if no option has it). Labels and values
  must be unique, negative values are allowed.

Custom entities belong to the `cXXXX custom` device and are enabled by default.
Change them with **Configure custom entity** (the variable is fixed) and delete
them with **Remove custom entities**.

## Actions

Forward smartphone events to the controller, or write any variable. Target a
HIQ-Home binary sensor or a device of the controller.

| Action                  | What it does                                                                     |
| ----------------------- | -------------------------------------------------------------------------------- |
| `hiq.presence_signal`   | Sends the smartphone presence signal                                             |
| `hiq.home_event`        | Sends the smartphone home event                                                  |
| `hiq.alarm_event`       | Sends the alarm clock event (alarm clock rings)                                  |
| `hiq.precede_event`     | Sends the event `time` minutes before the alarm clock, e.g. to preheat the house |
| `hiq.charge_on_event`   | Sends the charger connected event                                                |
| `hiq.charge_off_event`  | Sends the charger disconnected event                                             |
| `hiq.write_tag`         | Writes `value` to the variable `tag` (without the `cNAD.` prefix)                |

```yaml
action: hiq.write_tag
target:
  entity_id: binary_sensor.system_c1000_diagnostic_presence
data:
  tag: smartphone_presence_signal
  value: 1
```

## Troubleshooting

### Port 8442 is used by another app

The CybroScgiServer and the Cybro Edge Toolkit apps use UDP port 8442 too.
While such an app runs, the integration leaves the port to it and uses another
one: polling works, but the controllers can't push data to Home Assistant.

A repair under **Settings → System → Repairs** names the app and offers to stop
it (and to turn off its start on boot). Entries that still use the scgi server
of that app stop working then, so **switch them to the direct connection
first**. If the port is freed in another way, the integration takes it within
15 minutes.

### The controller isn't found

- Is Home Assistant in the same network segment as the controller? If not,
  enter the IP address when adding it.
- Docker without `network_mode: host`: enter the IP address.
- Only controllers running the HIQ program are listed. Add others by NAD.

### An entity is missing

- Many entities are disabled by default, see [Entities](#entities).
- Units with `general_error` set are skipped. Fix the unit and reload the
  integration.
- Some parameter entities are additions to the HIQ functionality and not
  supported by the stock HIQ firmware.

For debug logs and reporting problems, see [DEBUGGING.md][debugging].

## Tested devices

| HIQ software | Controller                 | Connection                                     | Home Assistant |
| ------------ | -------------------------- | ---------------------------------------------- | -------------- |
| HC-HIQ 6.1.1 | Cybro-3                    | direct                                         | OS 2026.10.4   |
| HC-HIQ 3.0.3 | Cybro-3, firmware 3.2.3    | cybroscgiserver 3.1.3 in a Docker container    |                |

Running it on other hardware? Please tell us in an issue.

## Contributing

Contributions are welcome, see the
[contribution guidelines](https://github.com/killer0071234/ha-hiq/blob/master/CONTRIBUTING.md).

## Credits

The code template was taken from [@amosyuen](https://github.com/amosyuen)'s
[ha-tplink-deco][ha_tplink_deco] integration.

---

[addon-badge]: https://my.home-assistant.io/badges/supervisor_addon.svg
[addon]: https://my.home-assistant.io/redirect/supervisor_addon/?addon=85493909_cybroscgiserver&repository_url=https%3A%2F%2Fgithub.com%2Fkiller0071234%2Fha-addon-repository
[config-flow-badge]: https://my.home-assistant.io/badges/config_flow_start.svg
[config-flow]: https://my.home-assistant.io/redirect/config_flow_start/?domain=hiq
[debugging]: https://github.com/killer0071234/ha-hiq/blob/master/DEBUGGING.md
[download-shield]: https://img.shields.io/github/downloads/killer0071234/ha-hiq/latest/hiq.zip.svg?style=for-the-badge&label=download%20hiq.zip
[download]: https://github.com/killer0071234/ha-hiq/releases/latest/download/hiq.zip
[entities-doc]: https://github.com/killer0071234/ha-hiq/blob/master/docs/entities.md
[ha_tplink_deco]: https://github.com/amosyuen/ha-tplink-deco
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[hacs-integration-badge]: https://my.home-assistant.io/badges/hacs_repository.svg
[hacs-integration]: https://my.home-assistant.io/redirect/hacs_repository/?owner=killer0071234&repository=ha-hiq
[integration-badge]: https://my.home-assistant.io/badges/integration.svg
[integration]: https://my.home-assistant.io/redirect/integration/?domain=hiq
[license-shield]: https://img.shields.io/github/license/killer0071234/ha-hiq.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-@killer0071234-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/killer0071234/ha-hiq.svg?style=for-the-badge
[releases]: https://github.com/killer0071234/ha-hiq/releases
[scgi-docker-shield]: https://img.shields.io/badge/dockerhub-cybroscgiserver-brightgreen.svg?style=for-the-badge
[scgi-docker]: https://hub.docker.com/r/killer007/cybroscgiserver
[user_profile]: https://github.com/killer0071234
