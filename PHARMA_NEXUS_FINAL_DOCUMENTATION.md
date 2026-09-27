# PHARMA NEXUS V2 — FINAL PROJECT DOCUMENTATION
**CITTA RISE — Problem 7: Smart Vendor Restocking & Bargaining Agent**

---

## 1. Project Title
* **Project Name:** Pharma Nexus V2
* **Competition / Track:** CITTA RISE — Problem 7
* **Sub-Title:** Autonomous Smart Vendor Restocking & Adaptive Bargaining Agent
* **Version:** 4.0.0 (Phases 0–9 Complete & Frozen)

---

## 2. Problem Statement
Hospital and retail pharmacies face severe operational challenges managing pharmaceutical supply chains:
1. **Critical Stockouts vs. Spoilage:** Inventory levels frequently fall below safety reorder points. Stockouts cause missed prescriptions and compromised patient care, while over-ordering leads to expired medication and financial loss.
2. **Time-Consuming Manual Sourcing:** Procurement officers must manually compare multiple vendor catalogs with differing base prices, delivery lead times, and Minimum Order Quantities (MOQs).
3. **Complex Multi-Constraint Optimization:** Every purchase decision must simultaneously satisfy five competing dimensions:
   * **Demand Coverage:** Daily sales rate and supplier lead time.
   * **Vendor MOQ:** Minimum batch thresholds imposed by manufacturers.
   * **Shelf-Life & Expiry:** Maximum sellable stock before batch expiration.
   * **Delivery SLA:** Urgent vs. routine replenishment timelines.
   * **Unit Pricing & Budget:** Total commitment cost and discount potential.
4. **Manual Negotiation & Disconnected ERP Writes:** Price bargaining is typically conducted via email or phone calls without structured reservation bounds. Once finalized, manual data entry into the ERP creates delays and risk of human transcription errors.

---

## 3. Solution Workflow
Pharma Nexus V2 provides an end-to-end autonomous procurement agent that connects stock monitoring directly to ERP execution through a structured, multi-stage pipeline:

```
[Inventory Observation]
         │
         ▼
[Store Procurement Agent]
         │
         ▼
[Deterministic Need & Expiry Calculation]
         │
         ▼
[Vendor Catalogue Discovery]
         │
         ▼
[Multi-Factor Deal Scoring & Vendor Selection]
         │
         ▼
[Multi-Round Adaptive Bargaining]
         │
         ▼
[Independent 7-Constraint Deal Validation]
         │
         ▼
[Autonomous Decision Gate (ACCEPT / REJECT / SWITCH / NO_ORDER)]
         │
         ▼
[Atomic SQLite Transaction (PO Insert + Stock Update)]
         │
         ▼
[ERP State Synchronization]
```

---

## 4. Why This Is an Agent
Unlike simple scripts, rule engines, or chatbots, Pharma Nexus implements a closed-loop **autonomous agent architecture**:

$$\text{OBSERVE} \longrightarrow \text{REASON} \longrightarrow \text{PLAN} \longrightarrow \text{ACT} \longrightarrow \text{OBSERVE RESULT} \longrightarrow \text{ADAPT} \longrightarrow \text{VERIFY} \longrightarrow \text{COMPLETE}$$

### The Store Procurement Agent Execution Cycle:
1. **OBSERVE:** Scans live SQLite inventory levels across all catalogue medicines.
2. **REASON:** Evaluates current stock against reorder thresholds, calculating required coverage units and verifying shelf-life constraints against expiry dates.
3. **PLAN:** Queries vendor offerings, constructs normalized trade-off scores (Price, Delivery SLA, MOQ Efficiency), and identifies the optimal supplier.
4. **ACT:** Initiates structured bargaining by proposing an aggressive opening target offer (10% discount).
5. **OBSERVE RESULT:** Receives the simulated vendor response (`ACCEPT`, `COUNTER`, or `REJECT`).
6. **ADAPT:** In Round 2, evaluates the vendor's counter-proposal against buyer reservation price ceilings and dynamically computes a midpoint concession.
7. **VERIFY:** Passes the negotiated agreement through an independent 7-constraint validator (guardrail) before committing.
8. **COMPLETE:** Executes an atomic database transaction to generate the Purchase Order and restock ERP inventory.

---

## 5. Architecture & Separation of Concerns

