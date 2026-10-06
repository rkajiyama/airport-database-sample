# Initial implementation review

Documentation: MIT. Review date: 2026-10-06.

## Scope and decisions

- Original schema and generator; airportdb and OpenFlights code/data were not
  reused. Data contributions: CC BY 4.0. Code/DDL/docs: MIT. Public Domain/CC0
  upstream material remains explicitly identified in LICENSE and SOURCES.md.
- All 86,208 source airport IDs and all 6,198 query airline QIDs are preserved.
- Airline codes are multi-valued and can be reused across brands/entities.
  Stable source IDs avoid treating an IATA code as a primary key.
- Generated schedules use UTC; local planned times are derived for each flight.
- Cancelled outbound/inbound flights are generated as a pair. Both legs share
  bounded delay so actual aircraft location and turnaround remain consistent.
- Import SQL quotes external source strings using NO_BACKSLASH_ESCAPES and
  apostrophe doubling. The documented importer uses --binary-mode to disable
  MySQL client commands in batch data. Foreign-key checking remains enabled.
- Source and output checksums are recorded and verified. A CSV-only clone is
  valid before generating the untracked load.sql; if SQL exists its hash is checked.
- Generation and loading are separate from source refresh. The CI uses pinned
  source snapshots and checks reproducibility without querying live endpoints.

## Local verification

Four tests passed: source-character SQL quoting, DST/date-line conversion,
complete Small data integrity, and deterministic generation/overbooking rejection.
All regenerated CSV and SQL hashes matched the committed manifest.

Additional data checks cover primary keys, foreign references, record counts,
UTC/local conversions, planned and actual fleet continuity, turnaround, seat
capacity/uniqueness, booking timestamps and cancellation consistency.

MySQL execution is checked by the repository's MySQL 8.4 GitHub Actions job;
consult the PR/Actions result for its actual outcome. This local environment did
not have a running MySQL server at initial verification time.

## Practical limits

- Airline coverage is all entities in the saved classification query, not an
  independently certified worldwide registry. Best-rank fields are extracted;
  full entity histories, code qualifiers and media are outside this release.
- Geography is retained as supplied. Timezones are populated for simulation
  airports only, not inferred for every source airport.
- Routes and fleets are synthetic. Carrier traffic rights, real fleets and
  published local timetables are not represented.
- Passengers have synthetic reservation records, not guaranteed feasible travel
  itineraries. Capacity is deliberately sparse at ten reservations per flight.
- The generator holds rows in memory. Very large profiles need streaming and
  chunked output. Source refresh changes master counts and requires updating the
  pinned SQL verification counts and documentation.

## Measured file sizes

- Generated CSV: 21,787,252 bytes (21.79 MB).
- Source snapshots and source manifest: approximately 17.49 MB.
- Generated SQL: 29,493,671 bytes (29.49 MB), regenerated locally rather than tracked.
- MySQL storage: obtain actual data/index lengths from sql/verify.sql; previous
  50-110 MB estimates are not measurements.
