# ml/ — ML / Data Engineer

**Stack:** Kaggle (experiments), Label Studio/CVAT (annotation), Hugging Face (optional lightweight models).

## Owns
- Dataset sourcing/annotation for any classification needs (e.g. product
  category detection, label-region classification)
- Evaluating *where* ML actually helps beyond the OCR + rules baseline
  (the baseline must work without ML — this is additive only)
- Fine-tuning/deploying a lightweight model only if the team decides it's needed

## Suggested datasets to start from
- Open Food Facts (product/label images + structured fields, India subset available)
- Open Food Facts AWS Images Dataset (images + pre-run OCR JSON)

## Suggested structure
```
ml/
├── notebooks/            # Kaggle/Colab experiments
├── annotation/             # Label Studio/CVAT project configs
├── datasets/                # scripts to pull/prep Open Food Facts data
├── models/                   # trained weights (gitignored, keep out of repo)
└── inference.py                # only wired into backend if baseline needs it
```

## Day 1–7 goal
This folder is explicitly **optional-path** work. Confirm with the team by
Day 3–4 whether ML adds real value on top of OCR+rules before investing
further time — don't let this block the core demo.
