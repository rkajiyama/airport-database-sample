-- SPDX-License-Identifier: MIT
USE airport_sample;
DELIMITER //
CREATE PROCEDURE verify_sample()
BEGIN
  IF (SELECT COUNT(*) FROM flight) <> 10000 OR
     (SELECT COUNT(*) FROM booking) <> 100000 OR
     (SELECT COUNT(*) FROM passenger) <> 30000 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Small counts do not match';
  END IF;
  IF (SELECT COUNT(*) FROM airport) <> 86208 OR
     (SELECT COUNT(*) FROM airline) <> 6198 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Pinned master counts do not match';
  END IF;
  IF EXISTS (
    SELECT 1 FROM booking b JOIN flight f USING (flight_id)
    JOIN flight_schedule s USING (schedule_id)
    JOIN aircraft a USING (aircraft_id)
    JOIN aircraft_type t USING (aircraft_type_id)
    WHERE b.seat_number > t.seat_capacity OR b.booked_at_utc >= f.scheduled_departure_utc
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Invalid seat/booking time';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM airport WHERE name LIKE '%''%') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Apostrophe-containing airport names missing';
  END IF;
END //
DELIMITER ;
CALL verify_sample();
DROP PROCEDURE verify_sample;
SELECT 'MySQL verification passed' AS result;
SELECT table_name, table_rows, data_length, index_length
FROM information_schema.tables WHERE table_schema = 'airport_sample'
ORDER BY table_name;
