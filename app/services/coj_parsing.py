"""
Parsing service for Module 2b: CoJ Bill Parsing.

Orchestrates the full pipeline:
  1. pypdf extracts raw text from the uploaded PDF
  2. Groq LLM interprets the text into structured JSON
  3. Validation checks that extracted amounts reconcile to the invoice total

No database interaction happens here — this is pure extraction logic.
The router calls parse_invoice() and passes the result to the template.
"""

import json
import os
from decimal import Decimal, ROUND_HALF_UP

from pypdf import PdfReader
import io

from groq import Groq


# Rounding tolerance for the totals sum check (R0.10 covers floating point
# and tariff rounding differences that appear on real CoJ invoices).
TOTALS_TOLERANCE = Decimal("0.10")

# Tolerance for VAT rate check: R1.00 covers cases where CoJ applies VAT
# only to certain line items (e.g. some grants are VAT-exempt).
VAT_TOLERANCE = Decimal("1.00")


# ---------------------------------------------------------------------------
# Step 1: PDF text extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract all text from a PDF given its raw bytes.
    Returns concatenated plain text from all pages.
    Raises ValueError if the PDF yields no readable text (e.g. image-only PDF).
    """
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)

    full_text = "\n".join(pages).strip()
    if not full_text:
        raise ValueError(
            "No text could be extracted from this PDF. "
            "It may be an image-based scan. Please check the file and try again."
        )
    return full_text


# ---------------------------------------------------------------------------
# Step 2: LLM prompt construction
# ---------------------------------------------------------------------------

ELECTRICITY_PROMPT = """You are extracting structured data from a City of Johannesburg electricity invoice (City Power account).

The text below was extracted from a PDF and may be poorly formatted — table columns often run together with spaces.

CRITICAL RULE FOR STEPS:
When there is only one step, it appears like:
  Step 1 2010.000 kWh @ R 2.5755 ( Billing Period 2026/04 ) 5176.76

When there are multiple steps, ALL steps appear on a SINGLE line with one combined total at the end:
  Step 1 500.000 kWh @ R 1.5000 ( Billing Period 2026/04 ) Step 2 1510.000 kWh @ R 2.5755 ( Billing Period 2026/04 ) 4637.55

In BOTH cases: extract each step's usage_amount and rate individually. The number at the end of the line is the combined total for all steps — do NOT use it as a per-step cost. Per-step cost will be computed separately as usage_amount × rate.

Extract ALL fixed charge line items (service charge, network charge, network surcharge, extended social package grant, etc.) even if their cost is 0.00.

Return ONLY valid JSON with this exact structure — no explanation, no markdown, no code fences:

{
  "invoice_date": "YYYY-MM-DD",
  "statement_year": 2026,
  "statement_month": 4,
  "invoice_number": "string",
  "account_number": "string",
  "payment_due_date": "YYYY-MM-DD",
  "reading_period_start": "YYYY-MM-DD",
  "reading_period_end": "YYYY-MM-DD",
  "meter_number": "string",
  "start_reading": 543123.0,
  "end_reading": 545133.0,
  "consumption": 2010.0,
  "steps": [
    {"label": "Step 1", "usage_amount": 2010.0, "rate": 2.5755}
  ],
  "fixed_charges": [
    {"label": "Extended Social Package Grant", "cost": 0.00},
    {"label": "Network Surcharge", "cost": 0.00},
    {"label": "Service charge", "cost": 278.98},
    {"label": "Network charge", "cost": 1125.75}
  ],
  "total_vat": 987.22,
  "total_due": 7568.71
}

All dates must be YYYY-MM-DD. All numbers must be plain numbers (not strings). statement_month must be an integer 1-12.

Invoice text:
"""

WATER_PROMPT = """You are extracting structured data from a City of Johannesburg water and sanitation invoice (Johannesburg Water account).

The text below was extracted from a PDF and may be poorly formatted — table columns often run together with spaces.

