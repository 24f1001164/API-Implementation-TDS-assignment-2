import re
from datetime import datetime
from dateutil.parser import parse

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class InvoiceRequest(BaseModel):
    text: str


class InvoiceResponse(BaseModel):
    vendor: str
    amount: float
    currency: str
    date: str


CURRENCIES = ["USD", "EUR", "GBP"]


def extract_vendor(text: str):
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # Look for Vendor:
    for line in lines:
        m = re.search(r"Vendor[:\-]?\s*(.+)", line, re.I)
        if m:
            return m.group(1).strip()

    # Ignore invoice-related lines
    ignore = [
        "invoice",
        "amount",
        "total",
        "due",
        "currency",
        "date",
        "payment",
    ]

    for line in lines:
        low = line.lower()
        if not any(x in low for x in ignore):
            return line.strip()

    return ""


def extract_amount(text: str):
    patterns = [
        r"Total(?: Due)?[: ]+\$?([0-9]+(?:\.[0-9]{1,2})?)",
        r"Amount(?: Due)?[: ]+\$?([0-9]+(?:\.[0-9]{1,2})?)",
        r"Due[: ]+\$?([0-9]+(?:\.[0-9]{1,2})?)",
        r"\$([0-9]+(?:\.[0-9]{1,2})?)",
    ]

    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return float(m.group(1))

    nums = re.findall(r"\b\d+(?:\.\d+)?\b", text)
    if nums:
        return float(max(nums, key=float))

    return 0.0


def extract_currency(text: str):
    m = re.search(r"\b(USD|EUR|GBP)\b", text, re.I)
    if m:
        return m.group(1).upper()

    if "$" in text:
        return "USD"

    return ""


def extract_date(text: str):
    # Already ISO
    m = re.search(r"(2026-\d{2}-\d{2})", text)
    if m:
        return m.group(1)

    # General date parser
    candidates = re.findall(
        r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|[A-Za-z]+ +\d{1,2}, +\d{4})",
        text,
    )

    for c in candidates:
        try:
            d = parse(c, fuzzy=True)
            return d.strftime("%Y-%m-%d")
        except Exception:
            pass

    return ""


@app.post("/extract", response_model=InvoiceResponse)
def extract(req: InvoiceRequest):

    text = req.text.strip()

    if not text:
        return InvoiceResponse(
            vendor="",
            amount=0,
            currency="",
            date=""
        )

    return InvoiceResponse(
        vendor=extract_vendor(text),
        amount=extract_amount(text),
        currency=extract_currency(text),
        date=extract_date(text),
    )
