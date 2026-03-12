# ArtNet Receiver

ArtNet Receiver is a Home Assistant custom integration that listens to **Art-Net / DMX** frames over UDP and maps DMX channels to Home Assistant `light` and `switch` entities.

It is built for practical Art-Net to Home Assistant workflows where you want reliable control, clear diagnostics, and better behavior during fades without flooding Home Assistant with outdated commands.

## Why use ArtNet Receiver

- **Local Art-Net listener** with configurable host, port, and universe
- **UI-based configuration** with config flow and options flow
- **Flexible DMX mapping** for lights and switches
- **Multiple profiles** for common lighting setups
- **Diagnostics sensors** to understand runtime behavior
- **Test services** for quick validation without an external sender
- **Configurable update rate** to reduce flooding during fades
- **Latest-value behavior** to stay as close as possible to the most recent DMX command

## Supported entities

- **`light`**
- **`switch`**

## Supported profiles

- **`switch`**
- **`dimmer`**
- **`rgb`**
- **`rgbw`**
- **`rgbww`**
- **`color_temp`**

## Installation

### Option 1: HACS

1. Open **HACS** in Home Assistant.
2. Go to the custom repositories section.
3. Add this repository URL.
4. Select category **Integration**.
5. Search for **ArtNet Receiver**.
6. Install the integration.
7. Restart Home Assistant.
8. Add **ArtNet Receiver** from **Settings -> Devices & Services**.

### Option 2: Manual installation

1. Copy `custom_components/artnet_receiver` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add **ArtNet Receiver** from **Settings -> Devices & Services**.

Expected path:

```text
config/custom_components/artnet_receiver/
```

## Quick overview

After installation, create the integration from the Home Assistant UI and configure:

- **Name**
- **Listen address**
- **UDP port**
- **Art-Net universe**
- **Update rate**

Available update rates:

- **`Fast`** = `50 ms`
- **`Normal`** = `100 ms`
- **`Low`** = `200 ms`

## Mapping profiles

### Switch

- **1 DMX channel**
- Best for relays, smart plugs, or simple on/off behavior

### Dimmer

- **1 DMX channel**
- Maps the DMX value to Home Assistant brightness

### RGB

- **4 DMX channels**
- Channel layout:
  - dimmer
  - red
  - green
  - blue

### RGBW

- **5 DMX channels**
- Channel layout:
  - dimmer
  - red
  - green
  - blue
  - white

### RGBWW

- **6 DMX channels**
- Channel layout:
  - dimmer
  - red
  - green
  - blue
  - cold white
  - warm white

### Color temperature

- **2 DMX channels**
- Channel layout:
  - dimmer
  - color temperature

## Fade behavior and update strategy

ArtNet Receiver is designed to avoid the classic Home Assistant catch-up effect where a light keeps replaying older commands after a fast DMX fade.

Current behavior is focused on:

- **keeping the latest value**
- **limiting update frequency**
- **reducing service flooding**
- **staying closer to the final requested state**

This is especially useful for:

- dimmer fades
- color temperature fades
- frequent DMX changes from live control

## Diagnostics

The integration exposes dedicated diagnostic sensors:

- **Activity**
- **Packets received**
- **Service calls sent**
- **Mappings**

Runtime diagnostics expose useful attributes such as:

- configured bind host
- effective bind host
- port
- universe
- polling mode
- service call interval in milliseconds
- active service workers
- queued service calls
- last service call
- configured mappings
- last error
- last packet metadata

The dedicated **Mappings** sensor also exposes:

- a readable summary
- structured mapping data
- JSON export in attributes

## Services

### `artnet_receiver.test_channel`

Inject a DMX value into a single channel for quick testing.

Fields:

- **`entry_id`** optional
- **`channel`**
- **`value`**

### `artnet_receiver.test_mapping`

Trigger a configured mapped entity without an external Art-Net sender.

Fields:

- **`entry_id`** optional
- **`mapping_entity`**
- **`value`**
- **`red`**
- **`green`**
- **`blue`**
- **`white`**
- **`cold_white`**
- **`warm_white`**
- **`color_temp`**

## Compatibility notes

Current Home Assistant domain:

```text
artnet_receiver
```

If you used an older local version based on the previous `dmaix` domain, this is a **breaking change**.

You may need to:

- recreate the integration entry
- update service calls
- recreate old references based on the former domain

## Repository structure

This repository is already structured as a HACS custom integration repository:

```text
custom_components/
  artnet_receiver/
README.md
hacs.json
```

## Recommended publication workflow

For HACS, the recommended approach is:

- **one repository**
- **one integration**
- **one `custom_components/artnet_receiver` package**

This keeps installation, releases, maintenance, and support much cleaner.

## Before publishing

Recommended finishing steps:

- add a **LICENSE** file
- create a first **GitHub release/tag** matching the integration version
- test installation from **HACS custom repository**
- add screenshots or a short GIF in the README
- optionally add CI validation

## Version

Current manifest version:

- **`0.2.0`**

## Known practical limitations

As with any Home Assistant light control pipeline, final behavior also depends on the target device and its native latency.

Typical limits can come from:

- Wi-Fi device latency
- cloud-based light integrations
- slow firmware reactions
- lights that internally smooth or delay state changes

For best results, local lights and locally controlled integrations usually perform better than cloud-based devices.

## Support and feedback

If you publish this repository publicly, it is useful to document:

- tested Home Assistant versions
- tested Art-Net senders
- tested device types
- known limitations by light platform
