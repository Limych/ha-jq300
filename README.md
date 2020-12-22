*Please :star: this repo if you find it useful*

**!!! Be careful! This is a BETA-version only. !!!**

# Home Assistant Integration of JQ-300/200/100 Indoor Air Quality Meter

[![GitHub Release](https://img.shields.io/github/tag-date/Limych/ha-jq300?label=release&style=popout)](https://github.com/Limych/ha-jq300/releases)
[![GitHub Activity](https://img.shields.io/github/commit-activity/y/Limych/ha-jq300.svg?style=popout)](https://github.com/Limych/ha-jq300/commits/master)
[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg?style=popout)](LICENSE.md)
![Requires.io](https://img.shields.io/requires/github/Limych/ha-jq300)

[![hacs](https://img.shields.io/badge/HACS-Default-orange.svg?style=popout)][hacs]
![Project Maintenance](https://img.shields.io/badge/maintainer-Andrey%20Khrolenok%20%40Limych-blue.svg?style=popout)

[![GitHub pull requests](https://img.shields.io/github/issues-pr/Limych/ha-jq300?style=popout)](https://github.com/Limych/ha-jq300/pulls)
[![Bugs](https://img.shields.io/github/issues/Limych/ha-jq300/bug.svg?colorB=red&label=bugs&style=popout)](https://github.com/Limych/ha-jq300/issues?q=is%3Aopen+is%3Aissue+label%3ABug)

[![Community Forum](https://img.shields.io/badge/community-forum-brightgreen.svg?style=popout)][forum-support]

This component allows you to integrate JQ-300 Indoor Air Quality Meter into Home Assistant. And receive values of it sensors: TVOC (volatile organic compounds), eCO<sub>2</sub> (carbon dioxide), HCHO (formaldehyde), humidity and PM 2.5 (ultrafine particles).

I also suggest you [visit the support topic][forum-support] on the community forum.

![](logo.jpeg)

_Thanks to [tomaae](https://github.com/tomaae) for the financial support in purchasing the device for creating this project._

**Note:**\
It was discovered that there is [no difference between the JQ-200 and JQ-300](https://community.home-assistant.io/t/jq-300-200-100-indoor-air-quality-meter/189098/42) models. Although the JQ-200 does not show PM2.5 sensor data in the official app, in fact this data is collected and transmitted from the cloud. Our component sees and displays them correctly. So you have the opportunity to save some money if you wish when purchasing.

## Known Limitations and Issues

- In some cases, the component may stop working.\
This is due to the fact that the authors of JQ-300 have recently begun to actively block attempts to receive data from their cloud bypassing the official application.\
There is only one way to fix it so far — to change the public IP address of your computer.

- Only one application can be logged into an cloud account at a time.\
Therefore, each time restarted HA, authorization from the official application on your phone will be lost. Authorization is restored when you restart the official application.

## Installation

### HACS - Recommended

1. Have [HACS](https://hacs.xyz) installed, this will allow you to easily manage and track updates.
1. Search for "JQ-300/200/100 Indoor Air Quality Meter".
1. Click Install below the found integration.
1. Configure using the configuration instructions below.
1. Restart Home-Assistant.

### Manual

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `jq300`.
4. Download file `jq300.zip` from the [latest release section][latest-release] in this repository.
5. Extract _all_ files from this archive you downloaded in the directory (folder) `jq300` you created.
1. Configure using the configuration instructions below.
1. Restart Home-Assistant.

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

![](example.png)

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
  _(list) (Optional)_\
  List of names of devices to add to Home Assistant.\
  For each device, all sensors are created, which are possible:\
  for all devices: TVOC, HCHO (Formaldehyde) and eCO<sub>2</sub>;\
  for JQ-200 and JQ-300 only: internal temperature and humidity;\
  for JQ-300 only: PM 2.5.\
  _Default value: all available devices_

**receive_tvoc_in_ppb**:\
  _(boolean) (Optional)_\
  By default, the cloud returns the TVOC value in `mg/m³` units. Setting this parameter to `True` allows to receive data in `ppb` units.\
  _Default value: False_

**receive_hcho_in_ppb**:\
  _(boolean) (Optional)_\
  By default, the cloud returns the HCHO (formaldehyde) value in `mg/m³` units. Setting this parameter to `True` allows to receive data in `ppb` units.\
  _Default value: False_

## Track updates

You can automatically track new versions of this component and update it by [HACS][hacs].

## Troubleshooting

To enable debug logs use this configuration:
```yaml
# Example configuration.yaml entry
logger:
  logs:
    custom_components.jq300: debug
```
... then restart HA.

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

## Authors & contributors

The original setup of this component is by [Andrey "Limych" Khrolenok][limych].

For a full list of all authors and contributors,
check [the contributor's page][contributors].

## License

creative commons Attribution-NonCommercial-ShareAlike 4.0 International License

See separate [license file](LICENSE.md) for full text.

[forum-support]: https://community.home-assistant.io/t/jq-300-200-100-indoor-air-quality-meter/189098
[hacs]: https://github.com/custom-components/hacs
[latest-release]: https://github.com/Limych/ha-jq300/releases/latest
[limych]: https://github.com/Limych
[contributors]: https://github.com/Limych/ha-jq300/graphs/contributors
