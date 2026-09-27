# Pharma Nexus V2 💊🤖
### CITTA RISE — Problem 7: Smart Vendor Restocking & Bargaining Agent

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3.1-61DAFB.svg?logo=react&logoColor=black)](https://reactjs.org/)
[![Vite](https://img.shields.io/badge/Vite-5.4.2-646CFF.svg?logo=vite&logoColor=white)](https://vitejs.dev/)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57.svg?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![pytest](https://img.shields.io/badge/pytest-82%20passed-brightgreen.svg?logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://python.org)

> **Pharma Nexus V2** is an end-to-end autonomous procurement agent that observes live pharmacy inventory, evaluates replenishment demand against shelf-life expiry, discovers vendor offerings, negotiates volume discounts via multi-round adaptive bargaining, validates deal constraints, and atomically commits purchase orders back to the ERP.

---

## 📌 Table of Contents
1. [Problem Statement](#-problem-statement)
2. [Solution & Autonomous Agent Loop](#-solution--autonomous-agent-loop)
3. [Architecture & Separation of Concerns](#-architecture--separation-of-concerns)
4. [Technology Stack](#-technology-stack)
5. [Quick Start & Setup](#-quick-start--setup)
6. [Hero Scenarios & Audited Results](#-hero-scenarios--audited-results)
7. [Core Decision & Validation Engine](#-core-decision--validation-engine)
8. [Testing & Quality Assurance](#-testing--quality-assurance)
9. [Traditional ERP vs. Pharma Nexus](#-traditional-erp-vs-pharma-nexus)
10. [Repository Structure](#-repository-structure)
11. [Limitations & Future Scope](#-limitations--future-scope)

---

## 🚨 Problem Statement
Hospital and retail pharmacies face severe operational challenges:
* **Critical Stockouts vs. Medicine Spoilage:** Inventory frequently drops below safety points. Stockouts cause missed prescriptions, while over-ordering leads to expired, hazardous medication.
* **Manual Vendor Comparison:** Sourcing managers manually compare disparate vendor catalogs with varying base prices, delivery SLAs, and Minimum Order Quantities (MOQs).
* **Multi-Constraint Optimization:** Every purchase order must simultaneously balance demand coverage, vendor MOQs, shelf-life capacity, delivery lead time, and unit pricing.
* **Manual Negotiation & Disconnected ERP Writes:** Price bargaining is typically conducted offline without reservation bounds, and manual ERP data entry introduces human error and delays.

---

## 💡 Solution & Autonomous Agent Loop
Pharma Nexus replaces manual workflows with a closed-loop **autonomous agent lifecycle**:

$$\text{OBSERVE} \longrightarrow \text{REASON} \longrightarrow \text{PLAN} \longrightarrow \text{ACT} \longrightarrow \text{OBSERVE RESULT} \longrightarrow \text{ADAPT} \longrightarrow \text{VERIFY} \longrightarrow \text{COMPLETE}$$

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

### Agent Lifecycle Stages:
1. **OBSERVE:** Scans live SQLite inventory to detect stock falling below reorder thresholds.
2. **REASON:** Calculates net replenishment units ($\text{daily\_sales} \times (\text{lead\_time} + \text{safety\_days}) - \text{current\_stock}$) and verifies shelf-life capacity.
3. **PLAN:** Queries vendor catalogues, enforces MOQ rules, and ranks candidates using normalized multi-factor scoring (Price 45%, Delivery 35%, MOQ 20%).
4. **ACT:** Proposes an aggressive opening target price (10% discount) to the top-ranked vendor.
5. **OBSERVE RESULT:** Receives vendor response (`ACCEPT`, `COUNTER`, or `REJECT`).
6. **ADAPT:** Adapts in Round 2 to vendor counters by calculating a dynamic midpoint concession within buyer reservation ceilings.
7. **VERIFY:** Passes the agreed deal through an independent 7-constraint validator firewall.
8. **COMPLETE:** Executes an atomic database transaction to insert the PO and increment ERP stock.

---

## 🏗️ Architecture & Separation of Concerns

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
│   - Typed AgentState Management                             │
│   - Autonomous Observe-Reason-Act Lifecycle                 │
│   - Adaptive Multi-Round Bargaining Protocol                │
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

* **Agent Reasoning Layer:** Handles goal-directed decision making, trade-off evaluation, and bargaining strategy.
* **Deterministic Tool Layer:** Enforces strict mathematical formulas (coverage calculations, MOQ flooring, deal scoring, SQLite transactions).
* **Validation Firewall:** Ensures no PO can ever be created without satisfying 100% of business constraints.

---

## 🛠️ Technology Stack
* **Backend:** Python 3.11+, FastAPI, Pydantic v2, Uvicorn
* **Database:** SQLite3 (WAL mode, Foreign Key constraints, Atomic Transactions)
* **Frontend:** React 18, Vite 5, Lucide React Icons, Vanilla CSS Glassmorphic Design System
* **Testing:** pytest 9.1+, FastAPI TestClient, httpx (82 automated tests)

---

## 🚀 Quick Start (Copy & Paste Run Commands)

### Terminal 1: Backend
```powershell
cd pharma-procurement-agent
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```
* **API:** `http://localhost:8000` | **Docs:** `http://localhost:8000/docs`

### Terminal 2: Frontend
```powershell
cd pharma-procurement-agent\frontend
npm install
npm run dev
```
* **UI:** `http://localhost:5173`

---

## 📊 Hero Scenarios & Audited Results
All three medicines in the baseline catalog have stock below reorder thresholds:

| Metric | Hero 1: Paracetamol | Hero 2: Cetirizine | Hero 3: Azithromycin |
| :--- | :---: | :---: | :---: |
| **Medicine ID** | `1` | `2` | `3` |
| **Initial Stock / Reorder Point** | 40 / 50 | 25 / 30 | 15 / 20 |
| **Daily Sales / Lead Time** | 20 / 5 days | 10 / 3 days | 5 / 4 days |
| **Net Required Quantity** | **100 units** | **25 units** | **15 units** |
| **Selected Vendor** | **Vendor B (ID: 2)** | **Vendor B (ID: 2)** | **Vendor B (ID: 2)** |
| **Base Price / Vendor MOQ** | $8.50 / 250 units | $2.20 / 30 units | $14.50 / 20 units |
| **Bargaining Sequence** | $7.65 $\rightarrow$ $8.07 $\rightarrow$ **$7.86 (ACCEPT)** | $1.98 $\rightarrow$ $2.09 $\rightarrow$ **$2.04 (ACCEPT)** | $13.05 $\rightarrow$ $13.78 $\rightarrow$ **$13.41 (ACCEPT)** |
| **Final Unit Price** | **$7.86** | **$2.04** | **$13.41** |
| **Final Quantity** | **250 units** *(MOQ adjusted)* | **30 units** *(MOQ adjusted)* | **20 units** *(MOQ adjusted)* |
| **Total Committed Cost** | **$1,965.00** | **$61.20** | **$268.20** |
| **Procurement Savings** | **$160.00 (7.53%)** | **$4.80 (7.27%)** | **$21.80 (7.52%)** |
| **Deal Validation** | **PASS (100%)** | **PASS (100%)** | **PASS (100%)** |
| **Decision & Generated PO** | `ACCEPT` (`PO-#0001`) | `ACCEPT` (`PO-#0002`) | `ACCEPT` (`PO-#0003`) |
| **ERP Stock Update** | **40 $\rightarrow$ 290** | **25 $\rightarrow$ 55** | **15 $\rightarrow$ 35** |

*Total Procurement Spend: **$2,294.40** | Total Direct Negotiated Savings: **$186.60** (Average Discount: **7.5%**).*

---

## 🛡️ Core Decision & Validation Engine

### 7-Constraint Validation Checklist
Before executing any write-back, `backend/tools/validator.py` independently verifies:
1. `required_qty`: Negotiated quantity meets or exceeds replenishment demand ($\text{qty} \ge \text{required\_qty}$).
2. `moq`: Negotiated quantity satisfies vendor MOQ ($\text{qty} \ge \text{MOQ}$).
3. `expiry`: Quantity does not exceed safe shelf-life capacity ($\text{qty} \le \text{daily\_sales} \times \text{expiry\_days\_left}$).
4. `price`: Unit price is within buyer reservation ceiling and above vendor floor.
5. `delivery`: Delivery SLA meets acceptable timeline.
6. `vendor`: Vendor is registered and matches selected candidate.
7. `negotiation_status`: Status is explicitly `ACCEPTED`.

### ACID Transaction & Rollback Safety
```sql
BEGIN TRANSACTION;
  SELECT current_stock FROM inventory WHERE med_id = ?;
  INSERT INTO purchase_orders (...) VALUES (...);
  UPDATE inventory SET current_stock = current_stock + ? WHERE med_id = ?;
COMMIT;
```
*Any failure during insertion or updating triggers an automatic **`ROLLBACK`**, guaranteeing 0 orphan POs and 0 corrupted inventory records.*

---

## 🧪 Testing & Quality Assurance
The codebase is validated by **82 automated tests** covering all layers:

```
collected 82 items

tests/test_agent.py .....................                                [ 25%]
tests/test_inventory.py .........                                        [ 36%]
tests/test_phase8_hero_validation.py ............                        [ 51%]
tests/test_purchase_order.py ...............                             [ 69%]
tests/test_validator.py ..............                                   [ 86%]
tests/test_vendor.py ...........                                         [100%]

======================== 82 passed, 1 warning in 2.90s ========================
```

* **`test_agent.py` (21 tests):** Agent state machine, lifecycle transitions, bargaining loop.
* **`test_inventory.py` (9 tests):** Inventory observation, demand formulas, expiry constraints.
* **`test_phase8_hero_validation.py` (12 tests):** End-to-end Hero audits, ZOPA bounds, decision branches, duplicate execution safety, rollback verification.
* **`test_purchase_order.py` (15 tests):** Atomic PO transactions, inventory write-back.
* **`test_validator.py` (14 tests):** 7-constraint validator edge cases and savings math.
* **`test_vendor.py` (11 tests):** Vendor quote querying, MOQ flooring, normalized multi-factor scoring.

---

## ⚖️ Traditional ERP vs. Pharma Nexus

| Dimension | Traditional Pharmacy ERP | Pharma Nexus V2 Autonomous Agent |
| :--- | :--- | :--- |
| **Inventory Monitoring** | Passive tables requiring human review | Active, continuous observation & need calculation |
| **Supplier Comparison** | Manual quote comparisons | Automated normalized scoring (Price 45%, SLA 35%, MOQ 20%) |
| **Price Negotiation** | Manual or skipped | Adaptive 2-round bargaining with dynamic midpoint adaptation |
| **Expiry & MOQ Safety** | Manual spreadsheet checks | Hardened deterministic mathematical constraints |
| **PO Execution** | Manual data entry (risk of errors) | Automated PO creation using agreed negotiated terms |
| **Database Updates** | Disconnected, multi-step manual updates | Atomic SQLite transaction with instant stock synchronization |

---

## 📂 Repository Structure
```
pharma-procurement-agent/
├── backend/
│   ├── agent/
│   │   └── store_agent.py          # Store Procurement Agent controller & AgentState
│   ├── database/
│   │   ├── db.py                   # SQLite connection, schemas & initialization
│   │   └── seed.py                 # Deterministic baseline seed data
│   ├── tools/
│   │   ├── inventory_tools.py      # Stock observation, need & expiry formulas
│   │   ├── vendor_tools.py         # Vendor quote querying & MOQ rules
│   │   ├── deal_scoring.py         # Multi-factor quote scoring engine
│   │   ├── negotiation_tools.py    # Adaptive bargaining engine & vendor simulation
│   │   ├── validator.py            # Independent 7-constraint deal validator
│   │   └── purchase_order_tools.py # Atomic PO transactions & ERP write-back
│   ├── main.py                     # FastAPI application & REST endpoints
│   └── requirements.txt            # Python dependencies
├── data/
│   └── pharmacy.db                 # SQLite database file
├── frontend/
│   ├── src/
│   │   ├── components/Navbar.jsx   # Top navigation header
│   │   ├── pages/
│   │   │   ├── Inventory.jsx       # Medicine stock & reorder monitor
│   │   │   ├── Vendors.jsx         # Vendor catalogue & offerings
│   │   │   ├── AgentControl.jsx    # Autonomous agent control center & logs
│   │   │   ├── Negotiation.jsx     # Live bargaining dialogue & analytics
│   │   │   └── PurchaseOrders.jsx  # Executed PO ledger & ERP records
│   │   ├── App.jsx                 # Main application shell
│   │   └── index.css               # Glassmorphic CSS design system
│   ├── package.json                # Frontend dependencies & scripts
│   └── vite.config.js              # Vite configuration
├── tests/
│   ├── test_agent.py               # Agent state machine & lifecycle tests
│   ├── test_inventory.py           # Inventory tool tests
│   ├── test_phase8_hero_validation.py # Complete Hero scenario audit tests
│   ├── test_purchase_order.py      # Transaction & write-back tests
│   ├── test_validator.py           # 7-constraint validator tests
│   └── test_vendor.py              # Vendor quote & scoring tests
├── PHARMA_NEXUS_FINAL_DOCUMENTATION.md # Detailed specification & architecture doc
└── README.md                       # Main project README
```

---

## 🔮 Limitations & Future Scope

### Current Limitations:
* **Demo Dataset:** Seeded for 3 core representative medicines and 3 vendor profiles.
* **Simulated Vendor APIs:** Vendors follow deterministic economic concession profiles.
* **Fixed 2-Round Bargaining:** Constrained to a 2-round negotiation protocol for fast convergence.
* **Local Persistence:** Single-file SQLite database tailored for single-store retail environments.

### Future Scope (Production Extensions):
* Live EDI and B2B REST vendor integrations.
* Machine learning predictive demand forecasting (seasonal trends, epidemic spikes).
* Multi-store warehouse rebalancing before external procurement.
* Role-based access control (RBAC) and high-value purchase order manager approvals.

---

## 📄 License & Credits
Developed for **CITTA RISE — Problem 7 (Smart Vendor Restocking & Bargaining Agent)**.  
Built with FastAPI, React, Vite, SQLite, and Python.
