# CryoCord CRM — Onboarding Approval Workflow (`cryocord_CRM`)

A custom Frappe app that manages CryoCord's client onboarding lifecycle inside ERPNext — from CRM handover to "ready for storage agreement" — with a real approval step, separation of duties, server-side transition guards, and an append-only audit trail of every decision.

**Stack:** ERPNext v15.x · Frappe v15.x <!-- TODO: exact versions from `bench version` -->

---

## Table of Contents

1. [Setup](#1-setup)
2. [What This App Contains](#2-what-this-app-contains)
3. [Data Model & Design Rationale](#3-data-model--design-rationale)
4. [Workflow & Server-Side Guards](#4-workflow--server-side-guards)
5. [Permissions & Separation of Duties](#5-permissions--separation-of-duties)
6. [Role & Permission Matrix](#6-role--permission-matrix)
7. [Audit Trail: Guarantees & Limitations](#7-audit-trail-guarantees--limitations)
8. [Report & REST API](#8-report--rest-api)
9. [Upgrade Safety](#9-upgrade-safety)
10. [Production-Readiness Note](#10-production-readiness-note)
11. [Assumptions & Deliberate Scope Decisions](#11-assumptions--deliberate-scope-decisions)
12. [What I Would Do With More Time](#12-what-i-would-do-with-more-time)

---

## 1. Setup

> This section is kept in sync with the app as features land — see commit history.

### 1.0 Prerequisites

- A working Frappe Bench with **Frappe v15.x** and **ERPNext v15.x** installed on the site
- MariaDB, Redis, Node ≥ 18 (standard bench environment)
- A site with ERPNext installed and setup wizard completed (company, currency **MYR**)

### 1.1 Install the app

```bash
cd frappe-bench
bench get-app https://github.com/IraHumanitas/CryoCord-CRM.git
bench --site <your-site> install-app cryocord_CRM
bench --site <your-site> migrate
bench --site <your-site> clear-cache
```

`install-app` creates the app's DocTypes; `migrate` syncs fixtures (idempotent — safe to re-run).

**What gets created automatically (fixtures):** 

* Custom fields added to standard ERPNext DocTypes.
* Roles and role-related configuration where required.
* Workflow configuration for **CryoCord Onboarding Case**.
* Notifications.
* Report configuration.
* Other application-specific metadata required by the implementation.

### 1.2 Create test users & assign roles

Create three users (Users → New User, user type **System User**) and assign one CryoCord role each:

| User (example) | Role |
|---|---|
| `sales.user@CRM.com` | CryoCord Sales Officer |
| `operation@CRM.com` | CryoCord Operations Manager |
| `sales.manager@CRM.com` | CryoCord Sales Manager |

> ⚠️ **Do not test as Administrator** — it bypasses every permission check, so everything will look like it "works" even when Doc Permission are wrong.

### 1.3 Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Custom fields / roles / workflow missing | Fixtures not synced → `bench --site <site> migrate`, check `fixtures` list in `hooks.py`, then `clear-cache` |
| Workflow buttons not showing | User lacks the transition's role, or logged in as a user with no CryoCord role |
| "Not permitted" opening Customer/Item as a CryoCord role | Custom DocPerm fixtures not synced (see above) |
| Totals not recalculating | Values are computed server-side on Save — save the document |

> **Note:** do not test as Administrator — it bypasses all permission checks.


## 2. What This App Contains

The CryoCord CRM app extends ERPNext/Frappe with a focused onboarding workflow while reusing standard ERPNext DocTypes wherever the existing data model is sufficient.

### Custom Components

| Component                             | Type                   | Purpose                                                                                                                                                                                    |
| ------------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **CryoCord Onboarding Case**          | Custom DocType         | Main system of record for the customer onboarding process, including requested packages, pricing, delivery information, workflow state, approvals, and handover references.                |
| **CryoCord Approval Audit Log**       | Custom DocType         | Append-only audit trail recording workflow transitions, actors, timestamps, reasons, blocked attempts, and request IP addresses.                                                           |
| **CryoCord Onboarding Case** workflow | Workflow               | Controls the onboarding lifecycle from Draft through Sales Review, Operations Approval, Ready for Storage Agreement, and Completed, including rejection, revision, and cancellation paths. |
| **Pending Approvals by Age**          | Script Report          | Provides Operations with a prioritized view of cases pending approval, including waiting time, queue status, EDD status, and priority score.                                               |
| **Status Change Notifications**       | Notification / Fixture | Provides workflow-related notifications when an onboarding case changes status.                                                                                                            |
| **Whitelisted API**                   | REST API               | Exposes the current onboarding case state and its approval audit history through a permission-checked server-side endpoint.                                                                |

### Standard ERPNext/Frappe DocTypes Reused

The app intentionally reuses standard ERPNext/Frappe DocTypes instead of duplicating their functionality:

| Standard DocType | Usage                                                                          |
| ---------------- | ------------------------------------------------------------------------------ |
| **Customer**     | Customer master and primary business relationship.                             |
| **Lead**         | Sales prospect and source of the onboarding process.                           |
| **Contact**      | Customer contact information.                                                  |
| **Address**      | Customer address information.                                                  |
| **Item**         | Service/package catalog used by onboarding cases.                              |
| **Item Group**   | Classification of service items.                                               |
| **Item Price**   | Price-list based pricing for service items.                                    |
| **Quotation**    | Existing ERPNext quotation data referenced during onboarding where applicable. |
| **Contract**     | Contract reference used before an onboarding case can be completed.            |
| **User**         | Sales and operations users involved in ownership, approval, and assignment.    |

### Fixtures

The app ships configuration required to reproduce the CryoCord setup across environments, including:

| Fixture                    | Contents                                                                                                                   |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **Roles**                  | CryoCord Sales Officer · Operations Manager · Customer Care · Management                                                   |
| **Custom Fields**          | `cc_*` fields on **Lead** and **Item**, including service interest, expected delivery date, and service/catalog attributes |
| **Property Setters**       | Configure the Item Link field to display **Item Name** instead of the Item Code                                            |
| **Workflow**               | **CryoCord Onboarding** workflow, including workflow states and workflow actions                                           |
| **Custom Doc Permissions** | Access configuration for CryoCord roles on **Customer, Lead, Contact, Address, Item, and Contract**                        |
| **Master Data**            | Lead Sources · Customer Groups · Item Groups                                                                               |
| **Notifications**          | Status-change notifications related to the CryoCord onboarding process                                                     |

The app keeps business-specific behavior inside the custom application while minimizing modifications to ERPNext core code, making the implementation safer to maintain across framework and ERPNext upgrades.

### Custom Fields Added to Standard DocTypes

The app extends standard ERPNext/Frappe DocTypes with CryoCord-specific fields where the existing schema does not cover the onboarding and service catalog requirements.

#### Lead

The following custom fields are added to **Lead**:

| Field                       | Type   | Purpose                                                                                                                             |
| --------------------------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| `cc_service_interest`       | Select | Captures the service category the lead is interested in, such as Stem Cell Banking, Cell Therapy, Biobanking, or Affiliate Product. |
| `cc_expected_delivery_date` | Date   | Records the expected delivery date for services where delivery-related information is relevant.                                     |
| `cc_preferred_hospital`     | Data   | Records the hospital preferred by the customer for applicable services.                                                             |
| `cc_lost_reason`            | Select | Records the reason a lead is marked as Lost Quotation, such as price, competitor, no response, medical reason, or duplicate lead.   |

The delivery date and preferred hospital fields are conditionally displayed based on the selected service interest. The lost reason is displayed when the Lead status is `Lost Quotation` or `Do Not Contact`.

#### Item

The following custom fields are added to **Item** to support CryoCord's service and storage catalog:

| Field                              | Type   | Purpose                                                                                                                                    |
| ---------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `cc_service_category`              | Select | Classifies the item into a CryoCord service category, such as Stem Cell Banking, Genetic Testing, Health Screening, or Storage Extension.  |
| `cc_cell_category`                 | Select | Identifies the cell category for applicable banking services, such as Hematopoietic Stem Cell, MSC, iPSC, or Immune Cell.                  |
| `cc_source_tissue`                 | Select | Identifies the biological source or tissue associated with the service, such as Cord Blood, Cord Tissue, Peripheral Blood, or Bone Marrow. |
| `cc_storage_segment`               | Select | Identifies the applicable storage segment: Baby, Adult, Research, or N/A.                                                                  |
| `cc_default_billing_type`          | Select | Defines the default billing model for the item: One-Time or Annual/Recurring.                                                              |
| `cc_default_storage_years`         | Int    | Stores the default storage duration in years for applicable services.                                                                      |
| `cc_is_storage_service`            | Check  | Indicates whether the item represents a storage service.                                                                                   |
| `cc_require_sample_collection`     | Check  | Indicates whether the service requires sample collection.                                                                                  |
| `cc_require_laboratory_processing` | Check  | Indicates whether the service requires laboratory processing.                                                                              |
| `cc_collection_kit_required`       | Check  | Indicates whether a collection kit is required when sample collection is enabled.                                                          |

Some Item fields are conditionally displayed based on the selected service category or related configuration. For example, cell category is shown for applicable banking services, while collection kit requirement depends on whether sample collection is required.


## 3. Data Model & Design Rationale

<!-- Define Data Model for Custom Doctype and adjust column for reuse doctype-->

### 3.1 Why reuse standard ERPNext records (Customer, Lead, Item) instead of creating my own?
### 3.2 Why is the Onboarding Case a custom DocType — why not Quotation or Opportunity?
### 3.3 When did I use a child table vs. a separate linked DocType, and why?
### 3.4 Frappe Workflow exists — why is server-side validation still necessary?
### 3.5 How are permissions enforced beyond hiding fields or buttons?
### 3.6 What does the audit trail guarantee, and what does it not?
### 3.7 How does the app stay upgrade-safe during ERPNext upgrades?

## 4. Workflow & Server-Side Guards

<!-- State diagram, transition table
     (from / action / to / docstatus / role / guard), and the note on why
     Rejected stays at docstatus 0 while immutability begins at Approved. -->

## 5. Permissions & Separation of Duties

<!-- Permissio: the four roles, permlevel 1 on approval fields,
     Custom DocPerms for standard DocTypes, and the SoD guard —
     including how it holds against direct REST calls. -->

## 6. Role & Permission Matrix

<!-- REQUIRED by brief. Columns: Business Role | Frappe Role |
     Create | Edit Draft | Approve | Reject | Close | Allowed Transitions |
     Enforced By (Role Permissions / Workflow / Python) — per rule. -->

## 7. Report 

<!-- Pending Approvals by Age report -->

## 8. REST API 

<!-- get_case_status endpoint —
     @frappe.whitelist(), explicit permission check, no allow_guest,
     example request/response, 200/403/401 test results. -->

## 9. Upgrade Safety

<!-- TODO: custom app only, cc_-prefixed Custom Fields + Property Setters via
     fixtures, no core edits, hooks are additive, patches for data migrations. -->

## 10. Production-Readiness Note

<!-- REQUIRED — a few sentences covering:
     what happens during bench migrate; which fixtures are synced;
     when a patch is used instead of a fixture; backup steps before applying
     in production; and how to restore if something goes wrong. -->


## 11. What I Would Do With More Time

<!-- PTIOANAL: fiture that not finish in this version-->

---

<!-- *Design documentation: see [`docs/design-spec.md`](docs/design-spec.md) for the full field-level specification and decision changelog.* -->