```
┌─────────────────────────────────────────────────────────────┐
│                    React / Vite Frontend                    │
│   (Inventory | Vendors | Agent Control | Bargaining | POs)   │
└──────────────────────────────┬──────────────────────────────┘
                               │ REST API (HTTP/JSON)
┌──────────────────────────────▼──────────────────────────────┐
│                    FastAPI Backend Router                   │
│   (/inventory, /vendors, /procurement/start, /execute, etc.)│
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│             Store Procurement Agent Controller              │
│   - AgentState Management                                   │
│   - Autonomous Observe-Reason-Act Lifecycle                 │
│   - Adaptive Multi-Round Negotiation Protocol               │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
┌──────────────▼──────────────┐┌──────────────▼───────────────┐
│     Deterministic Tools     ││    Validation & Safety       │
│  - inventory_tools.py       ││  - validator.py (7 checks)   │
│  - vendor_tools.py          ││  - Duplicate execution guard │
│  - deal_scoring.py          ││  - Execution state gate      │
│  - negotiation_tools.py     ││                              │
│  - purchase_order_tools.py  ││                              │
└──────────────┬──────────────┘└──────────────┬───────────────┘
               │                              │
┌──────────────▼──────────────────────────────▼───────────────┐
│                   SQLite Database (ERP)                     │
│  (inventory, vendors, vendor_offers, purchase_orders tables)│
└─────────────────────────────────────────────────────────────┘
```

### Separation Principle:
* **Agent Reasoning Layer:** Analyzes inventory health, evaluates candidate trade-offs, decides concession rates, and plans multi-round dialogue.
* **Deterministic Business Tool Layer:** Enforces frozen mathematical formulas (coverage calculations, MOQ flooring, deal scoring, SQLite transaction execution).
* **Independent Validator Guardrail:** Acts as a firewall between the agent's negotiation output and database write operations. No PO can ever be created without passing 100% of the validator's rule checks.

---

## 6. Technology Stack
* **Core Backend:** Python 3.11+, FastAPI (REST API, OpenAPI/Swagger docs, CORS middleware), Pydantic v2 (Schema validation & data models).
* **Database & Persistence:** SQLite3 (WAL mode, Foreign Key constraints, atomic transactions).
* **Testing & Quality Assurance:** pytest 9.1+ (82 automated unit, integration, and Hero scenario tests), FastAPI TestClient, httpx.
* **Frontend UI / UX:** React 18 (Hooks, state management), Vite 5 (Bundler & dev server), Lucide React (Icons), Vanilla CSS Design System (Glassmorphic dark theme, responsive layout).
* **Agent System:** Stateful StoreAgent controller, typed `AgentState` dataclasses, deterministic bargaining engines with structured fallback adapters.

---

## 7. Phase-by-Phase Implementation Summary

### Phase 0 — Architecture & Planning
* **Objective:** Define the complete procurement state machine, mathematical formulas, scoring weights, database schemas, and testing strategy.
* **Deliverables:** Architectural blueprint, database schema design, negotiation protocol specifications, and scoring models.

### Phase 1 — Foundation
* **Objective:** Establish SQLite database infrastructure with relational integrity and deterministic seed data.
* **Deliverables:** `backend/database/db.py` (table creation, foreign keys) and `backend/database/seed.py` (3 medicines, 3 vendors, 9 vendor offers).

### Phase 2 — Agent & Tools Foundation
* **Objective:** Implement deterministic inventory observation tools, stock need formulas, and expiry capacity checkers.
* **Deliverables:** `backend/tools/inventory_tools.py` (`get_inventory`, `calculate_need`, `check_expiry`).

### Phase 3 — Vendor Discovery & Selection
* **Objective:** Query vendor catalogues, enforce MOQ floors, and rank candidate quotes using multi-factor normalized scoring.
* **Deliverables:** `backend/tools/vendor_tools.py`, `backend/tools/deal_scoring.py` (Price 45%, Delivery 35%, MOQ 20%).

### Phase 4 — Adaptive Negotiation
* **Objective:** Implement multi-round bilateral bargaining between StoreAgent and vendors with concession profiles and target/reservation bounds.
* **Deliverables:** `backend/tools/negotiation_tools.py` (Round 1 aggressive target, Round 2 adaptive midpoint, vendor reservation floors).

### Phase 5 — Decision & Validation
* **Objective:** Construct an independent 7-constraint deal verification gate and state machine decision resolver (`ACCEPT`, `REJECT`, `SWITCH_VENDOR`, `NO_ORDER`, `UNRESOLVED`).
* **Deliverables:** `backend/tools/validator.py` (`validate_deal`, `validate_negotiation_action`, `calculate_deal_savings`).

### Phase 6 — PO Creation & ERP Write-Back
* **Objective:** Execute atomic database transactions to insert Purchase Orders and restock inventory stock, protected by strict execution guards.
* **Deliverables:** `backend/tools/purchase_order_tools.py` (`create_purchase_order_transaction`), execution guards in `StoreAgent.execute_procurement`.

