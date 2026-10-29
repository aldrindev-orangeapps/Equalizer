"""Application entry point for Laptop Equalizer."""

import tkinter as tk

from app_ui import LaptopEqualizerApp


def main() -> None:
    root = tk.Tk()
    LaptopEqualizerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
