-- SPDX-License-Identifier: MIT
-- Independent schema; no airportdb/FlughafenDB DDL was copied.
-- MySQL 8.4; create in a new, empty schema. Does not drop existing objects.
CREATE DATABASE IF NOT EXISTS airport_sample CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE airport_sample;

CREATE TABLE country (
  country_code VARCHAR(8) COLLATE utf8mb4_bin PRIMARY KEY,
  name VARCHAR(512) NOT NULL,
  continent VARCHAR(8)
) ENGINE=InnoDB;

CREATE TABLE region (
  region_code VARCHAR(64) COLLATE utf8mb4_bin PRIMARY KEY,
  name VARCHAR(512) NOT NULL,
  country_code VARCHAR(8) COLLATE utf8mb4_bin NOT NULL,
  FOREIGN KEY (country_code) REFERENCES country(country_code)
) ENGINE=InnoDB;

CREATE TABLE airport (
  airport_id BIGINT UNSIGNED PRIMARY KEY,
  ident VARCHAR(64) COLLATE utf8mb4_bin NOT NULL UNIQUE,
  airport_type VARCHAR(64) NOT NULL,
  name VARCHAR(512) NOT NULL,
  latitude_deg DECIMAL(12,8),
  longitude_deg DECIMAL(12,8),
  elevation_ft INT,
  continent VARCHAR(8),
  country_code VARCHAR(8) COLLATE utf8mb4_bin,
  region_code VARCHAR(64) COLLATE utf8mb4_bin,
  municipality VARCHAR(512),
  scheduled_service VARCHAR(8),
  gps_code VARCHAR(64) COLLATE utf8mb4_bin,
  icao_code VARCHAR(64) COLLATE utf8mb4_bin,
  iata_code VARCHAR(64) COLLATE utf8mb4_bin,
  local_code VARCHAR(64) COLLATE utf8mb4_bin,
  timezone_name VARCHAR(64),
  home_link TEXT,
  wikipedia_link TEXT,
  keywords TEXT,
  KEY airport_iata (iata_code),
  KEY airport_country_type (country_code, airport_type),
  FOREIGN KEY (country_code) REFERENCES country(country_code),
  FOREIGN KEY (region_code) REFERENCES region(region_code),
  CHECK (latitude_deg BETWEEN -90 AND 90),
  CHECK (longitude_deg BETWEEN -180 AND 180)
) ENGINE=InnoDB;

CREATE TABLE airline (
  airline_id BIGINT UNSIGNED PRIMARY KEY,
  wikidata_qid VARCHAR(32) COLLATE utf8mb4_bin NOT NULL UNIQUE,
  name_en VARCHAR(512) NOT NULL,
  name_ja VARCHAR(512),
  iata_codes JSON NOT NULL,
  icao_codes JSON NOT NULL,
  country_qids JSON NOT NULL,
  inception_values JSON NOT NULL,
  dissolved_values JSON NOT NULL
) ENGINE=InnoDB;

CREATE TABLE aircraft_type (
  aircraft_type_id BIGINT UNSIGNED PRIMARY KEY,
  name VARCHAR(128) NOT NULL,
  seat_capacity SMALLINT UNSIGNED NOT NULL,
  cruise_kmh SMALLINT UNSIGNED NOT NULL,
  max_block_minutes SMALLINT UNSIGNED NOT NULL,
  is_synthetic BOOLEAN NOT NULL,
  CHECK (seat_capacity > 0)
) ENGINE=InnoDB;

CREATE TABLE aircraft (
  aircraft_id BIGINT UNSIGNED PRIMARY KEY,
  aircraft_type_id BIGINT UNSIGNED NOT NULL,
  airline_id BIGINT UNSIGNED NOT NULL,
  synthetic_identifier VARCHAR(64) NOT NULL UNIQUE,
  base_airport_id BIGINT UNSIGNED NOT NULL,
  FOREIGN KEY (aircraft_type_id) REFERENCES aircraft_type(aircraft_type_id),
  FOREIGN KEY (airline_id) REFERENCES airline(airline_id),
  FOREIGN KEY (base_airport_id) REFERENCES airport(airport_id)
) ENGINE=InnoDB;

