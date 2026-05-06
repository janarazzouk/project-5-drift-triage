# Promotion Request Contract v1

## Purpose

This contract defines the HTTP request sent from the `agent` to the `model_service` when a human has approved a Production promotion.

The agent does not directly promote the model. The agent only requests promotion after human approval.

The model service remains responsible for running the programmatic promotion checklist and deciding whether promotion is allowed or blocked.

---

## Direction

```txt
agent  --->  model_service