"""Modern Tkinter interface for Laptop Equalizer."""

from __future__ import annotations

import subprocess
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from equalizer_backend import (
    EqualizerApoBackend,
    EqualizerError,
    EqualizerState,
    FREQUENCIES,
    discover_config_dir,
    recommended_preamp,
)
from settings_store import DEFAULT_PRESETS, SettingsStore, preset_state


COLORS = {
    "bg": "#F4F6FA",
    "surface": "#FFFFFF",
    "sidebar": "#111827",
    "sidebar_panel": "#1F2937",
    "primary": "#6750E8",
    "primary_dark": "#513BCB",
    "text": "#172033",
    "muted": "#697386",
    "border": "#DDE2EA",
    "success": "#087A55",
    "warning": "#B45309",
    "danger": "#C0362C",
    "track": "#E7EAF0",
}


def frequency_label(frequency: int) -> str:
    return f"{frequency // 1000}k" if frequency >= 1000 else str(frequency)


class LaptopEqualizerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("Laptop Equalizer")
        root.geometry("1180x720")
        root.minsize(1000, 650)
        root.configure(bg=COLORS["bg"])

        self.store = SettingsStore()
        self.state, self.custom_presets = self.store.load()
        config_dir = discover_config_dir()
        self.backend = EqualizerApoBackend(config_dir) if config_dir else None
        self.band_vars = {frequency: tk.DoubleVar(value=self.state.gains[frequency]) for frequency in FREQUENCIES}
        self.preamp_var = tk.DoubleVar(value=self.state.preamp)
        self.enabled_var = tk.BooleanVar(value=self.state.enabled)
        self.auto_headroom_var = tk.BooleanVar(value=True)
        self.preset_var = tk.StringVar(value="Custom")
        self.status_var = tk.StringVar()
        self.headroom_var = tk.StringVar()
        self._loading_values = False

        self._configure_styles()
        self._build_layout()
        self._refresh_backend_status()
        self._update_readouts()
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Surface.TFrame", background=COLORS["surface"])
        style.configure("Sidebar.TFrame", background=COLORS["sidebar"])
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=("Segoe UI", 9))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 24), foreground=COLORS["text"])
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground=COLORS["muted"])
        style.configure("CardTitle.TLabel", background=COLORS["surface"], font=("Segoe UI Semibold", 12), foreground=COLORS["text"])
        style.configure("CardText.TLabel", background=COLORS["surface"], font=("Segoe UI", 9), foreground=COLORS["muted"])
        style.configure("Value.TLabel", background=COLORS["surface"], font=("Segoe UI Semibold", 9), foreground=COLORS["primary"])
        style.configure("SidebarTitle.TLabel", background=COLORS["sidebar"], foreground="white", font=("Segoe UI Semibold", 17))
        style.configure("SidebarText.TLabel", background=COLORS["sidebar"], foreground="#AEB7C6", font=("Segoe UI", 9))
        style.configure("SidebarStatus.TLabel", background=COLORS["sidebar_panel"], foreground="#DDE4EE", font=("Segoe UI", 9), padding=10)
        style.configure("Primary.TButton", background=COLORS["primary"], foreground="white", borderwidth=0, padding=(15, 10), font=("Segoe UI Semibold", 9))
        style.map("Primary.TButton", background=[("active", COLORS["primary_dark"]), ("pressed", "#432DBA")])
        style.configure("Secondary.TButton", background=COLORS["surface"], foreground=COLORS["text"], bordercolor=COLORS["border"], borderwidth=1, padding=(12, 8), font=("Segoe UI Semibold", 9))
        style.map("Secondary.TButton", background=[("active", "#F0F2F6")])
        style.configure("Sidebar.TButton", background=COLORS["sidebar_panel"], foreground="#E5EAF2", bordercolor="#344155", borderwidth=1, padding=(12, 9), font=("Segoe UI Semibold", 9))
        style.map("Sidebar.TButton", background=[("active", "#2A374A")])
        style.configure("TCombobox", padding=(8, 7), fieldbackground="white", bordercolor=COLORS["border"])
        style.configure("TCheckbutton", background=COLORS["surface"], foreground=COLORS["text"], font=("Segoe UI", 9))
        style.map("TCheckbutton", background=[("active", COLORS["surface"])])

    def _build_layout(self) -> None:
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(self.root, style="Sidebar.TFrame", width=245, padding=(22, 24))
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        ttk.Label(sidebar, text="Laptop\nEqualizer", style="SidebarTitle.TLabel").pack(anchor="w")
        ttk.Label(sidebar, text="One sound profile for all playback", style="SidebarText.TLabel", wraplength=190).pack(anchor="w", pady=(7, 28))

        enabled = ttk.Checkbutton(sidebar, text="Equalizer enabled", variable=self.enabled_var, command=self._values_changed)
        enabled.configure(style="SidebarToggle.TCheckbutton")
        style = ttk.Style(self.root)
        style.configure("SidebarToggle.TCheckbutton", background=COLORS["sidebar"], foreground="white", font=("Segoe UI Semibold", 10))
        style.map("SidebarToggle.TCheckbutton", background=[("active", COLORS["sidebar"])], foreground=[("active", "white")])
        enabled.pack(anchor="w", pady=(0, 16))

        ttk.Button(sidebar, text="Apply to audio", style="Primary.TButton", command=self.apply_settings).pack(fill="x")
        ttk.Button(sidebar, text="Set up Equalizer APO", style="Sidebar.TButton", command=self.setup_backend).pack(fill="x", pady=(10, 0))
        ttk.Button(sidebar, text="Choose output devices", style="Sidebar.TButton", command=self.open_device_selector).pack(fill="x", pady=(8, 0))
        ttk.Label(sidebar, textvariable=self.status_var, style="SidebarStatus.TLabel", wraplength=180, justify="left").pack(fill="x", pady=(22, 0))
        ttk.Label(sidebar, text="Affects normal Windows playback only. Your microphone is never changed.", style="SidebarText.TLabel", wraplength=190, justify="left").pack(side="bottom", anchor="w")

        content = ttk.Frame(self.root, padding=(30, 25))
        content.grid(row=0, column=1, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(2, weight=1)
        ttk.Label(content, text="Shape your laptop sound", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(content, text="The same profile applies to YouTube, browsers, Spotify, games, and other playback apps.", style="Subtitle.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 20))

        card = ttk.Frame(content, style="Surface.TFrame", padding=(22, 20))
        card.grid(row=2, column=0, sticky="nsew")
        card.columnconfigure(tuple(range(11)), weight=1)
        card.rowconfigure(2, weight=1)

        ttk.Label(card, text="10-band graphic equalizer", style="CardTitle.TLabel").grid(row=0, column=0, columnspan=5, sticky="w")
        preset_box = ttk.Combobox(card, textvariable=self.preset_var, state="readonly", width=20)
        preset_box["values"] = self._preset_names()
        preset_box.grid(row=0, column=7, columnspan=3, sticky="e", padx=(10, 8))
        preset_box.bind("<<ComboboxSelected>>", self._load_preset)
        self.preset_box = preset_box
        ttk.Button(card, text="Save preset", style="Secondary.TButton", command=self.save_preset).grid(row=0, column=10, sticky="e")

        ttk.Separator(card).grid(row=1, column=0, columnspan=11, sticky="ew", pady=(16, 10))

        preamp_frame = ttk.Frame(card, style="Surface.TFrame")
        preamp_frame.grid(row=2, column=0, sticky="ns", padx=(0, 18), pady=(5, 0))
        ttk.Label(preamp_frame, text="PREAMP", style="CardText.TLabel").pack()
        self.preamp_value_label = ttk.Label(preamp_frame, text="0 dB", style="Value.TLabel")
        self.preamp_value_label.pack(pady=(5, 4))
        self._make_scale(preamp_frame, self.preamp_var, -20, 12).pack(expand=True, fill="y")
        ttk.Label(preamp_frame, text="Level", style="CardText.TLabel").pack(pady=(5, 0))

        self.value_labels: dict[int, ttk.Label] = {}
        for column, frequency in enumerate(FREQUENCIES, start=1):
            band = ttk.Frame(card, style="Surface.TFrame")
            band.grid(row=2, column=column, sticky="ns", padx=5, pady=(5, 0))
            value = ttk.Label(band, text="0 dB", style="Value.TLabel")
            value.pack(pady=(23, 4))
            self.value_labels[frequency] = value
            self._make_scale(band, self.band_vars[frequency], -12, 12).pack(expand=True, fill="y")
            ttk.Label(band, text=frequency_label(frequency), style="CardText.TLabel").pack(pady=(5, 0))
            ttk.Label(band, text="Hz" if frequency < 1000 else "kHz", style="CardText.TLabel").pack()

        footer = ttk.Frame(card, style="Surface.TFrame")
        footer.grid(row=3, column=0, columnspan=11, sticky="ew", pady=(18, 0))
        footer.columnconfigure(1, weight=1)
        ttk.Checkbutton(footer, text="Automatically add headroom to prevent clipping", variable=self.auto_headroom_var, command=self._auto_headroom_changed).grid(row=0, column=0, sticky="w")
        self.headroom_label = ttk.Label(footer, textvariable=self.headroom_var, style="CardText.TLabel")
        self.headroom_label.grid(row=0, column=1, sticky="e")
        ttk.Button(footer, text="Reset flat", style="Secondary.TButton", command=lambda: self._set_state(EqualizerState.flat(), "Flat")).grid(row=0, column=2, padx=(16, 0))

    def _make_scale(self, parent: ttk.Frame, variable: tk.DoubleVar, minimum: float, maximum: float) -> tk.Scale:
        return tk.Scale(
            parent, variable=variable, from_=maximum, to=minimum, resolution=0.5,
            orient="vertical", showvalue=False, length=285, width=11, sliderlength=19,
            bg=COLORS["surface"], activebackground=COLORS["primary"],
            troughcolor=COLORS["track"], highlightthickness=0, borderwidth=0,
            command=lambda _value: self._values_changed(),
        )

    def _current_state(self) -> EqualizerState:
        return EqualizerState(
            self.enabled_var.get(), self.preamp_var.get(),
            {frequency: variable.get() for frequency, variable in self.band_vars.items()},
        ).normalized()

    def _values_changed(self) -> None:
        if self._loading_values:
            return
        if self.auto_headroom_var.get():
            target = recommended_preamp({frequency: variable.get() for frequency, variable in self.band_vars.items()})
            self.preamp_var.set(target)
        self.preset_var.set("Custom")
        self._update_readouts()

    def _auto_headroom_changed(self) -> None:
        if self.auto_headroom_var.get():
            self.preamp_var.set(recommended_preamp(self._current_state().gains))
        self._update_readouts()

    def _update_readouts(self) -> None:
        state = self._current_state()
        self.preamp_value_label.configure(text=f"{state.preamp:+.1f} dB")
        for frequency, label in self.value_labels.items():
            label.configure(text=f"{state.gains[frequency]:+.1f}")
        peak = state.preamp + max(state.gains.values())
        if peak > 0.01:
            self.headroom_var.set(f"Possible clipping: estimated peak {peak:+.1f} dB")
            self.headroom_label.configure(foreground=COLORS["danger"])
        else:
            self.headroom_var.set(f"Headroom {abs(peak):.1f} dB")
            self.headroom_label.configure(foreground=COLORS["success"])

    def _preset_names(self) -> tuple[str, ...]:
        return ("Custom", *DEFAULT_PRESETS.keys(), *sorted(self.custom_presets))

    def _load_preset(self, _event: object = None) -> None:
        name = self.preset_var.get()
        if name == "Custom":
            return
        state = preset_state(name) if name in DEFAULT_PRESETS else self.custom_presets[name]
        self._set_state(state, name)

    def _set_state(self, state: EqualizerState, preset_name: str = "Custom") -> None:
        self._loading_values = True
        try:
            self.enabled_var.set(state.enabled)
            self.preamp_var.set(state.preamp)
            for frequency in FREQUENCIES:
                self.band_vars[frequency].set(state.gains[frequency])
            self.preset_var.set(preset_name)
        finally:
            self._loading_values = False
        self._update_readouts()

    def save_preset(self) -> None:
        name = simpledialog.askstring("Save preset", "Preset name:", parent=self.root)
        if not name or not name.strip():
            return
        name = name.strip()[:40]
        if name in DEFAULT_PRESETS:
            messagebox.showwarning("Reserved name", "Choose a different name; built-in presets cannot be replaced.", parent=self.root)
            return
        self.custom_presets[name] = self._current_state()
        self.preset_box["values"] = self._preset_names()
        self.preset_var.set(name)
        self.store.save(self._current_state(), self.custom_presets)

    def setup_backend(self) -> None:
        if not self.backend:
            self._offer_equalizer_apo_install()
            return
        try:
            self.backend.install_integration()
            self.backend.apply(self._current_state())
        except EqualizerError as exc:
            messagebox.showerror("Setup could not finish", str(exc), parent=self.root)
        else:
            messagebox.showinfo("Setup complete", "Laptop Equalizer is connected. Changes will apply when you press Apply to audio.", parent=self.root)
        self._refresh_backend_status()

    def apply_settings(self) -> None:
        if not self.backend or not self.backend.is_integrated:
            messagebox.showwarning("Setup required", "Install and set up Equalizer APO first.", parent=self.root)
            return
        state = self._current_state()
        try:
            self.backend.apply(state)
            self.store.save(state, self.custom_presets)
        except (EqualizerError, OSError) as exc:
            messagebox.showerror("Could not apply settings", str(exc), parent=self.root)
            self.status_var.set("Settings were not applied.")
        else:
            self.status_var.set("Applied successfully. Equalizer APO reloads changes immediately.")

    def open_device_selector(self) -> None:
        if not self.backend:
            self._offer_equalizer_apo_install()
            return
        configurator = self.backend.config_dir.parent / "Configurator.exe"
        if not configurator.is_file():
            messagebox.showerror("Device selector not found", f"Could not find {configurator}", parent=self.root)
            return
        try:
            subprocess.Popen([str(configurator)], cwd=str(configurator.parent))
        except OSError as exc:
            messagebox.showerror("Could not open device selector", str(exc), parent=self.root)

    def _offer_equalizer_apo_install(self) -> None:
        answer = messagebox.askyesno(
            "Equalizer APO required",
            "System-wide equalization for YouTube, browsers, and Spotify needs "
            "the Equalizer APO audio component. It is not installed on this PC.\n\n"
            "Open the official download page now?\n\n"
            "After installation:\n"
            "1. Select your speaker/headphone output in its Configurator.\n"
            "2. Restart Windows if requested.\n"
            "3. Reopen Laptop Equalizer and click Set up Equalizer APO.",
            parent=self.root,
        )
        if answer:
            webbrowser.open("https://sourceforge.net/projects/equalizerapo/")

    def _refresh_backend_status(self) -> None:
        if not self.backend:
            self.status_var.set("Equalizer APO not detected. Install it to enable system-wide playback EQ.")
        elif self.backend.is_integrated:
            self.status_var.set("Ready. Connected to Equalizer APO.")
        else:
            self.status_var.set("Equalizer APO detected. Complete the one-time setup.")

    def _on_close(self) -> None:
        try:
            self.store.save(self._current_state(), self.custom_presets)
        except OSError:
            pass
        self.root.destroy()
