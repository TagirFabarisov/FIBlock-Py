# Examples

Each script is self-contained and runnable. From a clone of the repository:

```bash
python -m pip install --upgrade pip       # once: editable installs need pip 21.3 or newer
pip install -e .                          # once, from the repository root
python examples/00_minimal_noise.py
```

(or, without installing, `PYTHONPATH=src python examples/00_minimal_noise.py`).

| Script | What it shows |
|---|---|
| `00_minimal_noise.py` | **Start here.** A small system that already exists (a tank, a temperature sensor, a thermostat) and the two calls that connect FIBlock to it. Noise on the sensor from t = 3 for 4 time units. |
| `01_deterministic.py` | Scheduled faults, no randomness: a methane-sensor bias and a water-sensor freeze at fixed times. |
| `02_stochastic_seeded.py` | Stochastic faults under a seed: Weibull wear-out activation with mean time to repair, a bus with a failure rate; the same seed replays exactly. |
| `03_custom_fault_type.py` | A user-defined fault type in a dozen lines: subclass `FaultType`, implement `apply`. |
| `04_chained_faults.py` | Chained faults through the trigger input: a bit flip forces a bus delay, the delay forces packet loss, the loss forces an actuator spike; the log shows the chain and the observed data errors. |
| `05_programmatic_and_replay.py` | An external search program setting the fault value between runs, export of the campaign as plain data, and exact replay from that data. |

Every script prints the values as they pass the injection points and then the
injection log, so the output shows both what the system saw and what FIBlock did.
