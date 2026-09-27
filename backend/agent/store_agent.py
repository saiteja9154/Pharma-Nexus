"""
StoreAgent: Central Controller for Store Procurement (Phase 4 Adaptive Negotiation).
Implements the autonomous Observe -> Reason -> Plan -> Act -> Update -> Negotiate loop
for pharmacy inventory evaluation, reorder detection, demand calculation, expiry validation,
deterministic vendor quote aggregation, multi-factor vendor selection, and adaptive bargaining.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from tools.inventory_tools import (
        get_inventory,
        calculate_need,
        check_expiry,
        DEFAULT_SAFETY_DAYS,
    )
    from tools.vendor_tools import get_vendor_quotes
    from tools.deal_scoring import score_quotes
    from tools.negotiation_tools import (
        MAX_NEGOTIATION_ROUNDS,
        calculate_target_price,
        calculate_reservation_price,
        get_vendor_floor_price,
        vendor_respond,
        generate_agent_negotiation_action,
    )
    from tools.validator import (
        validate_negotiation_action,
        validate_deal,
        calculate_deal_savings,
    )
    from tools.purchase_order_tools import create_purchase_order_transaction
except ImportError:
    from backend.tools.inventory_tools import (
        get_inventory,
        calculate_need,
        check_expiry,
        DEFAULT_SAFETY_DAYS,
    )
    from backend.tools.vendor_tools import get_vendor_quotes
    from backend.tools.deal_scoring import score_quotes
    from backend.tools.negotiation_tools import (
        MAX_NEGOTIATION_ROUNDS,
        calculate_target_price,
        calculate_reservation_price,
        get_vendor_floor_price,
        vendor_respond,
        generate_agent_negotiation_action,
    )
    from backend.tools.validator import (
        validate_negotiation_action,
        validate_deal,
        calculate_deal_savings,
    )
    from backend.tools.purchase_order_tools import create_purchase_order_transaction



class AgentActionType(str, Enum):
    """
    Structured action representation for Agent decision cycles.
    Includes Phase 2, 3, 4 & 5 active actions and Phase 6+ planned action placeholders.
    """
    # Active Actions
    OBSERVE_INVENTORY = "OBSERVE_INVENTORY"
    CALCULATE_NEED = "CALCULATE_NEED"
    CHECK_EXPIRY = "CHECK_EXPIRY"
    GET_QUOTES = "GET_QUOTES"
    SELECT_VENDOR = "SELECT_VENDOR"
    NEGOTIATE = "NEGOTIATE"
    OFFER = "OFFER"
    COUNTER = "COUNTER"
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    SWITCH_VENDOR = "SWITCH_VENDOR"
    VALIDATE_DEAL = "VALIDATE_DEAL"
    NO_ORDER = "NO_ORDER"

    # Phase 6+ Action Placeholders (Defined for clean architectural expansion)
    CREATE_PO = "CREATE_PO"


@dataclass
class AgentAction:
    """Structured representation of an individual action executed or planned by StoreAgent."""
    action: str
    medicine_id: Optional[int] = None
    reason: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentState:
    """
    Typed Agent State Model representing the procurement lifecycle for a specific medicine.
    Maintains clean state across observe, reason, tool calls, quote evaluation, vendor selection,
    multi-round adaptive bargaining, and independent multi-constraint deal validation.
    """
    medicine: Dict[str, Any] = field(default_factory=dict)
    inventory: Dict[str, Any] = field(default_factory=dict)
    required_qty: int = 0
    constraints: Dict[str, Any] = field(default_factory=dict)
    vendor_quotes: List[Any] = field(default_factory=list)
    selected_vendor: Optional[Any] = None
    negotiation: Dict[str, Any] = field(default_factory=dict)
    negotiation_history: List[Any] = field(default_factory=list)
    best_offer: Optional[Any] = None
    validation_result: Optional[Dict[str, Any]] = None
    savings: Optional[Dict[str, Any]] = None
    decision: Optional[str] = None
    decision_reason: Optional[str] = None
    po: Optional[Any] = None
    execution_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StoreAgent:
    """
    Store Procurement Agent controller.
    
    Architecture:
      StoreAgent -> AgentState -> Deterministic Tools -> Action Validator -> Vendor Simulation -> State Update -> Decision Summary
    """

    def __init__(
        self,
        db_path: Optional[Path | str] = None,
        safety_days: int = DEFAULT_SAFETY_DAYS
    ):
        self.db_path = db_path
        self.safety_days = safety_days
        self.states: Dict[int, AgentState] = {}
        self.actions_history: List[AgentAction] = []
        self.logs: List[Dict[str, Any]] = []

    def log(self, step: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Record structured logs for agent execution."""
        entry: Dict[str, Any] = {
            "step": step,
            "message": message,
        }
        if details:
            entry["details"] = details
        self.logs.append(entry)

    def record_action(self, action: AgentAction) -> None:
        """Track executed action in history."""
        self.actions_history.append(action)

    def negotiate_with_vendor(self, state: AgentState) -> AgentState:
        """
        Execute Phase 4 multi-round adaptive negotiation loop with the selected vendor.
        
        Flow:
          1. Calculate Target Price (10% discount) & Reservation Price ceiling.
          2. Round 1: Propose initial aggressive target offer.
          3. Observe deterministic vendor response.
          4. Round 2: Adapt proposal based on vendor counter / reservation bounds.
          5. Conclude with ACCEPTED / REJECTED status and record Best Offer & History.
        """
        if not state.selected_vendor:
            return state

        vendor = state.selected_vendor
        vendor_id = vendor["vendor_id"]
        vendor_name = vendor["vendor_name"]
        med_id = state.medicine["med_id"]
        med_name = state.medicine["name"]
        quantity = vendor["offered_qty"]
        base_price = vendor["base_price"]
        delivery_days = vendor["delivery_days"]

        # 1. Target & Reservation Price Calculations
        target_price = calculate_target_price(base_price)
        reservation_price = calculate_reservation_price(base_price)

        state.negotiation = {
            "status": "ACTIVE",
            "vendor_id": vendor_id,
            "vendor_name": vendor_name,
            "round": 0,
            "max_rounds": MAX_NEGOTIATION_ROUNDS,
            "initial_price": base_price,
            "target_price": target_price,
            "reservation_price": reservation_price,
            "current_offer": None,
            "vendor_response": None,
            "best_offer": None,
            "final_status": "ACTIVE",
            "history": [],
        }
        state.negotiation_history = []

        self.log(
            "NEGOTIATE",
            f"Initiating adaptive negotiation with {vendor_name} for {med_name} "
            f"(Initial: ${base_price:.2f}, Target: ${target_price:.2f}, Ceiling: ${reservation_price:.2f})."
        )

        last_vendor_resp = None

        for round_num in range(1, MAX_NEGOTIATION_ROUNDS + 1):
            state.negotiation["round"] = round_num

            # 2. Agent Proposal Generation
            ctx = {
                "round": round_num,
                "vendor_id": vendor_id,
                "med_name": med_name,
                "quantity": quantity,
                "required_qty": state.required_qty,
                "moq": vendor.get("moq"),
                "expiry_safe_qty": state.constraints.get("expiry", {}).get("expiry_safe_qty"),
                "target_price": target_price,
                "reservation_price": reservation_price,
                "last_vendor_response": last_vendor_resp,
                "max_rounds": MAX_NEGOTIATION_ROUNDS,
            }
            proposal = generate_agent_negotiation_action(ctx)

            # 3. Action Validation
            is_valid, validation_err = validate_negotiation_action(proposal, ctx)
            if not is_valid:
                self.log("ERROR", f"Agent proposal failed validation in round {round_num}: {validation_err}")
                state.negotiation["status"] = "VALIDATION_FAILED"
                state.negotiation["final_status"] = "REJECTED"
                state.decision = "VALIDATION_FAILED"
                break

            # Record Agent Turn
            agent_action_obj = AgentAction(
                action=proposal["action"],
                medicine_id=med_id,
                reason=proposal.get("reason"),
                params=proposal,
            )
            self.record_action(agent_action_obj)

            agent_turn = {
                "round": round_num,
                "speaker": "STORE_AGENT",
                "action": proposal["action"],
                "price": proposal["price"],
                "quantity": quantity,
                "message": proposal["message"],
                "reason": proposal.get("reason"),
            }
            state.negotiation_history.append(agent_turn)
            state.negotiation["history"].append(agent_turn)
            state.negotiation["current_offer"] = proposal["price"]

            if proposal["action"] == "OFFER":
                self.log(
                    "OFFER",
                    f"Round {round_num}: StoreAgent offered ${proposal['price']:.2f}/unit for {quantity} units to {vendor_name}."
                )
            elif proposal["action"] == "COUNTER":
                self.log(
                    "ADAPT",
                    f"Round {round_num}: StoreAgent adapted and countered with ${proposal['price']:.2f}/unit to {vendor_name}."
                )

            # 4. Vendor Response Execution
            v_resp = vendor_respond(
                vendor_id=vendor_id,
                offered_price=proposal["price"],
                quantity=quantity,
                base_price=base_price,
                round_num=round_num,
            )
            last_vendor_resp = v_resp

            vendor_turn = {
                "round": round_num,
                "speaker": "VENDOR",
                "action": v_resp["action"],
                "price": v_resp["price"],
                "quantity": quantity,
                "message": v_resp["message"],
            }
            state.negotiation_history.append(vendor_turn)
            state.negotiation["history"].append(vendor_turn)
            state.negotiation["vendor_response"] = v_resp["action"]

            self.log(
                "VENDOR_RESPONSE",
                f"Round {round_num}: {vendor_name} responded with {v_resp['action']} (${v_resp['price']:.2f}/unit)."
            )

            # 5. Evaluate State Outcomes
            if v_resp["action"] == "ACCEPT":
                agreed_price = v_resp["price"]
                total_cost = round(agreed_price * quantity, 2)
                initial_total = round(base_price * quantity, 2)
                savings = round(initial_total - total_cost, 2)
                discount_pct = round((savings / initial_total) * 100, 2) if initial_total > 0 else 0.0

                best_offer_dict = {
                    "vendor_id": vendor_id,
                    "vendor_name": vendor_name,
                    "quantity": quantity,
                    "unit_price": agreed_price,
                    "initial_price": base_price,
                    "delivery_days": delivery_days,
                    "total_cost": total_cost,
                    "savings": savings,
                    "discount_pct": discount_pct,
                    "status": "ACCEPTED",
                }
                state.best_offer = best_offer_dict
                state.negotiation["best_offer"] = best_offer_dict
                state.negotiation["status"] = "ACCEPTED"
                state.negotiation["final_status"] = "ACCEPTED"
                state.decision = "READY_FOR_VALIDATION"

                self.log(
                    "ACCEPT",
                    f"Negotiation successful with {vendor_name} for {med_name}. "
                    f"Agreed Price: ${agreed_price:.2f}/unit, Total: ${total_cost:.2f} (Savings: ${savings:.2f} / {discount_pct}%)."
                )
                break

            elif v_resp["action"] == "REJECT":
                state.negotiation["status"] = "REJECTED"
                state.negotiation["final_status"] = "REJECTED"
                state.best_offer = None
                state.decision = "NEGOTIATION_REJECTED"
                self.log("REJECT", f"Negotiation terminated. {vendor_name} rejected offer for {med_name}.")
                break

            elif v_resp["action"] == "COUNTER":
                # Vendor countered
                if round_num == MAX_NEGOTIATION_ROUNDS:
                    # Final round reached on Vendor Counter without acceptance
                    counter_price = v_resp["price"]
                    total_cost = round(counter_price * quantity, 2)
                    initial_total = round(base_price * quantity, 2)
                    savings = round(initial_total - total_cost, 2)
                    discount_pct = round((savings / initial_total) * 100, 2) if initial_total > 0 else 0.0

                    best_offer_dict = {
                        "vendor_id": vendor_id,
                        "vendor_name": vendor_name,
                        "quantity": quantity,
                        "unit_price": counter_price,
                        "initial_price": base_price,
                        "delivery_days": delivery_days,
                        "total_cost": total_cost,
                        "savings": savings,
                        "discount_pct": discount_pct,
                        "status": "UNACCEPTED_COUNTER",
                    }
                    state.best_offer = best_offer_dict
                    state.negotiation["best_offer"] = best_offer_dict
                    state.negotiation["status"] = "UNRESOLVED"
                    state.negotiation["final_status"] = "UNRESOLVED"
                    state.decision = "NEGOTIATION_UNRESOLVED"
                    self.log(
                        "UNRESOLVED",
                        f"Negotiation with {vendor_name} concluded after {MAX_NEGOTIATION_ROUNDS} rounds without agreement (Vendor counter: ${counter_price:.2f})."
                    )

        # Update decision reason with negotiation summary
        if state.negotiation.get("status") == "ACCEPTED" and state.best_offer:
            bo = state.best_offer
            state.decision_reason = (
                f"Selected {vendor_name} and negotiated unit price from ${base_price:.2f} to ${bo['unit_price']:.2f} "
                f"(Total: ${bo['total_cost']:.2f}, Savings: ${bo['savings']:.2f} / {bo['discount_pct']}%)."
            )
        elif state.negotiation.get("status") == "UNRESOLVED":
            state.decision_reason = (
                f"Selected {vendor_name} but negotiation remained unresolved after {MAX_NEGOTIATION_ROUNDS} rounds."
            )
        else:
            state.decision_reason = f"Selected {vendor_name} but negotiation failed ({state.negotiation.get('status', 'REJECTED')})."

        return state

    def validate_and_decide(self, state: AgentState) -> AgentState:
        """
        Phase 5 Deal Validation and Final Decision Engine.
        Independently verifies the negotiated deal against all 7 business constraints:
        required quantity, vendor MOQ, shelf-life expiry, reservation price ceiling,
        delivery SLA, vendor validity, and negotiation acceptance.
        
        Outcomes:
          - ACCEPT: All constraints pass. Deal confirmed and ready for PO creation.
          - SWITCH_VENDOR: Negotiated deal failed, but another candidate vendor is feasible.
          - REJECT: Negotiated deal failed and no feasible vendor alternative exists.
          - NO_ORDER: No viable procurement option.
        """
        med_id = state.medicine["med_id"]
        med_name = state.medicine["name"]

        # If no vendor was selected (e.g. no feasible quotes from Phase 3)
        if not state.selected_vendor:
            state.decision = "NO_ORDER"
            state.decision_reason = (
                f"No vendor satisfies the required quantity, MOQ, expiry, price, "
                f"and delivery constraints for {med_name}."
            )
            state.validation_result = {
                "valid": False,
                "checks": {
                    "required_qty": False,
                    "moq": False,
                    "expiry": False,
                    "price": False,
                    "delivery": False,
                    "vendor": False,
                    "negotiation_status": False,
                },
                "failed_checks": ["no_feasible_vendor"],
                "reason": "No feasible vendor quote available.",
            }
            state.savings = None
            self.log("NO_ORDER", f"FINAL DECISION: NO_ORDER for {med_name}.")
            return state

        # Compute vendor reservation floor price
        v_id = state.selected_vendor.get("vendor_id", 0)
        v_base = state.selected_vendor.get("base_price", 0.0)
        v_floor = get_vendor_floor_price(v_id, v_base) if v_base > 0 else None

        # Build validation context
        ctx = {
            "required_qty": state.required_qty,
            "moq": state.selected_vendor.get("moq"),
            "expiry_safe_qty": state.constraints.get("expiry", {}).get("expiry_safe_qty"),
            "reservation_price": state.negotiation.get("reservation_price"),
            "buyer_reservation_price": state.negotiation.get("reservation_price"),
            "vendor_floor_price": v_floor,
            "max_delivery_days": state.constraints.get("max_delivery_days"),
            "selected_vendor_id": state.selected_vendor.get("vendor_id"),
            "candidate_vendor_ids": [q["vendor_id"] for q in state.vendor_quotes],
            "negotiation_status": state.negotiation.get("status"),
        }

        # Step 1: Execute Independent Deal Validation Tool
        validation_res = validate_deal(state.best_offer, ctx)
        state.validation_result = validation_res

        validate_action = AgentAction(
            action=AgentActionType.VALIDATE_DEAL.value,
            medicine_id=med_id,
            reason="Independently validate negotiated deal against multi-constraint business rules.",
            params={"deal": state.best_offer, "context": ctx},
            result=validation_res,
        )
        self.record_action(validate_action)

        # Step 2: Formulate Decision based on Validation Result
        if validation_res["valid"]:
            # Calculate savings
            initial_price = state.best_offer.get("initial_price", state.selected_vendor.get("base_price", 0.0))
            negotiated_price = state.best_offer.get("unit_price", 0.0)
            quantity = state.best_offer.get("quantity", state.required_qty)

            savings_data = calculate_deal_savings(
                initial_price=initial_price,
                negotiated_price=negotiated_price,
                quantity=quantity,
            )
            state.savings = savings_data

            state.decision = "ACCEPT"
            state.decision_reason = (
                f"Deal accepted. All 7 procurement constraints satisfied. "
                f"Final commitment: ${savings_data['negotiated_total']:.2f} ({quantity} units @ ${negotiated_price:.2f}/u). "
                f"Total savings: ${savings_data['savings']:.2f} ({savings_data['savings_percent']}%). "
                f"Ready for PO creation."
            )
            self.log(
                "VALIDATE",
                f"Deal with {state.selected_vendor['vendor_name']} passed all 7 procurement constraints."
            )
            self.log(
                "DECISION",
                f"FINAL DECISION: ACCEPT for {med_name}. Savings: ${savings_data['savings']:.2f} ({savings_data['savings_percent']}%)."
            )
        else:
            state.savings = None
            failed_v_id = state.selected_vendor.get("vendor_id")
            failed_v_name = state.selected_vendor.get("vendor_name", "Selected Vendor")

            # Check for alternative feasible vendor in candidate quote set
            alt_feasible = [
                q for q in state.vendor_quotes
                if q.get("feasible") and q.get("vendor_id") != failed_v_id
            ]

            if alt_feasible:
                alt = alt_feasible[0]
                state.decision = "SWITCH_VENDOR"
                state.decision_reason = (
                    f"Negotiated deal with {failed_v_name} failed validation ({validation_res['reason']}). "
                    f"Alternative feasible vendor ({alt['vendor_name']}) available for switching."
                )
                switch_action = AgentAction(
                    action=AgentActionType.SWITCH_VENDOR.value,
                    medicine_id=med_id,
                    reason=f"Switch vendor from {failed_v_name} to {alt['vendor_name']}.",
                    params={"failed_vendor_id": failed_v_id, "alternative_vendor_id": alt["vendor_id"]},
                )
                self.record_action(switch_action)
                self.log(
                    "SWITCH_VENDOR",
                    f"Deal with {failed_v_name} failed validation. Recommending switch to alternative vendor {alt['vendor_name']}."
                )
            else:
                state.decision = "REJECT"
                state.decision_reason = (
                    f"Negotiated deal failed validation: {validation_res['reason']}. "
                    f"No alternative feasible vendors available."
                )
                self.log(
                    "REJECT",
                    f"FINAL DECISION: REJECT for {med_name}. Reason: {validation_res['reason']}."
                )

        return state

    def execute_procurement(self, state: AgentState) -> Dict[str, Any]:
        """
        Phase 6 ERP Write-Back Execution Engine.
        Enforces execution guard:
          1. state.decision == "ACCEPT"
          2. state.validation_result["valid"] is True
          3. Valid selected vendor & accepted best offer with quantity & price.
          4. Duplicate execution prevention (PO not already created).
        
        Executes atomic SQLite transaction:
          - Inserts Purchase Order record
          - Updates Inventory current_stock (stock_after = stock_before + quantity)
          
        Updates state.po, state.execution_result, and appends CREATE_PO action.
        """
        med_id = state.medicine.get("med_id")
        med_name = state.medicine.get("name", "Unknown Medicine")

        # Execution Guard 1: Decision must be ACCEPT
        if state.decision != "ACCEPT":
            err_msg = f"Cannot execute procurement for {med_name}: decision is '{state.decision}' (must be 'ACCEPT')."
            self.log("ERROR", err_msg)
            return {
                "success": False,
                "error": "INVALID_DECISION",
                "message": err_msg,
            }

        # Execution Guard 2: Validation must be valid
        if not state.validation_result or not state.validation_result.get("valid", False):
            val_reason = state.validation_result.get("reason", "Validation check failed") if state.validation_result else "No validation result"
            err_msg = f"Cannot execute procurement for {med_name}: deal validation failed ({val_reason})."
            self.log("ERROR", err_msg)
            return {
                "success": False,
                "error": "INVALID_VALIDATION",
                "message": err_msg,
            }

        # Execution Guard 3: Required deal information present
        if not state.selected_vendor or not state.best_offer:
            err_msg = f"Cannot execute procurement for {med_name}: missing selected vendor or agreed offer."
            self.log("ERROR", err_msg)
            return {
                "success": False,
                "error": "MISSING_DEAL_DATA",
                "message": err_msg,
            }

        if state.best_offer.get("status") != "ACCEPTED":
            err_msg = f"Cannot execute procurement for {med_name}: best offer status is '{state.best_offer.get('status')}' (must be 'ACCEPTED')."
            self.log("ERROR", err_msg)
            return {
                "success": False,
                "error": "UNACCEPTED_OFFER",
                "message": err_msg,
            }

        # Execution Guard 4: Duplicate execution prevention
        if state.po is not None and state.po.get("po_id"):
            err_msg = f"Procurement already executed for {med_name} (PO #{state.po.get('po_id')}). Duplicate execution prevented."
            self.log("WARNING", err_msg)
            return {
                "success": False,
                "error": "DUPLICATE_EXECUTION",
                "message": err_msg,
                "po": state.po,
                "execution_result": state.execution_result,
            }

        vendor = state.selected_vendor
        vendor_id = vendor["vendor_id"]
        vendor_name = vendor.get("vendor_name", f"Vendor {vendor_id}")
        quantity = int(state.best_offer["quantity"])
        unit_price = float(state.best_offer["unit_price"])
        total_cost = round(unit_price * quantity, 2)
        delivery_days = int(state.best_offer.get("delivery_days", vendor.get("delivery_days", 0)))

        # Step 5: Execute atomic database write-back
        try:
            tx_res = create_purchase_order_transaction(
                med_id=med_id,
                vendor_id=vendor_id,
                quantity=quantity,
                unit_price=unit_price,
                total_cost=total_cost,
                delivery_days=delivery_days,
                status="CREATED",
                db_path=self.db_path,
            )

            po_dict = {
                "po_id": tx_res["po_id"],
                "po_number": tx_res["po_number"],
                "med_id": med_id,
                "medicine_name": med_name,
                "vendor_id": vendor_id,
                "vendor_name": vendor_name,
                "quantity": quantity,
                "unit_price": unit_price,
                "total_cost": total_cost,
                "delivery_days": delivery_days,
                "status": "CREATED",
            }
            state.po = po_dict

            exec_dict = {
                "created": True,
                "po_id": tx_res["po_id"],
                "po_number": tx_res["po_number"],
                "inventory_before": tx_res["inventory_before"],
                "inventory_after": tx_res["inventory_after"],
            }
            state.execution_result = exec_dict

            # Update state inventory to reflect newly written back current_stock
            state.inventory["current_stock"] = tx_res["inventory_after"]

            # Record Agent Action
            po_action = AgentAction(
                action=AgentActionType.CREATE_PO.value,
                medicine_id=med_id,
                reason=f"Created PO {tx_res['po_number']} for {quantity} units of {med_name} with {vendor_name} @ ${unit_price:.2f}/u (${total_cost:.2f}). Inventory updated: {tx_res['inventory_before']} -> {tx_res['inventory_after']}.",
                params={
                    "po_id": tx_res["po_id"],
                    "po_number": tx_res["po_number"],
                    "med_id": med_id,
                    "vendor_id": vendor_id,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_cost": total_cost,
                    "delivery_days": delivery_days,
                },
                result=tx_res,
            )
            self.record_action(po_action)

            self.log(
                "CREATE_PO",
                f"Phase 6: Successfully created {tx_res['po_number']} for {med_name} "
                f"({quantity} units @ ${unit_price:.2f}/u = ${total_cost:.2f}) with {vendor_name}. "
                f"Inventory stock updated: {tx_res['inventory_before']} -> {tx_res['inventory_after']}.",
                details=tx_res,
            )

            return {
                "success": True,
                "po": po_dict,
                "execution_result": exec_dict,
                "inventory_before": tx_res["inventory_before"],
                "inventory_after": tx_res["inventory_after"],
                "savings": state.savings,
            }

        except Exception as e:
            err_msg = f"Database transaction failed during PO creation for {med_name}: {str(e)}"
            self.log("ERROR", err_msg)
            return {
                "success": False,
                "error": "TRANSACTION_FAILED",
                "message": err_msg,
            }

    def evaluate_medicine(self, item: Dict[str, Any]) -> AgentState:
        """
        Evaluate procurement necessity, retrieve candidate quotes, select optimal vendor,
        execute adaptive bargaining, and independently validate final deal terms.
        
        Flow:
          1. Initialize AgentState
          2. Reason: Check stock vs reorder point
          3. If stock < reorder point:
             - CALCULATE_NEED -> calculate required_qty
             - CHECK_EXPIRY -> check shelf-life capacity
             - GET_QUOTES -> query all candidate vendor offers
             - SELECT_VENDOR -> score offers & select optimal feasible supplier
             - NEGOTIATE -> execute adaptive multi-round negotiation
             - VALIDATE_DEAL -> execute Phase 5 multi-constraint deal validation
          4. If stock >= reorder point -> NO_PROCUREMENT
          5. Update AgentState with decision, validation_result, savings, and decision_reason
        """
        med_id = item["med_id"]
        med_name = item["name"]
        current_stock = item["current_stock"]
        reorder_point = item["reorder_point"]
        daily_sales = item["daily_sales"]
        lead_time_days = item["lead_time_days"]
        expiry_date = item["expiry_date"]

        # Step 1: Initialize AgentState
        state = AgentState(
            medicine={
                "med_id": med_id,
                "name": med_name,
            },
            inventory={
                "current_stock": current_stock,
                "reorder_point": reorder_point,
                "daily_sales": daily_sales,
                "lead_time_days": lead_time_days,
                "expiry_date": expiry_date,
            },
            required_qty=0,
            constraints={},
            vendor_quotes=[],
            selected_vendor=None,
            negotiation={},
            negotiation_history=[],
            best_offer=None,
            validation_result=None,
            savings=None,
            decision=None,
            decision_reason=None,
            po=None,
        )

        # Step 2: Observe and Reason on Stock Level
        if current_stock < reorder_point:
            # Step 3: Act - Calculate required quantity
            calc_action = AgentAction(
                action=AgentActionType.CALCULATE_NEED.value,
                medicine_id=med_id,
                reason=f"Current stock ({current_stock}) is below reorder point ({reorder_point}).",
                params={
                    "current_stock": current_stock,
                    "daily_sales": daily_sales,
                    "lead_time_days": lead_time_days,
                    "safety_days": self.safety_days,
                },
            )
            need_result = calculate_need(
                current_stock=current_stock,
                daily_sales=daily_sales,
                lead_time_days=lead_time_days,
                safety_days=self.safety_days,
            )
            calc_action.result = need_result
            self.record_action(calc_action)

            # Step 4: Act - Check expiry constraint
            exp_action = AgentAction(
                action=AgentActionType.CHECK_EXPIRY.value,
                medicine_id=med_id,
                reason="Check batch shelf life and maximum safe quantity before replenishment.",
                params={
                    "expiry_date": expiry_date,
                    "daily_sales": daily_sales,
                    "lead_time_days": lead_time_days,
                },
            )
            expiry_result = check_expiry(
                expiry_date_str=expiry_date,
                daily_sales=daily_sales,
                lead_time_days=lead_time_days,
            )
            exp_action.result = expiry_result
            self.record_action(exp_action)

            # Update State with quantity and constraints
            state.required_qty = need_result["required_qty"]
            state.constraints = {
                "safety_days": self.safety_days,
                "coverage_days": need_result["coverage_days"],
                "raw_need": need_result["raw_need"],
                "expiry": expiry_result,
            }

            self.log(
                "CALCULATE",
                f"{med_name} (ID: {med_id}) requires {state.required_qty} units. "
                f"[Stock: {current_stock}, Reorder Point: {reorder_point}, Coverage: {need_result['coverage_days']} days]"
            )
            self.log(
                "VERIFY",
                f"{med_name} expiry constraint checked: {expiry_result['expiry_days_left']} days remaining, "
                f"safe capacity {expiry_result['expiry_safe_qty']} units (Risk: {expiry_result['expiry_risk']})."
            )

            # Step 5: Act - GET_QUOTES from all vendors
            quotes_action = AgentAction(
                action=AgentActionType.GET_QUOTES.value,
                medicine_id=med_id,
                reason=f"Query vendor catalogue for {med_name} (required: {state.required_qty} units).",
                params={
                    "med_id": med_id,
                    "required_qty": state.required_qty,
                },
            )
            raw_quotes = get_vendor_quotes(
                med_id=med_id,
                required_qty=state.required_qty,
                db_path=self.db_path,
            )
            quotes_action.result = {"quotes_count": len(raw_quotes)}
            self.record_action(quotes_action)

            self.log(
                "GET_QUOTES",
                f"Retrieved {len(raw_quotes)} candidate vendor quotes for {med_name}."
            )

            # Step 6: Act - SELECT_VENDOR using Multi-Factor Deal Scoring
            expiry_safe_qty = expiry_result.get("expiry_safe_qty")
            scored_quotes = score_quotes(raw_quotes, expiry_safe_qty=expiry_safe_qty)
            state.vendor_quotes = scored_quotes

            for sq in scored_quotes:
                self.log(
                    "SCORE",
                    f"Vendor {sq['vendor_name']}: Score {sq['score']:.1f}/100 "
                    f"[Price: ${sq['base_price']:.2f}, Offered: {sq['offered_qty']} (MOQ: {sq['moq']}), "
                    f"Delivery: {sq['delivery_days']}d, Total: ${sq['total_cost']:.2f}] — {', '.join(sq['reasons'])}"
                )

            feasible_quotes = [q for q in scored_quotes if q["feasible"]]

            select_action = AgentAction(
                action=AgentActionType.SELECT_VENDOR.value,
                medicine_id=med_id,
                reason="Select highest-scoring feasible vendor using multi-factor trade-offs.",
                params={"feasible_count": len(feasible_quotes)},
            )

            if not feasible_quotes:
                state.selected_vendor = None
                state.decision = "NO_FEASIBLE_VENDOR"
                state.decision_reason = (
                    f"No feasible vendor found for {med_name}. All candidate offers violate constraints."
                )
                select_action.result = {"selected_vendor": None, "reason": "No feasible offer"}
                self.record_action(select_action)
                self.log("DECISION", f"{med_name}: No feasible vendor available.")

                # Validate No-Vendor State
                self.validate_and_decide(state)
            else:
                # Deterministic Tie-Breaker
                feasible_quotes.sort(
                    key=lambda q: (
                        -q["score"],
                        q["total_cost"],
                        q["delivery_days"],
                        q["moq"],
                        q["vendor_id"],
                    )
                )
                selected = feasible_quotes[0]
                state.selected_vendor = selected

                select_action.result = {
                    "selected_vendor_id": selected["vendor_id"],
                    "vendor_name": selected["vendor_name"],
                    "score": selected["score"],
                }
                self.record_action(select_action)

                self.log(
                    "SELECT_VENDOR",
                    f"Selected {selected['vendor_name']} for {med_name} "
                    f"(Score: {selected['score']:.1f}, Total: ${selected['total_cost']:.2f}, Delivery: {selected['delivery_days']}d)."
                )

                # Step 7: Phase 4 Adaptive Negotiation
                self.negotiate_with_vendor(state)

                # Step 8: Phase 5 Multi-Constraint Deal Validation and Decision
                self.validate_and_decide(state)

        else:
            # Stock is adequate
            exp_action = AgentAction(
                action=AgentActionType.CHECK_EXPIRY.value,
                medicine_id=med_id,
                reason="Check expiry on adequate stock.",
                params={"expiry_date": expiry_date, "daily_sales": daily_sales},
            )
            expiry_result = check_expiry(
                expiry_date_str=expiry_date,
                daily_sales=daily_sales,
                lead_time_days=lead_time_days,
            )
            exp_action.result = expiry_result
            self.record_action(exp_action)

            state.required_qty = 0
            state.constraints = {
                "safety_days": self.safety_days,
                "expiry": expiry_result,
            }
            state.vendor_quotes = []
            state.selected_vendor = None
            state.negotiation = {}
            state.negotiation_history = []
            state.best_offer = None
            state.validation_result = {
                "valid": True,
                "checks": {},
                "failed_checks": [],
                "reason": "Current stock is at or above reorder point. No procurement required.",
            }
            state.savings = None
            state.decision = "NO_PROCUREMENT"
            state.decision_reason = (
                f"Current stock ({current_stock}) is at or above reorder point ({reorder_point})."
            )

            self.log(
                "DECISION",
                f"{med_name} (ID: {med_id}) has adequate stock ({current_stock} >= {reorder_point}). No procurement needed."
            )

        self.states[med_id] = state
        return state

    def run(self, target_med_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute full Phase 5 StoreAgent cycle.
        
        Observe inventory -> Evaluate need -> Check expiry -> Gather vendor quotes ->
        Score offers -> Select optimal vendor -> Negotiate adaptive terms ->
        Independently validate deal -> Formulate final decision -> Maintain AgentState.
        """
        self.logs.clear()
        self.actions_history.clear()
        self.states.clear()

        # Step 1: OBSERVE Inventory
        self.log("OBSERVE", "Scanning pharmacy inventory from SQLite database...")
        observe_action = AgentAction(
            action=AgentActionType.OBSERVE_INVENTORY.value,
            reason="Read current inventory levels from database.",
        )
        inventory_items = get_inventory(self.db_path)
        observe_action.result = {"item_count": len(inventory_items)}
        self.record_action(observe_action)

        self.log(
            "OBSERVE",
            f"Inventory scanned. Found {len(inventory_items)} registered medicines in catalogue."
        )

        # Filter target medicine if specified
        if target_med_id is not None:
            inventory_items = [i for i in inventory_items if i["med_id"] == target_med_id]
            if not inventory_items:
                self.log("ERROR", f"Medicine with med_id={target_med_id} not found in inventory.")
                return {
                    "status": "error",
                    "message": f"Medicine med_id={target_med_id} not found.",
                    "medicines": [],
                    "logs": self.logs,
                }

        # Step 2: Evaluate Each Medicine, Select Vendors, Negotiate & Validate
        for item in inventory_items:
            self.evaluate_medicine(item)

        # Summary Metrics
        procurement_count = sum(
            1 for s in self.states.values() if s.required_qty > 0
        )
        selected_vendor_count = sum(
            1 for s in self.states.values() if s.selected_vendor is not None
        )
        negotiation_accepted_count = sum(
            1 for s in self.states.values() if s.negotiation.get("status") == "ACCEPTED"
        )
        deals_validated_count = sum(
            1 for s in self.states.values() if s.validation_result and s.validation_result.get("valid")
        )
        deals_accepted_count = sum(
            1 for s in self.states.values() if s.decision == "ACCEPT"
        )
        total_savings = sum(
            (s.savings.get("savings", 0.0) if s.savings else 0.0) for s in self.states.values()
        )

        self.log(
            "COMPLETE",
            f"Phase 5 evaluation, negotiation & validation completed. {procurement_count} items evaluated, "
            f"{deals_accepted_count} deals accepted (Total Savings: ${total_savings:.2f})."
        )

        # Build structured agent result
        return {
            "status": "completed",
            "medicines_evaluated": len(self.states),
            "procurement_needed_count": procurement_count,
            "selected_vendor_count": selected_vendor_count,
            "negotiation_accepted_count": negotiation_accepted_count,
            "deals_validated_count": deals_validated_count,
            "deals_accepted_count": deals_accepted_count,
            "total_savings": round(total_savings, 2),
            "medicines": [
                {
                    "med_id": state.medicine["med_id"],
                    "name": state.medicine["name"],
                    "current_stock": state.inventory["current_stock"],
                    "reorder_point": state.inventory["reorder_point"],
                    "daily_sales": state.inventory["daily_sales"],
                    "lead_time_days": state.inventory["lead_time_days"],
                    "required_qty": state.required_qty,
                    "procurement_needed": (state.required_qty > 0),
                    "decision": state.decision,
                    "decision_reason": state.decision_reason,
                    "vendor_quotes": state.vendor_quotes,
                    "selected_vendor": state.selected_vendor,
                    "negotiation": state.negotiation,
                    "negotiation_history": state.negotiation_history,
                    "best_offer": state.best_offer,
                    "validation_result": state.validation_result,
                    "savings": state.savings,
                    "po": state.po,
                    "execution_result": state.execution_result,
                    "expiry": state.constraints.get("expiry", {}),
                    "constraints": state.constraints,
                    "state": state.to_dict(),
                }
                for state in self.states.values()
            ],
            "actions": [a.to_dict() for a in self.actions_history],
            "logs": self.logs,
        }
