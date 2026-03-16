# DealTracker User Guide

DealTracker (`dt`) is a command-line application for small businesses to track, organize, and reconcile the documents that flow through a sales deal — from the first estimate request all the way through to final payment. It uses AI (Claude and GPT-4o) to read your documents, extract the important details, and flag any billing or payment discrepancies.

---

## Table of Contents

1. [How It Works](#how-it-works)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Core Concepts](#core-concepts)
5. [Quick Start](#quick-start)
6. [CLI Reference](#cli-reference)
   - [dt deal](#dt-deal)
   - [dt doc](#dt-doc)
   - [dt customer](#dt-customer)
   - [dt reconcile](#dt-reconcile)
   - [dt report](#dt-report)
7. [Document Types](#document-types)
8. [The Document Ingestion Flow](#the-document-ingestion-flow)
9. [Reconciliation Logic](#reconciliation-logic)
10. [Reports](#reports)
11. [File Storage](#file-storage)
12. [Tips and Best Practices](#tips-and-best-practices)

---

## How It Works

1. You create a **deal** for each job or project. The app assigns it a reference number like `JOB-2026-001`.
2. As documents arrive (emails, PDFs, photos, text files), you run `dt doc add <file>`. The AI reads the document, extracts the key information, and you confirm or correct it.
3. You link each document to its deal — either by picking from a list, or automatically if the document contains the deal reference number.
4. The app tracks the full document timeline for each deal and checks that the amounts all add up: agreed quote → invoice → payment.
5. At any time you can run a reconciliation check to see if anything is over-billed, under-paid, or missing, and generate a report.

---

## Installation

### Requirements

- Python 3.11 or higher
- An OpenAI API key (for image and scanned PDF extraction)
- An Anthropic API key (for text document extraction)

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/paulwilcox99/reconcile.git
cd reconcile

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate       # macOS / Linux
# venv\Scripts\activate        # Windows

# 3. Install the application
pip install -e .

# 4. Verify the install
dt --version
```

After installing inside the virtual environment, the `dt` command is available whenever the venv is active. To use it without activating the venv each time, call it directly:

```bash
/path/to/reconcile/venv/bin/dt --help
```

### System Dependencies for PDF Reports

Generating PDF reports uses **weasyprint**, which requires system libraries on Linux:

```bash
# Ubuntu / Debian
sudo apt-get install libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf2.0-0

# macOS (Homebrew)
brew install pango gdk-pixbuf libffi
```

If weasyprint is unavailable, the app automatically falls back to reportlab for PDF generation.

---

## Configuration

Copy the example environment file and fill in your API keys:

```bash
cp .env.example .env
```

Edit `.env`:

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Optional — defaults shown below
OPENAI_MODEL=gpt-4o
ANTHROPIC_MODEL=claude-opus-4-5
RECONCILE_TOLERANCE=0.50
FUZZY_THRESHOLD=0.85
```

| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key | Required |
| `ANTHROPIC_API_KEY` | Your Anthropic (Claude) API key | Required |
| `OPENAI_MODEL` | OpenAI model to use | `gpt-4o` |
| `ANTHROPIC_MODEL` | Anthropic model to use | `claude-opus-4-5` |
| `RECONCILE_TOLERANCE` | Dollar amount within which amounts are considered equal | `0.50` |
| `FUZZY_THRESHOLD` | Similarity threshold (0–1) for customer name matching | `0.85` |

> **Never commit your `.env` file.** It is excluded from git by default.

---

## Core Concepts

### Deal

A deal represents a single job or project for a customer. Every deal has:

- A **reference number** (e.g., `JOB-2026-001`) — auto-generated or custom
- A **customer**
- A **description** of the work
- A **status**: `open` → `reconciled` / `disputed` / `closed`
- An **agreed amount** — set automatically when a quote or purchase order is added

### Document

Every file you add to the system is a document. A document is linked to exactly one deal and has a confirmed type (estimate, invoice, payment, etc.), date, and amount.

### Reference Number

Every deal gets a unique reference number in the format `JOB-YYYY-NNN` (e.g., `JOB-2026-001`). If you put this number on your outgoing documents (quotes, invoices), the AI will find it and automatically link incoming responses to the right deal.

### Reconciliation

The app compares three amounts for each deal:

- **Agreed** — the amount from the confirmed quote or purchase order
- **Invoiced** — the total of all invoices sent
- **Paid** — the total confirmed as received (from payment documents)

Any discrepancy flags the deal as `over_billed`, `under_billed`, `over_paid`, or `under_paid`.

---

## Quick Start

```bash
# Step 1: Create a deal for a new job
dt deal new --customer "Acme Corp" --description "Office Renovation - 3rd Floor"
# → Deal created: JOB-2026-001

# Step 2: Add documents as they arrive
dt doc add customer_email_requesting_estimate.txt
dt doc add our_quote.pdf
dt doc add acme_purchase_order.pdf
dt doc add our_invoice.pdf
dt doc add payment_confirmation.eml

# Step 3: Check that everything adds up
dt reconcile check JOB-2026-001

# Step 4: Generate a report
dt report generate --deal JOB-2026-001 --format all
```

---

## CLI Reference

All commands follow the pattern:

```
dt <group> <command> [arguments] [options]
```

Run `--help` on any command or group for details:

```bash
dt --help
dt deal --help
dt doc add --help
```

---

### dt deal

Manage deals.

---

#### `dt deal new`

Create a new deal and assign it a reference number.

```
dt deal new [OPTIONS]
```

| Option | Description |
|---|---|
| `--customer`, `-c` TEXT | Customer name (prompted if omitted) |
| `--description`, `-d` TEXT | Job or project description (prompted if omitted) |
| `--ref` TEXT | Custom reference number (auto-generated if omitted) |

**Examples:**

```bash
# Interactive prompts for both fields
dt deal new

# Provide everything inline
dt deal new --customer "Hartley Realty" --description "Kitchen Remodel - 512 Oakwood"

# Use a custom reference number
dt deal new --customer "Acme Corp" --description "Roof Repair" --ref "ACME-2026-01"
```

**Output:**
```
New customer: Hartley Realty (ID: 1)
Deal created:  JOB-2026-001  Kitchen Remodel - 512 Oakwood  (ID: 1)
```

---

#### `dt deal list`

List all deals.

```
dt deal list [OPTIONS]
```

| Option | Description |
|---|---|
| `--customer`, `-c` TEXT | Filter by customer name (partial match) |
| `--status`, `-s` CHOICE | Filter by status: `open`, `reconciled`, `disputed`, `closed`, `incomplete`, `all` (default: `all`) |

**Examples:**

```bash
dt deal list
dt deal list --status open
dt deal list --customer "Hartley"
```

---

#### `dt deal show`

Show full deal detail including document timeline and reconciliation.

```
dt deal show <DEAL_REF>
```

`DEAL_REF` can be either the numeric ID (`1`) or the reference number (`JOB-2026-001`).

**Examples:**

```bash
dt deal show JOB-2026-001
dt deal show 1
```

---

#### `dt deal set-agreed`

Manually override the agreed amount for a deal (normally set automatically from the quote).

```
dt deal set-agreed <DEAL_REF> <AMOUNT>
```

**Examples:**

```bash
dt deal set-agreed JOB-2026-001 10500.00
dt deal set-agreed 2 12400.00
```

---

#### `dt deal close`

Mark a deal as closed. Prompts for confirmation.

```
dt deal close <DEAL_REF>
```

**Examples:**

```bash
dt deal close JOB-2026-001
dt deal close 2
```

---

### dt doc

Manage documents.

---

#### `dt doc add`

Ingest a document: the AI extracts information, you confirm it, and you link it to a deal.

```
dt doc add <FILE_PATH> [OPTIONS]
```

| Argument / Option | Description |
|---|---|
| `FILE_PATH` | Path to the file to ingest |
| `--provider` CHOICE | AI provider: `auto` (default), `openai`, or `anthropic` |

**Supported file types:** `.pdf`, `.txt`, `.text`, `.eml`, `.email`, `.md`, `.jpg`, `.jpeg`, `.png`, `.tiff`, `.webp`, `.bmp`

**AI routing:**
- Text files and emails → **Claude** (Anthropic)
- Images → **GPT-4o Vision** (OpenAI)
- PDFs with extractable text → **Claude**
- Scanned / image-only PDFs → **GPT-4o Vision**

**Examples:**

```bash
dt doc add invoice.pdf
dt doc add customer_email.eml
dt doc add photo_of_po.jpg
dt doc add quote.txt --provider openai   # force a specific provider
```

**The ingestion flow:**

1. The AI reads the document and extracts: document type, date, customer name, deal description, deal reference number, and total amount.
2. The results are displayed in a table.
3. You are asked to **[a]ccept**, **[e]dit**, or **[r]eject**.
   - **Accept** — saves the AI extraction as-is.
   - **Edit** — walks through each field so you can correct anything.
   - **Reject** — discards the document and removes it from staging.
4. The app looks for a deal to link the document to:
   - If the AI found a reference number (e.g., `JOB-2026-001`) in the document, it looks it up and asks you to confirm.
   - If no reference was found, a numbered list of existing deals is shown. Enter the number, **[n]** to create a new deal, or **[x]** to cancel.
5. The document is saved to `data/documents/{customer}/{deal_ref}/` and recorded in the database.

**Tip:** Put your deal reference number on all outgoing documents (quotes, invoices, receipts). When customers reference it in their responses, the app finds the deal automatically.

---

#### `dt doc list`

List documents.

```
dt doc list [OPTIONS]
```

| Option | Description |
|---|---|
| `--deal` TEXT | Filter by deal ID or reference |
| `--unconfirmed` | Show only unconfirmed documents |

**Examples:**

```bash
dt doc list
dt doc list --deal JOB-2026-001
dt doc list --unconfirmed
```

---

#### `dt doc show`

Show full detail for a single document including AI extraction data and confidence score.

```
dt doc show <DOC_ID>
```

**Examples:**

```bash
dt doc show 4
```

---

#### `dt doc reprocess`

Re-run AI extraction on an existing document. Useful if the original extraction was poor or you want to try a different AI provider.

```
dt doc reprocess <DOC_ID> [OPTIONS]
```

| Option | Description |
|---|---|
| `--provider` CHOICE | `auto`, `openai`, or `anthropic` |

**Examples:**

```bash
dt doc reprocess 4
dt doc reprocess 4 --provider openai
```

---

### dt customer

Manage customers.

---

#### `dt customer list`

List all customers.

```
dt customer list
```

---

#### `dt customer show`

Show a customer and all their deals.

```
dt customer show <CUSTOMER_ID>
```

**Examples:**

```bash
dt customer show 1
```

---

#### `dt customer add`

Manually add a customer without going through document ingestion.

```
dt customer add [OPTIONS]
```

| Option | Description |
|---|---|
| `--name`, `-n` TEXT | Customer name (required, prompted if omitted) |
| `--email`, `-e` TEXT | Email address |
| `--phone`, `-p` TEXT | Phone number |
| `--notes` TEXT | Any notes |

**Examples:**

```bash
dt customer add --name "Pinnacle Medical" --email "admin@pinnacle.com" --phone "555-317-9900"
```

---

### dt reconcile

Check whether the amounts on a deal match up correctly.

---

#### `dt reconcile check`

Run reconciliation on a single deal and display the result.

```
dt reconcile check <DEAL_REF> [OPTIONS]
```

| Option | Description |
|---|---|
| `--save` | Save the reconciliation snapshot to the database |
| `--verbose`, `-v` | Show which document IDs were used in the calculation |

**Examples:**

```bash
dt reconcile check JOB-2026-001
dt reconcile check JOB-2026-002 --verbose
dt reconcile check 1 --save
```

**Output example — clean:**
```
Agreed (Quote/PO):  $10,719.00
Invoiced:           $10,719.00
Paid:               $10,719.00
Status:             CLEAN
```

**Output example — discrepancy:**
```
Agreed (Quote/PO):  $12,400.00
Invoiced:           $12,750.00
Paid:               $0.00
Status:             OVER BILLED
Discrepancies:
  • INVOICE_MISMATCH: billed $12,750.00 vs agreed $12,400.00 (over-billed by $350.00)
```

---

#### `dt reconcile check-all`

Run reconciliation on all open and disputed deals at once.

```
dt reconcile check-all [OPTIONS]
```

| Option | Description |
|---|---|
| `--save` | Save snapshots to the database and update deal statuses |
| `--only-issues` | Only show deals that have discrepancies |

**Examples:**

```bash
dt reconcile check-all
dt reconcile check-all --only-issues
dt reconcile check-all --save
```

---

#### `dt reconcile summary`

Show a reconciliation overview table for all deals in the system.

```
dt reconcile summary
```

---

### dt report

Generate reports.

---

#### `dt report generate`

Generate a report for one deal, all deals for a customer, or all deals.

```
dt report generate [OPTIONS]
```

| Option | Description |
|---|---|
| `--deal` TEXT | Deal ID or reference (e.g., `JOB-2026-001`) |
| `--customer` INTEGER | Customer ID — reports all deals for that customer |
| `--all-deals` | Report on every deal in the system |
| `--format` CHOICE | `terminal` (default), `html`, `pdf`, or `all` |
| `--output`, `-o` PATH | Directory to save HTML/PDF files (default: `data/reports/YYYY-MM-DD/`) |

You must specify one of `--deal`, `--customer`, or `--all-deals`.

**Examples:**

```bash
# Single deal, terminal only
dt report generate --deal JOB-2026-001

# Single deal, all formats
dt report generate --deal JOB-2026-001 --format all

# All deals, save HTML and PDF to Desktop
dt report generate --all-deals --format all --output ~/Desktop/reports

# All deals for customer ID 1
dt report generate --customer 1 --format pdf
```

**What the report contains:**

- Deal summary (reference, customer, description, status, agreed amount)
- Complete document timeline in workflow order with dates, types, amounts, and links to the original files
- Reconciliation summary with discrepancies highlighted in red

---

#### `dt report list`

List all previously generated HTML and PDF report files.

```
dt report list
```

---

## Document Types

DealTracker recognises these document types in the standard deal workflow:

| Type | Description |
|---|---|
| `estimate_request` | Customer asking for a rough price (no amount) |
| `estimate` | Your rough price estimate sent to the customer |
| `quote_request` | Customer asking for a formal, binding quote |
| `quote` | Your formal quote — **sets the agreed amount** |
| `purchase_order` | Customer's official authorization to proceed — also sets agreed amount if no quote exists |
| `invoice` | Your bill to the customer after work is complete |
| `payment` | Confirmation that the customer has paid |
| `receipt` | Your receipt acknowledging payment received |

The AI determines the type automatically. If it gets it wrong, choose **[e]dit** during confirmation and correct it.

---

## The Document Ingestion Flow

Understanding this flow helps you use the app effectively.

```
dt doc add invoice.pdf
        │
        ▼
  Copy to staging area
  (data/documents/unassigned/)
        │
        ▼
  AI reads document
  Extracts: type, date, customer, description,
            deal reference, amount, notes
        │
        ▼
  Show extraction table
  ┌─────────────────────────────┐
  │ Document Type  │ Invoice    │
  │ Date           │ 2026-02-18 │
  │ Customer       │ Acme Corp  │
  │ Deal Reference │ JOB-2026-1 │  ← if found
  │ Amount         │ $10,719    │
  └─────────────────────────────┘
        │
        ▼
  [a]ccept / [e]dit / [r]eject
        │
        ▼
  Link to deal:
  ┌──────────────────────────────────────────┐
  │ IF reference found in doc                │
  │   → look up deal → confirm link          │
  │ ELSE                                     │
  │   → show deal list → pick number or [n]  │
  └──────────────────────────────────────────┘
        │
        ▼
  Move file to:
  data/documents/{customer}/{JOB-XXXX-NNN}/
        │
        ▼
  Save to database
  Update agreed_amount if quote or PO
```

---

## Reconciliation Logic

When you run `dt reconcile check`, the engine:

1. Collects all **confirmed** documents for the deal.
2. Finds the **agreed amount**: the most recent confirmed `quote`, or a `purchase_order` if no quote exists.
3. Sums all `invoice` documents → **invoiced total**.
4. Sums all `payment` documents → **paid total**. Falls back to `receipt` documents if no payment documents are recorded.
5. Compares the three amounts and flags discrepancies.

### Discrepancy types

| Status | Meaning |
|---|---|
| `clean` | All amounts match within tolerance |
| `incomplete` | Deal is in progress — not all document types present yet |
| `over_billed` | Invoice total is higher than the agreed quote amount |
| `under_billed` | Invoice total is lower than the agreed quote amount |
| `over_paid` | Payment received exceeds the invoice total |
| `under_paid` | Payment received is less than the invoice total |
| `missing_docs` | Payment exists but no invoice, or invoice exists but no quote |

### Amount tolerance

Amounts within **$0.50** of each other are treated as equal (handles rounding differences). Configurable via `RECONCILE_TOLERANCE` in `.env`.

### Payment vs Receipt

A **receipt** is your acknowledgment of payment — it does not count as a second payment. If both a `payment` and a `receipt` document exist on a deal, only the payment is counted toward the paid total.

---

## Reports

Reports can be generated in three formats simultaneously with `--format all`.

### Terminal

Printed directly to the screen using color-coded tables. Discrepant invoice amounts are highlighted in red.

### HTML

Saved to `data/reports/YYYY-MM-DD/`. Open in any web browser. Contains:
- Deal summary table
- Document timeline with clickable links to the original files
- Reconciliation panel (green border = clean, red border = discrepancy)

### PDF

Same content as HTML, converted via weasyprint (or reportlab fallback). Suitable for printing or emailing to a client or accountant.

Reports are **never overwritten** — each run creates a new timestamped file (e.g., `deal_1_143022.pdf`).

---

## File Storage

```
data/
├── dealtracker.db              ← SQLite database (all deal/doc records)
├── documents/
│   └── {customer-slug}/
│       └── {JOB-XXXX-NNN}/
│           ├── invoice.pdf     ← original file, copied on ingestion
│           ├── quote.txt
│           └── ...
└── reports/
    └── YYYY-MM-DD/
        ├── deal_1_143022.html
        ├── deal_1_143022.pdf
        └── full_181546.pdf     ← all-deals report
```

Files are organised by customer and deal reference number so you can always find the original document. The database stores the full path to each file and report links point to these locations.

---

## Tips and Best Practices

**Put your deal reference number on all outgoing documents.**
When you send a quote or invoice, include `JOB-2026-001` on it. When the customer sends back a PO or payment confirmation referencing that number, the app finds the right deal automatically without you having to select from a list.

**Create the deal before adding documents.**
Run `dt deal new` when you start a job. This gives you the reference number to put on your paperwork from the start.

**Use [e]dit when the AI gets the description wrong.**
The AI sometimes writes a long verbose description. During confirmation, press **e** and type a clean, consistent description. Consistent descriptions help with future matching and make reports easier to read.

**Check reconciliation regularly.**
Run `dt reconcile check-all --only-issues` to quickly see if any deals have billing or payment problems before they become disputes.

**Re-process a document if extraction was poor.**
If the AI misread a scanned document, try reprocessing with the other provider:
```bash
dt doc reprocess 7 --provider openai
```

**Back up your database.**
The database at `data/dealtracker.db` contains everything. Copy it regularly or put `data/` in your backup solution. The documents directory contains the original files and is equally important.
