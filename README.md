# FIBlock-Py

```python
from fiblock import Bias, Drift, Delay, PacketLoss
```

FIBlock-Py is the Python implementation of **FIBlock**, a model-based
fault-injection framework for cyber-physical systems. It provides a
programmable API for deterministic, stochastic, and algorithmically controlled
injection of faults across heterogeneous CPS components: sensing,
computation/control, communication, and physical elements.

The original FIBlock is a MATLAB/Simulink block library:
**https://github.com/TagirFabarisov/FIBlock**. FIBlock-Py is written from
scratch in Python and carries over the FIBlock idea: a fault attached to a
point in the system, described by independent, freely combinable choices of
what the error looks like, when it activates, and how long it lasts, with
per-fault enabling, multi-point injection, chained (conditional) faults, and a
labelled record of every activation. Users can define their own fault types.

**Status:** under development. The API shown above is the target interface.

## Citation

If you use FIBlock or FIBlock-Py, please cite the original FIBlock paper:

> T. Fabarisov, I. Mamaev, A. Morozov, and K. Janschek,
> "Model-based Fault Injection Experiments for the Safety Analysis of
> Exoskeleton System," *Proceedings of ESREL 2020 / PSAM 15*, 2020.
> arXiv:[2101.01283](https://arxiv.org/abs/2101.01283).

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
