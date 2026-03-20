# Standard Operating Procedure (SOP)

<!-- ============================================================
     SOP TEMPLATE v1.0
     Purpose : Back-Office / BPS Process Documentation
     Usage   : Consumed by AI pipeline (Transcripts / Audio / Video)
     ============================================================ -->

---

## 📋 DOCUMENT CONTROL

| Field | Details |
|---|---|
| **SOP ID** | `SOP-[DEPT]-[SEQ]-[YYYY]` |
| **SOP Title** | _(Full descriptive name of the process)_ |
| **Process Owner** | _(Name / Role)_ |
| **Department / BU** | _(e.g., Finance Operations / HR Shared Services)_ |
| **Effective Date** | `YYYY-MM-DD` |
| **Review Date** | `YYYY-MM-DD` |
| **Version** | `1.0` |
| **Classification** | `Internal / Confidential / Restricted` |
| **Source Reference** | _(Transcript ID / Video File / Audio Recording ID)_ |

### Revision History

| Version | Date | Author | Change Summary | Approved By |
|---|---|---|---|---|
| 1.0 | `YYYY-MM-DD` | _(Name)_ | Initial Draft | _(Name)_ |
| | | | | |

---

## 1. PURPOSE

> _One to three sentences explaining **why** this process exists and what business outcome it supports._

**Example:**
This SOP defines the end-to-end steps for processing vendor invoices in the Accounts Payable function, ensuring accurate payment within agreed SLAs and maintaining audit compliance.

---

## 2. SCOPE

### 2.1 In-Scope
- _(Process variant / sub-process 1)_
- _(Process variant / sub-process 2)_

### 2.2 Out-of-Scope
- _(What is explicitly NOT covered by this SOP)_

### 2.3 Applicable Regions / Entities
| Region / Entity | Applicable? | Notes |
|---|---|---|
| _(e.g., India)_ | ✅ Yes | |
| _(e.g., APAC)_ | ⚠️ Partial | _(Describe exception)_ |
| _(e.g., EMEA)_ | ❌ No | |

---

## 3. ROLES & RESPONSIBILITIES

| Role | Responsibility | Team / Location |
|---|---|---|
| **Process Owner** | Accountable for SOP accuracy and outcomes | _(Team name)_ |
| **Operator / Processor** | Executes day-to-day process steps | _(Team name)_ |
| **Reviewer / Checker** | Validates output quality | _(Team name)_ |
| **Approver** | Final sign-off authority | _(Team name)_ |
| **BPS Partner** | _(If transitioned — describe role)_ | _(Vendor name / location)_ |
| **System / Bot** | _(Automated steps performed by RPA/AI)_ | _(Platform: UiPath / AA / etc.)_ |

> **RACI Legend:** R = Responsible · A = Accountable · C = Consulted · I = Informed

---

## 4. DEFINITIONS & ABBREVIATIONS

| Term / Acronym | Definition |
|---|---|
| BPS | Business Process Services |
| SLA | Service Level Agreement |
| TAT | Turnaround Time |
| _(Term)_ | _(Definition)_ |

---

## 5. PREREQUISITES & INPUTS

### 5.1 System Access Required
| System / Application | Access Level | URL / Path |
|---|---|---|
| _(e.g., SAP ERP)_ | _(Read / Write / Admin)_ | _(URL or navigation path)_ |
| _(e.g., Shared Mailbox)_ | _(Read / Write)_ | _(Email address)_ |

### 5.2 Input Documents / Data
| Input | Source | Format | Frequency |
|---|---|---|---|
| _(e.g., Invoice PDF)_ | _(Vendor email / Portal)_ | PDF / Excel | Daily |
| _(e.g., Purchase Order)_ | _(ERP system)_ | System record | On-demand |

### 5.3 Knowledge / Skills Required
- _(Domain knowledge needed — e.g., basic accounting principles)_
- _(System proficiency — e.g., SAP navigation)_
- _(Language / communication requirements)_

---

## 6. PROCESS OVERVIEW

```
┌─────────────────────────────────────────────────────────────────┐
│                    HIGH-LEVEL PROCESS FLOW                      │
│                                                                 │
│  [TRIGGER] ──► [STEP 1] ──► [STEP 2] ──► [STEP 3] ──► [END]   │
│                   │              │                              │
│               [Decision]    [Exception]                         │
│               Yes / No       Handler                            │
└─────────────────────────────────────────────────────────────────┘
```

> **Note for AI Pipeline:** Replace the ASCII diagram above with an auto-generated BPMN or flowchart image when building the SOP from transcript/video source.

