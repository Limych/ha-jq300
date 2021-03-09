*Please :star: this repo if you find it useful*

# Home Assistant Integration of JQ-300/200/100 Indoor Air Quality Meter

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]][license]

[![hacs][hacs-shield]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]

[![Community Forum][forum-shield]][forum]

_Integration JQ-300 Indoor Air Quality Meter into Home Assistant. From this device you can receive values of TVOC (volatile organic compounds), eCO<sub>2</sub> (carbon dioxide), HCHO (formaldehyde), humidity and PM 2.5 (ultrafine particles)._

I also suggest you [visit the support topic][forum] on the community forum.

![logo][logoimg]

_Thanks to [tomaae](https://github.com/tomaae) for the financial support in purchasing the device for creating this project._

## Known Limitations and Issues

- Only one application can be logged into an cloud account at a time.\
Therefore, each time restarted HA, authorization from the official application on your phone will be lost. Authorization is restored when you restart the official application.

## Installation

### HACS - Recommended

1. Have [HACS](https://hacs.xyz) installed, this will allow you to easily manage and track updates.
1. Search for "JQ-300/200/100 Indoor Air Quality Meter".
1. Click Install below the found integration.
1. **(Not implemented for now, sorry)** _If you want to configure component via Home Assistant UI..._\
    in the HA UI go to "Configuration" -> "Integrations" click "+" and search for "Jq300".
1. _If you want to configure component via `configuration.yaml`..._\
    follow instructions below, then restart Home Assistant.

### Manual

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
1. If you do not have a `custom_components` directory (folder) there, you need to create it.
1. In the `custom_components` directory (folder) create a new folder called `jq300`.
1. Download file `jq300.zip` from the [latest release section][latest-release] in this repository.
1. Extract _all_ files from this archive you downloaded in the directory (folder) `jq300` you created.
1. **(Not implemented for now, sorry)** _If you want to configure component via Home Assistant UI..._\
    in the HA UI go to "Configuration" -> "Integrations" click "+" and search for "Jq300".
1. _If you want to configure component via `configuration.yaml`..._\
    follow instructions below, then restart Home Assistant.

<p align="center">* * *</p>
I put a lot of work into making this repo and component available and updated to inspire and help others! I will be glad to receive thanks from you — it will give me new strength and add enthusiasm:
<p align="center"><br>
<a href="https://www.patreon.com/join/limych?" target="_blank"><img src="http://khrolenok.ru/support_patreon.png" alt="Patreon" width="250" height="48"></a>
<br>or&nbsp;support via Bitcoin or Etherium:<br>
<a href="https://sochain.com/a/mjz640g" target="_blank"><img src="http://khrolenok.ru/support_bitcoin.png" alt="Bitcoin" width="150"><br>
16yfCfz9dZ8y8yuSwBFVfiAa3CNYdMh7Ts</a>
</p>

## Usage

To use this component in your installation, add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
jq300:
  username: YOUR_EMAIL
  password: YOUR_PASSWORD
```

![example][exampleimg]

> **_Note_**:\
> Before using the devices you need to connect them to your account through the official app.
>
> Only one application can be logged into an account at a time. Therefore, each time restarted this integration, authorization from the official application on your phone will be lost. Authorization is restored when you restart the official application.

We recommend using [the IAQ UK sensor](https://github.com/Limych/ha-iaquk) to evaluate overall air quality. Example configuration:

```yaml
# Example configuration.yaml entry
jq300:
  username: YOUR_EMAIL
  password: YOUR_PASSWORD
  devices:
    - Kitchen
iaquk:
  Kitchen:
    sources:
      humidity: sensor.kitchen_humidity
      co2: sensor.kitchen_eco2
      tvoc: sensor.kitchen_tvoc
      hcho: sensor.kitchen_hcho
      pm: sensor.kitchen_pm25
```

### Configuration variables

**username**:\
  _(string) (Required)_\
  The username for accessing your account.

**password**:\
  _(string) (Required)_\
  The password for accessing your account.

**devices**:\
  _(list) (Optional) (Default value: all available devices)_\
  List of names of devices to add to Home Assistant.\
  For each device, all sensors are created, which are possible:\
  for all devices: TVOC, HCHO (Formaldehyde) and eCO<sub>2</sub>;\
  for JQ-200 and JQ-300 only: internal temperature and humidity;\
  for JQ-300 only: PM 2.5.

**receive_tvoc_in_ppb**:\
  _(boolean) (Optional) (Default value: False)_\
  By default, the cloud returns the TVOC value in `mg/m³` units. Setting this parameter to `True` allows to receive data in `ppb` units.

**receive_hcho_in_ppb**:\
  _(boolean) (Optional) (Default value: False)_\
  By default, the cloud returns the HCHO (formaldehyde) value in `mg/m³` units. Setting this parameter to `True` allows to receive data in `ppb` units.

## Track updates

You can automatically track new versions of this component and update it by [HACS][hacs].

## Troubleshooting

To enable debug logs use this configuration:
```yaml
# Example configuration.yaml entry
logger:
  default: info
  logs:
    custom_components.jq300: debug
```
... then restart HA.

## Contributions are welcome!

This is an active open-source project. We are always open to people who want to
use the code or contribute to it.

We have set up a separate document containing our
[contribution guidelines](CONTRIBUTING.md).

Thank you for being involved! :heart_eyes:

## Authors & contributors

The original setup of this component is by [Andrey "Limych" Khrolenok](https://github.com/Limych).

For a full list of all authors and contributors,
check [the contributor's page][contributors].

## License

creative commons Attribution-NonCommercial-ShareAlike 4.0 International License

See separate [license file](LICENSE.md) for full text.

***

[component]: https://github.com/Limych/ha-jq300
[commits-shield]: https://img.shields.io/github/commit-activity/y/Limych/ha-jq300.svg?style=popout
[commits]: https://github.com/Limych/ha-jq300/commits/master
[hacs-shield]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=popout
[hacs]: https://hacs.xyz
[logoimg]: https://github.com/Limych/ha-jq300/raw/master/logo.jpeg
[exampleimg]: https://github.com/Limych/ha-jq300/raw/master/example.png
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=popout
[forum]: https://community.home-assistant.io/t/jq-300-200-100-indoor-air-quality-meter/189098
[license]: https://github.com/Limych/ha-jq300/blob/main/LICENSE.md
[license-shield]: https://img.shields.io/badge/license-Creative_Commons_BY--NC--SA_License-lightgray.svg?style=popout
[maintenance-shield]: https://img.shields.io/badge/maintainer-Andrey%20Khrolenok%20%40Limych-blue.svg?style=popout
[releases-shield]: https://img.shields.io/github/release/Limych/ha-jq300.svg?style=popout
[releases]: https://github.com/Limych/ha-jq300/releases
[releases-latest]: https://github.com/Limych/ha-jq300/releases/latest
[user_profile]: https://github.com/Limych
[report_bug]: https://github.com/Limych/ha-jq300/issues/new?template=bug_report.md
[suggest_idea]: https://github.com/Limych/ha-jq300/issues/new?template=feature_request.md
[contributors]: https://github.com/Limych/ha-jq300/graphs/contributors
