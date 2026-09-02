# Restricted model interface

The restricted model implementation is not distributed with this package.

The private stage may read authorized participant-level inputs in its approved environment. It must write only disclosure-checked aggregate files that satisfy `schemas/aggregate_output.schema.json`.

The public stage does not require or import the private likelihood, order-integration, optimization, parameter-vector, information-matrix, or checkpoint modules. Replacing the restricted stage is permitted only when the replacement emits the same aggregate schema and passes the public validation checks.

Model-reliability inputs are limited to model-level diagnostics and synthetic validation records defined in `schemas/model_reliability_input.schema.json`.
