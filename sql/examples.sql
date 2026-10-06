-- SPDX-License-Identifier: MIT
USE airport_sample;

-- Complete master vs the subset used for synthetic operations.
SELECT (SELECT COUNT(*) FROM airport) AS all_airports,
       (SELECT COUNT(*) FROM airline) AS all_airlines,
       (SELECT COUNT(DISTINCT airline_id) FROM route) AS simulated_airlines;

-- Multiple organizations can share a code; JSON_CONTAINS is explicit.
SELECT wikidata_qid, name_en, iata_codes
FROM airline WHERE JSON_CONTAINS(iata_codes, '"NH"');

-- Bookings by origin airport (all values are synthetic).
SELECT a.ident, a.name, COUNT(*) AS reservations
FROM booking b
JOIN flight f USING (flight_id)
JOIN flight_schedule s USING (schedule_id)
JOIN route r USING (route_id)
JOIN airport a ON a.airport_id = r.origin_airport_id
WHERE b.status = 'confirmed'
GROUP BY a.airport_id, a.ident, a.name
ORDER BY reservations DESC;

-- Synthetic booked revenue by airline, USD only.
SELECT a.name_en, SUM(b.price) AS synthetic_booked_revenue_usd
FROM booking b JOIN flight f USING (flight_id)
JOIN flight_schedule s USING (schedule_id)
JOIN route r USING (route_id) JOIN airline a USING (airline_id)
WHERE b.status = 'confirmed' AND b.currency = 'USD'
GROUP BY a.airline_id, a.name_en ORDER BY synthetic_booked_revenue_usd DESC;

-- One-stop connection candidates with 60-240 minutes for transfer.
SELECT f1.flight_id AS first_flight, f2.flight_id AS second_flight,
       r1.origin_airport_id, r1.destination_airport_id AS transfer_airport,
       r2.destination_airport_id,
       TIMESTAMPDIFF(MINUTE, f1.scheduled_arrival_utc, f2.scheduled_departure_utc) AS transfer_minutes
FROM flight f1 JOIN flight_schedule s1 ON s1.schedule_id = f1.schedule_id
JOIN route r1 ON r1.route_id = s1.route_id
JOIN route r2 ON r2.origin_airport_id = r1.destination_airport_id
JOIN flight_schedule s2 ON s2.route_id = r2.route_id
JOIN flight f2 ON f2.schedule_id = s2.schedule_id
WHERE f1.service_date_utc = '2026-01-01'
  AND f1.status = 'completed' AND f2.status = 'completed'
  AND r1.origin_airport_id <> r2.destination_airport_id
  AND f2.scheduled_departure_utc BETWEEN f1.scheduled_arrival_utc + INTERVAL 60 MINUTE
      AND f1.scheduled_arrival_utc + INTERVAL 240 MINUTE
LIMIT 20;
