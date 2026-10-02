"""
build_exe.py  -  EK J .exe banavva mate.

Chalavva:  BUILD-EXE.bat  par double-click
Athva:     python build_exe.py

Banshe:  dist/M32-AutoFX.exe   <-- BAS AA EK J FILE

Aa ek file ma badhu bhegu chhe:
   * Screen wado program (GUI)
   * Automation
   * Mixer shodhvanu, channel pasand karvanu, scan, test
   * Nakli mixer (mixer vagar test karva)
   * Badhi guide file (gujarati ma)

Pehli var chalavo etle config.json ane guide file jate
exe ni bajuma bani jashe.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "M32-AutoFX"

# aa file exe ni ANDAR mukvani (pachhi jate bahar nikle chhe)
DATA_FILES = [
    "VAANCHO.txt",
    "README-GUJARATI.txt",
    "JAVAB-TAMARA-SAVAL.txt",
    "CODING-GUIDE.txt",
]

# aa module code ma andar thi import thay chhe, etle hathe kahevu pade
HIDDEN = [
    "m32_gui", "m32_automation", "m32_engine", "m32_core", "osc_lite",
    "m32_switcher", "m32_simulator", "find_mixer", "meter_scan",
    "channel_select", "test_fx", "test_all",
]


def make_vaancho():
    """dist ma mukvani tunki gujarati guide."""
    return """\
========================================================================
        MIDAS M32  --  AUTO FX MUTE
        (Python ni jarur nathi -- ek j file)
========================================================================

CHALU KARVA :  M32-AutoFX.exe  par double-click.  Bas.

Aa EK J FILE ne gme tya copy karo -- pen drive ma, bija PC ma,
gme tya. Pehli var chalavo etle baaki ni badhi file
(config.json, guide) JATE tени bajuma bani jashe.


-------------------------------------------------------------
PEHLI VAR VAAPRO TYARE
-------------------------------------------------------------

  1. LAN cable mixer na REMOTE port ma ane PC ma bharavo
  2. M32-AutoFX.exe kholo
  3. "Network ma shodho" dabavo -- mixer jate mali jashe
  4. Dabi baju je mic sambhalva hoy tena par tick karo
  5. Jamni baju thi nakki karo shu chalu/band karvu
     (Mute Group 5 pehlethi set chhe)
  6. TEST dabavi ne mixer ni screen par check karo
  7. Badhu barabar lage to  CHALU KARO  dabavo


-------------------------------------------------------------
MIXER NA HOY TO PAN CHALSE
-------------------------------------------------------------

  M32-AutoFX.exe gui --sim

  Nakli M32 andar j chalu thai jashe. Nakli kalakaar gata
  dekhashe: CH 1 Guruji, CH 2 Vocal 2, CH 4 Tabla, CH 5 Flute.


-------------------------------------------------------------
BIJA TOOL (CMD ma)
-------------------------------------------------------------

  M32-AutoFX.exe tools           badhi yaadi batave
  M32-AutoFX.exe run             CMD ma automation chalavo
  M32-AutoFX.exe find            network ma mixer shodho
  M32-AutoFX.exe select 1,5,9    channel 1, 5, 9 pasand karo
  M32-AutoFX.exe scan            bolo etle channel jate shodhe
  M32-AutoFX.exe testfx          3 var on/off kari ne check karo
  M32-AutoFX.exe test            badha test chalavo (mixer vagar)
  M32-AutoFX.exe sim             fakt nakli mixer chalavo


-------------------------------------------------------------
DHYAN RAKHO
-------------------------------------------------------------

  * GUI kholo etle turat meter dekhashe, PAN "CHALU KARO"
    dabavo tya sudhi MIXER PAR KAI J NAHI THAY.
    Etle live program vakhte pan salamat rite kholi shakay.

  * Antivirus kyarek navu .exe ne roke chhe (PyInstaller thi
    banela badha exe sathe aavu thay chhe). "Allow" / "Keep"
    dabavo, athva antivirus ma aa folder ne chhut aapo.

  * PC band thay to automation band thai jashe, pan mixer
    jem chhe tem chalu rahe chhe. Vadhare mahiti mate
    JAVAB-TAMARA-SAVAL.txt vancho.

========================================================================
"""


def main():
    # VAANCHO.txt taiyar karo (exe ni andar jashe)
    with open(os.path.join(HERE, "VAANCHO.txt"), "w", encoding="utf-8") as f:
        f.write(make_vaancho())

    sep = ";" if os.name == "nt" else ":"
    cmd = [sys.executable, "-m", "PyInstaller",
           "--onefile", "--windowed", "--clean", "--noconfirm",
           "--name", NAME,
           "--distpath", os.path.join(HERE, "dist"),
           "--workpath", os.path.join(HERE, "build"),
           "--specpath", os.path.join(HERE, "build"),
           "--paths", HERE]

    icon = os.path.join(HERE, "icon.ico")
    if os.path.exists(icon):
        cmd += ["--icon", icon]

    for mod in HIDDEN:
        cmd += ["--hidden-import", mod]

    for name in DATA_FILES:
        path = os.path.join(HERE, name)
        if os.path.exists(path):
            cmd += ["--add-data", "%s%s." % (path, sep)]

    # docs folder ane REQUIREMENTS pan andar mukо
    docs = os.path.join(HERE, "docs")
    if os.path.isdir(docs):
        cmd += ["--add-data", "%s%sdocs" % (docs, sep)]
    req = os.path.join(HERE, "REQUIREMENTS.md")
    if os.path.exists(req):
        cmd += ["--add-data", "%s%s." % (req, sep)]

    cmd.append(os.path.join(HERE, "m32_app.py"))

    print("=" * 64)
    print("   %s.exe banavu chhu ...  (2-3 minute)" % NAME)
    print("=" * 64)
    if subprocess.run(cmd).returncode != 0:
        print("[X] exe banyu nahi")
        return 1

    # juna be exe hoy to kaadhi nakho (have ek j joiye)
    dist = os.path.join(HERE, "dist")
    for old in ("M32-AutoFX-CMD.exe", "CHALU-KARO.bat"):
        p = os.path.join(dist, old)
        if os.path.exists(p):
            os.remove(p)
    # juni chhutti file pan kaadhi nakho -- exe jate banavi deshe
    for old in DATA_FILES + ["config.json"]:
        p = os.path.join(dist, old)
        if os.path.exists(p):
            os.remove(p)

    exe = os.path.join(dist, NAME + ".exe")
    size = os.path.getsize(exe) / (1024.0 * 1024.0)

    print()
    print("=" * 64)
    print("   THAI GAYU !")
    print("=" * 64)
    print("   %s   (%.1f MB)" % (exe, size))
    print()
    print("   BAS AA EK J FILE copy karvani chhe.")
    print("   Pehli var chalavo etle config.json ane badhi guide")
    print("   file jate teni bajuma bani jashe.")
    print("=" * 64)

    return 0


if __name__ == "__main__":
    sys.exit(main())
