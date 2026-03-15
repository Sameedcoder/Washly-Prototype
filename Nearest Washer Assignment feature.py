import math
from firebase_admin import firestore
from firebase_functions import firestore_fn

db = firestore.client()


def haversine_km(loc1, loc2) -> float:
    # Standard haversine formula — gives us straight-line distance
    # between two GPS coordinates in kilometres. Good enough for
    # city-scale matching; no need for road-routing at this stage.
    R = 6371  # Earth's radius in km
    lat1, lon1 = math.radians(loc1.latitude), math.radians(loc1.longitude)
    lat2, lon2 = math.radians(loc2.latitude), math.radians(loc2.longitude)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


@firestore_fn.on_document_created(document="bookings/{booking_id}")
def assign_nearest_washer(event: firestore_fn.Event):
    # Fires the moment a new booking lands in Firestore.
    # Our job here: find the closest free washer and lock them in
    # before another booking can grab them.
    booking = event.data.to_dict()
    customer_loc = booking["customerLocation"]

    # Pull every washer who's currently marked available.
    # In production you'd want to add a geohash bounding box here
    # to avoid scanning the entire users collection.
    washers = (
        db.collection("users")
        .where("role", "==", "washer")
        .where("isAvailable", "==", True)
        .stream()
    )

    # Walk through every available washer and keep track of whoever
    # is physically closest to the customer right now.
    nearest, min_dist = None, float("inf")
    for doc in washers:
        w = doc.to_dict()
        dist = haversine_km(customer_loc, w["location"])
        if dist < min_dist:
            min_dist = dist
            nearest = doc

    # No one's free — leave the booking as pending and let the
    # frontend know it should show a "finding a washer..." state.
    if not nearest:
        event.data.reference.update({"status": "pending"})
        return

    booking_ref = event.data.reference
    washer_ref  = db.collection("users").document(nearest.id)

    @firestore.transactional
    def assign(transaction):
        # Re-read the washer inside the transaction to catch the race
        # condition where two bookings pick the same person at the same time.
        # If they're no longer available by the time we get here, bail out.
        washer_snap = washer_ref.get(transaction=transaction)
        if not washer_snap.to_dict().get("isAvailable"):
            raise Exception("Washer was grabbed by another booking — needs retry")

        # Assign the washer and flip their availability in one atomic write.
        # Both updates succeed together or neither does.
        transaction.update(booking_ref, {"washerId": nearest.id, "status": "assigned"})
        transaction.update(washer_ref,  {"isAvailable": False})

    transaction = db.transaction()
    assign(transaction)