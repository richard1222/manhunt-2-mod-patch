# Manhunt 2 — PS3 HEN conversion

Date: 2026-10-21  
Scope: USA PS2 image, `SLUS_216.13`, supplied by the owner as an uncensored ISO.  
Success condition: create a PS2 Classics encrypted image whose decrypted contents match the supplied ISO exactly. Real-hardware playability is a separate gate.

## RR — Really Readable rundown

**Proven:** the supplied ISO was converted to `ISO.BIN.ENC`, then decrypted to an ISO with the same byte length and SHA-256 as the original. The conversion therefore preserves the supplied image's contents. The matching encrypted emulator CONFIG and PS2 Classics Launcher installer were prepared locally. **Unknown:** this converted image has not yet been booted or played on the friend's HEN PS3; neither the uncensor modifications nor cut-content restoration were independently audited in this session.

## Current state

| Class | Claim | Evidence |
| --- | --- | --- |
| Proven | ISO metadata identifies PLAYSTATION / MANHUNT2 and boot executable SLUS_216.13. | 7-Zip ISO listing |
| Proven | Original and decrypted image are each 2,657,058,816 bytes and have identical SHA-256. | Hashes below |
| Proven | Encrypted image is 2,662,268,928 bytes. | Local file measurement |
| Proven | Matching encrypted CONFIG was obtained from the webMAN MOD developer repository. | Source below; 49,152 bytes, PS2 header |
| Inference | This is the appropriate PS2 Classics image format for the friend's HEN setup. | Converter output and webMAN loading documentation |
| Unknown | Booting, saves, controls, performance, execution appearance, and stability on the friend's console. | Hardware testing pending |

The owner's CECH-2001A uses CFW. The intended recipient uses HEN; their model and firmware were not established in this session. Earlier CFW hardware findings elsewhere in this repository do not verify this HEN conversion.

## How it works

HEN uses an encrypted PS2 Classics image. The converter wraps and encrypts the existing ISO; it does not remove censorship or restore deleted content. The CONFIG is a separate emulator configuration file.

Prepared locally:

- `ISO.BIN.ENC` — encrypted game image.
- `ISO.BIN.ENC.CONFIG` — matching encrypted emulator configuration.
- `PS2_Classics_Launcher.pkg` — launcher installer only, not an installable game package.
- `READ-ME.txt` — transfer and launch instructions.

Game images, extracted assets, keys, and account files are not included in this repository.

## Evidence and conditions

Converter package: PS2 Classics GUI 2.2.3, using its bundled `ps2classic.exe` in CEX mode and standard PS2 Classics Placeholder content ID. The bundled helper derived the converter's standard placeholder key locally.

Verification method: encrypt the original read-only input; decrypt the result into a new scratch file; compare both file lengths and SHA-256 hashes.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| Supplied ISO | 2657058816 | `012476A7A233406629B0FBABD75F92F3333F21CFD8D25E581B824C5875CFB1A6` |
| Decrypted verification ISO | 2657058816 | `012476A7A233406629B0FBABD75F92F3333F21CFD8D25E581B824C5875CFB1A6` |
| Encrypted image | 2662268928 | `B0BEDD2C02C70E738ED3AA3CA387495387D95BB8CB41DC7113FF512677551BD1` |

The original input was not modified. No console screenshot was captured because no hardware test occurred in this session. Hash equality proves preservation of the input, not emulator compatibility or the nature of its modifications.

## Transfer and launch

1. Install PS2 Classics Launcher if needed; this route also requires webMAN MOD.
2. Copy `ISO.BIN.ENC` and `ISO.BIN.ENC.CONFIG` together to the PS3's internal drive:
   `/dev_hdd0/PS2ISO/Manhunt 2 [SLUS_216.13]/`.
3. Enable HEN, refresh webMAN's game list if necessary, and mount the game under webMAN Games → PLAYSTATION 2.
4. Open PS2 Classics Launcher from the XMB.

## Negative results and limitations

The initial shell download attempts for the converter failed with Windows TLS errors. The owner downloaded the archive, which extracted successfully. A first CONFIG URL using a `.CONFIG` suffix returned HTTP 404; the database's encrypted entry correctly uses `ENC/SLUS_216.13.ENC`. These failures do not indicate a problem with the game image.

## Next gate

On the friend's HEN PS3, record model, firmware, HEN/webMAN versions, boot result, a save/load test, the first bookend execution, and progress through the previously sensitive doors/truck sequence. Capture real console screenshots or video. Keep HEN compatibility marked unverified until those observations exist.

## Sources

- [PS2 Classics GUI](https://www.psx-place.com/resources/ps2-classics-gui.638/)
- [webMAN image paths and CONFIG naming](https://github.com/aldostools/webMAN-MOD/wiki/Game-Paths-%26-Covers)
- [Matching encrypted CONFIG](https://raw.githubusercontent.com/aldostools/webMAN-MOD/master/_Projects_/updater/PS2CONFIG/USRDIR/CONFIG/ENC/SLUS_216.13.ENC)
- [PS2 Classics Launcher](https://github.com/aldostools/Resources/releases/tag/Launchers)
