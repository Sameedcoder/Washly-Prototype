Core Features
1. Booking & Washer Assignment
When a customer books a wash, a Cloud Function fires instantly and finds the nearest available washer using the Haversine formula on live GPS coordinates. The assignment is done inside a Firestore transaction to prevent two bookings from grabbing the same washer at the same time.
2. Commission Split
Every completed job automatically triggers a payment capture and a Stripe transfer. Washly keeps 15% of the job price, and the washer receives 85% directly into their connected Stripe account — no manual payouts needed.
3. Rating & Feedback
After a job is marked complete, the customer can leave a score (1–5) and an optional comment. The washer's overall rating updates automatically using an incremental rolling average stored on their profile.
Others features yet to come 
