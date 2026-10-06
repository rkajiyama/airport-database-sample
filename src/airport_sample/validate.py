"""Check source coverage, references, time zones, fleet and seats. SPDX-License-Identifier: MIT"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from .fetch import ROOT
from .generate import FIELDS, read_csv, timestamp, verify_sources


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate(source: Path, output: Path) -> dict:
    source_manifest = verify_sources(source)
    manifest = json.loads((output / "manifest.json").read_text())
    require(hashlib.sha256((source / "manifest.json").read_bytes()).hexdigest() == manifest["source_manifest_sha256"], "Wrong source manifest")
    for name, info in manifest["outputs"].items():
        # load.sql is reproducible but not tracked; CSV-only distributions can
        # still be validated before the user generates the import SQL.
        if name == "load.sql" and not (output / name).exists():
            continue
        require(hashlib.sha256((output / name).read_bytes()).hexdigest() == info["sha256"], f"Output checksum mismatch: {name}")
    tables = {name: read_csv(output / f"{name}.csv") for name in FIELDS}
    indexes = {}
    for name, rows in tables.items():
        key = FIELDS[name][0]
        indexes[name] = {row[key]: row for row in rows}
        require(len(indexes[name]) == len(rows) == manifest["row_counts"][name], f"Primary key/count mismatch: {name}")
    require(set(indexes["airport"]) == {r["id"] for r in read_csv(source / "airports.csv")}, "Incomplete airport master")
    source_qids = {b["airline"]["value"].rsplit("/", 1)[-1] for b in json.loads((source / "airlines.json").read_text())["results"]["bindings"]}
    require({r["wikidata_qid"] for r in tables["airline"]} == source_qids, "Incomplete airline master")
    expected = {e["file"]: e["entity_count"] for e in source_manifest["sources"]}
    for table, filename in (("country", "countries.csv"), ("region", "regions.csv"), ("airport", "airports.csv"), ("airline", "airlines.json")):
        require(len(tables[table]) == expected[filename], f"Source count mismatch: {table}")
    references = {
        "region": [("country_code", "country")],
        "airport": [("country_code", "country"), ("region_code", "region")],
        "aircraft": [("aircraft_type_id", "aircraft_type"), ("airline_id", "airline"), ("base_airport_id", "airport")],
        "route": [("airline_id", "airline"), ("origin_airport_id", "airport"), ("destination_airport_id", "airport")],
        "flight_schedule": [("route_id", "route"), ("aircraft_id", "aircraft")],
        "flight": [("schedule_id", "flight_schedule")],
        "booking": [("flight_id", "flight"), ("passenger_id", "passenger")],
    }
    for table, keys in references.items():
        for row in tables[table]:
            for key, target in keys:
                require(not row[key] or row[key] in indexes[target], f"Missing reference: {table}.{key}={row[key]}")
    config = manifest["config"]
    require(len(tables["flight"]) == config["flight_count"], "Flight count")
    require(len(tables["booking"]) == config["flight_count"] * config["bookings_per_flight"], "Booking count")
    require(len(tables["passenger"]) == config["passenger_count"], "Passenger count")
    aircraft_ops = defaultdict(list)
    actual_ops = defaultdict(list)
    for flight in tables["flight"]:
        schedule = indexes["flight_schedule"][flight["schedule_id"]]
        route = indexes["route"][schedule["route_id"]]
        aircraft = indexes["aircraft"][schedule["aircraft_id"]]
        require(route["airline_id"] == aircraft["airline_id"], "Aircraft/route operator mismatch")
        departure = datetime.fromisoformat(flight["scheduled_departure_utc"])
        arrival = datetime.fromisoformat(flight["scheduled_arrival_utc"])
        require(arrival - departure == timedelta(minutes=int(schedule["duration_minutes"])), "Block duration mismatch")
        require(schedule["valid_from_utc"] <= flight["service_date_utc"] <= schedule["valid_to_utc"], "Flight outside schedule validity")
        require(flight["service_date_utc"] == departure.date().isoformat(), "UTC service date mismatch")
        require(departure.time().isoformat(timespec="seconds") == schedule["departure_time_utc"], "Schedule departure mismatch")
        for label, value, airport_key in (("departure", departure, "origin_airport_id"), ("arrival", arrival, "destination_airport_id")):
            zone = ZoneInfo(indexes["airport"][route[airport_key]]["timezone_name"])
            require(timestamp(value.replace(tzinfo=timezone.utc).astimezone(zone)) == flight[f"{label}_local"], "Local time conversion mismatch")
        aircraft_ops[schedule["aircraft_id"]].append((departure, arrival, route))
        if flight["status"] == "cancelled":
            require(not flight["actual_departure_utc"] and not flight["actual_arrival_utc"], "Cancelled flight has actual times")
        else:
            actual_dep = datetime.fromisoformat(flight["actual_departure_utc"])
            actual_arr = datetime.fromisoformat(flight["actual_arrival_utc"])
            require(actual_arr > actual_dep, "Invalid actual times")
            actual_ops[schedule["aircraft_id"]].append((actual_dep, actual_arr, route))
    for aircraft_id, operations in aircraft_ops.items():
        previous = None
        for departure, arrival, route in sorted(operations, key=lambda op: op[0]):
            if previous:
                require(departure >= previous[1] + timedelta(minutes=config["turnaround_minutes"]), "Overlapping aircraft/short turnaround")
                require(previous[2]["destination_airport_id"] == route["origin_airport_id"], "Aircraft location discontinuity")
            else:
                require(route["origin_airport_id"] == indexes["aircraft"][aircraft_id]["base_airport_id"], "Aircraft starts away from base")
            previous = (departure, arrival, route)
        require(previous[2]["destination_airport_id"] == indexes["aircraft"][aircraft_id]["base_airport_id"], "Aircraft does not return to base")
    for aircraft_id, operations in actual_ops.items():
        previous = None
        for departure, arrival, route in sorted(operations, key=lambda op: op[0]):
            if previous:
                require(departure >= previous[1] + timedelta(minutes=config["turnaround_minutes"]), "Actual turnaround too short")
                require(previous[2]["destination_airport_id"] == route["origin_airport_id"], "Actual aircraft location discontinuity")
            else:
                require(route["origin_airport_id"] == indexes["aircraft"][aircraft_id]["base_airport_id"], "Actual aircraft starts away from base")
            previous = (departure, arrival, route)
        require(previous[2]["destination_airport_id"] == indexes["aircraft"][aircraft_id]["base_airport_id"], "Actual aircraft does not return to base")
    seats, passengers = set(), set()
    booking_counts = defaultdict(int)
    for booking in tables["booking"]:
        flight = indexes["flight"][booking["flight_id"]]
        schedule = indexes["flight_schedule"][flight["schedule_id"]]
        aircraft = indexes["aircraft"][schedule["aircraft_id"]]
        capacity = int(indexes["aircraft_type"][aircraft["aircraft_type_id"]]["seat_capacity"])
        seat_key = (booking["flight_id"], booking["seat_number"])
        passenger_key = (booking["flight_id"], booking["passenger_id"])
        require(seat_key not in seats and passenger_key not in passengers, "Duplicate seat/passenger booking")
        require(1 <= int(booking["seat_number"]) <= capacity, "Seat beyond aircraft capacity")
        require(float(booking["price"]) >= 0, "Negative price")
        require(booking["booked_at_utc"] < flight["scheduled_departure_utc"], "Booking after departure")
        require((booking["status"] == "cancelled") == (flight["status"] == "cancelled"), "Booking/flight cancellation mismatch")
        seats.add(seat_key)
        passengers.add(passenger_key)
        booking_counts[booking["flight_id"]] += 1
    require(all(booking_counts[f["flight_id"]] == config["bookings_per_flight"] for f in tables["flight"]), "Reservations per flight mismatch")
    return {"result": "passed", "row_counts": manifest["row_counts"], "checks": ["source/output hashes", "full master coverage", "primary keys", "foreign references", "counts", "UTC/local times", "scheduled/actual fleet continuity/turnaround", "seat capacity/uniqueness", "booking dates/cancellation"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "data/source")
    parser.add_argument("--output", type=Path, default=ROOT / "data/small")
    args = parser.parse_args()
    result = validate(args.source, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
