# civic lane corpus — provenance

Source: FixMyStreet (mySociety) Open311 API — public civic defect reports
(https://www.fixmystreet.com/open311/v2/requests.json, jurisdiction=fixmystreet).
Real citizen free-text reports, fetched 2026-10-11, ~8 pages × ~870 rows.

- text = report title + description (truncated 500 chars, whitespace-normalized)
- 320 raw `service_name` labels (council-specific wording) merged to 13 canonical
  routes by keyword map (see tools/build_civic.py for the mapping)
- No names/coords retained — only text + canonical route
- License: FMS reports are public submissions; corpus is derived data for
  benchmarking/training, same usage class as CLINC/GoEmotions research sets.
  Attribution: mySociety / FixMyStreet.
- train.jsonl 3751 rows / holdout.jsonl 941 rows, 80/20 per-route split, seed 11
