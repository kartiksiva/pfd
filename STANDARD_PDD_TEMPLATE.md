# [Process Name] - Process Definition Document (PDD)

## 1. Document Control
| Version | Date | Author | Description |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-03-05 | [Author Name] | Initial Draft (As-Is Process) |

## 2. Process Overview
*   **Process Name:** [e.g., Invoice Validation]
*   **Objective:** [Short description of why the process exists]
*   **Frequency:** [e.g., Daily / On-demand]
*   **Estimated Volume:** [e.g., 50 cases/day]
*   **Manual Effort:** [e.g., 15 mins per case]

## 3. Scope
### 3.1 In-Scope
*   [e.g., Processing PDF invoices from the 'AP_Inbox']
*   [e.g., Data entry into SAP FICO module]

### 3.2 Out-of-Scope
*   [e.g., Physical paper invoices]
*   [e.g., Handling tax disputes (requires Human-in-the-Loop)]

## 4. Prerequisites & Systems
### 4.1 Prerequisites
*   [e.g., Access to Shared Drive]
*   [e.g., Active SAP User Profile]

### 4.2 Application Inventory
| Application | Version | Access Method |
| :--- | :--- | :--- |
| SAP S/4HANA | v2023 | Desktop Client |
| Microsoft Outlook | Office 365 | Web/Desktop |
| Internal Portal | v1.2 | Chrome/Edge |

---

## 5. Detailed Process Steps (As-Is)
*This is the core of the document. Use a table for structured steps and nested lists for complex logic.*

| Step # | Action | Role | System | Input | Output |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1.1 | Open Outlook and navigate to 'Invoices' folder. | Operator | Outlook | Email | Invoice PDF |
| 1.2 | Download the attachment to the 'Pending' directory. | Operator | File Explorer | PDF | File on Local Path |
| 1.3 | Open Internal Portal and upload the PDF for OCR. | Operator | Web Portal | File | Extracted Data |
| 1.4 | Compare Extracted Data with SAP Records. | Analyst | SAP | Data | Validation Result |

### Step 1.4 Details (Sub-steps)
1.  Log into **SAP** using credentials.
2.  Enter Transaction Code **FB60**.
3.  **If** Invoice Number exists:
    *   Proceed to Step 1.5.
4.  **Else** (Invoice missing):
    *   Route to "Business Exception - Missing PO".

---

## 6. Business Rules & Logic
*Define the 'brains' of the process.*
*   **Rule 1:** Only process invoices where the Total Amount is > $0.
*   **Rule 2:** Invoices from "Vendor X" must be routed to the Priority Queue.

## 7. Exceptions Handling
### 7.1 Business Exceptions
*   **Scenario:** Duplicate Invoice Number.
*   **Action:** Move to 'Duplicates' folder and notify requester via email.

### 7.2 Technical Exceptions
*   **Scenario:** SAP System Down.
*   **Action:** Wait 15 minutes and retry; if persistent, alert IT Support.

## 8. Inputs & Outputs
*   **Primary Input:** PDF Document via Email.
*   **Primary Output:** Verified Record in SAP; Confirmation Email.

## 9. Metrics & Risks
*   **Success Metric:** Accuracy Rate > 98%.
*   **Risk:** Poor OCR quality on handwritten invoices.
*   **Mitigation:** Human-in-the-loop review for confidence scores < 85%.

---
**Document generated for Process Excellence / Automation Readiness.**