### Phase 7 — UI Polish & Integration
* **Objective:** Build a 5-tab React/Vite dashboard connecting all REST API endpoints with real-time log streaming and negotiation visualizations.
* **Deliverables:** `frontend/src/pages/` (`Inventory.jsx`, `Vendors.jsx`, `AgentControl.jsx`, `Negotiation.jsx`, `PurchaseOrders.jsx`), `Navbar.jsx`, `index.css`.

### Phase 8 — Hero Scenario Testing
* **Objective:** Full audit and validation of all 3 Hero medicines, decision state branches, transaction rollbacks, duplicate execution idempotency, and REST APIs.
* **Deliverables:** `tests/test_phase8_hero_validation.py` (12 comprehensive integration tests, 100% passing).

### Phase 9 — Hard Freeze
* **Objective:** Lock code, schemas, and endpoints; execute final verification across frontend and backend.
* **Deliverables:** Frozen production codebase, passing test suite (82/82 tests), clean Vite bundle.

---

## 8. Agent State Model
The `AgentState` dataclass tracks the entire procurement lifecycle per medicine:

```python
@dataclass
class AgentState:
    medicine: Dict[str, Any]            # med_id, name
    inventory: Dict[str, Any]           # current_stock, reorder_point, daily_sales, lead_time, expiry
    required_qty: int                   # Computed net replenishment need
    constraints: Dict[str, Any]         # safety_days, coverage_days, raw_need, expiry metrics
    vendor_quotes: List[Any]            # All scored candidate quotes with feasibility flags
    selected_vendor: Optional[Any]      # Top-ranked feasible vendor quote
    negotiation: Dict[str, Any]         # Active negotiation parameters (round, target, ceiling, status)
    negotiation_history: List[Any]      # Round-by-round dialogue history
    best_offer: Optional[Any]           # Final agreed deal terms (price, quantity, savings)
    validation_result: Optional[Dict]   # 7-constraint validator outcome
    savings: Optional[Dict[str, Any]]   # Total savings amount and percentage
    decision: Optional[str]             # Final decision (ACCEPT / REJECT / SWITCH_VENDOR / etc.)
    decision_reason: Optional[str]      # Explainable natural language rationale
    po: Optional[Any]                   # Executed Purchase Order metadata
    execution_result: Optional[Dict]    # Transaction outcome and inventory before/after
```

### State Transitions:
1. **UNINITIALIZED** $\rightarrow$ Initial state before scan.
2. **OBSERVED** $\rightarrow$ Live inventory stock loaded from database.
3. **EVALUATED** $\rightarrow$ Stock evaluated vs reorder point; required quantity calculated.
4. **SOURCED** $\rightarrow$ Vendor quotes fetched, scored, and top vendor selected.
5. **NEGOTIATING** $\rightarrow$ Multi-round bargaining underway.
6. **VALIDATING** $\rightarrow$ Negotiated deal submitted to 7-point validator.
7. **DECIDED** $\rightarrow$ Decision resolved (`ACCEPT`, `REJECT`, `SWITCH_VENDOR`, `NO_ORDER`).
8. **COMMITTED** $\rightarrow$ PO written to database; inventory incremented.

---

## 9. Inventory Reasoning & Mathematical Formulas
All inventory calculations are deterministic and executed by `inventory_tools.py`:

### 1. Coverage Days:
$$\text{coverage\_days} = \text{lead\_time\_days} + \text{safety\_days}$$
*(Default safety buffer = 2 days)*

### 2. Raw Need & Required Quantity:
$$\text{raw\_need} = \text{daily\_sales} \times \text{coverage\_days}$$
$$\text{required\_qty} = \max(\text{raw\_need} - \text{current\_stock},\, 0)$$

### 3. Expiry Shelf-Life Capacity:
$$\text{expiry\_days\_left} = (\text{expiry\_date} - \text{reference\_date}).\text{days}$$
$$\text{expiry\_safe\_qty} = \text{daily\_sales} \times \text{expiry\_days\_left}$$
$$\text{expiry\_risk} = (\text{expiry\_days\_left} < 30) \lor (\text{expiry\_days\_left} \le \text{lead\_time\_days})$$

---

## 10. Vendor Discovery & Multi-Factor Scoring

### MOQ Order Quantity Rule:
Vendors enforce minimum order batches. The agent adjusts the order quantity to respect vendor constraints:
$$\text{offered\_qty} = \max(\text{required\_qty},\, \text{vendor\_MOQ})$$
$$\text{total\_cost} = \text{base\_price} \times \text{offered\_qty}$$

