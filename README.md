# ArtNet Receiver

ArtNet Receiver is a Home Assistant custom integration that listens to **Art-Net / DMX** frames over UDP and maps DMX channels to Home Assistant `light` and `switch` entities.

It is designed for practical Art-Net to Home Assistant control with:

- dynamic mapping configuration
- multiple light profiles
- diagnostics sensors
- test services
- configurable update rate to reduce service flooding during fades

## Features

- Listen to **Art-Net** on a configurable host, port and universe
- Map DMX channels to Home Assistant entities
- Supported target domains:
  - `light`
  - `switch`
- Supported profiles:
  - `switch`
  - `dimmer`
  - `rgb`
  - `rgbw`
  - `rgbww`
  - `color_temp`
- Config flow and options flow in Home Assistant UI
- Mapping diagnostics exposed in sensors and diagnostics export
- Test services for channels and mappings
- Configurable output cadence:
  - `Fast` = 50 ms
  - `Normal` = 100 ms
  - `Low` = 200 ms

## Installation

### HACS custom repository

1. Open **HACS** in Home Assistant.
2. Go to the custom repositories section.
3. Add this repository URL.
4. Select category **Integration**.
5. Search for **ArtNet Receiver**.
6. Install it.
7. Restart Home Assistant.

### Manual installation

1. Copy `custom_components/artnet_receiver` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add **ArtNet Receiver** from the integrations UI.

Expected final path:

```text
config/custom_components/artnet_receiver/
```

## Configuration

After installation, add the integration from **Settings -> Devices & Services -> Add Integration**.

### Network settings

- **Name**
- **Listen address**
- **UDP port**
- **Art-Net universe**
- **Update rate**
  - `Fast (50 ms)`
  - `Normal (100 ms)`
  - `Low (200 ms)`

### Mapping profiles

#### Switch

- 1 DMX channel
- Suitable for switches, plugs, relays, or simple on/off behavior

#### Dimmer

- 1 DMX channel
- Maps DMX value to Home Assistant brightness

#### RGB

- 4 DMX channels
- Layout:
  - dimmer
  - red
  - green
  - blue

#### RGBW

- 5 DMX channels
- Layout:
  - dimmer
  - red
  - green
  - blue
  - white

#### RGBWW

- 6 DMX channels
- Layout:
  - dimmer
  - red
  - green
  - blue
  - cold white
  - warm white

#### Color temperature

- 2 DMX channels
- Layout:
  - dimmer
  - color temperature

## How it works

- The integration listens for Art-Net DMX frames on UDP.
- Incoming values are matched against configured mappings.
- For each mapped entity, the integration stores the latest received value.
- Instead of forwarding every DMX frame immediately, it applies the latest value at the configured cadence.
- This avoids excessive Home Assistant service calls during fades.

## Diagnostics

The integration exposes diagnostic sensors, including:

- **Activity**
- **Packets received**
- **Service calls sent**
- **Mappings**

Runtime diagnostics include useful attributes such as:

- configured bind host
- effective bind host
- port
- universe
- polling mode
- service call interval in milliseconds
- queued service calls
- last service call
- configured mappings
- last error

The dedicated **Mappings** sensor also exposes:

- a readable summary
- structured mappings data
- JSON mappings export in attributes

## Services

### `artnet_receiver.test_channel`

Inject a DMX value into a single channel.

Fields:

- `entry_id` optional
- `channel`
- `value`

### `artnet_receiver.test_mapping`

Trigger a configured mapped entity without an external Art-Net sender.

Fields:

- `entry_id` optional
- `mapping_entity`
- `value`
- `red`
- `green`
- `blue`
- `white`
- `cold_white`
- `warm_white`
- `color_temp`

## Notes about compatibility

- This integration currently uses the Home Assistant domain:

```text
artnet_receiver
```

- If you used an older local version based on the previous `dmaix` domain, that is a **breaking change**.
- Existing config entries and service names from the old domain may need to be recreated.

## HACS repository layout

This repository is structured for HACS as a custom integration repository:

```text
custom_components/
  artnet_receiver/
README.md
hacs.json
```

## Recommended repository strategy

For HACS, a **dedicated repository for this integration** is the best option.

Recommended:

- one repository
- one integration
- one `custom_components/artnet_receiver` package

Why:

- cleaner HACS installation
- easier versioning and releases
- clearer issues and changelog
- simpler maintenance

So yes: **a separate repository dedicated to this custom component is better**.

## Suggested next steps before publishing

- add a license file
- add screenshots or GIFs in the README
- create a first GitHub release tag matching the integration version
- test installation from HACS custom repository
- optionally add CI for validation

## Development status

Current version from manifest:

- `0.2.0`

## Support

If you publish this on GitHub, it is worth documenting:

- supported Home Assistant versions
- supported Art-Net senders tested
- known limitations for slow cloud/Wi-Fi lights
