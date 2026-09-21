# Layer 2 — Analysis

Layer 2 consumes Layer 1 data. It does not collect data. It does not depend on fish, powuk, or any other POW.

## What belongs here

- Signal construction from Layer 1 observations
- Backtesting and evaluation
- Model training and prediction
- Cross-domain analysis (does UK grid constraint predict LSE repricing?)
- Experiment tracking

## What does NOT belong here

- Collectors (those are Layer 1)
- Raw data storage (Layer 1)
- Domain-specific scrapers (Layer 1)
- Trading execution (separate repo)
- Dashboards (separate repo)

## Architecture

```
Layer 1 (data garden)
  ├── source manifests (operational contract)
  ├── collectors (each source has one)
  ├── raw bytes (append-only)
  ├── normalized events (idempotent)
  └── health checks

Layer 2 (analysis)  ← you are here
  ├── signals (from Layer 1 observations)
  ├── models (compete on same data)
  ├── experiments (versioned, reproducible)
  └── evaluations (which model predicts?)
```

## The Key Distinction

Layer 1 preserves the tape. Layer 2 asks questions about the tape.

Baking the target model into the sensor is a mistake. Layer 1 must remain model-agnostic.