### Hard Feasibility Constraints:
A vendor quote is flagged as **Infeasible (Score = 0.0)** if:
1. $\text{offered\_qty} < \text{required\_qty}$
2. $\text{offered\_qty} < \text{vendor\_MOQ}$
3. $\text{offered\_qty} > \text{expiry\_safe\_qty}$ *(Risk of medicine expiring before sale)*

### Multi-Factor Scoring Weights:
For feasible quotes, components are normalized across candidates:

| Factor | Weight | Formula / Description |
| :--- | :---: | :--- |
| **Price Score** | **45%** | $1.0 - \frac{\text{base\_price} - \min(\text{price})}{\max(\text{price}) - \min(\text{price})}$ *(Lower price = higher score)* |
| **Delivery SLA Score** | **35%** | $1.0 - \frac{\text{delivery\_days} - \min(\text{delivery})}{\max(\text{delivery}) - \min(\text{delivery})}$ *(Faster delivery = higher score)* |
| **MOQ Efficiency** | **20%** | $\min\left(1.0,\, \frac{\text{required\_qty}}{\text{offered\_qty}}\right)$ *(100% if exact match, penalized if over-ordering)* |

$$\text{Composite Score} = (0.45 \times \text{Price Score} + 0.35 \times \text{Delivery Score} + 0.20 \times \text{MOQ Score}) \times 100.0$$

### Deterministic Tie-Breaking Order:
When scores are equal or close, the agent sorts candidates by:
$$\text{Tuple: } (-\text{score},\, \text{total\_cost},\, \text{delivery\_days},\, \text{moq},\, \text{vendor\_id})$$

---

## 11. Adaptive Negotiation Protocol

```
Round 1: StoreAgent proposes Target Price ($P_{target} = 0.90 \times P_{base}$)
                │
                ▼
         Vendor evaluates offer vs Vendor Floor ($P_{floor}$)
                │
                ├─ If $P_{offer} \ge \text{acceptance threshold} \rightarrow$ ACCEPT
                └─ If $P_{offer} < \text{acceptance threshold} \rightarrow$ COUNTER ($P_{v\_counter}$)
                │
                ▼
Round 2: StoreAgent adapts to Counter:
         $P_{agent\_counter} = \text{round}\left(\frac{P_{target} + P_{v\_counter}}{2},\, 2\right)$
                │
                ▼
         Vendor evaluates Round 2 counter:
                ├─ If $P_{agent\_counter} \ge P_{floor} \rightarrow$ ACCEPT
                └─ If $P_{agent\_counter} < P_{floor} \rightarrow$ REJECT / COUNTER
```

### Buyer Price Bounds:
* **Target Price ($P_{target}$):** Base price discounted by 10% ($P_{base} \times 0.90$).
* **Buyer Reservation Ceiling ($P_{res}$):** Baseline quote price ($P_{base} \times 1.00$). The agent will never accept a price above this ceiling.

### Vendor Reservation Floors:
* **Vendor A (ID 1 — Low-Margin Leader):** 4% max concession tolerance (Floor: $0.96 \times P_{base}$).
* **Vendor B (ID 2 — Fast Delivery & Flexible Margin):** 8% max concession tolerance (Floor: $0.92 \times P_{base}$).
* **Vendor C (ID 3 — Moderate Supplier):** 6% max concession tolerance (Floor: $0.94 \times P_{base}$).

---

## 12. Independent 7-Constraint Deal Validation & Decision State Machine
Before any purchase order is generated, `backend/tools/validator.py` evaluates 7 independent checks:

| # | Constraint Check | Validation Rule |
| :---: | :--- | :--- |
| **1** | `required_qty` | $\text{negotiated\_qty} \ge \text{required\_qty} > 0$ |
| **2** | `moq` | $\text{negotiated\_qty} \ge \text{vendor\_MOQ}$ |
| **3** | `expiry` | $\text{negotiated\_qty} \le \text{expiry\_safe\_qty}$ |
| **4** | `price` | $0 < \text{unit\_price} \le \text{buyer\_reservation\_ceiling}$ AND $\text{unit\_price} \ge \text{vendor\_reservation\_floor}$ |
| **5** | `delivery` | $\text{delivery\_days} \le \text{max\_delivery\_days}$ (if specified) |
| **6** | `vendor` | Vendor is registered and matches selected candidate |
| **7** | `negotiation_status` | Status is explicitly `ACCEPTED` by both parties |

### Decision Outcomes:
* **`ACCEPT`:** All 7 validation checks pass. Deal is approved for execution.
* **`SWITCH_VENDOR`:** The top-ranked vendor failed negotiation/validation, but a viable second-choice feasible vendor exists.
* **`REJECT`:** Negotiation failed or validation violated, with no alternative suppliers available.
* **`NO_ORDER`:** No feasible quotes available across all suppliers.
* **`UNRESOLVED`:** Max negotiation rounds reached without reaching bilateral consensus.
* **`NO_PROCUREMENT`:** Stock level is already above the reorder point.