### Process Metrics at a Glance
| Metric | Target |
|---|---|
| **Average Handling Time (AHT)** | _(e.g., 15 minutes per case)_ |
| **SLA / TAT** | _(e.g., Same-day processing by 5 PM)_ |
| **Volume / Frequency** | _(e.g., ~200 transactions/day)_ |
| **Error Rate Threshold** | _(e.g., < 1%)_ |

---

## 7. DETAILED PROCESS STEPS

> **AI Pipeline Instructions:**
> - Each step below maps to a timestamp segment in the source transcript/video.
> - Populate `[TIMESTAMP]` with the source reference (e.g., `00:04:32`).
> - Screenshots / screen recordings should be embedded under the relevant step.

---

### STEP 1 — [Step Name]

| Attribute | Detail |
|---|---|
| **Performed By** | _(Role)_ |
| **System Used** | _(Application name)_ |
| **Source Timestamp** | `[TIMESTAMP]` |
| **Est. Duration** | _(e.g., 2 minutes)_ |

**Action:**
_(Clear imperative instruction — e.g., "Open the shared mailbox and filter emails with subject containing 'Invoice'.")_

**Expected Result:**
_(What the operator should see or achieve upon completing this step.)_

**Screenshot / Screen Reference:**
> `[SCREENSHOT_PLACEHOLDER_STEP_1]`
> _(AI pipeline: embed extracted screenshot or screen recording frame here)_

**Notes / Tips:**
- _(Any helpful context, keyboard shortcuts, or watch-outs)_

---

### STEP 2 — [Step Name]

| Attribute | Detail |
|---|---|
| **Performed By** | _(Role)_ |
| **System Used** | _(Application name)_ |
| **Source Timestamp** | `[TIMESTAMP]` |
| **Est. Duration** | _(e.g., 3 minutes)_ |

**Action:**
_(Step instruction)_

**Expected Result:**
_(Expected outcome)_

**Screenshot / Screen Reference:**
> `[SCREENSHOT_PLACEHOLDER_STEP_2]`

**Decision Point:**

```
Is [condition] true?
    ├── YES → Proceed to Step 3
    └── NO  → Go to Exception Handling (Section 9)
```

---

### STEP 3 — [Step Name]

| Attribute | Detail |
|---|---|
| **Performed By** | _(Role)_ |
| **System Used** | _(Application name)_ |
| **Source Timestamp** | `[TIMESTAMP]` |
| **Est. Duration** | _(e.g., 5 minutes)_ |

**Action:**
_(Step instruction)_

**Expected Result:**
_(Expected outcome)_

**Screenshot / Screen Reference:**
> `[SCREENSHOT_PLACEHOLDER_STEP_3]`

---

<!-- Add more STEP blocks as needed following the pattern above -->

---

## 8. QUALITY CHECKS & VALIDATION

| Check # | What to Validate | How to Validate | Done By | Frequency |
|---|---|---|---|---|
| QC-01 | _(Field/data to check)_ | _(Check method)_ | _(Role)_ | _(Per transaction / Daily)_ |
| QC-02 | | | | |
| QC-03 | | | | |

### Checklist (Operator Self-Check)
- [ ] _(Item 1 verified)_
- [ ] _(Item 2 verified)_
- [ ] _(Item 3 verified)_
- [ ] Output saved to correct folder/system
- [ ] Case/ticket updated with completion status

---

## 9. EXCEPTION HANDLING

> Document every known exception scenario. The AI pipeline should extract these from escalation patterns observed in the transcript/recording.

### Exception Matrix

| Exception ID | Scenario | Trigger / Symptom | Action to Take | Escalation Path |
|---|---|---|---|---|
| EXC-01 | _(e.g., Duplicate invoice)_ | _(e.g., Same invoice number already exists)_ | _(e.g., Flag and hold; notify team lead)_ | _(Role → Role)_ |
| EXC-02 | _(e.g., Missing PO number)_ | _(e.g., Invoice received without PO reference)_ | _(e.g., Send back to vendor with template email)_ | _(Role → Role)_ |
| EXC-03 | _(e.g., System unavailable)_ | _(e.g., Application timeout / error message)_ | _(e.g., Log in tracker; retry after 30 min)_ | _(Role → IT Helpdesk)_ |

### Escalation Matrix
| Level | Trigger Condition | Contact | Response Time |
|---|---|---|---|
| L1 | _(Operator cannot resolve within X minutes)_ | _(Team Lead name/role)_ | 30 min |
| L2 | _(L1 unable to resolve)_ | _(Manager / SME)_ | 2 hours |
| L3 | _(Business impact / SLA breach risk)_ | _(Director / Client)_ | 4 hours |

---

## 10. SLA & PERFORMANCE TARGETS

