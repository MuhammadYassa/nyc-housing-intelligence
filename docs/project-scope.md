# Project Scope

## Problem

New York City already knows which buildings have problems. When a tenant loses heat in January, reports mold, or finds rats in a stairwell, that report is logged; when a city inspector confirms a housing code violation, that finding is recorded with a severity class and left open until the landlord fixes it. All of it is published as public data. But a renter deciding whether to sign a lease cannot use any of it: the records live in several large, separate datasets, keyed by identifiers the average person has never heard of, with no reliable way to go from "123 Main Street, Apartment 4B" to that building's actual history. So the information exists, is free, and is effectively unreadable — and renters sign leases without knowing whether the building they are moving into loses heat every winter or has hazardous violations that have been open for years.

## First milestone

Given a valid BBL, return MapPLUTO property information and currently open HPD violations grouped by class.

That is the entire milestone. It is deliberately small: it establishes the property spine, the join key, and the ingestion discipline that everything else will be built on top of.

## Non-goals for the first milestone

These are explicitly out of scope. Each is deferred, not cancelled.

- 311 data
- HPD complaints
- Address fuzzy matching
- Machine learning
- AI summaries
- React frontend
- User accounts
- Redis
- Landlord scoring

## First milestone success criteria

The milestone is complete when all of the following hold:

- **Data can be reloaded without duplicates.** Running ingestion twice produces the same row counts as running it once.
- **Invalid records are identified.** Records that fail validation are detected and reported rather than silently dropped or silently loaded.
- **Every output can be traced back to its NYC source.** Any value returned by the system can be attributed to the specific source dataset and record it came from.
- **A property can be joined to its violations through BBL.** The join is correct and verifiable.
- **Tests confirm the counts for selected properties.** A fixed set of known properties has asserted violation counts by class, verified against the source data.