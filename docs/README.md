# Documentation

| Document | What's in it |
|---|---|
| [Serial API](API.md) | Every command, reply, error and event, plus timing, the startup state and a checklist for writing your own driver. Start here to control the PicoFox from software. |
| [How it works](THEORY.md) | The signal path, how the Si5351 makes FM, what the stepped modulation does to measurements, why `ATT` turns RF off briefly, and how the two processor cores share the work. |
| [Measured performance](PERFORMANCE.md) | Measurements of one PicoFox r3 on an HP 8935: output level, attenuator accuracy, level across the band, best SINAD and the tone. With methods and limits. |

THEORY.md marks how each statement is known: *from the code*, *from the
schematic*, *measured*, *computed* or *inferred*. PERFORMANCE.md gives
the method for each measurement.
