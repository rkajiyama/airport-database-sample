# Sources and attribution

The dataset compilation and synthetic records are distributed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Credit **RKajiyama, airport-database-sample**, link to
<https://github.com/rkajiyama/airport-database-sample>, and indicate changes.
This grant covers only rights held by this project. Upstream material remains
Public Domain/CC0; reuse of those upstream facts is not made conditional on
attributing this project.

## OurAirports

- Provider: OurAirports community / David Megginson.
- Source: <https://ourairports.com/data/>.
- Terms: Public Domain; provider attribution is requested but not required.
- Files: `airports.csv`, `countries.csv`, `regions.csv`.
- Full downloaded airport rows are preserved, including closed facilities,
  heliports, small airfields and rows without IATA codes.
- Original snapshots and checksums: `data/source/manifest.json`.
- Changes: column renaming, source-ID preservation, sorting, and timezone
  annotation for the configured 30 simulation airports. Other airport
  timezone values remain NULL. Geography is not corrected silently.

## Wikidata

- Provider: Wikidata contributors.
- License: CC0 1.0 for structured data.
- Terms: <https://www.wikidata.org/wiki/Wikidata:Licensing>.
- Query: `config/airlines.rq` (no LIMIT, no active/code/country filter).
- Coverage: every returned entity classified as an instance of airline
  (Q46970) or an instance of a subclass of airline at retrieval time.
- Includes dissolved entities and brands classified as airlines. It is not
  a guarantee of completeness against a worldwide aviation registry.
- Fields: English/Japanese labels, truthy IATA/ICAO codes, country QIDs,
  inception and dissolution values. Multi-values are preserved as JSON arrays.
- The query uses `wdt:` best-rank values. Deprecated statements, historical
  revisions, qualifiers and full statement provenance are not exported.
  Code reuse is preserved across entities; codes are not unique keys.
- Original SPARQL result and query: `data/source/airlines.json` and manifest.
- Changes: group repeated query rows by QID; assign stable numeric ID from QID;
  sort and deduplicate field values; use QID when the English label is absent.
- Wikipedia article text, logos and Wikimedia media are not included.

## Original synthetic data

- Author: RKajiyama / airport-database-sample project.
- License: CC BY 4.0.
- Routes, schedules, flights, aircraft, passengers, bookings, prices, delays
  and cancellations are synthetic, even when an airline/airport name is real.
- Flight numbers and aircraft identifiers have a SYN prefix. Passenger names
  are explicitly synthetic; emails use the reserved `.invalid` domain.
- No passenger data, commercial timetable, airportdb DDL/data or OpenFlights
  database was copied.
- Airport timezone annotations were independently specified in configuration;
  conversions use the host Python `zoneinfo`/IANA timezone database. Pin the
  Python and timezone database versions when requiring byte-for-byte results
  across hosts (especially after timezone-rule updates).

## Code and tools

Original Python, SQL DDL, configuration, queries, tests and documentation use
MIT. The generator requires Python 3.11+ standard library and system timezone
data; no third-party name-generation corpus is used. MySQL and GitHub Actions
are execution tools, not part of the distributed source-data license.

If updating sources, preserve the new snapshot manifest and revise this notice
when adding other sources. A new source must be reviewed before inclusion.
