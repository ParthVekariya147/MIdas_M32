"""
m32_app.py  -  EK J ENTRY.  Badhu ahi thi chalu thay chhe.

.exe banave to AA file thi bane chhe. Etle:
  * Ek j M32-AutoFX.exe copy karo -- bijа kai ni jarur nathi
  * Pehli var chalavo etle config.json ane badhi guide file
    jate exe ni bajuma bani jashe
  * Double-click        -> screen wado program (GUI) khule
  * Argument aapo       -> CMD tool chale (console jate khule)

Dakhla:
    M32-AutoFX.exe                    GUI khole
    M32-AutoFX.exe gui --sim          GUI + nakli mixer
    M32-AutoFX.exe run                background automation
    M32-AutoFX.exe find               network ma mixer shodho
    M32-AutoFX.exe select 1,5,9       channel pasand karo
    M32-AutoFX.exe scan               bolo etle channel jate shodhe
    M32-AutoFX.exe testfx             3 var on/off kari ne check
    M32-AutoFX.exe sim                nakli mixer chalavo
    M32-AutoFX.exe test               badha test chalavo
    M32-AutoFX.exe tools              aa yaadi batave
"""

import os
import sys

# tool nu naam -> (module, function, gujarati varnan)
TOOLS = {
    "gui":    ("m32_gui",        "Screen wado program (GUI)"),
    "run":    ("m32_automation", "Automation CMD ma chalavo"),
    "find":   ("find_mixer",     "Network ma mixer shodho"),
    "select": ("channel_select", "Channel jate pasand karo"),
    "scan":   ("meter_scan",     "Bolo etle channel jate shodhe"),
    "testfx": ("test_fx",        "3 var on/off kari ne check karo"),
    "sim":    ("m32_simulator",  "Nakli mixer chalavo"),
    "test":   ("test_all",       "Badha test chalavo (mixer vagar)"),
}

GUI_TOOLS = ("gui",)


# ---------------------------------------------------------------- console
def ensure_console():
    """
    Windowed exe ma kaali window hoti nathi. CMD tool chalavvu hoy
    tyare ahi thi ek console kholi devay chhe.
    """
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        if kernel32.GetConsoleWindow():
            return                       # pehlethi console chhe

        # CMD mathi chalavyu hoy to E J window ma lakho,
        # nahi to navi window kholo.
        ATTACH_PARENT_PROCESS = -1
        if not kernel32.AttachConsole(ATTACH_PARENT_PROCESS):
            if not kernel32.AllocConsole():
                return
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)
        try:
            sys.stdin = open("CONIN$", "r", encoding="utf-8")
        except OSError:
            pass
    except Exception:
        pass


def hold_console():
    """Tool puru thay etle window turat band na thai jay."""
    if not getattr(sys, "frozen", False):
        return
    try:
        print()
        input("  ENTER dabavo etle aa window band thashe... ")
    except Exception:
        pass


def show_tools(made=None):
    exe = os.path.basename(sys.argv[0])
    print()
    print("=" * 64)
    print("   MIDAS M32  --  AUTO FX     (badhu ek j file ma)")
    print("=" * 64)
    if made:
        print("   Aa file jate banavi didhi:")
        for name in made:
            print("      + %s" % name)
        print()
    print("   Kai na lakho to SCREEN wado program khule chhe.")
    print()
    for key, (_mod, desc) in TOOLS.items():
        print("      %s %-8s   %s" % (exe, key, desc))
    print()
    print("   Dakhla:")
    print("      %s gui --sim        GUI + nakli mixer" % exe)
    print("      %s select 1,5,9     channel 1, 5, 9 pasand karo" % exe)
    print("=" * 64)


# ---------------------------------------------------------------- run
def run_module(mod_name, strip_first):
    if strip_first:
        del sys.argv[1]
    __import__(mod_name)
    sys.modules[mod_name].main()


def main():
    import m32_core as core

    # pehli var chalavo tyare jaruri badhi file jate banavi de
    made = core.first_run_setup()

    args = sys.argv[1:]
    first = args[0].lower() if args else ""

    # ---------------- yaadi ----------------
    if first in ("tools", "list", "--tools", "-h", "--help", "/?"):
        ensure_console()
        core.setup_console()
        show_tools(made)
        hold_console()
        return

    # ---------------- GUI ----------------
    if not args or first in GUI_TOOLS:
        run_module("m32_gui", strip_first=bool(args))
        return

    # ---------------- CMD wada tool ----------------
    ensure_console()
    core.setup_console()
    if made:
        print("[i] Aa file jate banavi: %s" % ", ".join(made))

    if first in TOOLS:
        mod_name, _desc = TOOLS[first]
        run_module(mod_name, strip_first=True)
    else:
        # sidha flag aapya hoy (dakhla: --sim --index 0,4)
        run_module("m32_automation", strip_first=False)
    hold_console()


if __name__ == "__main__":
    main()
