"""
Adaptive Negotiation Engine for Store Procurement Agent (Phase 4).
Implements multi-round bargaining protocols, target/reservation price boundary calculations,
deterministic vendor counter-offering simulation, and structured LLM/fallback agent proposals.
"""

from typing import Dict, Any, Optional

# Centralized negotiation parameters
MAX_NEGOTIATION_ROUNDS = 2
DEFAULT_TARGET_DISCOUNT_PCT = 0.10  # 10% target discount below baseline quote
DEFAULT_RESERVATION_DISCOUNT_PCT = 0.00  # Max acceptable price is baseline quote price


def calculate_target_price(base_price: float, discount_pct: float = DEFAULT_TARGET_DISCOUNT_PCT) -> float:
    """Calculate buyer target discount price."""
    return round(base_price * (1.0 - discount_pct), 2)


def calculate_reservation_price(base_price: float, discount_pct: float = DEFAULT_RESERVATION_DISCOUNT_PCT) -> float:
    """Calculate buyer reservation price ceiling (walk-away threshold)."""
    return round(base_price * (1.0 - discount_pct), 2)


def get_vendor_floor_price(vendor_id: int, base_price: float) -> float:
    """
    Calculate deterministic vendor reservation floor price based on vendor concession tolerance:
      - Vendor A (ID 1): Low margin leader -> 4% max concession (Floor: 96%)
      - Vendor B (ID 2): Flexible volume margin -> 8% max concession (Floor: 92%)
      - Vendor C (ID 3): Moderate supplier -> 6% max concession (Floor: 94%)
    """
    if vendor_id == 1:
        return round(base_price * 0.96, 2)
    elif vendor_id == 2:
        return round(base_price * 0.92, 2)
    elif vendor_id == 3:
        return round(base_price * 0.94, 2)
    return round(base_price * 0.90, 2)


def vendor_respond(
    vendor_id: int,
    offered_price: float,
    quantity: int,
    base_price: float,
    round_num: int,
) -> Dict[str, Any]:
    """
    Deterministic Vendor Response Simulator.
    Evaluates buyer proposal against vendor pricing tolerance and returns ACCEPT, COUNTER, or REJECT.
    
    Vendor Profiles:
      - Vendor A (ID 1): Low-margin leader. Concession tolerance up to 4% (Floor: 96%).
      - Vendor B (ID 2): Fast delivery, flexible volume margins. Concession tolerance up to 8% (Floor: 92%).
      - Vendor C (ID 3): Moderate supplier. Concession tolerance up to 6% (Floor: 94%).
    """
    ratio = offered_price / base_price if base_price > 0 else 1.0

    if vendor_id == 1:
        # Vendor A (Low Margin Leader, Floor: 96%)
        if round_num == 1:
            if ratio >= 0.98:
                action = "ACCEPT"
                counter_price = offered_price
                msg = f"Vendor A accepts ${offered_price:.2f} for {quantity} units."
            elif ratio >= 0.90:
                action = "COUNTER"
                counter_price = round(base_price * 0.96, 2)
                msg = f"Vendor A: Best wholesale rate is ${counter_price:.2f} per unit."
            else:
                action = "REJECT"
                counter_price = base_price
                msg = f"Vendor A: Offer of ${offered_price:.2f} is below cost floor. Rejected."
        else:
            # Round 2: Accept if buyer meets 4% discount floor
            if ratio >= 0.96:
                action = "ACCEPT"
                counter_price = offered_price
                msg = f"Vendor A accepts agreed rate of ${offered_price:.2f} per unit for {quantity} units."
            elif ratio >= 0.90:
                action = "COUNTER"
                counter_price = round(base_price * 0.96, 2)
                msg = f"Vendor A: Final offer remains ${counter_price:.2f} per unit."
            else:
                action = "REJECT"
                counter_price = base_price
                msg = f"Vendor A: Counter offer rejected."

    elif vendor_id == 2:
        # Vendor B (Hero Vendor: Fast Delivery & Flexible Margin, Floor: 92%)
        if round_num == 1:
            if ratio >= 0.95:
                action = "ACCEPT"
                counter_price = offered_price
                msg = f"Vendor B accepts ${offered_price:.2f} per unit. Order confirmed for {quantity} units."
            elif ratio >= 0.88:
                action = "COUNTER"
                # Midpoint concession
                counter_price = round((offered_price + base_price) / 2, 2)
                msg = f"Vendor B: We can meet you halfway at ${counter_price:.2f} per unit."
            elif ratio >= 0.80:
                action = "COUNTER"
                counter_price = round(base_price * 0.92, 2)
                msg = f"Vendor B: We can offer a volume discount at ${counter_price:.2f} per unit."
            else:
                action = "REJECT"
                counter_price = base_price
                msg = f"Vendor B: Offer of ${offered_price:.2f} is outside our discount policy. Rejected."
        else:
            # Round 2: Accept if buyer adapted proposal meets 8% concession floor (>= 92%)
            if ratio >= 0.92:
                action = "ACCEPT"
                counter_price = offered_price
                msg = f"Vendor B accepts buyer counter of ${offered_price:.2f} per unit. Order confirmed for {quantity} units."
            elif ratio >= 0.85:
                action = "COUNTER"
                counter_price = round(base_price * 0.92, 2)
                msg = f"Vendor B: Lowest possible rate is ${counter_price:.2f} per unit."
            else:
                action = "REJECT"
                counter_price = base_price
                msg = f"Vendor B: Offer of ${offered_price:.2f} is rejected."

    else:
        # Vendor C (Moderate Supplier, Floor: 94%)
        if round_num == 1:
            if ratio >= 0.96:
                action = "ACCEPT"
                counter_price = offered_price
                msg = f"Vendor C accepts ${offered_price:.2f} per unit."
            elif ratio >= 0.88:
                action = "COUNTER"
                counter_price = round(base_price * 0.94, 2)
                msg = f"Vendor C: We counter with ${counter_price:.2f} per unit."
            else:
                action = "REJECT"
                counter_price = base_price
                msg = f"Vendor C: Offer of ${offered_price:.2f} is rejected."
        else:
            # Round 2: Accept if buyer meets 6% discount floor
            if ratio >= 0.94:
                action = "ACCEPT"
                counter_price = offered_price
                msg = f"Vendor C accepts rate of ${offered_price:.2f} per unit."
            elif ratio >= 0.88:
                action = "COUNTER"
                counter_price = round(base_price * 0.94, 2)
                msg = f"Vendor C: Final counter is ${counter_price:.2f} per unit."
            else:
                action = "REJECT"
                counter_price = base_price
                msg = f"Vendor C: Counter of ${offered_price:.2f} rejected."

    return {
        "round": round_num,
        "speaker": "VENDOR",
        "action": action,
        "price": counter_price,
        "quantity": quantity,
        "message": msg,
    }


