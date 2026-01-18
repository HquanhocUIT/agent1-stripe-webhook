import os
import json
import base64
import hashlib
import time
import stripe

# -------- Helpers --------
def get_raw_body(event) -> bytes:
    body = event.get("body", "")
    if event.get("isBase64Encoded"):
        return base64.b64decode(body)
    return body.encode("utf-8")

def sha256_token(value: str | None) -> str | None:
    """Deterministic token for PII (same input => same token)."""
    if not value:
        return None
    value = value.strip().lower()
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

# -------- Main handler --------
def lambda_handler(event, context):
    # 0) Load secret
    endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not endpoint_secret:
        return {"statusCode": 500, "body": "Missing STRIPE_WEBHOOK_SECRET env"}

    # 1) Get Stripe signature header
    headers = event.get("headers") or {}
    sig_header = headers.get("stripe-signature") or headers.get("Stripe-Signature")
    if not sig_header:
        # This is the "NOT valid ping" path
        return {"statusCode": 400, "body": "Missing stripe-signature header"}

    # 2) Verify webhook signature (PING VALID?)
    payload = get_raw_body(event)

    try:
        stripe_event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=endpoint_secret
        )
    except stripe.error.SignatureVerificationError:
        print("❌ INVALID Stripe signature")
        return {"statusCode": 401, "body": "Invalid signature"}
    except Exception as e:
        print("❌ Verify error:", str(e))
        return {"statusCode": 500, "body": str(e)}

    print("✅ VALID Stripe webhook")
    print("Event ID:", stripe_event.get("id"))
    print("Event type:", stripe_event.get("type"))

    # 3) Normalize (convert Stripe payload => internal JSON standard)
    obj = (stripe_event.get("data") or {}).get("object") or {}
    event_type = stripe_event.get("type")
    received_at = int(time.time())

    # Common IDs
    transaction_id = obj.get("id")  # e.g. pi_...
    customer_id = obj.get("customer")

    # Amount normalization (Stripe uses minor units)
    amount_minor = obj.get("amount_received") or obj.get("amount") or obj.get("amount_total") or 0
    currency = obj.get("currency")

    # For trace/reconcile
    payment_intent_id = obj.get("payment_intent") if obj.get("object") != "payment_intent" else obj.get("id")
    charge_id = obj.get("charge") or obj.get("latest_charge")

    # Potential email fields (depends on event/object)
    receipt_email = obj.get("receipt_email") or obj.get("customer_email")
    if not receipt_email:
        cust_details = obj.get("customer_details") or {}
        receipt_email = cust_details.get("email")

    normalized = {
        "provider": "stripe",
        "source": "webhook",

        "event_id": stripe_event.get("id"),
        "event_type": event_type,
        "received_at": received_at,

        "transaction": {
            "transaction_id": transaction_id,
            "amount_minor": amount_minor,   # keep as integer (cents)
            "currency": currency,
            "status": obj.get("status"),
            "created": obj.get("created"),
        },

        # Tokenized PII ONLY
        "pii": {
            "email_token": sha256_token(receipt_email),
            "customer_id_token": sha256_token(customer_id),
        },

        # Non-PII references (useful for agent2 reconciliation)
        "refs": {
            "payment_intent_id": payment_intent_id,
            "charge_id": charge_id,
            "customer_id": customer_id,
        }
    }

    print("✅ NORMALIZED JSON:", json.dumps(normalized, ensure_ascii=False))

    # 4) Return fast for Stripe
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"ok": True})
    }