| KPI | Definition | Target | Measurement Method |
|---|---|---|---|
| Accuracy Rate | % transactions processed without error | ≥ 99% | Monthly audit sample |
| Turnaround Time | Time from receipt to completion | ≤ _(X hours)_ | System timestamp |
| Productivity | Transactions per FTE per day | ≥ _(X)_ | Volume tracker |
| First-Time-Right | % completed without rework | ≥ 95% | QC log |

---

## 11. TOOLS & SYSTEMS REFERENCE

| Tool / System | Purpose in Process | Version / Module | Access Request Process |
|---|---|---|---|
| _(e.g., SAP S/4HANA)_ | _(Invoice posting)_ | _(Module: FI-AP)_ | _(IT Service Desk ticket)_ |
| _(e.g., MS Outlook)_ | _(Email communication)_ | _(Office 365)_ | _(Auto-provisioned)_ |
| _(e.g., SharePoint)_ | _(Document storage)_ | _(Site URL)_ | _(Manager approval)_ |
| _(e.g., UiPath Bot)_ | _(Automated data extraction)_ | _(Bot name/version)_ | _(RPA team request)_ |

---

## 12. TRAINING & KNOWLEDGE TRANSFER

### Training Requirements
| Training Module | Delivery Mode | Duration | Frequency |
|---|---|---|---|
| _(Process overview)_ | _(Classroom / e-Learning / Video)_ | _(X hours)_ | _(Onboarding)_ |
| _(System navigation)_ | _(Hands-on / Shadow)_ | _(X hours)_ | _(Onboarding)_ |
| _(Refresher training)_ | _(e-Learning)_ | _(X hours)_ | _(Annual)_ |

### Transition Readiness (BPS-Specific)
| Milestone | Criteria | Status |
|---|---|---|
| Shadow (Read) | Operator observes 10 live transactions | ⬜ Pending |
| Reverse Shadow | Operator processes; SME monitors | ⬜ Pending |
| Supervised Processing | Operator processes independently; SME available | ⬜ Pending |
| Sign-Off | Error rate < threshold for X consecutive days | ⬜ Pending |

---

## 13. CONTROLS & COMPLIANCE

| Control | Type | Description | Evidence Required |
|---|---|---|---|
| _(e.g., Dual Authorization)_ | Preventive | Two approvers required for amounts > $X | _(System log / Email trail)_ |
| _(e.g., Daily Reconciliation)_ | Detective | System count vs manual log compared daily | _(Reconciliation report)_ |
| _(e.g., Access Review)_ | Preventive | Quarterly review of user access rights | _(Access report sign-off)_ |

### Relevant Policies / Regulations
- _(e.g., Company Finance Policy v3.2)_
- _(e.g., GDPR / Data Protection requirements)_
- _(e.g., Client-specific compliance requirement)_

---

## 14. RELATED DOCUMENTS

| Document | Type | Location |
|---|---|---|
| _(e.g., Process Map — BPMN)_ | _(Diagram)_ | _(SharePoint URL / folder path)_ |
| _(e.g., Work Instruction — Step X Detail)_ | _(WI)_ | _(Link)_ |
| _(e.g., Client SLA Agreement)_ | _(Contract)_ | _(Secure folder)_ |
| _(e.g., Training Deck)_ | _(PPT)_ | _(Link)_ |

---

## 15. AI PIPELINE METADATA

> **This section is for machine consumption only. Populated automatically by the AI SOP builder.**

```yaml
# AI Pipeline Metadata Block
source_type: ""          # transcript | audio | video | manual
source_id: ""            # File name or recording ID
source_duration: ""      # For audio/video (HH:MM:SS)
extraction_model: ""     # Model used to generate this SOP
extraction_date: ""      # YYYY-MM-DD
confidence_score: ""     # Overall extraction confidence (0.0 – 1.0)
review_required: true    # Flag for human review before publishing

sections_extracted:
  - section: "process_steps"
    timestamp_range: ""  # e.g., 00:01:00 – 00:18:45
    confidence: ""

  - section: "exceptions"
    timestamp_range: ""
    confidence: ""

  - section: "roles"
    timestamp_range: ""
    confidence: ""

screenshots_extracted: []  # List of auto-captured screen frames
placeholders_remaining: [] # List of [PLACEHOLDER] tags still needing human fill
```

---

## 16. SIGN-OFF

| Role | Name | Signature | Date |
|---|---|---|---|
| **Process Owner** | | | |
| **Operations Manager** | | | |
| **QA / Compliance** | | | |
| **BPS Partner Lead** _(if applicable)_ | | | |
| **Client Approver** _(if applicable)_ | | | |

---

> **Template Version:** 1.0
> **For AI Pipeline Issues:** Contact the CoE team for schema updates or field mapping changes.
