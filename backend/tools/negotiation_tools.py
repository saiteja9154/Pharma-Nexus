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


# Centralized configurable vendor negotiation profiles
VENDOR_PROFILES = {
    1: {
        "name": "Vendor A",
        "description": "Low-Margin Bulk Wholesale Supplier",
        "floor_ratio": 0.96,
        "round1_accept_ratio": 0.98,
        "round1_counter_ratio": 0.90,
        "round2_accept_ratio": 0.96,
        "round2_counter_ratio": 0.90,
    },
    2: {
        "name": "Vendor B",
        "description": "Fast Delivery, Flexible Volume Margin",
        "floor_ratio": 0.92,
        "round1_accept_ratio": 0.95,
        "round1_counter_ratio": 0.88,
        "round2_accept_ratio": 0.92,
        "round2_counter_ratio": 0.85,
    },
    3: {
        "name": "Vendor C",
        "description": "Regional Balanced Distributor",
        "floor_ratio": 0.94,
        "round1_accept_ratio": 0.96,
        "round1_counter_ratio": 0.88,
        "round2_accept_ratio": 0.94,
        "round2_counter_ratio": 0.88,
    },
    4: {
        "name": "Vendor D",
        "description": "Generic Medicine Supplier",
        "floor_ratio": 0.93,
        "round1_accept_ratio": 0.95,
        "round1_counter_ratio": 0.87,
        "round2_accept_ratio": 0.93,
        "round2_counter_ratio": 0.87,
    },
    5: {
        "name": "Vendor E",
        "description": "Hospital Supply Distributor",
        "floor_ratio": 0.95,
        "round1_accept_ratio": 0.97,
        "round1_counter_ratio": 0.90,
        "round2_accept_ratio": 0.95,
        "round2_counter_ratio": 0.90,
    },
    6: {
        "name": "Vendor F",
        "description": "Specialty Pharmaceutical Supplier",
        "floor_ratio": 0.97,
        "round1_accept_ratio": 0.98,
        "round1_counter_ratio": 0.92,
        "round2_accept_ratio": 0.97,
        "round2_counter_ratio": 0.92,
    },
}


def get_vendor_floor_price(vendor_id: int, base_price: float, custom_floor_ratio: Optional[float] = None) -> float:
    """
    Calculate deterministic vendor reservation floor price based on vendor concession tolerance:
      - Uses configured profile floor ratio if available, or custom floor ratio.
    """
    if custom_floor_ratio is not None:
        return round(base_price * custom_floor_ratio, 2)
    profile = VENDOR_PROFILES.get(vendor_id)
    floor = profile["floor_ratio"] if profile else 0.94
    return round(base_price * floor, 2)


