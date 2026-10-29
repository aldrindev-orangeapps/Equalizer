# Laptop Equalizer

A focused Windows desktop equalizer for normal playback from YouTube, browsers,
Spotify, games, and other apps. One shared 10-band profile is applied through
[Equalizer APO](https://sourceforge.net/projects/equalizerapo/); microphone and
recording devices are not managed by this application.

## Features

- 10 bands from 31 Hz to 16 kHz, plus preamp control
- Built-in Flat, Bass Boost, Deep Bass, Vocal, Gaming, Movies, and Treble Boost presets
- Custom presets stored locally
- Optional automatic headroom to reduce digital clipping
- Live 48-band RGB spectrum analyzer using Windows WASAPI loopback
- Instant enable/bypass without changing the Windows master volume
- Safe integration that preserves the existing Equalizer APO configuration
- Output-device selector provided by Equalizer APO
- Standard-library-only Python runtime and a standalone PyInstaller build

## Requirements

- Windows 10 or Windows 11
- Equalizer APO installed and enabled for the desired speaker/headphone device
- Python 3.10 or newer when running from source

Install the analyzer dependencies once when running from source:

```powershell
npm run setup
```

Equalizer APO performs the audio processing. Laptop Equalizer is the friendly
control interface and does not install an audio driver of its own.

## Run from source

```powershell
python .\laptop_equalizer.py
```

Or use the included npm command:

```powershell
npm start
```

On first use:

1. Install Equalizer APO from its official SourceForge project.
2. During its installation, choose the speaker or headphone output to process.
3. Restart Windows if the Equalizer APO installer requests it.
4. Open Laptop Equalizer and select **Set up Equalizer APO** once.
5. Choose a preset or adjust the bands, then select **Apply to audio**.

If Windows prevents the one-time setup from writing inside `Program Files`, run
Laptop Equalizer as administrator for setup. Normal use usually does not require
elevation when the Equalizer APO config directory permits user changes.

## Safety and storage

The app does not replace `config.txt`. It appends a marked block that includes
`laptop-equalizer.txt`, then owns only that generated file. Existing Equalizer
APO filters remain untouched. App settings and custom presets are stored at:

```text
%LOCALAPPDATA%\LaptopEqualizer\settings.json
```

Large positive EQ boosts can clip. Automatic headroom is enabled by default and
reduces preamp by the size of the largest boost.

Some applications using exclusive or raw audio modes can bypass Windows system
effects. Standard browser, YouTube, Spotify, and shared-mode playback are the
intended use cases.

## Tests

```powershell
python -m unittest discover -s tests -v
```

The same test suite is available through npm:

```powershell
npm test
```

Tests use temporary folders and never access the installed Equalizer APO files.

## Build the standalone EXE

Install PyInstaller in the build environment, then run:

```powershell
python -m PyInstaller --noconfirm ".\Laptop Equalizer.spec"
```

The portable application is written to `dist\Laptop Equalizer.exe`.

You can also build through npm. This remains a Python/PyInstaller application;
npm is only used as a convenient command runner, so there are no JavaScript
packages to install.

```powershell
npm run build
```

To run the tests first and build only when they pass:

```powershell
npm run verify-build
```
