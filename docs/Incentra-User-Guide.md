# Incentra — User Guide

**Sales Compensation Platform**

Version 1.0 · June 2026

---

## Table of contents

1. [Introduction](#1-introduction)
2. [Getting started](#2-getting-started)
3. [Roles and navigation](#3-roles-and-navigation)
4. [Recommended setup order](#4-recommended-setup-order)
5. [User Setup](#5-user-setup)
6. [Compensation plans](#6-compensation-plans)
7. [Commission rules](#7-commission-rules)
8. [Orders and transactions](#8-orders-and-transactions)
9. [How commission is calculated](#9-how-commission-is-calculated)
10. [Commission management (admin / finance / manager)](#10-commission-management-admin--finance--manager)
11. [Incentive Details — sales rep statement](#11-incentive-details--sales-rep-statement)
12. [Disputes](#12-disputes)
13. [Payouts](#13-payouts)
14. [Territories](#14-territories)
15. [Audit log](#15-audit-log)
16. [Integrations (Connect)](#16-integrations-connect)
17. [AI commission assistant](#17-ai-commission-assistant)
18. [CSV templates and import tips](#18-csv-templates-and-import-tips)
19. [Troubleshooting](#19-troubleshooting)
20. [Quick reference](#20-quick-reference)

---

## 1. Introduction

**Incentra** helps your organisation manage sales compensation end to end:

- Define **compensation plans** and rate structures
- Load **orders** (sales transactions)
- **Calculate commissions** automatically based on role, position, product, and rules
- **Approve** commissions for payroll
- Give sales reps a personal **Incentive Details** statement
- Handle **disputes**, **payouts**, and **audit** trails

This guide explains how to use the application from day-to-day setup through payroll export.

---

## 2. Getting started

### 2.1 Sign in

1. Open your Incentra URL (for example `https://incentra.co.in` or `http://localhost:3000` in development).
2. Enter your **email** and **password** on the login page.
3. Click **Sign in**.

If your organisation uses SSO, use **Sign in with SSO** when that option is enabled.

### 2.2 First login

- Admins should change the default password using **Password** in the sidebar footer.
- Your name and role appear in the top bar after login.

### 2.3 Sign out

Click **Logout** at the bottom of the left sidebar.

---

## 3. Roles and navigation

The sidebar menu depends on your role.

| Role | What you see |
|------|----------------|
| **Sales Rep** (and other non-admin roles) | Dashboard, Incentive Details |
| **Manager** | Dashboard, Commissions, Audit Log |
| **Finance / Finance Viewer** | Dashboard, Commissions, Audit Log, Payouts |
| **Admin / Administrator** | Full menu: Dashboard, Commissions, Orders, Comp Plans, Commission Rules, User Setup, Territories, Audit Log, Payouts |

### Admin-only actions

- Create and edit compensation plans
- Import orders
- Manage users and hierarchy
- Approve commissions (full workflow)
- Recalculate commissions
- Connect CRM integrations ( **Connect** icon in the top bar )

---

## 4. Recommended setup order

For a new organisation, configure Incentra in this order:

```
1. User Setup        → Add employees, roles, positions, hierarchy
2. Territories       → (Optional) Define sales territories
3. Comp Plans        → Create monthly plans with rate tables
4. Commission Rules  → (Optional) Bonuses, overrides, conditions
5. Orders            → Create or import sales transactions
6. Commissions       → Review, approve, export for payroll
7. Payouts           → Track payment runs
```

**Important:** An order only generates commission when:

- The employee exists in **User Setup** with a matching **employee_id**
- An **Active** compensation plan covers the order date and matches the employee's **role** or **position**
- The order status is **Success** (see [Section 8.4](#84-order-status-booked-vs-success))

---

## 5. User Setup

**Menu:** User Setup (admin only)

User Setup defines who earns commission and how hierarchy splits work.

### 5.1 Tabs

| Tab | Purpose |
|-----|---------|
| **User** | Create or edit a single employee profile |
| **People** | Browse all users |
| **Title** | Job titles (reference data) |
| **Position** | Position names used on plans and orders |
| **Hierarchy** | Manager–rep relationships and split percentages |
| **Upload** | Bulk CSV import of users |

### 5.2 Required fields for each user

| Field | Why it matters |
|-------|----------------|
| **Email** | Login and unique identity |
| **Name** | Display on statements and reports |
| **Employee ID** | Must match `employee_id` on orders |
| **Role** | Must match the **role** on compensation plans (e.g. `Sales Rep`, `Manager`) |

### 5.3 Optional but useful fields

- **Position name** — matches position-specific compensation plans
- **Business group**, **Territory**, **Personal target**
- **Enable login** — allows the user to sign in to Incentra

### 5.4 Hierarchy

On the **Hierarchy** tab you define who reports to whom:

- **Parent participant** — typically the manager
- **Child participant** — the sales rep
- **Split percentage** — percentage of commission kept by the rep; the manager receives the remainder

Example: Split 80% → rep keeps 80%, manager gets 20% of the calculated commission.

### 5.5 Bulk upload

Use the **Upload** tab to import many users from CSV. Duplicate emails or employee IDs are rejected.

---

## 6. Compensation plans

**Menu:** Comp Plans (admin only)

A compensation plan defines **how much** commission is paid for a given role or position in a given month.

### 6.1 Creating a plan

1. Click **New plan**.
2. Fill in the header:
   - **Plan name** — descriptive label
   - **Role** — must match User Setup (e.g. `Sales Rep`)
   - **Compensation month** — the month this plan applies to
   - **Status** — set to **Active** for commission to run
   - **Commission table type** — see below
3. Save the plan, then add rate tiers.

### 6.2 Commission table types

Incentra supports three table types:

#### A. Tier-Based Rate Table (RATE)

Commission varies by **sales amount band**.

| From amount | To amount | Rate % | Bonus |
|-------------|-----------|--------|-------|
| 0 | 50,000 | 5% | 0 |
| 50,001 | (open) | 8% | 500 |

Formula: `Sales × Rate% + Bonus`

#### B. Flat Rate Table (FLAT)

A single flat percentage above a minimum threshold.

| Flat rate | Minimum sales | Bonus |
|-----------|---------------|-------|
| 6% | 0 | 0 |

#### C. SC Lookup Table (LOOKUP)

Commission depends on **product**, **service**, and **distribution** channel, plus a sales band.

| Product | Service | Distribution | Sales band | Rate | Bonus |
|---------|---------|--------------|------------|------|-------|
| Widget Pro | Support | Partner | 0 – open | 12% | 500 |
| Widget Pro | (any) | (any) | 0 – 50,000 | 5% | 0 |
| (blank) | (blank) | (blank) | 0 – open | 3% | 0 |

- Leave a dimension **blank** on a row to match **any** value on the order.
- The most specific matching row wins.

### 6.3 Plan matching priority

When an order is processed, Incentra selects a plan in this order:

1. **Position plan** — plan with matching `position_name`
2. **Role plan** — plan with matching `role` and no position on the plan
3. Plan must be **Active** and the order date must fall within the plan's effective dates

---

## 7. Commission rules

**Menu:** Commission Rules (admin only)

Commission rules add **conditional adjustments** on top of the base plan calculation (bonuses, rate overrides, etc.).

### 7.1 How rules work

```
Order → Base plan calculation → Commission rules → Final commission
```

Rules are attached to a **compensation plan** and evaluated in **sequence**.

### 7.2 Rule structure

| Section | Description |
|---------|-------------|
| **Conditions** | When the rule applies (optional — empty means all orders on the plan) |
| **Results** | What to do when matched (override rate, add bonus, etc.) |
| **Stop on match** | Stop evaluating further rules after this one matches |

### 7.3 Condition fields

You can filter on order and employee attributes, including:

- Product, Service, Distribution
- Region, Customer segment, Business group
- Order status, Currency, Sales amount
- Position, Employee ID, Territory, Role

### 7.4 Result types

| Result type | Effect |
|-------------|--------|
| **Override tier %** | Replace base rate with a new percentage |
| **Add bonus (₹)** | Add a flat amount to the commission |
| **Flat amount / Multiplier / Override amount** | Advanced adjustments |

### 7.5 After saving a rule

Existing orders are **not** updated automatically. On the **Commissions** page, run **Recalculate** for the affected period to apply new rules to historical orders.

---

## 8. Orders and transactions

**Menu:** Orders (admin only)

Orders represent sales transactions that drive commission.

### 8.1 Create order (manual)

1. Open **Orders** → **Create order**.
2. Enter required fields:
   - **Order ID** — unique per organisation
   - **Order date**
   - **Employee ID** — must exist in User Setup
   - **Sales amount**
3. Optional: product, service, distribution, region, customer segment, etc.
4. Set **Status** (see [8.4](#84-order-status-booked-vs-success)).
5. Click **Save order**.

### 8.2 Import CSV

1. Open **Orders** → **Import CSV**.
2. Download the **template** if needed (`orders_template.csv`).
3. Upload a UTF-8 CSV with a header row.
4. Review the import summary (success / failed / commission warnings).

Re-importing the same `order_id` **updates** the order and recalculates commission (unless already approved — see [Section 10](#10-commission-management-admin--finance--manager)).

### 8.3 Required CSV columns

| Column | Required |
|--------|----------|
| order_id | Yes |
| order_date | Yes (YYYY-MM-DD) |
| employee_id | Yes |
| sales_amount | Yes |

### 8.4 Order status: Booked vs Success

| Status | Commission |
|--------|------------|
| **Booked** | Not calculated — deal is open |
| **Pending** | Not calculated |
| **Cancelled** | Not calculated |
| **Success** | Commission calculated when a plan matches |

**Typical workflow:**

1. Import or create order with status **Booked**.
2. When the deal closes, change status to **Success** (re-import CSV with updated status, or update via API).
3. Commission is calculated automatically.

> **Tip:** Only rows with `order_status = Success` appear in commission results.

---

## 9. How commission is calculated

End-to-end flow:

```
┌─────────────┐
│    Order    │  employee_id, order_date, sales_amount, status = Success
└──────┬──────┘
       ▼
┌─────────────────────┐
│  Find comp plan     │  position plan → role plan; Active + date match
└──────┬──────────────┘
       ▼
┌─────────────────────┐
│  Apply rate table   │  RATE / FLAT / LOOKUP tier
└──────┬──────────────┘
       ▼
┌─────────────────────┐
│  Commission rules   │  conditions → bonuses / overrides
└──────┬──────────────┘
       ▼
┌─────────────────────┐
│  Hierarchy split    │  rep + manager shares
└──────┬──────────────┘
       ▼
┌─────────────────────┐
│  Commission record  │  status: calculated
└─────────────────────┘
```

### Commission statuses

| Status | Meaning |
|--------|---------|
| **calculated** | System-generated, awaiting approval |
| **manager_approved** | Manager signed off |
| **approved** | Finance/admin approved — ready for payroll |
| **paid** | Included in a completed payout run |

Approved commissions are **protected** from accidental overwrite during order re-import unless an admin runs **force recalculate**.

---

## 10. Commission management (admin / finance / manager)

**Menu:** Commissions

### 10.1 Viewing commissions

- Use **Search** to filter by employee name or ID.
- Use **Status filter** to show calculated, approved, paid, etc.
- Click a row to open **Explain** (calculation breakdown and AI Q&A).

### 10.2 Period actions

Set **Start date** and **End date**, then:

| Action | Who | Purpose |
|--------|-----|---------|
| **Manager approve** | Manager | First approval step |
| **Finance approve** | Finance / Admin | Mark ready for payroll |
| **Admin approve** | Admin | Shortcut to finance-approved |
| **Export payroll CSV** | Finance / Admin | Download approved commissions |
| **Recalculate** | Admin | Re-run calculation for the period |

### 10.3 Recalculate

Use when plans, rules, or orders changed:

- **OK** on the confirmation dialog = replace **approved** commissions too (use with care).
- **Cancel** = skip orders that already have approved commissions.

You can combine recalculate with the employee search box to scope to one rep.

### 10.4 Disputes panel

At the bottom of the Commissions page, admins see all disputes. Reps submit disputes from **Incentive Details** (see [Section 12](#12-disputes)).

---

## 11. Incentive Details — sales rep statement

**Menu:** Incentive Details (sales reps)

This is the rep's personal commission statement.

### 11.1 Tabs

| Tab | Shows |
|-----|-------|
| **Orders** | Orders and commission per deal |
| **Credits** | Credit amounts from rules |
| **Commission rate** | Effective rates applied |
| **Commission earned** | Earned amounts by period |
| **Adjustments** | Manual or rule-driven adjustments |
| **Payout status** | Payment status |

### 11.2 Period filter

Set start and end dates to view a specific pay period.

### 11.3 Explain and dispute

- Click a commission row to open the **explanation** modal (how it was calculated).
- Use **Dispute** on a row to flag an incorrect amount (see [Section 12](#12-disputes)).

---

## 12. Disputes

Disputes let reps question a commission; admins resolve them.

### 12.1 Rep workflow

1. Open **Incentive Details**.
2. Find the commission and click **Dispute**.
3. Describe the issue and submit.
4. When admin resolves the dispute, click **Okay** to acknowledge.
5. After acknowledgment, either party can **Delete** the closed dispute record.

### 12.2 Admin workflow

1. Open **Commissions** → **Disputes** panel.
2. Review open disputes.
3. **Resolve** (accept change) or **Reject** with a message.
4. Rep must acknowledge before the dispute can be deleted.

### 12.3 Dispute statuses

| Status | Meaning |
|--------|---------|
| **open** | Awaiting admin action |
| **resolved** | Admin accepted / adjusted |
| **rejected** | Admin declined the dispute |

---

## 13. Payouts

**Menu:** Payouts (admin and finance)

Track payroll payment runs.

1. **Create** a payout run with name and date range (draft).
2. When bank transfer completes, **Mark paid** and optionally enter a payment reference.
3. Approved commissions in that period move to **paid** status.

---

## 14. Territories

**Menu:** Territories (admin only)

Define sales territories (name and code). Assign territories to users in User Setup and reference them in commission rule conditions.

---

## 15. Audit log

**Menu:** Audit Log (admin, finance, manager)

View a tamper-evident log of important actions: logins, uploads, approvals, recalculations, and more. Each entry includes timestamp, user, action, and request ID.

---

## 16. Integrations (Connect)

**Access:** **Connect** icon (grid) in the top bar — admin only

Connect external systems to sync orders automatically:

- **Salesforce** and other CRM connectors
- **Generic REST** APIs
- **Webhooks** for inbound order data

After syncing, orders follow the same commission rules (including **Success** status requirement).

Configure integrations in the Connect dialog, then run **Sync orders** to pull data.

---

## 17. AI commission assistant

Inside the **Explain** modal (on Commissions or Incentive Details):

- View a step-by-step **calculation breakdown**
- **Ask AI** any question about the commission (e.g. "How can I earn more next month?")
- Use **What-if** to simulate commission on a different sales amount

The AI uses order, plan, and rep context. Responses may take up to a minute on local AI setups.

---

## 18. CSV templates and import tips

### 18.1 Order template

Download from **Orders → Import CSV → Download template**, or use:

```
order_id,order_date,employee_id,position_name,customer_name,product_name,service_name,distribution,sales_amount,quantity,order_status,currency
```

### 18.2 Import tips

- Use **UTF-8** encoding.
- Dates: `YYYY-MM-DD` (also accepts `DD-MM-YYYY`, `MM/DD/YYYY`).
- `order_id` must be unique within your organisation.
- Set `order_status` to **Success** when the deal is closed.
- Re-importing the same `order_id` updates the row and recalculates commission.

### 18.3 Common import warnings

| Warning | Fix |
|---------|-----|
| No User Setup profile for employee_id | Add the rep in User Setup |
| No active plan for month | Create an Active plan for that month and role |
| Order status is Booked | Change to Success when deal closes |
| Commission amount zero | Check rate tiers / lookup rows / thresholds |

---

## 19. Troubleshooting

### No commission generated

Check in order:

1. Order status = **Success**
2. Employee exists in User Setup with correct **employee_id**
3. Employee **role** (or **position**) matches an **Active** plan
4. Plan **compensation month** includes the order date
5. Plan has at least one rate tier (or lookup row)
6. Sales amount falls within a tier band

### Commission amount seems wrong

1. Open **Explain** on the commission row.
2. Verify which plan and tier matched.
3. Check **Commission Rules** for overrides or bonuses.
4. Check **Hierarchy** split if manager also received a share.
5. For LOOKUP plans, verify product / service / distribution on the order.

### Re-import did not update commission

Approved commissions are locked. Admin must run **Recalculate** with force, or change status back and re-approve.

### Duplicate users on CSV upload

User Setup rejects duplicate **email** or **employee_id**. Edit the existing user instead.

---

## 20. Quick reference

### Admin monthly checklist

- [ ] Create compensation plans for the new month
- [ ] Verify User Setup is current (new hires, role changes)
- [ ] Import or sync orders (Success status for closed deals)
- [ ] Review **Commissions** → resolve disputes
- [ ] Manager + Finance approval workflow
- [ ] Export payroll CSV
- [ ] Create payout run and mark paid

### Key URLs (development)

| Item | URL |
|------|-----|
| Application | http://localhost:3000 |
| API | http://localhost:8000/api/ |
| Order CSV template | `/orders_template.csv` |

### Support contacts

Configure `NOTIFY_EMAILS` in your environment to receive order upload alerts. Contact your Incentra administrator for access issues.

---

*© Incentra — Sales Compensation Platform. This document is intended for end users and administrators.*