---

## 13. Purchase Order & ERP Write-Back
When a deal is validated with `ACCEPT`, the agent executes `execute_procurement()`:
1. **Enforces Execution Guards:**
   * Guard 1: `state.decision == "ACCEPT"`
   * Guard 2: `state.validation_result["valid"] == True`
   * Guard 3: Non-null selected vendor and agreed best offer.
   * Guard 4: Duplicate execution protection (`state.po is None`).
2. **Uses Final Negotiated Values:**
   * Order quantity is the final agreed quantity ($\ge \text{MOQ}$).
   * Unit price is the negotiated discounted price (not the baseline catalog price).
3. **Updates ERP State:**
   * Generates formatted PO Number (e.g., `PO-#0001`).
   * Updates in-memory `AgentState.inventory["current_stock"]` to match database reality.

---

## 14. Transaction Safety & ACID Integrity
Database updates are executed inside an atomic SQLite transaction in `purchase_order_tools.py`:

```sql
BEGIN TRANSACTION;
  -- 1. Read current stock
  SELECT current_stock FROM inventory WHERE med_id = ?;
  
  -- 2. Insert Purchase Order
  INSERT INTO purchase_orders (med_id, vendor_id, quantity, unit_price, total_cost, delivery_days, status)
  VALUES (?, ?, ?, ?, ?, ?, 'CREATED');
  
  -- 3. Restock inventory
  UPDATE inventory
  SET current_stock = current_stock + ?
  WHERE med_id = ?;
COMMIT;
```

### Rollback Guarantee:
If an error occurs during PO insertion, inventory update, or network timeout:
$$\text{Exception Triggered} \longrightarrow \text{ROLLBACK} \longrightarrow \text{Database returns to exact pre-execution state}$$
*Verified by automated trigger-abort tests: 0 orphan POs, 0 phantom inventory increases.*

---

## 15. Frontend Dashboard Architecture
The frontend is built with React 18, Vite 5, Lucide icons, and custom CSS:

```
┌─────────────────────────────────────────────────────────────┐
│  PHARMA NEXUS — Smart Vendor Restocking & Bargaining ERP    │
│  [Live System Status: 8000 Online] [Phase 4/6 Active]       │
├─────────────────────────────────────────────────────────────┤
│  [1. Inventory] [2. Vendors] [3. Agent Control]             │
│  [4. Live Negotiation] [5. Purchase Orders]                 │
└─────────────────────────────────────────────────────────────┘
```

1. **Inventory Screen (`/inventory`):**
   * Displays medicine stock levels, reorder thresholds, daily sales rate, supplier lead times, and expiry dates.
   * Dynamic status badges: `LOW STOCK` (Amber/Red) vs. `ADEQUATE` (Green).
2. **Vendor Directory (`/vendors`):**
   * Comprehensive catalog of all 3 vendors and 9 medicine offerings.
   * Highlights base wholesale prices, MOQ constraints, and delivery lead times.
3. **Agent Control Center (`/agent`):**
   * One-click trigger for autonomous procurement evaluation and execution.
   * Visual state breakdown: Stock need, expiry safety capacity, quote scoring comparison table.
   * Real-time execution log timeline.
4. **Live Negotiation Screen (`/negotiation`):**
   * Interactive round-by-round chat dialogue between StoreAgent and Vendor.
   * Displays initial catalog quote, opening offer, vendor counter, agent adaptation, and final agreed discount.
5. **Purchase Orders Ledger (`/purchase-orders`):**
   * Complete audit trail of executed POs with generated PO numbers, agreed quantities, negotiated unit rates, total spend, and delivery SLAs.

---

## 16. Hero Scenarios — Exact Audited Results (Phase 8)
All three medicines in the seed catalog have stock below their reorder points. Here are the exact audited outcomes:

