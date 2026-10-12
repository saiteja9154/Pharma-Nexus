"""
Supplier Gateway Interface for Store Procurement Agent.
Architectural interface separating simulated demo responses from live external
supplier APIs (e.g., EDI 850/855/856, AS2, PEPPOL, cXML, or modern Supplier REST APIs).

Explicitly declares that simulated responses are generated locally in demo mode,
and provides a clean contract for future real supplier quotation and ordering integrations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class SupplierGatewayInterface(ABC):
    """
    Abstract contract for supplier communications.
    Defines methods required for real-world electronic supplier ordering and negotiation.
    """

    @abstractmethod
    def request_quotation(
        self,
        vendor_id: int,
        med_id: int,
        quantity: int,
    ) -> Dict[str, Any]:
        """Request formal price quote / terms from supplier for specified quantity."""
        pass

    @abstractmethod
    def submit_negotiation_proposal(
        self,
        vendor_id: int,
        med_id: int,
        proposed_unit_price: float,
        quantity: int,
        round_num: int,
    ) -> Dict[str, Any]:
        """Submit bargaining proposal/counter-offer to supplier."""
        pass

    @abstractmethod
    def transmit_purchase_order(
        self,
        po_id: int,
        vendor_id: int,
        med_id: int,
        quantity: int,
        unit_price: float,
        total_cost: float,
    ) -> Dict[str, Any]:
        """Transmit confirmed purchase order electronically to supplier."""
        pass

    @abstractmethod
    def query_delivery_status(
        self,
        po_id: int,
    ) -> Dict[str, Any]:
        """Query dispatch/fulfillment status and ASN (Advance Shipping Notice) tracking."""
        pass


class SimulatedSupplierGateway(SupplierGatewayInterface):
    """
    Local simulation implementation for demonstration and offline ERP operation.
    Explicitly labeled as simulated supplier responses.
    """

    def __init__(self, mode: str = "SIMULATED_DEMO_MODE"):
        self.mode = mode
        self.disclaimer = (
            "NOTICE: Simulated supplier response for demo and offline ERP evaluation. "
            "No live external supplier API contacted."
        )

    def request_quotation(
        self,
        vendor_id: int,
        med_id: int,
        quantity: int,
    ) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "is_simulated": True,
            "vendor_id": vendor_id,
            "med_id": med_id,
            "requested_quantity": quantity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "disclaimer": self.disclaimer,
        }

    def submit_negotiation_proposal(
        self,
        vendor_id: int,
        med_id: int,
        proposed_unit_price: float,
        quantity: int,
        round_num: int,
    ) -> Dict[str, Any]:
        from tools.negotiation_tools import vendor_respond
        resp = vendor_respond(
            vendor_id=vendor_id,
            offered_price=proposed_unit_price,
            quantity=quantity,
            base_price=proposed_unit_price,
            round_num=round_num,
        )
        resp["is_simulated"] = True
        resp["mode"] = self.mode
        resp["disclaimer"] = self.disclaimer
        return resp

    def transmit_purchase_order(
        self,
        po_id: int,
        vendor_id: int,
        med_id: int,
        quantity: int,
        unit_price: float,
        total_cost: float,
    ) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "is_simulated": True,
            "po_id": po_id,
            "status": "ORDER_TRANSMITTED",
            "vendor_id": vendor_id,
            "med_id": med_id,
            "quantity": quantity,
            "total_cost": total_cost,
            "acknowledgement_id": f"SIM-ACK-#{po_id:04d}",
            "disclaimer": self.disclaimer,
            "transmitted_at": datetime.now(timezone.utc).isoformat(),
        }

    def query_delivery_status(
        self,
        po_id: int,
    ) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "is_simulated": True,
            "po_id": po_id,
            "shipping_status": "IN_TRANSIT",
            "carrier": "PharmaExpress Logistics (Simulated)",
            "tracking_number": f"SIM-TRK-{po_id:04d}",
            "disclaimer": self.disclaimer,
        }

    def negotiate_terms(
        self,
        vendor_id: int,
        vendor_name: str,
        medicine_name: str,
        quantity: int,
        initial_price: float,
        target_discount_pct: float = 0.10,
        max_rounds: int = 2,
    ) -> Dict[str, Any]:
        """
        Simulate a multi-round negotiation with vendor profile behavioral models.
        Clearly labeled as simulated negotiation (demo mode).
        """
        try:
            from tools.negotiation_tools import vendor_respond, calculate_target_price
        except ImportError:
            from backend.tools.negotiation_tools import vendor_respond, calculate_target_price

        target_price = calculate_target_price(initial_price, target_discount_pct)
        turns = []
        best_offer = None
        status = "IN_PROGRESS"

        # Round 1 Proposal
        agent_proposal_r1 = {
            "round": 1,
            "speaker": "STORE_AGENT",
            "action": "OFFER",
            "price": target_price,
            "quantity": quantity,
            "message": f"We require {quantity} units of {medicine_name}. Can you offer ${target_price:.2f}/u?",
        }
        turns.append(agent_proposal_r1)

        v_resp_r1 = vendor_respond(vendor_id, target_price, quantity, initial_price, 1)
        turns.append(v_resp_r1)

        if v_resp_r1["action"] == "ACCEPT":
            status = "AGREED"
            unit_p = float(v_resp_r1["price"])
            total_c = round(unit_p * quantity, 2)
            savings = round((initial_price - unit_p) * quantity, 2)
            best_offer = {
                "unit_price": unit_p,
                "quantity": quantity,
                "total_cost": total_c,
                "savings": savings,
                "discount_pct": round(((initial_price - unit_p) / initial_price) * 100, 1) if initial_price > 0 else 0.0,
                "status": "ACCEPTED",
            }
        elif v_resp_r1["action"] == "COUNTER" and max_rounds >= 2:
            counter_p = float(v_resp_r1["price"])
            midpoint = round((target_price + counter_p) / 2, 2)
            agent_proposal_r2 = {
                "round": 2,
                "speaker": "STORE_AGENT",
                "action": "COUNTER",
                "price": midpoint,
                "quantity": quantity,
                "message": f"Can we meet at ${midpoint:.2f} per unit?",
            }
            turns.append(agent_proposal_r2)

            v_resp_r2 = vendor_respond(vendor_id, midpoint, quantity, initial_price, 2)
            turns.append(v_resp_r2)

            if v_resp_r2["action"] == "ACCEPT":
                status = "AGREED"
                unit_p = float(v_resp_r2["price"])
                total_c = round(unit_p * quantity, 2)
                savings = round((initial_price - unit_p) * quantity, 2)
                best_offer = {
                    "unit_price": unit_p,
                    "quantity": quantity,
                    "total_cost": total_c,
                    "savings": savings,
                    "discount_pct": round(((initial_price - unit_p) / initial_price) * 100, 1) if initial_price > 0 else 0.0,
                    "status": "ACCEPTED",
                }
            else:
                status = "UNRESOLVED" if v_resp_r2["action"] == "COUNTER" else "REJECTED"
        else:
            status = "REJECTED"

        return {
            "mode": self.mode,
            "is_simulated": True,
            "simulation_notice": "Simulated negotiation based on vendor profile behavioral model (Demo Mode).",
            "vendor_id": vendor_id,
            "vendor_name": vendor_name,
            "status": status,
            "turns": turns,
            "best_offer": best_offer,
            "disclaimer": self.disclaimer,
        }


class ExternalSupplierAPIAdapter(SupplierGatewayInterface):
    """
    Integration adapter for future live external supplier APIs.
    Demonstrates architectural readiness without pretending live external APIs currently exist.
    """

    def __init__(self, api_endpoint: Optional[str] = None, api_key: Optional[str] = None):
        self.api_endpoint = api_endpoint
        self.api_key = api_key

    def request_quotation(self, vendor_id: int, med_id: int, quantity: int) -> Dict[str, Any]:
        raise NotImplementedError(
            "Live supplier API credentials not configured. Please use SimulatedSupplierGateway for demo mode."
        )

    def submit_negotiation_proposal(
        self, vendor_id: int, med_id: int, proposed_unit_price: float, quantity: int, round_num: int
    ) -> Dict[str, Any]:
        raise NotImplementedError(
            "Live supplier negotiation protocol not configured. Please use SimulatedSupplierGateway for demo mode."
        )

    def transmit_purchase_order(
        self, po_id: int, vendor_id: int, med_id: int, quantity: int, unit_price: float, total_cost: float
    ) -> Dict[str, Any]:
        raise NotImplementedError(
            "Live supplier electronic order transmission not configured. Please use SimulatedSupplierGateway for demo mode."
        )

    def query_delivery_status(self, po_id: int) -> Dict[str, Any]:
        raise NotImplementedError(
            "Live supplier tracking API not configured. Please use SimulatedSupplierGateway for demo mode."
        )
