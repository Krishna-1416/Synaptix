# reports/ — Backend Engineer (report generation)

## Owns
- ReportLab templates for the generated PDF compliance report
- `generated/` subfolder for output PDFs at runtime (gitignored — don't commit generated files)

## Suggested structure
```
reports/
├── templates/
│   └── compliance_report_template.py   # ReportLab layout: fields, violations, evidence images
└── generated/          # gitignored - runtime output only
```
