import stripe
from firebase_functions import firestore_fn
from firebase_admin import firestore
from google.cloud.firestore import SERVER_TIMESTAMP

stripe.api_key = "sk_live_..."

# Washly takes 15% of every job. Changing this one constant
# is all you need to adjust the split across the whole platform.
PLATFORM_RATE = 0.15


@firestore_fn.on_document_updated(document="bookings/{booking_id}")
def process_payment_on_completion(event: firestore_fn.Event):
    # This function watches every booking update, so we need to
    # bail out early if this isn't actually a completion event.
    before = event.data.before.to_dict()
    after  = event.data.after.to_dict()

    if before["status"] == after["status"] or after["status"] != "completed":
        return  # Not a completion transition — nothing to do here

    total = float(after["serviceSnapshot"]["price"])

    # Always derive washer_payout as (total - fee) rather than (total * 0.85).
    # Floating point rounding means the two approaches can differ by a penny
    # on some amounts, and that adds up across thousands of transactions.
    platform_fee  = round(total * PLATFORM_RATE, 2)
    washer_payout = round(total - platform_fee, 2)

   
    

    # Record the final breakdown on the booking document so we have
    # a clean audit trail without having to query Stripe every time.
    event.data.after.reference.update({
        "payment.total":        total,
        "payment.platformFee":  platform_fee,
        "payment.washerPayout": washer_payout,
        "payment.status":       "paid",
        "completedAt":          SERVER_TIMESTAMP,
    })

    # Free the washer up for their next job now that this one is wrapped up.
    db.collection("users").document(after["washerId"]).update({"isAvailable": True})