def generate_agent_negotiation_action(
    context: Dict[str, Any],
    use_llm: bool = False,
) -> Dict[str, Any]:
    """
    Generate next structured StoreAgent negotiation action.
    Supports deterministic reasoning fallback and extensible LLM adapter.
    """
    round_num = context.get("round", 1)
    vendor_id = context.get("vendor_id", 1)
    med_name = context.get("med_name", "Medicine")
    quantity = context.get("quantity", 100)
    target_price = context.get("target_price", 0.0)
    reservation_price = context.get("reservation_price", 0.0)
    last_vendor_response = context.get("last_vendor_response")

    if round_num == 1:
        # Round 1: Open with target price
        return {
            "round": 1,
            "speaker": "STORE_AGENT",
            "action": "OFFER",
            "vendor_id": vendor_id,
            "price": target_price,
            "quantity": quantity,
            "message": f"We require {quantity} units of {med_name}. Can you offer a volume rate of ${target_price:.2f} per unit?",
            "reason": f"Proposing target price of ${target_price:.2f} (10% discount) for volume order.",
        }

    else:
        # Round 2: Evaluate vendor counter and adapt
        if last_vendor_response and last_vendor_response.get("action") == "COUNTER":
            counter_p = float(last_vendor_response.get("price", reservation_price))

            if counter_p <= target_price:
                return {
                    "round": 2,
                    "speaker": "STORE_AGENT",
                    "action": "ACCEPT",
                    "vendor_id": vendor_id,
                    "price": counter_p,
                    "quantity": quantity,
                    "message": f"We accept your counter of ${counter_p:.2f} per unit.",
                    "reason": f"Vendor counter (${counter_p:.2f}) meets or beats target price (${target_price:.2f}).",
                }
            elif counter_p <= reservation_price:
                # Adapt: Counter at midpoint between target and vendor counter
                midpoint = round((target_price + counter_p) / 2, 2)
                return {
                    "round": 2,
                    "speaker": "STORE_AGENT",
                    "action": "COUNTER",
                    "vendor_id": vendor_id,
                    "price": midpoint,
                    "quantity": quantity,
                    "message": f"We can proceed if you can meet us at ${midpoint:.2f} per unit.",
                    "reason": f"Vendor countered at ${counter_p:.2f}. Adapting counter to midpoint ${midpoint:.2f} within reservation limit (${reservation_price:.2f}).",
                }
            else:
                return {
                    "round": 2,
                    "speaker": "STORE_AGENT",
                    "action": "REJECT",
                    "vendor_id": vendor_id,
                    "price": counter_p,
                    "quantity": quantity,
                    "message": f"Vendor counter of ${counter_p:.2f} exceeds our reservation ceiling of ${reservation_price:.2f}.",
                    "reason": f"Vendor counter (${counter_p:.2f}) exceeds reservation ceiling (${reservation_price:.2f}).",
                }
        else:
            # Fallback if no specific counter was provided
            return {
                "round": 2,
                "speaker": "STORE_AGENT",
                "action": "COUNTER",
                "vendor_id": vendor_id,
                "price": target_price,
                "quantity": quantity,
                "message": f"We maintain our proposal of ${target_price:.2f} per unit.",
                "reason": "Maintaining target price proposal.",
            }