### Summary Results Table:
| Metric | Hero 1: Paracetamol | Hero 2: Cetirizine | Hero 3: Azithromycin |
| :--- | :---: | :---: | :---: |
| **Medicine ID** | `1` | `2` | `3` |
| **Initial Stock / Reorder Point** | 40 / 50 | 25 / 30 | 15 / 20 |
| **Daily Sales / Lead Time** | 20 / 5 days | 10 / 3 days | 5 / 4 days |
| **Net Required Quantity** | **100 units** | **25 units** | **15 units** |
| **Expiry Days Left / Safe Cap** | 98 days / 1,960 units | 21 days / 210 units | 55 days / 275 units |
| **Selected Vendor** | **Vendor B (ID: 2)** | **Vendor B (ID: 2)** | **Vendor B (ID: 2)** |
| **Selection Score / Delivery** | 65.50 / 2 days | 74.17 / 2 days | 66.88 / 2 days |
| **Base Price / Vendor MOQ** | $8.50 / 250 units | $2.20 / 30 units | $14.50 / 20 units |
| **Round 1 Proposal $\rightarrow$ Counter** | Agent $7.65 $\rightarrow$ Vendor $8.07 | Agent $1.98 $\rightarrow$ Vendor $2.09 | Agent $13.05 $\rightarrow$ Vendor $13.78 |
| **Round 2 Counter $\rightarrow$ Response** | Agent $7.86 $\rightarrow$ Vendor **ACCEPT** | Agent $2.04 $\rightarrow$ Vendor **ACCEPT** | Agent $13.41 $\rightarrow$ Vendor **ACCEPT** |
| **Final Unit Price** | **$7.86** *(Base: $8.50)* | **$2.04** *(Base: $2.20)* | **$13.41** *(Base: $14.50)* |
| **Final Order Quantity** | **250 units** *(MOQ adjusted)* | **30 units** *(MOQ adjusted)* | **20 units** *(MOQ adjusted)* |
| **Total Committed Cost** | **$1,965.00** | **$61.20** | **$268.20** |
| **Direct Procurement Savings** | **$160.00 (7.53%)** | **$4.80 (7.27%)** | **$21.80 (7.52%)** |
| **Deal Validation (7 Checks)** | **PASS (100%)** | **PASS (100%)** | **PASS (100%)** |
| **Final Decision** | **ACCEPT** | **ACCEPT** | **ACCEPT** |
| **Generated PO Number** | `PO-#0001` | `PO-#0002` | `PO-#0003` |
| **Inventory Stock (Before $\rightarrow$ After)** | **40 $\rightarrow$ 290** | **25 $\rightarrow$ 55** | **15 $\rightarrow$ 35** |

*Total Procurement Spend: **$2,294.40** | Total Direct Negotiated Savings: **$186.60** (Average Discount: **7.5%**).*

---

## 17. Testing & Verification Suite

### Automated Test Results:
* **Total Tests:** **82 passed** in 2.90 seconds (0 failures, 0 errors, 0 skipped).
* **Test Framework:** `pytest 9.1.1`, `FastAPI TestClient`, `Python 3.11`.

```
============================= test session starts =============================
collected 82 items

tests\test_agent.py .....................                                [ 25%]
tests\test_inventory.py .........                                        [ 36%]
tests\test_phase8_hero_validation.py ............                        [ 51%]
tests\test_purchase_order.py ...............                             [ 69%]
tests\test_validator.py ..............                                   [ 86%]
tests\test_vendor.py ...........                                         [100%]

======================== 82 passed, 1 warning in 2.90s ========================
```

### Test Suite Breakdown:
1. **`test_agent.py` (21 tests):** Agent state machine, lifecycle transitions, multi-round negotiation flow, decision formulation, logs.
2. **`test_inventory.py` (9 tests):** Inventory reading, coverage days, raw need calculation, expiry limits, zero-stock edge cases.
3. **`test_phase8_hero_validation.py` (12 tests):** End-to-end Hero audits (Paracetamol, Cetirizine, Azithromycin), ZOPA bounds, decision branches, execution guards, duplicate safety, atomic rollbacks, state isolation, reproducibility.
4. **`test_purchase_order.py` (15 tests):** Atomic PO insertion, inventory increments, transaction rollbacks on failure, PO history retrieval.
5. **`test_validator.py` (14 tests):** Independent 7-constraint checks, reservation price breaches, MOQ violations, expiry overshoots, savings math.
6. **`test_vendor.py` (11 tests):** Vendor quote querying, MOQ quantity enforcement, normalized scoring (Price 45%, Delivery 35%, MOQ 20%), tie-breaking.

### Frontend Build Verification:
* **Bundler:** Vite 5.4.21 production build transforms 1,587 modules in 2.89s with **0 errors**.

---

## 18. What Is Unique About This Project?

1. **True Autonomous Agent vs. CRUD Application:**
   Standard ERPs passively store numbers and wait for human inputs. Pharma Nexus actively monitors stock, computes dynamic replenishment requirements, discovers suppliers, bargains autonomously, and executes transactions.
2. **Bilateral Adaptive Negotiation Engine:**
   Implements a two-round economic bargaining protocol with mathematically modeled Zone of Possible Agreement (ZOPA), vendor concession tolerances (4%–8%), buyer reservation ceilings, and dynamic midpoint adaptation.