def vendor_respond(
    vendor_id: int,
    offered_price: float,
    quantity: int,
    base_price: float,
    round_num: int,
    custom_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Deterministic Vendor Response Simulator.
    Evaluates buyer proposal against vendor pricing tolerance and returns ACCEPT, COUNTER, or REJECT.
    Clearly labeled as simulated negotiation (demo mode).
    """
    ratio = offered_price / base_price if base_price > 0 else 1.0
    profile = custom_profile or VENDOR_PROFILES.get(vendor_id) or {
        "name": f"Vendor #{vendor_id}",
        "floor_ratio": 0.94,
        "round1_accept_ratio": 0.96,
        "round1_counter_ratio": 0.88,
        "round2_accept_ratio": 0.94,
        "round2_counter_ratio": 0.88,
    }

    v_name = profile.get("name", f"Vendor #{vendor_id}")
    floor = profile.get("floor_ratio", 0.94)
    floor_price = round(base_price * floor, 2)

    if vendor_id == 1:
        # Vendor A: Low Margin Leader (Floor: 96%)
        if round_num == 1:
            if ratio >= profile["round1_accept_ratio"]:
                action = "ACCEPT"
                counter_price = offered_price
                msg = f"{v_name} accepts ${offered_price:.2f} for {quantity} units."
            elif ratio >= profile["round1_counter_ratio"]:
                action = "COUNTER"
                counter_price = floor_price
                msg = f"{v_name}: Best wholesale rate is ${counter_price:.2f} per unit."
            else:
                action = "REJECT"
                counter_price = base_price
                msg = f"{v_name}: Offer of ${offered_price:.2f} is below cost floor. Rejected."
        else:
            if ratio >= profile["round2_accept_ratio"]:
                action = "ACCEPT"
                counter_price = offered_price
                msg = f"{v_name} accepts agreed rate of ${offered_price:.2f} per unit for {quantity} units."
            elif ratio >= profile["round2_counter_ratio"]:
                action = "COUNTER"
                counter_price = floor_price
                msg = f"{v_name}: Final offer remains ${counter_price:.2f} per unit."
            else:
                action = "REJECT"
                counter_price = base_price
                msg = f"{v_name}: Counter offer rejected."

    elif vendor_id == 2:
        # Vendor B: Fast Delivery & Flexible Margin (Hero Winner, Floor: 92%)
        if round_num == 1:
            if ratio >= profile["round1_accept_ratio"]:
                action = "ACCEPT"
                counter_price = offered_price
                msg = f"{v_name} accepts ${offered_price:.2f} per unit. Order confirmed for {quantity} units."
            elif ratio >= profile["round1_counter_ratio"]:
                action = "COUNTER"
                counter_price = round((offered_price + base_price) / 2, 2)
                msg = f"{v_name}: We can meet you halfway at ${counter_price:.2f} per unit."
            elif ratio >= 0.80:
                action = "COUNTER"
                counter_price = floor_price
                msg = f"{v_name}: We can offer a volume discount at ${counter_price:.2f} per unit."
            else:
                action = "REJECT"
                counter_price = base_price
                msg = f"{v_name}: Offer of ${offered_price:.2f} is outside our discount policy. Rejected."
        else:
            if ratio >= profile["round2_accept_ratio"]:
                action = "ACCEPT"
                counter_price = offered_price
                msg = f"{v_name} accepts buyer counter of ${offered_price:.2f} per unit. Order confirmed for {quantity} units."
            elif ratio >= profile["round2_counter_ratio"]:
                action = "COUNTER"
                counter_price = floor_price
                msg = f"{v_name}: Lowest possible rate is ${counter_price:.2f} per unit."
            else:
                action = "REJECT"
                counter_price = base_price
                msg = f"{v_name}: Offer of ${offered_price:.2f} is rejected."

    else:
        # Generic / Vendor C / D / E / F configurable logic
        r1_acc = profile.get("round1_accept_ratio", 0.96)
        r1_cnt = profile.get("round1_counter_ratio", 0.88)
        r2_acc = profile.get("round2_accept_ratio", floor)
        r2_cnt = profile.get("round2_counter_ratio", 0.88)

        if round_num == 1:
            if ratio >= r1_acc:
                action = "ACCEPT"
                counter_price = offered_price
                msg = f"{v_name} accepts ${offered_price:.2f} per unit."
            elif ratio >= r1_cnt:
                action = "COUNTER"
                counter_price = floor_price
                msg = f"{v_name}: We counter with ${counter_price:.2f} per unit."
            else:
                action = "REJECT"
                counter_price = base_price
                msg = f"{v_name}: Offer of ${offered_price:.2f} is rejected."
        else:
            if ratio >= r2_acc:
                action = "ACCEPT"
                counter_price = offered_price
                msg = f"{v_name} accepts rate of ${offered_price:.2f} per unit."
            elif ratio >= r2_cnt:
                action = "COUNTER"
                counter_price = floor_price
                msg = f"{v_name}: Final counter is ${counter_price:.2f} per unit."
            else:
                action = "REJECT"
                counter_price = base_price
                msg = f"{v_name}: Counter of ${offered_price:.2f} rejected."

    return {
        "round": round_num,
        "speaker": "VENDOR",
        "action": action,
        "price": counter_price,
        "quantity": quantity,
        "message": msg,
        "is_simulated": True,
        "simulation_label": "Simulated Supplier Response (Demo Mode)",
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
