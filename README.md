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
7. [Report](#7-report)
8. [REST API](#8-rest-api)
9. [Upgrade Safety](#9-upgrade-safety)
10. [Production-Readiness Note](#10-production-readiness-note)
11. [What I Would Do With More Time](#11-what-i-would-do-with-more-time)
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
* Roles, Role Profiles & Permissions — CryoCord roles, role profiles, and custom DocPerm configuration.
* Workflow configuration for **CryoCord Onboarding Case**.
* Notifications.
* Report configuration.
* Other application-specific metadata required by the implementation.

### 1.2 Demo Accounts

The following accounts are provided for testing role-based access and workflow permissions:

| Role | Email | Password |
|---|---|---|
| Sales User | `sales.user@cms.com` | `CMSCryocord` |
| Sales Manager | `sales.manager@cms.com` | `CMSCryocord` |
| Operations Manager | `operations.manager@cms.com` | `CMSCryocord` |

> These accounts are intended for local development and demonstration purposes only.

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
| **Roles**                  | Sales User | Sales Manager | Operations                                                 |
| **Custom Fields**          | `cc_*` fields on **Lead** and **Item**, including service interest, expected delivery date, and service/catalog attributes |
| **Property Setters**       | Configure the Item Link field to display **Item Name** instead of the Item Code                                            |
| **Workflow**               | **CryoCord Onboarding** workflow, including workflow states and workflow actions                                           |
| **Custom Doc Permissions** | Access configuration for CryoCord roles on **Customer, Lead, Contact, Address, Item, and Contract**                        |
| **Master Data**            | Company · Item · Item Groups · Price List · Item Price · User                                                                           |
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

### 3.1 Why reuse standard ERPNext records (Customer, Lead, Item) instead of creating my own?

The application reuses standard ERPNext records where the required business concept already exists.

* **Customer** is reused as the master record for the customer receiving the CryoCord service.
* **Lead** is reused for the CRM lifecycle and remains the source of sales-related information before onboarding.
* **Item** is reused as the service/package catalog, with custom `cc_` fields added for CryoCord-specific attributes such as storage-service eligibility.
* **Contact** and **Address** are also reused rather than creating duplicate customer-related master data.

This avoids duplicating ERPNext's existing master-data relationships, permissions, and standard behavior. Custom fields are added only where CryoCord-specific information is required.

### 3.2 Why is the Onboarding Case a custom DocType — why not Quotation or Opportunity?

`CryoCord Onboarding Case` is used as the system of record for the onboarding and approval lifecycle because the process represents more than a sales transaction.

The case contains business information and workflow-specific data such as:

* onboarding ownership and assignment,
* requested service packages,
* approval states,
* submission and decision metadata,
* handover references,
* onboarding completion information,
* server-side business validations.

A **Quotation** represents a commercial quotation, while an **Opportunity** represents a sales opportunity. Neither is a natural system of record for the complete operational approval lifecycle required by the assessment.

Keeping the process in a dedicated DocType also allows the application to define its own workflow, permissions, immutability rules, audit trail, and business validations without changing the meaning of standard ERPNext documents.

#### Customer-to-Case Relationship

A Customer may have multiple Onboarding Cases over time. However, only one active/in-flight Onboarding Case is allowed for a Customer at a time.

A new Onboarding Case can be created after a previous case reaches Completed or Cancelled. If an existing in-flight case is found, creation of another case for the same Customer is rejected.

This allows repeat onboarding while preventing multiple concurrent onboarding processes for the same Customer.


### 3.3 When did I use a child table vs. a separate linked DocType, and why?

The requested service packages are implemented as a **child table** inside `CryoCord Onboarding Case`.

A child table is appropriate because each package row belongs directly to a single onboarding case and does not require an independent lifecycle.

Each row stores information such as:

* selected service item,
* quantity,
* rate,
* discount,
* calculated amounts.

The actual service definition remains in the standard **Item** DocType, while the child table represents the specific items requested in that case.

A separate linked DocType would be more appropriate for a record that has its own lifecycle, permissions, or independent business meaning. The requested package rows do not require that level of independence.

### 3.4 Frappe Workflow exists — why is server-side validation still necessary?

Frappe Workflow provides the configured workflow states and transitions, but the application still validates transitions on the server.

The server-side implementation checks that:

* the target state is valid,
* the transition exists in the configured workflow,
* the current user has the required role,
* required fields are present,
* separation-of-duties rules are satisfied,
* state-specific business requirements are met,
* server-managed fields cannot be supplied arbitrarily by the client.

This is necessary because workflow buttons and client-side UI restrictions are not a sufficient security boundary. A user may interact with the document through the API or another non-standard client, so the business rules must also be enforced in Python.

### 3.5 How are permissions enforced beyond hiding fields or buttons?

Authorization is implemented in multiple layers.

Standard Frappe **Role Permissions / DocPerm** provide the baseline permissions for each role.

For `CryoCord Onboarding Case`, additional row-level restrictions are implemented through:

* `get_permission_query_conditions()` to restrict which records are visible,
* `has_permission()` to validate access to an individual document,
* server-side workflow guards to control who may perform each transition,
* field permission levels for protected fields,
* server-managed field enforcement to prevent client-side tampering.

For example, a Sales User can only access cases assigned to that user through `sales_officer`, while Operations Managers cannot access cases that are still in the early sales stages.

Therefore, changing the UI, removing a button, or manually constructing an API request does not by itself bypass the authorization rules.

### 3.6 What does the audit trail guarantee, and what does it not?

The application records the onboarding case lifecycle through a dedicated **CryoCord Approval Audit Log**.

The audit trail records transition-related information such as:

* previous state,
* new state,
* action,
* actor,
* timestamp,
* reason,
* IP address where available.

Successful workflow transitions are recorded after the document update through the document lifecycle hooks, while creation is also recorded as an initial transition.

The audit trail provides a historical record of the application's recorded workflow transitions. It is not intended to be a complete database-level history of every field modification, every failed database transaction, or every change made directly outside the application's controlled workflow.

Therefore, the audit log should be understood as a **workflow audit trail**, not a full database change-data-capture system.

### 3.7 How does the app stay upgrade-safe during ERPNext upgrades?

The application keeps its customizations inside the **custom CryoCord app** rather than modifying ERPNext/Frappe core code.

Upgrade-safety is supported by:

* reusing standard ERPNext DocTypes instead of replacing them,
* adding CryoCord-specific fields using the custom app,
* keeping workflow and permission configuration in the application's own fixtures/configuration,
* implementing business rules through DocType controller methods and hooks,
* keeping API endpoints and reports inside the custom app,
* avoiding direct modifications to ERPNext source files.

This makes ERPNext upgrades safer because the application's business logic remains separated from the framework and ERPNext core. Standard ERPNext functionality can therefore be upgraded independently, while the CryoCord-specific behavior remains within the custom application.

Where ERPNext behavior or schema changes between versions affect the customization, the application's fixtures, patches, and tests should be updated as part of the upgrade process.



## 4. Workflow & Server-Side Guards

`CryoCord Onboarding Case` uses a Frappe Workflow for the overall lifecycle, with additional server-side guards to enforce authorization and business rules.

### 4.1 Workflow States

The onboarding lifecycle is:

```text
Draft
  │
  ├── Submit for Review ───────────────→ Sales Review
  │                                        │
  │                                        ├── Request Revision ──→ Draft
  │                                        │
  │                                        └── Submit for Operations Approval
  │                                                  ↓
  │                                  Pending Operations Approval
  │                                      │              │
  │                                      │              └── Reject ──→ Rejected
  │                                      │
  │                                      └── Approve
  │                                             ↓
  │                                  Operations Approved
  │                                             │
  │                                             └── Mark Ready
  │                                                    ↓
  │                                  Ready for Storage Agreement
  │                                             │
  │                                             └── Complete
  │                                                    ↓
  │                                               Completed
  │
  └── Cancel ──→ Cancelled
```

Rejected cases can be revised and returned to Draft:

```text
Rejected → Draft
```

Cases can also be cancelled from the applicable pre-completion stages.

### 4.2 Transition Rules

| From                        | Action                         | To                          | Docstatus | Role               | Server-Side Guard                                                                           |
| --------------------------- | ------------------------------ | --------------------------- | --------: | ------------------ | ------------------------------------------------------------------------------------------- |
| Draft                       | Submit for Review              | Sales Review                |         0 | Sales User         | Required customer, service category, contact, address, payment terms, and requested package |
| Sales Review                | Request Revision               | Draft                       |         0 | Sales Manager      | Sales Manager role required                                                                 |
| Sales Review                | Submit for Operations Approval | Pending Operations Approval |         0 | Sales Manager      | Requested package required; submission metadata is generated server-side                    |
| Pending Operations Approval | Approve                        | Operations Approved         |         0 | Operations Manager | Separation of duties; decision metadata generated server-side                               |
| Pending Operations Approval | Reject                         | Rejected                    |         0 | Operations Manager | Separation of duties; rejection reason required                                             |
| Operations Approved         | Mark Ready                     | Ready for Storage Agreement |         1 | Operations Manager | Operations Manager role required                                                            |
| Ready for Storage Agreement | Complete                       | Completed                   |         1 | Operations Manager | Contract reference required; onboarding date generated server-side                          |
| Rejected                    | Revise                         | Draft                       |         0 | Sales User         | Rejection reason is cleared server-side                                                     |
| Draft / Sales Review        | Cancel                         | Cancelled                   |         0 | Sales Manager      | Sales Manager role required                                                                 |
| Pending Operations Approval | Cancel                         | Cancelled                   |         0 | Operations Manager | Operations Manager role required                                                            |

### 4.3 Server-Side Guards

The Frappe Workflow configuration defines the available states and transitions, while the DocType controller enforces the business rules on the server.

The server validates:

* whether the target workflow state is valid;
* whether the requested transition is defined in the workflow;
* whether the current user has the required role;
* whether mandatory business fields are present;
* whether the selected items are valid CryoCord storage-service items;
* whether the item group matches the selected Service Category, except for `All Item Groups`;
* whether separation-of-duties requirements are satisfied;
* whether server-managed fields are protected from client-side modification;
* whether state-specific requirements such as rejection reason and contract reference are satisfied.

This provides defense in depth so that workflow rules cannot be bypassed by directly manipulating the document or calling the API.

### 4.4 Why Rejected Remains `docstatus = 0`

A rejected case remains in `docstatus = 0` because rejection represents a **workflow decision**, not a finalized ERP document submission.

The case can still be revised and returned to Draft:

```text
Rejected → Draft → Sales Review
```

Keeping the document in `docstatus = 0` allows the same onboarding record to continue through the workflow without requiring a new document or an amendment cycle solely because the approval decision was negative.

### 4.5 Why Immutability Begins After Approval

Business content becomes progressively protected once the case leaves the editable states.

`Draft` and `Rejected` remain editable so that the Sales User can prepare or revise the case. Once the case reaches the approval process and especially after `Operations Approved`, the protected business content must no longer be changed arbitrarily.

Server-side immutability checks therefore prevent modification of protected fields and requested packages after the case has entered a locked workflow stage.

This ensures that the information reviewed and approved by Operations remains consistent with the information used for the subsequent storage-agreement and completion stages.


## 5. Permissions & Separation of Duties

Access is controlled through standard Frappe Role Permissions, custom `DocPerm` configurations, row-level permission hooks, and server-side validation. Baseline DocType permissions define what actions each role can perform, while row-level and server-side rules further restrict access based on record ownership, workflow stage, and business requirements.

### 5.1 Role-Based DocType Permissions

The following table summarizes the baseline permissions configured for the application's primary roles:

| DocType                      | Sales User                                | Sales Manager           | Operations Manager                      | System Manager |
| ---------------------------- | ----------------------------------------- | ----------------------- | --------------------------------------- | -------------- |
| **Lead**                     | Create / Read / Update assigned leads     | Create / Read / Update  | Read                                    | Full           |
| **Customer**                 | Create / Read / Update assigned customers | Create / Read / Update  | Read                                    | Full           |
| **Contact**                  | Create / Read / Update                    | Create / Read / Update  | Read                                    | Full           |
| **Address**                  | Create / Read / Update                    | Create / Read / Update  | Read                                    | Full           |
| **Item**                     | Read                                      | Read / Update           | Read                                    | Full           |
| **Contract**                 | Read                                      | Create / Read / Update  | Create / Read / Update                  | Full           |
| **CryoCord Onboarding Case** | Create / Read / Update own assigned cases | Read / Update all cases | Read / Update cases in Operations stage | Full           |

These permissions represent the **baseline DocType-level authorization**. Additional restrictions are applied through row-level permission hooks and server-side business logic.

> **Note:** Workflow transition permissions are enforced separately and are not represented solely by the DocType permission matrix above.

### 5.2 Row-Level Permissions

`CryoCord Onboarding Case` uses Frappe's `permission_query_conditions` and `has_permission` hooks to enforce record-level access.

The access rules are:

* **Sales User** can access only cases where `sales_officer` matches the authenticated user.
* **Sales Manager** can access onboarding cases across the sales team.
* **Operations Manager** can access cases that have reached the Operations stage. Cases that are still in the early sales stages remain restricted.
* **System Manager** has unrestricted access.

These hooks **restrict access but do not grant baseline DocType permissions**. The corresponding `DocPerm` configuration is therefore maintained separately.

### 5.3 Field-Level Permissions

Approval and decision-related fields are protected using Frappe's permission levels. Fields containing system-generated approval metadata are assigned a higher permission level to prevent ordinary users from directly modifying them.

Server-managed fields include:

* `submitted_by`
* `submitted_on`
* `decision_by`
* `decision_on`
* `rejection_reason`
* `onboarded_on`

These values are populated and validated by server-side workflow logic rather than trusted from client-side requests.

### 5.4 Workflow Authorization
— soona.
> in section 6

### 5.5 Separation of Duties

The Operations approval stage enforces separation of duties at the server level.

An **Operations Manager cannot approve or reject a case that they originally submitted or own**. The restriction is evaluated against the authenticated Frappe session user:

```python
if user in (self.owner, self.sales_officer):
    frappe.throw(
        _("You cannot approve or reject a case you submitted yourself.")
    )
```

Because this validation is performed server-side, changing the client-side UI or manually constructing an API request does not bypass the restriction.

### 5.7 Authorization Layers

The overall authorization model can be summarized as follows:

| Layer                           | Responsibility                                                                         |
| ------------------------------- | -------------------------------------------------------------------------------------- |
| **Role Permissions / DocPerm**  | Defines baseline permissions for each role and DocType.                                |
| **Permission Query Conditions** | Restricts which records are returned to a user.                                        |
| **`has_permission`**            | Performs record-level permission checks for individual documents.                      |
| **Field Permission Level**      | Protects sensitive and server-managed fields from direct editing.                      |
| **Workflow Validation**         | Ensures only valid state transitions are allowed.                                      |
| **Server-Side Business Rules**  | Enforces requirements such as separation of duties and required fields.                |
| **API Validation**              | Ensures direct API requests are subject to the same authorization rules as UI actions. |

This layered authorization model ensures that permissions are enforced independently of the client interface and remain effective for both normal Frappe UI interactions and direct API requests.


## 6. Role & Permission Matrix

The following matrix summarizes the permissions and workflow actions available to each business role for the **CryoCord Onboarding Case**.

| Business Role      | Frappe Role        | Create | Edit Draft             | Approve                        | Reject | Close  | Allowed Transitions                                                                                                                        | Enforced By                          |
| ------------------ | ------------------ | ------ | ---------------------- | ------------------------------ | ------ | ------ | ------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------ |
| Sales User         | Sales User         | Yes    | Own cases              | No                             | No     | No     | Draft → Sales Review, Rejected → Draft                                                                                                     | Role Permissions + Python            |
| Sales Manager      | Sales Manager      | No     | All accessible cases   | Submit for Operations Approval | No     | Cancel | Sales Review → Pending Operations Approval, Sales Review → Draft, Draft/Sales Review → Cancelled                                           | Role Permissions + Workflow + Python |
| Operations Manager | Operations Manager | No     | Operations-stage cases | Yes                            | Yes    | Yes    | Pending Operations Approval → Approved/Rejected/Cancelled, Approved → Ready for Storage Agreement, Ready for Storage Agreement → Completed | Role Permissions + Workflow + Python |
| System Manager     | System Manager     | Yes    | Yes                    | Yes                            | Yes    | Yes    | All valid workflow transitions                                                                                                             | Role Permissions + Workflow + Python |

### Workflow Transition Responsibility

The main workflow responsibilities are:

| Transition                                        | Responsible Role   |
| ------------------------------------------------- | ------------------ |
| Draft → Sales Review                              | Sales User         |
| Sales Review → Draft                              | Sales Manager      |
| Sales Review → Pending Operations Approval        | Sales Manager      |
| Pending Operations Approval → Operations Approved | Operations Manager |
| Pending Operations Approval → Rejected            | Operations Manager |
| Operations Approved → Ready for Storage Agreement | Operations Manager |
| Ready for Storage Agreement → Completed           | Operations Manager |
| Draft / Sales Review → Cancelled                  | Sales Manager      |
| Pending Operations Approval → Cancelled           | Operations Manager |
| Rejected → Draft                                  | Sales User         |

Workflow transitions are validated server-side in addition to the Frappe Workflow configuration. This prevents users from bypassing workflow rules through direct API or document manipulation.


## 7. Report

### Pending Approvals by Age

The **Pending Approvals by Age** Script Report provides an operational view of Onboarding Cases that are pending in the approval workflow. The report focuses on how long each case has been waiting, its queue condition, Expected Delivery Date (EDD), and an automatically calculated priority.

#### Purpose

This report is intended to help the Operations and Management teams identify cases that require attention based on:

* How many days the case has been waiting since `submitted_on`
* The age of the approval queue
* Whether the Expected Delivery Date is overdue or approaching
* The commercial value of the case
* A calculated priority score

#### Data Source

The report reads data from:

```text
CryoCord Onboarding Case
```

The main fields used are:

```text
name
customer
service_category
sales_officer
expected_delivery_date
grand_total_excl_tax
submitted_on
workflow_state
```

#### Filters

The report supports the following filters:

| Filter         | Description                                       |
| -------------- | ------------------------------------------------- |
| Workflow State | Filter cases by their current workflow state      |
| Sales Officer  | Filter cases assigned to a specific Sales Officer |
| Queue Status   | Filter by `Normal`, `Warning`, or `Critical`      |
| EDD Status     | Filter by `On Track`, `Due Soon`, or `Overdue`    |

The first two filters are applied directly in the database query, while `Queue Status` and `EDD Status` are calculated from the report data and applied before the final result is returned.

#### Waiting Days

`Waiting Days` is calculated from the case's `submitted_on` date up to the current date.

The calculation is:

```text
Waiting Days = Today - Submitted On
```

Cases are then grouped into the following aging categories:

| Waiting Days | Aging    | Queue Status |
| -----------: | -------- | ------------ |
|          0–2 | 0-2 Days | Normal       |
|          3–7 | 3-7 Days | Warning      |
|           >7 | >7 Days  | Critical     |

#### EDD Status

When an Expected Delivery Date is available, the report calculates `Days to EDD` and assigns an EDD status:

| Condition                    | EDD Status |
| ---------------------------- | ---------- |
| EDD has passed               | Overdue    |
| EDD is within 3 days         | Due Soon   |
| EDD is more than 3 days away | On Track   |

Cases without an Expected Delivery Date use `-` as their EDD status.

#### Priority Score

The report calculates a priority score using waiting time, EDD urgency, and case value.

| Condition             | Score |
| --------------------- | ----: |
| Waiting > 7 days      |   +30 |
| Waiting 3–7 days      |   +15 |
| EDD overdue           |   +40 |
| EDD due within 3 days |   +20 |
| Grand Total ≥ 10,000  |   +10 |

The resulting score determines the priority:

| Score | Priority  |
| ----: | --------- |
|  ≥ 60 | 🔴 High   |
| 30–59 | 🟡 Medium |
|  < 30 | 🟢 Low    |

This provides a simple prioritization mechanism for identifying cases that have both prolonged approval waiting time and/or approaching delivery deadlines.

#### Sorting

The final result is sorted by:

1. Highest priority score
2. Highest waiting days
3. Earliest `submitted_on`

This places the cases with the highest operational urgency at the top of the report.

#### Report Summary

The report provides the following summary indicators:

```text
Total Cases
Critical Queue
Warning Queue
Overdue EDD
Due Soon
Average Waiting Days
```

`Average Waiting Days` is calculated across all cases returned after the selected filters are applied.

#### Chart

The report includes a donut chart showing the distribution of cases by aging category:

```text
0-2 Days
3-7 Days
>7 Days
```

This provides a quick visual representation of the current approval queue and helps identify whether cases are accumulating in the older aging categories.



## 8. REST API

### Get Onboarding Case Status

The `get_onboarding_case_status` endpoint returns the current state of a **CryoCord Onboarding Case** together with its audit history.

The endpoint is exposed using Frappe's `@frappe.whitelist()` and does **not** use `allow_guest=True`. Access is explicitly checked using the document's read permission before any case data or audit history is returned.

### Endpoint

```text
GET /api/method/crm_cryocord.api.onboarding_case.get_onboarding_case_status
```

### Parameters

| Parameter | Type   | Required | Description                             |
| --------- | ------ | -------- | --------------------------------------- |
| `name`    | String | Yes      | Name/ID of the CryoCord Onboarding Case |

### Example Request

```text
GET /api/method/crm_cryocord.api.onboarding_case.get_onboarding_case_status?name=SAR-2026-0005
```

The request must be authenticated using a valid Frappe session or API credentials.

### Example Response

```json
{
    "message": {
        "onboarding_case": {
            "name": "SAR-2026-0005",
            "customer": "CryoCare Medical Centre",
            "workflow_state": "Draft",
            "docstatus": 0,
            "submitted_on": null,
            "decision_by": null,
            "decision_on": null
        },
        "audit_history": [
            {
                "performed_at": "2026-08-13T10:15:32",
                "from_state": null,
                "to_state": "Draft",
                "action": "Create",
                "performed_by": "sales@example.com",
                "remarks": null,
                "is_blocked_attempt": 0
            }
        ]
    }
}
```

The response intentionally exposes only the fields required by the API contract rather than returning the complete document.

### Authorization

The endpoint performs an explicit read-permission check on the requested Onboarding Case. A user who does not have permission to access the case cannot retrieve either its current state or audit history.

The audit history is therefore protected by the same authorization boundary as the parent Onboarding Case.

### Security

The endpoint is intentionally not exposed to guest users:

```python
@frappe.whitelist()
def get_onboarding_case_status(name):
```

No `allow_guest=True` is configured. Authentication is therefore required before the endpoint can be executed.

### Test Results

| Test                                       | Result                                                  |
| ------------------------------------------ | ------------------------------------------------------- |
| Authenticated request with valid case ID   | **200 OK** — returns current state and audit history    |
| Authenticated request with invalid case ID | **DoesNotExistError** — case does not exist             |
| Authenticated user without read permission | **403 / PermissionError** — access denied               |
| Request without authentication             | **401 / AuthenticationError** — authentication required |

These tests verify both the functional response and the server-side authorization boundary of the endpoint.



## 9. Upgrade Safety

The CryoCord customization is implemented entirely inside the custom application and avoids modifications to Frappe or ERPNext core code.

### Customization Strategy

* All CryoCord-specific business logic is implemented in the custom `crm_cryocord` app.
* Standard ERPNext DocTypes such as `Customer`, `Lead`, `Item`, `Contact`, and `Address` are reused rather than modified at the core level.
* Custom fields use the `cc_` prefix to clearly separate CryoCord-specific fields from standard ERPNext fields.
* Property Setters are used for UI and metadata customizations instead of editing standard DocType definitions directly.

### Fixtures

Custom fields, Property Setters, workflow configuration, roles, permissions, and other required configuration are maintained through the application's fixtures where applicable.

This allows the customization to be reproduced consistently across environments after installation or migration.

### Hooks and Server-Side Logic

The application's DocType controllers, permission hooks, workflow guards, reports, and API endpoints are implemented as additive customizations.

No Frappe or ERPNext core Python, JavaScript, or configuration files are modified.

### Data Migrations

When a future schema or data change requires migration, the application can use Frappe patches to transform existing data in a controlled and versioned manner.

This keeps migration logic within the custom application and avoids manual changes to ERPNext core data structures.

### Upgrade Approach

Because the customization is isolated from the framework and ERPNext core, upgrades can be performed while minimizing merge conflicts and reducing the risk of losing custom business logic.

After an ERPNext/Frappe upgrade, the custom application's fixtures, patches, workflow configuration, permissions, reports, APIs, and server-side validations should be verified against the upgraded version.


## 10. Production-Readiness Note

Before applying the CryoCord application to a production environment, database and site configuration should be backed up so the deployment can be restored if a migration or customization change causes unexpected issues.

### `bench migrate`

Running:

```bash
bench --site <site> migrate
```

applies pending Frappe/ERPNext migrations and synchronizes the custom application's required metadata and configuration for the site. This includes applicable fixtures such as Custom Fields, Property Setters, Workflow configuration, Roles, and other exported records configured by the application.

The migration should be followed by validation of the affected DocTypes, workflow transitions, permissions, reports, and API endpoints.

### Fixtures vs. Patches

Fixtures are used for **configuration and metadata** that should be reproducible across environments, such as Custom Fields, Property Setters, roles, and workflow-related configuration.

A **patch** should be used when an upgrade requires an actual **data transformation or migration of existing records**, especially when the change cannot be expressed as static fixture data.

For example, adding a new Custom Field can be handled through fixture synchronization, while converting existing records to populate a newly introduced value should be handled through a patch.

### Backup Before Production Migration

Before running migration commands in production:

```bash
bench --site <site> backup
```

The backup should be verified and retained according to the production backup policy before applying the migration.

For higher-risk changes, application-level and infrastructure-level backups should also be coordinated according to the deployment environment.

### Restore / Rollback

If a migration causes an unrecoverable issue, stop further deployment changes and restore the affected site from the verified pre-migration backup.

The restore process should include:

1. Restore the database backup.
2. Restore site files/private files if they were included in the backup strategy.
3. Ensure the application version is compatible with the restored database state.
4. Restart the required bench services.
5. Verify core DocTypes, permissions, workflow transitions, reports, and API endpoints.

Production migration should therefore be treated as a controlled deployment step rather than a manual database modification. A verified backup provides the rollback point before applying schema, metadata, or data changes.


## 11. What I Would Do With More Time

If more time were available, I would further validate and refine the business process before expanding the implementation.

* **Explore the CRM process in more depth** — Work more closely with the business flow to understand the complete customer journey from lead qualification through onboarding, approval, contracting, and subsequent service operations. This could reveal additional business states or transitions that would make the workflow more representative of the real CRM process.

* **Refine the workflow states and transition rules** — Re-evaluate whether each current workflow state represents a meaningful business milestone, and determine whether some states should be split, merged, or have additional validation requirements based on the actual operational process.

* **Improve downstream process integration** — Further define how a completed onboarding case should connect with downstream processes such as contracts, billing, and storage operations, rather than treating the onboarding workflow as an isolated lifecycle.

---

<!-- *Design documentation: see [`docs/design-spec.md`](docs/design-spec.md) for the full field-level specification and decision changelog.* -->