# CRM_map

Reproducible analysis code for the CRMmap study.

The build reproduces publication tables, Figures 2-3, and the model-reliability summaries used in Supplementary Table S9 from disclosure-checked aggregate inputs.

```bash
python -m pip install -r requirements.txt
python scripts/build_release_outputs.py --input-dir path/to/aggregate_inputs --output-dir build
```
