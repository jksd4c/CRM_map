# CRM_map

Reproducible analysis code for the CRMmap study.

The build reproduces publication tables, Figures 2-3, model-diagnostic summaries, and Weibull state-duration analyses from disclosure-checked aggregate inputs.

```bash
python -m pip install -r requirements.txt
python scripts/build_release_outputs.py --input-dir path/to/aggregate_inputs --output-dir build
```

The Weibull module can also be run separately:

```bash
python scripts/build_weibull_outputs.py --input-dir path/to/weibull_inputs --output-dir build/weibull
```

Required aggregate input columns are listed in `schemas/weibull_aggregate_input.schema.json`. The public module evaluates supplied transition parameters; it does not fit the interval-censored multistate model.
