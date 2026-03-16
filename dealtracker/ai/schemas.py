from typing import Literal, Optional
from pydantic import BaseModel


DOC_TYPES = Literal[
    "estimate_request",
    "estimate",
    "quote_request",
    "quote",
    "purchase_order",
    "invoice",
    "payment",
    "receipt",
    "unknown",
]

DOC_TYPE_LABELS = {
    "estimate_request": "Estimate Request",
    "estimate": "Estimate",
    "quote_request": "Quote Request",
    "quote": "Quote",
    "purchase_order": "Purchase Order",
    "invoice": "Invoice",
    "payment": "Payment",
    "receipt": "Receipt",
    "unknown": "Unknown",
}

# Workflow order for display/sorting
DOC_TYPE_ORDER = [
    "estimate_request", "estimate", "quote_request", "quote",
    "purchase_order", "invoice", "payment", "receipt", "unknown",
]


class DocumentExtraction(BaseModel):
    document_date: Optional[str] = None        # ISO 8601 preferred; raw string accepted
    customer_name: Optional[str] = None
    deal_description: Optional[str] = None     # job/project description
    deal_reference: Optional[str] = None       # any job/deal/order reference number found
    document_type: DOC_TYPES = "unknown"
    total_amount_usd: Optional[float] = None
    currency_detected: str = "USD"
    notes: Optional[str] = None
    confidence: float = 0.0                    # 0.0–1.0, self-reported
    extraction_warnings: list[str] = []


EXTRACTION_SCHEMA_JSON = DocumentExtraction.model_json_schema()

SYSTEM_PROMPT = """You are a document extraction assistant for a business deal tracker.

The user runs a small business. Documents flow in this order:
  estimate_request → estimate → quote_request → quote → purchase_order → invoice → payment → receipt

Extract the following fields from the provided document and return ONLY valid JSON
matching the schema below. If a field cannot be determined with reasonable confidence,
return null. Do not invent values. Flag uncertainty in extraction_warnings.

Schema:
{
  "document_date": "ISO 8601 date string or null",
  "customer_name": "name of the customer/company or null",
  "deal_description": "brief description of the job or project or null",
  "deal_reference": "any job number, deal ID, order number, or reference code found in the document (e.g. JOB-2025-001, PO-123, Quote #7) or null if none found",
  "document_type": "one of: estimate_request | estimate | quote_request | quote | purchase_order | invoice | payment | receipt | unknown",
  "total_amount_usd": "total dollar amount as a float, or null",
  "currency_detected": "currency code, default USD",
  "notes": "any other relevant notes, caveats, or line item summary or null",
  "confidence": "your confidence in the extraction from 0.0 to 1.0",
  "extraction_warnings": ["list of uncertainty notes, e.g. 'amount unclear'"]
}

Return ONLY the JSON object, no explanation, no markdown fences.
"""
