# Download Input Spreadsheet - Process Definition Document (PDD)

## 1. Document Control
| Version | Date | Author | Description |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-03-10 | PFCD Agent | Initial Draft (As-Is Process) |

## 2. Process Overview
*   **Process Name:** Download Input Spreadsheet
*   **Objective:** To automate the entry of data from a spreadsheet into a dynamic web form where field positions change after each submission.
*   **Frequency:** User clicks the 'Start' button on the RPA Challenge web page.
*   **Estimated Volume:** TBD
*   **Manual Effort:** TBD

## 3. Scope
### 3.1 In-Scope
*   Covers the process from downloading the input spreadsheet to submitting all required records through the web form for 10 rounds.

### 3.2 Out-of-Scope
*   Future-state redesign and optimization.

## 4. Prerequisites & Systems
### 4.1 Prerequisites
*   Input data spreadsheet is available and downloaded.
*   Web form is accessible and ready for input.
*   Automation tool or user is prepared to process 10 rounds.

### 4.2 Application Inventory
| Application | Version | Access Method |
| :--- | :--- | :--- |
| Excel/Spreadsheet Application | Unknown | As observed in evidence |
| RPA Challenge Web Portal | Unknown | As observed in evidence |
| RPA Challenge Web Portal, Excel | Unknown | As observed in evidence |

---

## 5. Detailed Process Steps (As-Is)
*This is the core of the document. Use a table for structured steps and nested lists for complex logic.*

| Step # | Action | Role | System | Input | Output |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | Download the Excel file containing the data records to be entered. | User | RPA Challenge Web Portal | Web page with download link | Downloaded Excel file |
| 2 | Initiate the challenge by clicking the 'Start' button, which begins the countdown and enables form submission rounds. | User | RPA Challenge Web Portal | Ready web page | Challenge timer starts, form enabled |
| 3 | Read the next record from the downloaded Excel file for entry. | Automation Bot | Excel/Spreadsheet Application | Excel file | Single data record |
| 4 | Identify the correct input fields on the web form, as their positions change after each submission. | Automation Bot | RPA Challenge Web Portal | Data record, dynamic form | Mapped data to fields |
| 5 | Input the mapped data into the corresponding form fields. | Automation Bot | RPA Challenge Web Portal | Mapped data | Form populated with data |
| 6 | Click the 'Submit' button to send the data for the current round. | Automation Bot | RPA Challenge Web Portal | Populated form | Form submission, next round triggered |
| 7 | Repeat steps 3-6 for each record in the spreadsheet, for a total of 10 rounds. | Automation Bot | RPA Challenge Web Portal, Excel | Remaining records | All records submitted |

### Step Details
1.  Follow the sequence listed in the table above.
2.  Apply business rules and exception handling where applicable.

## 6. Business Rules & Logic
*Define the 'brains' of the process.*
*   **Rule 1:** All form fields must be filled for each record.
*   **Rule 2:** Field mapping must be dynamic to accommodate changing positions.
*   **Rule 3:** Process must complete 10 rounds without errors.
*   **Rule 4:** No penalties for submissions before clicking 'Start'.

## 7. Exceptions Handling
### 7.1 Business Exceptions
*   **Scenario:** Start button unresponsive
*   **Action:** Requires business review and follow-up.
*   **Scenario:** Process interruption or incomplete rounds
*   **Action:** Requires business review and follow-up.

### 7.2 Technical Exceptions
*   **Scenario:** Download fails or file is corrupted
*   **Action:** Retry, log, and escalate to technical owner if persistent.
*   **Scenario:** Spreadsheet read error
*   **Action:** Retry, log, and escalate to technical owner if persistent.
*   **Scenario:** Field not found or mapping error
*   **Action:** Retry, log, and escalate to technical owner if persistent.
*   **Scenario:** Input error or validation failure
*   **Action:** Retry, log, and escalate to technical owner if persistent.
*   **Scenario:** Submission fails or error message displayed
*   **Action:** Retry, log, and escalate to technical owner if persistent.

## 8. Inputs & Outputs
*   **Primary Input:** Excel data file
*   **Primary Output:** All spreadsheet records successfully submitted via the web form

## 9. Metrics & Risks
*   **Success Metric:** Number of successful submissions
*   **Success Metric:** Accuracy of data entry
*   **Success Metric:** Time taken to complete all rounds
*   **Success Metric:** Number of errors or retries
*   **Risk:** Automation fails to identify dynamic fields
*   **Mitigation:** Define owner, threshold, and contingency action.
*   **Risk:** Data entry errors due to field mapping issues
*   **Mitigation:** Define owner, threshold, and contingency action.
*   **Risk:** Process interruption due to system or network failure
*   **Mitigation:** Define owner, threshold, and contingency action.
*   **Risk:** Incomplete submission of all records
*   **Mitigation:** Define owner, threshold, and contingency action.


## 10. SIPOC
| Supplier | Input | Process | Output | Customer |
| :--- | :--- | :--- | :--- | :--- |
| RPA Challenge Web Portal | Excel data file | Download Input Spreadsheet | Downloaded Excel file | User/Automation Bot |
| User | Downloaded Excel file | Start Challenge | Challenge timer starts | Automation Bot |
| Excel/Spreadsheet Application | Excel file | Extract Data from Spreadsheet | Single data record | Automation Bot |
| Automation Bot | Data record, dynamic form | Map Data to Dynamic Form Fields | Mapped data to fields | Automation Bot |
| Automation Bot | Mapped data | Enter Data into Form | Form populated with data | RPA Challenge Web Portal |
| Automation Bot | Populated form | Submit Form | Form submission, next round triggered | RPA Challenge Web Portal |

---
**Document generated for Process Excellence / Automation Readiness.**
