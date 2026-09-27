"""
Deal Scoring Engine for Store Procurement Agent (Phase 3 Foundation).
Implements deterministic, multi-factor evaluation of vendor quotes based on:
- Unit Price & Total Cost (Weight: 45%)
- Delivery Speed SLA (Weight: 35%)
- MOQ Order Efficiency (Weight: 20%)
- Hard Feasibility Constraints (Expiry capacity, minimum quantities)
"""

from typing import List, Dict, Any, Optional, Tuple

# Default explainable scoring weights
DEFAULT_WEIGHTS = {
    "price": 0.45,
    "delivery": 0.35,
    "moq": 0.20,
}


def check_quote_feasibility(
    quote: Dict[str, Any],
    expiry_safe_qty: Optional[int] = None,
) -> Tuple[bool, List[str]]:
    """
    Evaluate deterministic feasibility constraints for a vendor offer.
    
    Hard constraints:
      1. offered_qty >= required_qty
      2. offered_qty >= vendor_MOQ
      3. offered_qty <= expiry_safe_qty (if expiry shelf-life capacity is specified)
    """
    violations: List[str] = []
    offered_qty = quote.get("offered_qty", 0)
    required_qty = quote.get("required_qty", 0)
    moq = quote.get("moq", 0)

    if offered_qty < required_qty:
        violations.append(
            f"Offered quantity ({offered_qty}) is below required quantity ({required_qty})."
        )

    if offered_qty < moq:
        violations.append(
            f"Offered quantity ({offered_qty}) violates vendor MOQ ({moq})."
        )

    if expiry_safe_qty is not None:
        if offered_qty > expiry_safe_qty:
            violations.append(
                f"Offered quantity ({offered_qty}) exceeds expiry-safe capacity ({expiry_safe_qty}). Risk of spoilage."
            )

    feasible = len(violations) == 0
    return feasible, violations


def score_quotes(
    quotes: List[Dict[str, Any]],
    expiry_safe_qty: Optional[int] = None,
    weights: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """
    Score and rank a collection of vendor quotes for a specific medicine.
    
    Scoring Model:
      - Price Score (45%): 1.0 - (price - min_price) / (max_price - min_price)
      - Delivery Score (35%): 1.0 - (delivery - min_delivery) / (max_delivery - min_delivery)
      - MOQ Efficiency (20%): required_qty / offered_qty (penalizes excess mandatory buffer)
      - Feasibility: Infeasible quotes receive score = 0.0
    """
    if not quotes:
        return []

    w = weights or DEFAULT_WEIGHTS

    # Extract bounds across candidate quotes for relative normalization
    prices = [q["base_price"] for q in quotes]
    deliveries = [q["delivery_days"] for q in quotes]

    min_p, max_p = min(prices), max(prices)
    min_d, max_d = min(deliveries), max(deliveries)

    scored_quotes: List[Dict[str, Any]] = []

    for q in quotes:
        feasible, violations = check_quote_feasibility(q, expiry_safe_qty)

        # 1. Price Score
        if max_p == min_p:
            p_score = 1.0
        else:
            p_score = 1.0 - ((q["base_price"] - min_p) / (max_p - min_p))

        # 2. Delivery Score
        if max_d == min_d:
            d_score = 1.0
        else:
            d_score = 1.0 - ((q["delivery_days"] - min_d) / (max_d - min_d))

        # 3. MOQ Efficiency Score (1.0 if exact match, lower if high MOQ forces over-ordering)
        req_qty = q.get("required_qty", 1)
        off_qty = q.get("offered_qty", 1)
        moq_score = min(1.0, req_qty / off_qty) if off_qty > 0 else 0.0

        # Composite Score
        if feasible:
            raw_score = (
                w["price"] * p_score +
                w["delivery"] * d_score +
                w["moq"] * moq_score
            ) * 100.0
            final_score = round(raw_score, 2)
        else:
            final_score = 0.0

        # Build explainable reasons list
        reasons: List[str] = []
        if not feasible:
            reasons.extend(violations)
        else:
            if q["base_price"] == min_p:
                reasons.append(f"Lowest unit price (${q['base_price']:.2f})")
            else:
                reasons.append(f"Price: ${q['base_price']:.2f}/unit (benchmark: ${min_p:.2f})")

            if q["delivery_days"] == min_d:
                reasons.append(f"Fastest delivery ({q['delivery_days']} days)")
            else:
                reasons.append(f"Delivery: {q['delivery_days']} days")

            if q["offered_qty"] == q["required_qty"]:
                reasons.append("Exact quantity match (100% MOQ efficiency)")
            else:
                reasons.append(f"MOQ requires {q['offered_qty']} units (needed: {q['required_qty']})")

        scored_item = dict(q)
        scored_item.update(
            {
                "feasible": feasible,
                "score": final_score,
                "price_score": round(p_score, 3),
                "delivery_score": round(d_score, 3),
                "moq_score": round(moq_score, 3),
                "reasons": reasons,
                "infeasible_reasons": violations,
            }
        )
        scored_quotes.append(scored_item)

    return scored_quotes


def score_deal(
    quote: Dict[str, Any],
    all_quotes: Optional[List[Dict[str, Any]]] = None,
    expiry_safe_qty: Optional[int] = None,
) -> Dict[str, Any]:
    """Score an individual quote either in candidate context or standalone."""
    candidate_list = all_quotes or [quote]
    scored = score_quotes(candidate_list, expiry_safe_qty=expiry_safe_qty)
    for sq in scored:
        if sq["vendor_id"] == quote.get("vendor_id"):
            return sq
    return scored[0]