IMPORTANT: This PDF contains THREE sections. You must extract data from the correct section:
- "City of Johannesburg / Property Rates" — IGNORE unless it contains non-zero amounts
- "Johannesburg Water / Water & Sanitation" — THIS IS THE SECTION TO EXTRACT FROM
- "PIKITUP / Refuse" — IGNORE unless it contains non-zero amounts

If Property Rates or Refuse contain non-zero amounts, add them to fixed_charges with labels "Property Rates (anomaly)" and "Refuse (anomaly)" respectively.

CRITICAL RULE FOR STEPS:
Steps may appear across one or more lines due to PDF formatting. A step always follows the pattern:
  Step N  <usage> KL @ R <rate>

For example, this may appear as:
  Step 1 23.655 KL @ R 0.0000 ( Billing Period 2026/04 ) Step 2 15.770 KL @ R 29.840 Step 3 0.575
  KL @ R 31.150
  488.49

Read across line breaks to find all steps. The standalone number after the last step (e.g. 488.49) is the combined total for all steps — do NOT use it as a per-step cost.

Extract each step's usage_amount and rate individually.

Extract ALL fixed charge line items from the Water & Sanitation section (extended social package grant, water demand levy, sewer charge, etc.) even if their cost is 0.00.

Return ONLY valid JSON with this exact structure — no explanation, no markdown, no code fences:

{
  "invoice_date": "YYYY-MM-DD",
  "statement_year": 2026,
  "statement_month": 4,
  "invoice_number": "string",
  "account_number": "string",
  "payment_due_date": "YYYY-MM-DD",
  "reading_period_start": "YYYY-MM-DD",
  "reading_period_end": "YYYY-MM-DD",
  "meter_number": "string",
  "start_reading": 10324.0,
  "end_reading": 10364.0,
  "consumption": 40.0,
  "steps": [
    {"label": "Step 1", "usage_amount": 23.655, "rate": 0.0},
    {"label": "Step 2", "usage_amount": 15.770, "rate": 29.840},
    {"label": "Step 3", "usage_amount": 0.575, "rate": 31.150}
  ],
  "fixed_charges": [
    {"label": "Extended Social Package Grant", "cost": 0.00},
    {"label": "Water Demand Levy", "cost": 325.40},
    {"label": "Sewer charge", "cost": 3488.65}
  ],
  "total_vat": 645.38,
  "total_due": 4947.92
}

All dates must be YYYY-MM-DD. All numbers must be plain numbers (not strings). statement_month must be an integer 1-12.

Invoice text:
"""


def build_prompt(invoice_type: str, raw_text: str) -> str:
    """Return the appropriate prompt with the extracted PDF text appended."""
    if invoice_type == "electricity":
        return ELECTRICITY_PROMPT + raw_text
    else:
        return WATER_PROMPT + raw_text


# ---------------------------------------------------------------------------
# Step 3: Groq API call
# ---------------------------------------------------------------------------

def call_groq(prompt: str) -> dict:
    """
    Send the prompt to the Groq API and parse the JSON response.
    Reads GROQ_API_KEY from environment.
    Raises ValueError if the response is not valid JSON.
    Raises RuntimeError on API errors.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Please add it to your .env file."
        )

    client = Groq(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise data extraction assistant. You return only valid JSON, nothing else."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0,  # Zero temperature for deterministic extraction
            max_tokens=2000,
        )
    except Exception as e:
        raise RuntimeError(f"Groq API request failed: {e}")

    content = response.choices[0].message.content.strip()

    # Strip markdown code fences if the model added them despite instructions
    if content.startswith("```"):
        lines = content.split("\n")
        # Remove opening fence (```json or ```) and closing fence (```)
        content = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"The LLM returned a response that is not valid JSON: {e}\n\nRaw response:\n{content}"
        )


# ---------------------------------------------------------------------------
# Step 4: Compute step costs
# ---------------------------------------------------------------------------