3. **Dual-Layer Architecture (Agent Reasoning + Deterministic Business Tools):**
   Separates flexible agent reasoning from frozen, deterministic business formulas. The agent cannot hallucinate prices or ignore MOQs because mathematical calculations are handled by hardened tools.
4. **Independent 7-Point Validation Firewall:**
   An independent validation gate intercepts every negotiated deal before database commitment, checking required quantity, MOQ, expiry limits, price bounds, delivery SLA, vendor validity, and agreement status.
5. **ACID Transactional Safety & Write-Back Guardrails:**
   Uses atomic SQLite transactions with automatic rollback on failure and duplicate execution guards to prevent double-ordering.
6. **Complete Auditability & Explainable Decisions:**
   Every calculation, scoring weight, negotiation turn, and validation check produces structured logs, creating a transparent audit trail for pharmacy management.

---

## 19. Why Pharma Nexus?
Pharmacy procurement is one of the highest-stakes supply chain environments:
* **Medicines Have Hard Expiry Dates:** Sourcing too much inventory causes spoilage and hazardous waste; sourcing too little leads to deadly stockouts.
* **Strict Minimum Order Quantities (MOQs):** Wholesalers enforce rigid minimum lot sizes that must be balanced against expiry limits.
* **Delivery Speed Directly Impacts Health:** Slower shipping during stockouts can halt patient treatments.
* **Bargaining Drives Profit Margins:** High-volume repeat orders yield substantial savings when systematic bargaining is applied across multiple drug lines.
* **Zero Tolerance for Data Inconsistency:** Partial database writes can cause inventory count discrepancies, regulatory penalties, and erroneous reorders.

---

## 20. Traditional ERP vs. Pharma Nexus

| Dimension | Traditional Pharmacy ERP | Pharma Nexus V2 Autonomous Agent |
| :--- | :--- | :--- |
| **Inventory Monitoring** | Passive tables; alerts require human review | Active, continuous observation and demand calculation |
| **Supplier Comparison** | Manual phone calls or email quote sheets | Automated discovery with multi-factor scoring (Price, SLA, MOQ) |
| **Vendor Selection** | Subjective, prone to individual bias | Objective, explainable normalized scoring algorithm |
| **Price Negotiation** | Manual, inconsistent, or skipped | Multi-round adaptive bargaining with ZOPA enforcement |
| **Expiry & MOQ Feasibility**| Manually calculated in spreadsheets | Deterministic mathematical constraint enforcement |
| **PO Creation** | Manual data entry (risk of transcription errors) | Automated PO generation using final negotiated terms |
| **Database Synchronization**| Disconnected, multi-step manual updates | Atomic SQLite transaction (PO Insert + Stock Increment) |
| **Audit Trail** | Fragmented paper and email trails | Structured step-by-step logs and negotiation history |

---

## 21. Why This Is Not Just a Chatbot

```
┌─────────────────────────────────────────────────────────────┐
│                 Generic AI Chatbot                          │
│   User Prompt ───► LLM Text Generation ───► Chat Message    │
│   (No tools, no state, no database write, hallucination risk)│
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                 Pharma Nexus Agent                          │
│                                                             │
│   1. OBSERVE live database state                            │
│   2. REASON on inventory deficit & expiry shelf-life        │
│   3. CALL deterministic calculation tools                   │
│   4. GATHER and score supplier quotes                       │
│   5. EXECUTE multi-round adaptive bargaining                │
│   6. PASS deal through independent 7-constraint validator   │
│   7. COMMIT atomic database transaction & update ERP state  │
└─────────────────────────────────────────────────────────────┘
```

Pharma Nexus is a stateful, action-oriented system integrated directly into an operational ERP environment.

---

## 22. Business Value & ROI
* **Direct Financial Savings:** $186.60 saved across just 3 test medicines (7.5% average unit cost reduction). Scaled to a catalog of 2,000 SKUs, annual procurement savings exceed tens of thousands of dollars.
* **Labor Reduction:** Eliminates 80%+ of manual vendor catalog comparison, quote calculation, and PO drafting work.
* **Spoilage Prevention:** Hard expiry checks ensure no order quantity exceeds the volume sellable before batch expiration.
* **Elimination of Data Entry Errors:** Automatic PO generation and atomic ERP write-back eliminate discrepancies between negotiated deals and database records.

---

## 23. Current System Limitations
1. **Curated Demo Dataset:** Baseline seed data is configured for 3 core representative medicines and 3 vendor profiles to enable deterministic testing.
2. **Simulated Vendor API Responses:** Vendor responses follow deterministic economic concession profiles rather than live external REST APIs.
3. **Fixed Negotiation Horizon:** Bargaining protocol is constrained to a 2-round structure to guarantee rapid convergence.
4. **Local SQLite Persistence:** Uses single-file SQLite database suitable for single-store retail environments rather than distributed PostgreSQL/Oracle clusters.

