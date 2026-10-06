"""Build complete masters and a synthetic round-trip fleet. SPDX-License-Identifier: MIT"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import random
from zoneinfo import ZoneInfo

from .fetch import ROOT

# Table order is also import order. All fields are represented losslessly as text
# in CSV; empty string represents SQL NULL (no empty string domain values).
FIELDS = {
    "country": ["country_code", "name", "continent"],
    "region": ["region_code", "name", "country_code"],
    "airport": ["airport_id", "ident", "airport_type", "name", "latitude_deg", "longitude_deg", "elevation_ft", "continent", "country_code", "region_code", "municipality", "scheduled_service", "gps_code", "icao_code", "iata_code", "local_code", "timezone_name", "home_link", "wikipedia_link", "keywords"],
    "airline": ["airline_id", "wikidata_qid", "name_en", "name_ja", "iata_codes", "icao_codes", "country_qids", "inception_values", "dissolved_values"],
    "aircraft_type": ["aircraft_type_id", "name", "seat_capacity", "cruise_kmh", "max_block_minutes", "is_synthetic"],
    "aircraft": ["aircraft_id", "aircraft_type_id", "airline_id", "synthetic_identifier", "base_airport_id"],
    "route": ["route_id", "airline_id", "origin_airport_id", "destination_airport_id", "distance_km", "is_synthetic"],
    "flight_schedule": ["schedule_id", "route_id", "aircraft_id", "synthetic_flight_number", "valid_from_utc", "valid_to_utc", "departure_time_utc", "duration_minutes", "operating_days_utc", "is_synthetic"],
    "flight": ["flight_id", "schedule_id", "service_date_utc", "scheduled_departure_utc", "scheduled_arrival_utc", "departure_local", "arrival_local", "actual_departure_utc", "actual_arrival_utc", "status", "is_synthetic"],
    "passenger": ["passenger_id", "synthetic_name", "email", "is_synthetic"],
    "booking": ["booking_id", "flight_id", "passenger_id", "seat_number", "price", "currency", "booked_at_utc", "status", "is_synthetic"],
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def qid(url: str) -> str:
    return url.rsplit("/", 1)[-1]


def build_airlines(source: Path) -> list[dict]:
    grouped: dict[str, dict[str, set[str]]] = {}
    for binding in json.loads(source.read_text())["results"]["bindings"]:
        entity = qid(binding["airline"]["value"])
        values = grouped.setdefault(entity, {k: set() for k in ("name_en", "name_ja", "iata", "icao", "country", "inception", "dissolved")})
        for key in values:
            if key in binding:
                value = binding[key]["value"]
                values[key].add(qid(value) if key == "country" else value)
    rows = []
    for entity, values in sorted(grouped.items(), key=lambda pair: int(pair[0][1:])):
        # QID numeric component provides a stable surrogate across snapshots.
        row = {"airline_id": int(entity[1:]), "wikidata_qid": entity,
               "name_en": next(iter(sorted(values["name_en"])), entity),
               "name_ja": next(iter(sorted(values["name_ja"])), "")}
        for source_key, dest in (("iata", "iata_codes"), ("icao", "icao_codes"), ("country", "country_qids"), ("inception", "inception_values"), ("dissolved", "dissolved_values")):
            row[dest] = json.dumps(sorted(values[source_key]), ensure_ascii=False, separators=(",", ":"))
        rows.append(row)
    return rows


def distance_km(a: dict, b: dict) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, [float(a["latitude_deg"]), float(a["longitude_deg"]), float(b["latitude_deg"]), float(b["longitude_deg"])])
    hav = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1.0, max(0.0, hav))))


def timestamp(value: datetime) -> str:
    return value.replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")


def sql_literal(value: object) -> str:
    # Export sets NO_BACKSLASH_ESCAPES, so apostrophe doubling is sufficient.
    # Other characters, including source backslashes/newlines, remain literal.
    if value is None or value == "":
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def export_sql(output: Path, tables: dict[str, list[dict]]) -> None:
    with (output / "load.sql").open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("-- Data: CC-BY-4.0; generated SQL statements: MIT. See LICENSE and SOURCES.md.\n")
        handle.write("-- Run sql/schema.sql first against an EMPTY database. UTC values are DATETIME.\n")
        handle.write("USE airport_sample;\nSET NAMES utf8mb4;\nSET @saved_sql_mode = @@SESSION.sql_mode;\nSET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_BACKSLASH_ESCAPES';\n")
        for table, rows in tables.items():
            fields = FIELDS[table]
            handle.write("START TRANSACTION;\n")
            for index in range(0, len(rows), 500):
                handle.write(f"INSERT INTO `{table}` (" + ",".join(f"`{field}`" for field in fields) + ") VALUES\n")
                handle.write(",\n".join("(" + ",".join(sql_literal(row[field]) for field in fields) + ")" for row in rows[index:index + 500]))
                handle.write(";\n")
            handle.write("COMMIT;\n")
        handle.write("SET SESSION sql_mode = @saved_sql_mode;\n")


def verify_sources(source: Path) -> dict:
    manifest = json.loads((source / "manifest.json").read_text())
    for entry in manifest["sources"]:
        raw = (source / entry["file"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError(f"Source checksum mismatch: {entry['file']}")
    return manifest


def build(source: Path, config: dict) -> dict[str, list[dict]]:
    verify_sources(source)
    days, flight_count = config["days"], config["flight_count"]
    if days < 1 or flight_count < 2 or flight_count % 2 or config["passenger_count"] < config["bookings_per_flight"] or not 1 <= config["bookings_per_flight"] <= 180:
        raise ValueError("Require positive days, an even flight_count, and valid passenger/seat counts")
    if config["passenger_count"] > flight_count * config["bookings_per_flight"]:
        raise ValueError("Each configured passenger must receive at least one booking")
    turnaround = config["turnaround_minutes"]
    if not 1 <= turnaround <= 240:
        raise ValueError("turnaround_minutes must be in [1, 240]")
    rng = random.Random(config["seed"])
    tables = {name: [] for name in FIELDS}
    for row in sorted(read_csv(source / "countries.csv"), key=lambda r: r["code"]):
        tables["country"].append(dict(zip(FIELDS["country"], [row["code"], row["name"], row["continent"]])))
    for row in sorted(read_csv(source / "regions.csv"), key=lambda r: r["code"]):
        tables["region"].append(dict(zip(FIELDS["region"], [row["code"], row["name"], row["iso_country"]])))
    for row in sorted(read_csv(source / "airports.csv"), key=lambda r: int(r["id"])):
        tables["airport"].append(dict(zip(FIELDS["airport"], [int(row["id"]), row["ident"], row["type"], row["name"], row["latitude_deg"], row["longitude_deg"], row["elevation_ft"], row["continent"], row["iso_country"], row["iso_region"], row["municipality"], row["scheduled_service"], row["gps_code"], row.get("icao_code", ""), row["iata_code"], row["local_code"], config["airports"].get(row["ident"], ""), row["home_link"], row["wikipedia_link"], row["keywords"]])))
    tables["airline"] = build_airlines(source / "airlines.json")
    by_ident = {a["ident"]: a for a in tables["airport"]}
    by_qid = {a["wikidata_qid"]: a for a in tables["airline"]}
    airports = [by_ident[ident] for ident in config["airports"]]
    airlines = [by_qid[entity] for entity in config["airline_qids"]]
    if len(airports) < 2 or not airlines:
        raise ValueError("At least two airports and one airline required")
    for airport in airports:
        ZoneInfo(airport["timezone_name"])
    tables["aircraft_type"].append(dict(zip(FIELDS["aircraft_type"], [1, "Synthetic narrow-body 180", 180, 780, 600, 1])))
    start = date.fromisoformat(config["start_date_utc"])
    cycles = flight_count // 2
    fleet_count = math.ceil(cycles / days)
    candidates = [(a, b, distance_km(a, b)) for index, a in enumerate(airports) for b in airports[index + 1:] if 100 <= distance_km(a, b) <= 7000]
    if not candidates:
        raise ValueError("No suitable synthetic round-trip routes")
    route_ids: dict[tuple[int, int, int], int] = {}
    for aircraft_id in range(1, fleet_count + 1):
        # Ensure every selected airline is used; geography is synthetic.
        airline = airlines[(aircraft_id - 1) % len(airlines)]
        a, b, distance = rng.choice(candidates)
        duration = math.ceil((40 + distance / 780 * 60) / 5) * 5
        if duration > 600:
            raise ValueError("Route exceeds the aircraft block-time limit")
        departure_minute = rng.randrange(0, 1440 - (2 * duration + 2 * turnaround) + 1)
        # Allocate days evenly: all aircraft operate first, then the remainder.
        cycle_days = cycles // fleet_count + (aircraft_id <= cycles % fleet_count)
        # Both legs share cancellation/delay so the aircraft stays at its base
        # after a cancelled rotation and retains the full turnaround interval.
        operations = [(rng.random() < 0.01, rng.randrange(0, min(20, turnaround))) for _ in range(cycle_days)]
        tables["aircraft"].append(dict(zip(FIELDS["aircraft"], [aircraft_id, 1, airline["airline_id"], f"SYN-{aircraft_id:06d}", a["airport_id"]])))
        for leg, origin, destination in ((0, a, b), (1, b, a)):
            key = (airline["airline_id"], origin["airport_id"], destination["airport_id"])
            if key not in route_ids:
                route_ids[key] = len(route_ids) + 1
                tables["route"].append(dict(zip(FIELDS["route"], [route_ids[key], *key, round(distance, 3), 1])))
            minute = departure_minute + leg * (duration + turnaround)
            schedule_id = (aircraft_id - 1) * 2 + leg + 1
            schedule = dict(zip(FIELDS["flight_schedule"], [schedule_id, route_ids[key], aircraft_id, f"SYN{schedule_id:06d}", start.isoformat(), (start + timedelta(days=cycle_days - 1)).isoformat(), f"{minute // 60:02d}:{minute % 60:02d}:00", duration, "1234567", 1]))
            tables["flight_schedule"].append(schedule)
            for day in range(cycle_days):
                departure = datetime.combine(start + timedelta(days=day), datetime.min.time(), timezone.utc) + timedelta(minutes=minute)
                arrival = departure + timedelta(minutes=duration)
                # Bounded synthetic delay fits within the turnaround margin.
                cancelled, delay = operations[day]
                actual_departure = departure + timedelta(minutes=delay)
                actual_arrival = arrival + timedelta(minutes=delay)
                tables["flight"].append(dict(zip(FIELDS["flight"], [len(tables["flight"]) + 1, schedule_id, departure.date().isoformat(), timestamp(departure), timestamp(arrival), timestamp(departure.astimezone(ZoneInfo(origin["timezone_name"]))), timestamp(arrival.astimezone(ZoneInfo(destination["timezone_name"]))), "" if cancelled else timestamp(actual_departure), "" if cancelled else timestamp(actual_arrival), "cancelled" if cancelled else "completed", 1])))
    for passenger_id in range(1, config["passenger_count"] + 1):
        tables["passenger"].append(dict(zip(FIELDS["passenger"], [passenger_id, f"Synthetic Passenger {passenger_id:06d}", f"passenger{passenger_id:06d}@example.invalid", 1])))
    routes = {row["route_id"]: row for row in tables["route"]}
    schedules = {row["schedule_id"]: row for row in tables["flight_schedule"]}
    for flight in tables["flight"]:
        distance = routes[schedules[flight["schedule_id"]]["route_id"]]["distance_km"]
        for seat in rng.sample(range(1, 181), config["bookings_per_flight"]):
            booking_id = len(tables["booking"]) + 1
            passenger_id = (booking_id - 1) % config["passenger_count"] + 1
            booked = datetime.fromisoformat(flight["scheduled_departure_utc"]) - timedelta(days=rng.randrange(1, 91))
            price = round(40 + distance * rng.uniform(0.04, 0.16), 2)
            tables["booking"].append(dict(zip(FIELDS["booking"], [booking_id, flight["flight_id"], passenger_id, seat, f"{price:.2f}", "USD", timestamp(booked), "cancelled" if flight["status"] == "cancelled" else "confirmed", 1])))
    if len(tables["flight"]) != flight_count:
        raise ValueError("Flight count mismatch")
    return tables


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the Small database from pinned sources")
    parser.add_argument("--source", type=Path, default=ROOT / "data/source")
    parser.add_argument("--config", type=Path, default=ROOT / "config/small.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/small")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    tables = build(args.source, config)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        write_csv(args.output / f"{name}.csv", FIELDS[name], rows)
        print(f"{name}: {len(rows):,}")
    export_sql(args.output, tables)
    summary = {"data_license": "CC-BY-4.0", "code_license": "MIT", "config": config, "row_counts": {name: len(rows) for name, rows in tables.items()}, "source_manifest_sha256": hashlib.sha256((args.source / "manifest.json").read_bytes()).hexdigest(), "outputs": {path.name: {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(args.output.glob("*.csv"))}}
    summary["outputs"]["load.sql"] = {"bytes": (args.output / "load.sql").stat().st_size, "sha256": hashlib.sha256((args.output / "load.sql").read_bytes()).hexdigest()}
    (args.output / "manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