def compute_step_costs(extracted: dict) -> list[dict]:
    """
    Add a computed 'cost' field to each step (usage_amount × rate).
    Returns the updated steps list.
    """
    steps = []
    for step in extracted.get("steps", []):
        usage = Decimal(str(step.get("usage_amount", 0)))
        rate = Decimal(str(step.get("rate", 0)))
        cost = (usage * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        steps.append({
            "label": step.get("label", "Step"),
            "usage_amount": float(usage),
            "rate": float(rate),
            "cost": float(cost),
        })
    return steps


# ---------------------------------------------------------------------------
# Step 5: Validation checks
# ---------------------------------------------------------------------------

def run_checks(
    extracted: dict,
    steps_with_costs: list[dict],
    invoice_type: str,
    expected_account_number: str | None,
    expected_meter_number: str | None,
) -> list[dict]:
    """
    Run all validation checks and return a list of check result dicts.

    Each check has:
      label    — display name
      pass     — bool
      severity — "error" (blocks DB write) or "warning" (informational)
      message  — human-readable result string
    """
    checks = []

    # --- 1. Invoice totals ---
    steps_total = sum(Decimal(str(s["cost"])) for s in steps_with_costs)
    fixed_total = sum(
        Decimal(str(c.get("cost", 0)))
        for c in extracted.get("fixed_charges", [])
    )
    vat = Decimal(str(extracted.get("total_vat", 0)))
    total_due = Decimal(str(extracted.get("total_due", 0)))
    computed = steps_total + fixed_total + vat
    discrepancy = abs(computed - total_due)
    totals_pass = discrepancy <= TOTALS_TOLERANCE

    checks.append({
        "label": "Invoice totals",
        "pass": totals_pass,
        "severity": "error",
        "message": (
            f"Steps R{steps_total:.2f} + fixed R{fixed_total:.2f} + VAT R{vat:.2f} "
            f"= R{computed:.2f}, matches total R{total_due:.2f}"
            if totals_pass else
            f"Steps R{steps_total:.2f} + fixed R{fixed_total:.2f} + VAT R{vat:.2f} "
            f"= R{computed:.2f}, but invoice total is R{total_due:.2f} "
            f"(discrepancy R{discrepancy:.2f})"
        ),
        # Expose breakdown so the template can render the usage subtotal row
        "breakdown": {
            "steps_total": float(steps_total),
            "fixed_total": float(fixed_total),
            "vat": float(vat),
        },
    })

    # --- 2. Account number ---
    parsed_account = str(extracted.get("account_number", "")).strip()
    if not expected_account_number:
        checks.append({
            "label": "Account number",
            "pass": True,
            "severity": "warning",
            "message": "Expected account number not configured in Complex Info — skipped",
        })
    elif parsed_account == expected_account_number.strip():
        checks.append({
            "label": "Account number",
            "pass": True,
            "severity": "error",
            "message": f"Account number {parsed_account} matches",
        })
    else:
        checks.append({
            "label": "Account number",
            "pass": False,
            "severity": "error",
            "message": f'Parsed "{parsed_account}" but expected "{expected_account_number.strip()}"',
        })

    # --- 3. Meter number ---
    parsed_meter = str(extracted.get("meter_number", "")).strip()
    if not expected_meter_number:
        checks.append({
            "label": "Meter number",
            "pass": True,
            "severity": "warning",
            "message": "Expected meter number not configured in Complex Info — skipped",
        })
    elif parsed_meter == expected_meter_number.strip():
        checks.append({
            "label": "Meter number",
            "pass": True,
            "severity": "error",
            "message": f"Meter number {parsed_meter} matches",
        })
    else:
        checks.append({
            "label": "Meter number",
            "pass": False,
            "severity": "error",
            "message": f'Parsed "{parsed_meter}" but expected "{expected_meter_number.strip()}"',
        })

    # --- 4. Consumption arithmetic (end − start = consumption) ---
    try:
        end = Decimal(str(extracted.get("end_reading", 0)))
        start = Decimal(str(extracted.get("start_reading", 0)))
        printed = Decimal(str(extracted.get("consumption", 0)))
        arithmetic = end - start
        diff = abs(arithmetic - printed)
        arith_pass = diff <= Decimal("0.005")
        unit = "kWh" if invoice_type == "electricity" else "KL"
        checks.append({
            "label": "Consumption arithmetic",
            "pass": arith_pass,
            "severity": "error",
            "message": (
                f"{end} − {start} = {arithmetic} {unit}, matches printed consumption {printed} {unit}"
                if arith_pass else
                f"{end} − {start} = {arithmetic} {unit}, but printed consumption is {printed} {unit}"
            ),
        })
    except Exception as e:
        checks.append({
            "label": "Consumption arithmetic",
            "pass": False,
            "severity": "error",
            "message": f"Could not verify: {e}",
        })

    # --- 5. Step usage sum (steps add up to consumption) ---
    try:
        step_sum = sum(Decimal(str(s["usage_amount"])) for s in steps_with_costs)
        printed = Decimal(str(extracted.get("consumption", 0)))
        diff = abs(step_sum - printed)
        sum_pass = diff <= Decimal("0.005")
        unit = "kWh" if invoice_type == "electricity" else "KL"
        checks.append({
            "label": "Step usage sum",
            "pass": sum_pass,
            "severity": "error",
            "message": (
                f"Steps sum to {step_sum} {unit}, matches consumption {printed} {unit}"
                if sum_pass else
                f"Steps sum to {step_sum} {unit} but consumption is {printed} {unit} — a step may be missing"
            ),
        })
    except Exception as e:
        checks.append({
            "label": "Step usage sum",
            "pass": False,
            "severity": "error",
            "message": f"Could not verify: {e}",
        })

    # --- 6. VAT rate (should be ~15% of pre-VAT total) ---
    try:
        pre_vat = steps_total + fixed_total
        if pre_vat > 0:
            expected_vat = (pre_vat * Decimal("0.15")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            vat_diff = abs(vat - expected_vat)
            vat_pass = vat_diff <= VAT_TOLERANCE
            checks.append({
                "label": "VAT rate",
                "pass": vat_pass,
                "severity": "warning",
                "message": (
                    f"VAT R{vat:.2f} is approximately 15% of pre-VAT total R{pre_vat:.2f} (expected R{expected_vat:.2f})"
                    if vat_pass else
                    f"VAT R{vat:.2f} differs from expected 15% of R{pre_vat:.2f} = R{expected_vat:.2f} — some line items may be VAT-exempt"
                ),
            })
    except Exception as e:
        checks.append({
            "label": "VAT rate",
            "pass": False,
            "severity": "warning",
            "message": f"Could not verify: {e}",
        })

    return checks


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_invoice(
    file_bytes: bytes,
    invoice_type: str,
    expected_account_number: str | None = None,
    expected_meter_number: str | None = None,
) -> dict:
    """
    Full pipeline: extract PDF text → call Groq → compute step costs → run checks.

    Returns:
      {
        "success": True,
        "raw_text": str,
        "extracted": dict,       # fields from LLM
        "steps": list[dict],     # steps with computed costs added
        "checks": list[dict],    # all validation check results
        "all_errors_pass": bool, # True if no error-severity check failed
        "anomalies": list[str],  # any anomaly warnings
      }
    or on failure:
      {
        "success": False,
        "error": str,
        "raw_text": str | None,
      }
    """
    raw_text = None
    try:
        raw_text = extract_text_from_pdf(file_bytes)
        prompt = build_prompt(invoice_type, raw_text)
        extracted = call_groq(prompt)
        steps_with_costs = compute_step_costs(extracted)
        checks = run_checks(extracted, steps_with_costs, invoice_type, expected_account_number, expected_meter_number)

        all_errors_pass = all(
            c["pass"] for c in checks if c["severity"] == "error"
        )

        anomalies = [
            charge["label"]
            for charge in extracted.get("fixed_charges", [])
            if "anomaly" in charge.get("label", "").lower()
            and charge.get("cost", 0) > 0
        ]

        return {
            "success": True,
            "raw_text": raw_text,
            "extracted": extracted,
            "steps": steps_with_costs,
            "checks": checks,
            "all_errors_pass": all_errors_pass,
            "anomalies": anomalies,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "raw_text": raw_text,
        }
