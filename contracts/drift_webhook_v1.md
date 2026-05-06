# Drift Webhook Contract v1

## Purpose

This contract defines the HTTP webhook sent from the `model_service` to the `agent` when the drift report changes severity.

The model service owns drift detection. The agent owns investigations and follow-up actions.

---

## Direction

```txt
model_service  --->  agent