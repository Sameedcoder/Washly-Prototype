from firebase_functions import https_fn
from firebase_admin import firestore
from google.cloud.firestore import SERVER_TIMESTAMP


@https_fn.on_call()
def submit_rating(req: https_fn.CallableRequest):
    booking_id  = req.data["bookingId"]
    score       = req.data["score"]        # expects an integer between 1 and 5
    comment     = req.data.get("comment", "")
    customer_id = req.auth.uid

    booking_ref  = db.collection("bookings").document(booking_id)
    booking      = booking_ref.get().to_dict()

    # A few sanity checks before we touch anything.
    # These should never fail in normal usage but protect against
    # someone calling the function directly with a crafted payload.
    if booking["customerId"] != customer_id:
        raise https_fn.HttpsError("permission-denied", "That's not your booking.")

    if booking["status"] != "completed":
        raise https_fn.HttpsError("failed-precondition", "Can't rate a job that isn't done yet.")

    if booking.get("rating"):
        raise https_fn.HttpsError("already-exists", "You've already rated this job.")

    # Attach the rating directly to the booking document.
    # This means we can always trace a washer's rating back to the
    # exact job it came from — useful if a rating ever gets disputed.
    booking_ref.update({
        "rating": {
            "score":     score,
            "comment":   comment,
            "createdAt": SERVER_TIMESTAMP,
        }
    })

    # Update the washer's overall average rating.
    # We do this inside a transaction because two customers could
    # theoretically submit ratings for the same washer at the same time,
    # and a plain read-modify-write would silently drop one of them.
    washer_ref = db.collection("users").document(booking["washerId"])

    @firestore.transactional
    def update_avg(transaction):
        washer    = washer_ref.get(transaction=transaction).to_dict()
        old_count = washer.get("ratingCount", 0)
        old_avg   = washer.get("rating", 0.0)
        new_count = old_count + 1

        # Incremental average: no need to store all past scores,
        # just the running count and current average.
        new_avg = round((old_avg * old_count + score) / new_count, 2)
        transaction.update(washer_ref, {"rating": new_avg, "ratingCount": new_count})

    transaction = db.transaction()
    update_avg(transaction)

    return {"success": True}
