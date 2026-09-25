"""CAN-SPAM and GDPR compliance validation [SEED: 2399]."""

class ComplianceError(Exception):
    """Raised when outreach message violates compliance rules."""

class ComplianceChecker:
    """Validates outreach messages against legal frameworks."""

    def validate(self, message: str) -> bool:
        """Ensure message contains required compliance elements."""
        msg_lower = message.lower()
        
        # CAN-SPAM requires physical address and unsubscribe mechanism
        has_address = "[physical address]" in msg_lower or "street" in msg_lower or "ave" in msg_lower or "blvd" in msg_lower
        has_unsub = "unsubscribe" in msg_lower or "opt-out" in msg_lower or "opt out" in msg_lower
        
        if not has_unsub:
            raise ComplianceError("Message missing unsubscribe/opt-out mechanism (CAN-SPAM/GDPR violation)")
            
        # We allow placeholders for physical address in templates
        if not has_address and "[physical address]" not in message:
             raise ComplianceError("Message missing physical address placeholder (CAN-SPAM violation)")
             
        return True