---

## 24. Future Scope (Not Currently Implemented)
* **Real-World Vendor Integrations:** Integration with live EDI (Electronic Data Interchange) and vendor B2B REST endpoints.
* **Predictive Demand Forecasting:** Machine learning models (ARIMA, Prophet, LSTM) incorporating seasonal illness trends and weather patterns.
* **Multi-Store Warehouse Rebalancing:** Autonomous inventory transfers between regional pharmacy branches prior to external procurement.
* **Supplier Reliability Scoring:** Dynamic vendor ratings based on historical on-time delivery rates and damage-in-transit reports.
* **Enterprise Auth & Approvals:** Multi-tier role-based access control (RBAC) with supervisor threshold approvals for high-value purchase orders.

---

## 25. Final 3–5 Minute Demonstration Flow

```
[1. Problem Demo]      Navigate to /inventory: Show Paracetamol (40 stock < 50 reorder).
                              │
                              ▼
[2. Agent Trigger]     Navigate to /agent: Click "Run Procurement Agent".
                              │
                              ▼
[3. Live Reasoning]    Observe Agent Logs: Calculate need (100u) -> Expiry check -> Score quotes.
                              │
                              ▼
[4. Vendor Selection]  Highlight Vendor B selection (Score: 65.5, MOQ: 250, Delivery: 2d).
                              │
                              ▼
[5. Bargaining Audit]  Navigate to /negotiation: Show Round 1 offer ($7.65) -> Vendor counter ($8.07) -> Round 2 counter ($7.86) -> Vendor ACCEPT.
                              │
                              ▼
[6. Validation Gate]   Review Validation Checklist: All 7 green checkmarks verified.
                              │
                              ▼
[7. ERP Execution]     Click "Execute Procurement" -> Atomic Transaction commits.
                              │
                              ▼
[8. Verified PO & ERP] Navigate to /purchase-orders (PO-#0001 created) and /inventory (Stock updated from 40 to 290).
```

---

## 26. Judge Q&A Reference Guide

#### Q1: Why is this an agent and not a script?
**A:** A script executes fixed linear code. Pharma Nexus maintains a typed `AgentState`, observes dynamic database state, reasons about multi-constraint trade-offs, plans actions, adapts proposal pricing based on counter-party responses across multiple rounds, and validates decisions through guardrails before execution.

#### Q2: Where is AI used versus deterministic rules?
**A:** Agent reasoning, goal formulation, and adaptive bargaining strategy handle high-level decision flows, while deterministic tools execute mathematical formulas (coverage calculations, MOQ flooring, deal scoring, SQLite transactions) to guarantee zero hallucinations in financial and inventory records.

#### Q3: How is the negotiation adaptive?
**A:** In Round 1, the agent proposes an aggressive target discount (10%). If the vendor counters, the agent observes the vendor's counter in context of its reservation ceiling and dynamically computes a midpoint concession in Round 2.

#### Q4: How are MOQs and expiry dates balanced?
**A:** The vendor tool adjusts order volume to $\max(\text{required\_qty}, \text{MOQ})$. The deal scoring engine calculates the medicine's expiry-safe capacity ($\text{daily\_sales} \times \text{expiry\_days\_left}$) and flags any vendor quote exceeding that limit as infeasible (Score = 0).

#### Q5: How are hallucinations and erroneous writes prevented?
**A:** Through an independent 7-constraint validator firewall (`validator.py`). Even if an agent attempted to submit an invalid price or quantity, the validator rejects the deal and blocks database execution.

#### Q6: What happens if a database write fails midway?
**A:** All database write operations are wrapped in an atomic SQLite transaction. If PO insertion or inventory update fails, the entire transaction is rolled back, leaving zero orphaned records.

#### Q7: Why are all 82 tests passing?
**A:** The test suite covers all unit modules, edge cases, validator rules, transaction rollbacks, API routes, and full Hero scenario audits with 100% reproducibility.

---

## 27. Final Summary
Pharma Nexus V2 demonstrates how autonomous AI agents can transform enterprise supply chains by combining **intelligent goal-directed reasoning**, **adaptive economic bargaining**, and **hardened deterministic safety guardrails** to deliver verified financial savings and automated operational accuracy.

$$\boxed{\textbf{AI Reasoning} + \textbf{Adaptive Bargaining} + \textbf{Deterministic Guardrails} + \textbf{Atomic ERP Execution}}$$
