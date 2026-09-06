from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Synaptix - SIH26034 Legal Metrology Inspector")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before deployment
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/inspect")
def inspect():
    # Day 1 stub: return a hardcoded object matching shared/schemas/inspection_schema.json
    # so the frontend team can build against a real shape immediately.
    return {
        "inspection_id": "INS-STUB-001",
        "product": {"name": "Sample Product", "category": "food"},
        "fields": {
            "manufacturer": None,
            "country_of_origin": None,
            "net_quantity": None,
            "manufacture_date": None,
            "mrp": None,
            "consumer_care": None,
        },
        "visual_checks": {"readability": None, "font_height": None, "placement": None},
        "compliance": {"status": "REVIEW", "violations": []},
    }
