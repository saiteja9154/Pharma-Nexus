"""
Action and Deal Validator for Store Procurement Agent (Phase 4).
Ensures all structured agent actions, negotiation proposals, and deal parameters
undergo strict schema and business rule validation before execution.
"""

from typing import Dict, Any, Tuple, Optional

# Supported Phase 4 action types
VALID_ACTIONS = {
    "OBSERVE_INVENTORY",
    "CALCULATE_NEED",
    "CHECK_EXPIRY",
    "GET_QUOTES",
    "SELECT_VENDOR",
    "NEGOTIATE",
    "OFFER",
    "COUNTER",
    "ACCEPT",
    "REJECT",
    "SWITCH_VENDOR",
}


def validate_negotiation_action(
    action_data: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validate an agent negotiation proposal before sending to vendor.
    
    Checks:
      1. Schema: action type, price, quantity, vendor_id.
      2. Price: Must be positive (> 0).
      3. Quantity: Must be positive (> 0) and meet known requirements.
      4. Negotiation Limits: Round must not exceed max allowed rounds.
      5. Reservation Price: Buyer proposed price should not exceed reservation limit.
    """
    if not isinstance(action_data, dict):
        return False, "Action data must be a dictionary."

    action = action_data.get("action")
    if not action or action not in VALID_ACTIONS:
        return False, f"Unsupported or missing action type: '{action}'."

    # Validate price for offer/counter/accept
    if action in {"OFFER", "COUNTER", "ACCEPT"}:
        price = action_data.get("price")
        if price is None or not isinstance(price, (int, float)) or price <= 0:
            return False, f"Invalid proposal price: {price}. Price must be a positive number."

        # Business check: Reservation price constraint
        if context and "reservation_price" in context and context["reservation_price"] is not None:
            res_price = context["reservation_price"]
            # Allow tiny epsilon for float rounding
            if price > (res_price + 0.001):
                return False, f"Proposed price (${price:.2f}) exceeds buyer reservation price (${res_price:.2f})."

    # Validate quantity
    if action in {"OFFER", "COUNTER", "NEGOTIATE"}:
        qty = action_data.get("quantity")
        if qty is not None:
            if not isinstance(qty, int) or qty <= 0:
                return False, f"Invalid proposal quantity: {qty}. Quantity must be a positive integer."

            if context:
                # Business check: MOQ constraint
                moq = context.get("moq")
                if moq is not None and qty < moq:
                    return False, f"Proposed quantity ({qty}) violates vendor MOQ ({moq})."

                # Business check: Required quantity constraint
                req_qty = context.get("required_qty")
                if req_qty is not None and qty < req_qty:
                    return False, f"Proposed quantity ({qty}) is less than required quantity ({req_qty})."

                # Business check: Expiry safe capacity constraint
                expiry_safe_qty = context.get("expiry_safe_qty")
                if expiry_safe_qty is not None and qty > expiry_safe_qty:
                    return False, f"Proposed quantity ({qty}) exceeds expiry-safe capacity ({expiry_safe_qty})."

    # Validate vendor ID
    vendor_id = action_data.get("vendor_id")
    if context and "vendor_id" in context:
        expected_vendor = context["vendor_id"]
        if vendor_id is not None and vendor_id != expected_vendor:
            return False, f"Vendor ID mismatch: proposal has {vendor_id}, expected {expected_vendor}."

    # Validate round count
    round_num = action_data.get("round", 1)
    max_rounds = context.get("max_rounds", 2) if context else 2
    if round_num > max_rounds:
        return False, f"Negotiation round ({round_num}) exceeds maximum allowed rounds ({max_rounds})."

    return True, None


def calculate_deal_savings(
    initial_price: float,
    negotiated_price: float,
    quantity: int,
) -> Dict[str, Any]:
    """
    Deterministic calculation of procurement savings against initial baseline quote.
    """
    if quantity <= 0 or initial_price <= 0:
        return {
            "baseline_total": 0.0,
            "negotiated_total": 0.0,
            "savings": 0.0,
            "savings_percent": 0.0,
        }

    baseline_total = round(float(initial_price) * quantity, 2)
    negotiated_total = round(float(negotiated_price) * quantity, 2)
    savings = round(baseline_total - negotiated_total, 2)
    savings_percent = round((savings / baseline_total) * 100, 2) if baseline_total > 0 else 0.0

    return {
        "baseline_total": baseline_total,
        "negotiated_total": negotiated_total,
        "savings": savings,
        "savings_percent": savings_percent,
    }


def validate_deal(
    deal: Optional[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Phase 5 Independent Deal Validator.
    Performs comprehensive, multi-constraint verification of a negotiated deal.
    
    Checks:
      1. required_qty: negotiated_qty >= required_qty
      2. moq: negotiated_qty >= vendor_moq
      3. expiry: negotiated_qty <= expiry_safe_qty (daily_sales * expiry_days_left)
      4. price: unit_price > 0 and unit_price <= reservation_price ceiling
      5. delivery: delivery_days <= max_delivery_days (if configured)
      6. vendor: vendor is valid, selected, and present in candidate quotes
      7. negotiation_status: negotiation is explicitly ACCEPTED and agreed
    """
    ctx = context or {}
    checks: Dict[str, bool] = {
        "required_qty": False,
        "moq": False,
        "expiry": False,
        "price": False,
        "delivery": False,
        "vendor": False,
        "negotiation_status": False,
    }
    failed_checks = []
    failure_reasons = []

    if not deal or not isinstance(deal, dict):
        return {
            "valid": False,
            "checks": checks,
            "failed_checks": list(checks.keys()),
            "reason": "No valid negotiated deal provided for validation.",
        }

    qty = deal.get("quantity", 0)
    price = deal.get("unit_price", 0.0)
    vendor_id = deal.get("vendor_id")
    deal_status = deal.get("status", "UNACCEPTED")
    delivery_days = deal.get("delivery_days", 0)

    # 1. Required Quantity Check
    req_qty = ctx.get("required_qty", 0)
    if qty >= req_qty and qty > 0:
        checks["required_qty"] = True
    else:
        failed_checks.append("required_qty")
        failure_reasons.append(f"Negotiated quantity ({qty}) is below required quantity ({req_qty}).")

    # 2. Vendor MOQ Check
    moq = ctx.get("moq", 0)
    if qty >= moq:
        checks["moq"] = True
    else:
        failed_checks.append("moq")
        failure_reasons.append(f"Negotiated quantity ({qty}) is below vendor MOQ ({moq}).")

    # 3. Expiry Safety Check
    expiry_safe_qty = ctx.get("expiry_safe_qty")
    if expiry_safe_qty is not None:
        if qty <= expiry_safe_qty:
            checks["expiry"] = True
        else:
            failed_checks.append("expiry")
            failure_reasons.append(f"Quantity ({qty}) exceeds expiry-safe quantity ({expiry_safe_qty}).")
    else:
        checks["expiry"] = True

    # 4. Negotiated Price Check
    # Enforce bilateral bargaining economic invariants:
    #   a) Buyer Reservation Ceiling: Price must not exceed buyer max budget/quote ceiling
    #   b) Vendor Reservation Floor: Price must not violate vendor minimum acceptable floor
    res_ceiling = ctx.get("buyer_reservation_price") or ctx.get("reservation_price") or ctx.get("reservation_ceiling")
    res_floor = ctx.get("vendor_floor_price") or ctx.get("reservation_floor") or ctx.get("floor_price")

    if price > 0:
        price_valid = True
        # Verify Buyer Ceiling
        if res_ceiling is not None:
            if price > (res_ceiling + 0.001):
                price_valid = False
                failed_checks.append("price")
                failure_reasons.append(f"Negotiated price (${price:.2f}) exceeds reservation ceiling (${res_ceiling:.2f}).")
        # Verify Vendor Floor
        if res_floor is not None:
            if price < (res_floor - 0.001):
                price_valid = False
                failed_checks.append("price")
                failure_reasons.append(f"Negotiated price (${price:.2f}) violates vendor reservation/floor price (${res_floor:.2f}).")
        
        if price_valid and "price" not in failed_checks:
            checks["price"] = True
    else:
        failed_checks.append("price")
        failure_reasons.append(f"Invalid negotiated unit price: {price}.")

    # 5. Delivery SLA Check
    max_delivery = ctx.get("max_delivery_days")
    if max_delivery is not None:
        if delivery_days <= max_delivery:
            checks["delivery"] = True
        else:
            failed_checks.append("delivery")
            failure_reasons.append(f"Delivery time ({delivery_days}d) exceeds maximum acceptable timeline ({max_delivery}d).")
    else:
        checks["delivery"] = (delivery_days >= 0)

    # 6. Vendor Validity Check
    candidate_vendor_ids = ctx.get("candidate_vendor_ids", [])
    expected_vendor_id = ctx.get("selected_vendor_id")
    if vendor_id is not None and (not candidate_vendor_ids or vendor_id in candidate_vendor_ids):
        if expected_vendor_id is None or vendor_id == expected_vendor_id:
            checks["vendor"] = True
        else:
            failed_checks.append("vendor")
            failure_reasons.append(f"Vendor mismatch: deal vendor ({vendor_id}) != selected vendor ({expected_vendor_id}).")
    else:
        failed_checks.append("vendor")
        failure_reasons.append(f"Invalid or unknown vendor ID ({vendor_id}).")

    # 7. Negotiation Status Check
    neg_status = ctx.get("negotiation_status") or deal_status
    if neg_status == "ACCEPTED" and deal_status == "ACCEPTED":
        checks["negotiation_status"] = True
    else:
        failed_checks.append("negotiation_status")
        failure_reasons.append(f"Negotiation status is not ACCEPTED (current: {neg_status}).")

    is_valid = len(failed_checks) == 0
    if is_valid:
        summary_reason = "Negotiated deal satisfies all procurement constraints."
    else:
        summary_reason = "; ".join(failure_reasons)

    return {
        "valid": is_valid,
        "checks": checks,
        "failed_checks": failed_checks,
        "reason": summary_reason,
    }