CREATE TABLE route (
  route_id BIGINT UNSIGNED PRIMARY KEY,
  airline_id BIGINT UNSIGNED NOT NULL,
  origin_airport_id BIGINT UNSIGNED NOT NULL,
  destination_airport_id BIGINT UNSIGNED NOT NULL,
  distance_km DECIMAL(10,3) NOT NULL,
  is_synthetic BOOLEAN NOT NULL,
  UNIQUE KEY route_identity (airline_id, origin_airport_id, destination_airport_id),
  FOREIGN KEY (airline_id) REFERENCES airline(airline_id),
  FOREIGN KEY (origin_airport_id) REFERENCES airport(airport_id),
  FOREIGN KEY (destination_airport_id) REFERENCES airport(airport_id),
  CHECK (origin_airport_id <> destination_airport_id),
  CHECK (distance_km > 0)
) ENGINE=InnoDB;

CREATE TABLE flight_schedule (
  schedule_id BIGINT UNSIGNED PRIMARY KEY,
  route_id BIGINT UNSIGNED NOT NULL,
  aircraft_id BIGINT UNSIGNED NOT NULL,
  synthetic_flight_number VARCHAR(32) NOT NULL UNIQUE,
  valid_from_utc DATE NOT NULL,
  valid_to_utc DATE NOT NULL,
  departure_time_utc TIME NOT NULL,
  duration_minutes SMALLINT UNSIGNED NOT NULL,
  operating_days_utc CHAR(7) NOT NULL,
  is_synthetic BOOLEAN NOT NULL,
  FOREIGN KEY (route_id) REFERENCES route(route_id),
  FOREIGN KEY (aircraft_id) REFERENCES aircraft(aircraft_id),
  CHECK (valid_to_utc >= valid_from_utc),
  CHECK (duration_minutes > 0),
  CHECK (departure_time_utc >= '00:00:00' AND departure_time_utc < '24:00:00')
) ENGINE=InnoDB;

CREATE TABLE flight (
  flight_id BIGINT UNSIGNED PRIMARY KEY,
  schedule_id BIGINT UNSIGNED NOT NULL,
  service_date_utc DATE NOT NULL,
  scheduled_departure_utc DATETIME NOT NULL,
  scheduled_arrival_utc DATETIME NOT NULL,
  departure_local DATETIME NOT NULL,
  arrival_local DATETIME NOT NULL,
  actual_departure_utc DATETIME,
  actual_arrival_utc DATETIME,
  status ENUM('completed', 'cancelled') NOT NULL,
  is_synthetic BOOLEAN NOT NULL,
  UNIQUE KEY flight_identity (schedule_id, service_date_utc),
  KEY flight_departure (scheduled_departure_utc),
  FOREIGN KEY (schedule_id) REFERENCES flight_schedule(schedule_id),
  CHECK (scheduled_arrival_utc > scheduled_departure_utc),
  CHECK (actual_arrival_utc IS NULL OR actual_arrival_utc > actual_departure_utc)
) ENGINE=InnoDB;

CREATE TABLE passenger (
  passenger_id BIGINT UNSIGNED PRIMARY KEY,
  synthetic_name VARCHAR(128) NOT NULL,
  email VARCHAR(128) NOT NULL UNIQUE,
  is_synthetic BOOLEAN NOT NULL
) ENGINE=InnoDB;

CREATE TABLE booking (
  booking_id BIGINT UNSIGNED PRIMARY KEY,
  flight_id BIGINT UNSIGNED NOT NULL,
  passenger_id BIGINT UNSIGNED NOT NULL,
  seat_number SMALLINT UNSIGNED NOT NULL,
  price DECIMAL(10,2) NOT NULL,
  currency CHAR(3) NOT NULL,
  booked_at_utc DATETIME NOT NULL,
  status ENUM('confirmed', 'cancelled') NOT NULL,
  is_synthetic BOOLEAN NOT NULL,
  UNIQUE KEY booking_seat (flight_id, seat_number),
  UNIQUE KEY booking_passenger (flight_id, passenger_id),
  FOREIGN KEY (flight_id) REFERENCES flight(flight_id),
  FOREIGN KEY (passenger_id) REFERENCES passenger(passenger_id),
  CHECK (price >= 0),
  CHECK (seat_number > 0)
) ENGINE=InnoDB;
