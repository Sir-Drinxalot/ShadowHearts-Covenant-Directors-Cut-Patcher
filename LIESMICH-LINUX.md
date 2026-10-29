# Shadow Hearts: Covenant – Director's Cut Patcher für Linux

Linux-Anleitung für den Patcher (v0.3.2, ursprünglich [JimmyMcThiccus/ShadowHearts-Covenant-Directors-Cut-Patcher](https://github.com/JimmyMcThiccus/ShadowHearts-Covenant-Directors-Cut-Patcher)). Dasselbe Skript läuft unter Windows und Linux, und die Patch-Logik ist dieselbe. Die fertigen ISOs sind also identisch. Die ausführliche englische Anleitung steht in `README.md`.

## Was für Linux angepasst wurde

- **`pcmscodec` ist ein natives Linux-Programm** (x86_64, statisch gelinkt, läuft auf jeder Distribution und auf dem Steam Deck). Es ersetzt `pcmscodec.exe` und wurde aus dem mitgelieferten Rust-Quelltext in `pcmscodec_src/` gebaut.
- **Die Codec-Suche im Patcher wurde angepasst.** Bisher nahm der Patcher immer zuerst `pcmscodec.exe`, auch unter Linux. Das scheitert dort, und die zwei umgerechneten UnDub-Szenen behalten ohne klare Fehlermeldung den englischen Ton. Jetzt gilt:
  1. `pcmscodec` neben dem Skript. Ein fehlendes Ausführungsrecht (passiert oft beim Entpacken) wird automatisch gesetzt.
  2. Sonst `pcmscodec` im `PATH`.
  3. Sonst, falls Rust (`cargo`) installiert ist: Der Codec wird aus `pcmscodec_src/` gebaut. Das ist z. B. auf ARM-Rechnern nötig.

  Jeder Kandidat wird vorher kurz getestet, damit ein Programm für die falsche CPU nicht erst mitten im Patchen auffällt.
- Bei `--edition undub` meldet der Patcher gleich zu Beginn, ob numpy oder der Codec fehlen, und nennt den passenden Installationsbefehl.

## Voraussetzungen

- Deine eigenen ISOs: *Shadow Hearts: Covenant* (USA) Disc 1+2 und *Shadow Hearts II Director's Cut* (Japan) Disc 1+2
- Python 3.8 oder neuer (ist auf praktisch jeder Distribution schon installiert)
- Nur für die **UnDub**-Edition: numpy (scipy ist optional und liefert ein etwas besseres Resampling)

```bash
sudo apt install python3-numpy python3-scipy      # Debian, Ubuntu, Mint, Pop!_OS
```
```bash
sudo dnf install python3-numpy python3-scipy      # Fedora
```
```bash
sudo pacman -S python-numpy python-scipy          # Arch, Manjaro
```

Auf dem Steam Deck (SteamOS ist schreibgeschützt) geht es am einfachsten mit einer virtuellen Umgebung:

```bash
python3 -m venv ~/sh2dc-venv && ~/sh2dc-venv/bin/pip install numpy scipy
```

Danach startest du den Patcher mit `~/sh2dc-venv/bin/python3` statt `python3`.

## Benutzung

Im entpackten Ordner (`sh2dc_patcher.py`, `patchdata.zip` und `pcmscodec` müssen zusammen liegen):

```bash
python3 sh2dc_patcher.py --edition regular --us1 "US Disc 1.iso" --us2 "US Disc 2.iso" --dc1 "DC Disc 1.iso" --dc2 "DC Disc 2.iso" --out Patched
```

- `--edition undub` statt `regular` für die japanischen Stimmen
- `--discs 1` baut nur Disc 1 (dafür reichen `--us1` und `--dc1`)
- `--single-disc` baut ein einziges Image ohne Discwechsel (braucht alle vier ISOs, ergibt ca. 6,9 GB)

Pfade mit Leerzeichen bitte in Anführungszeichen setzen. Pro Disc werden etwa 5 GB freier Speicher gebraucht. Deine Original-ISOs werden nicht verändert.

## Codec selbst bauen (optional)

Wenn du dem mitgelieferten Programm nicht traust oder kein x86_64 hast:

```bash
cd pcmscodec_src && cargo build --release && cp target/release/pcmscodec .. && cd ..
```

Oder einfach `pcmscodec` löschen. Ist `cargo` installiert, baut der Patcher den Codec beim nächsten UnDub-Lauf selbst.
