# Design — Fix Suggestions

## Architecture Overview

```
Domain Layer:   report.py          — TopicFixSuggestions, FixSuggestionsReport data classes
                fix_suggestions.py — pure transformation: ContractsValidationReport → FixSuggestionsReport
                                     3-level hierarchy mirroring the validation report:
                                     FixSuggestionsReport → TopicFixSuggestions → PairFixSuggestion
CLI Layer:      cli/validate.py    — renders FixSuggestionsReport with context-aware labels;
                                     honours --how-to-fix flag on both validate commands
```

No new adapters, no new services, no new config. This feature is entirely additive — two
existing CLI commands grow a flag, and one new domain module handles all the logic.

### File Placement

| Module | File | Change |
|---|---|---|
| Fix report data classes | `contract_sentinel/domain/report.py` | **modified** — `TopicFixSuggestions`, `FixSuggestionsReport` added |
| Fix suggestion logic | `contract_sentinel/domain/fix_suggestions.py` | **new** |
| Validate CLI commands | `contract_sentinel/cli/validate.py` | **modified** — `--how-to-fix` flag + rendering |
| Fix suggestion unit tests | `tests/unit/test_domain/test_fix_suggestions.py` | **new** |

---

## 1. Domain Module — `fix_suggestions.py`

### Data Model

```python
# contract_sentinel/domain/report.py

@dataclasses.dataclass
class TopicFixSuggestions:
    topic: str
    pairs: list[PairFixSuggestion]   # sparse — only pairs with CRITICAL violations

@dataclasses.dataclass
class FixSuggestionsReport:
    suggestions_by_topic: list[TopicFixSuggestions]  # sparse — only topics with at least one failing pair

    @property
    def has_suggestions(self) -> bool:
        return len(self.suggestions_by_topic) > 0
```

```python
# contract_sentinel/domain/fix_suggestions.py

@dataclasses.dataclass
class FixSuggestion:
    """Internal atomic unit — one per CRITICAL violation. Never stored on PairFixSuggestion."""
    producer_instruction: str
    consumer_instruction: str

@dataclasses.dataclass
class PairFixSuggestion:
    """Pure value object — pre-rendered fix blocks for one producer/consumer pair."""
    producer_id: str
    consumer_id: str
    producer_instructions: str   # numbered prompt block, ready to print
    consumer_instructions: str   # numbered prompt block, ready to print
```

`PairFixSuggestion` is a plain value object — no behaviour, no computed properties.
`FixSuggestion` is used only inside `suggest_fixes` as a transient intermediary; it is
assembled per-violation, used to build the two rendered strings, then discarded.
`producer_instructions` and `consumer_instructions` are built in one place (`suggest_fixes`)
from the same list, so producer item N always corresponds to consumer item N.

The fix report is a **sparse view** of the validation report. Topics where all pairs pass are
omitted from `FixSuggestionsReport.suggestions_by_topic`. Pairs with no CRITICAL violations are
omitted from `TopicFixSuggestions.pairs`. The CLI renderer can iterate without any conditional
skipping — everything present needs to be printed.

### Public Interface

```python
# pair-level — tested directly
def suggest_fixes(pair: PairViolations) -> PairFixSuggestion | None: ...

# report-level — used by the CLI
def build_contracts_fix_report(report: ContractsValidationReport) -> FixSuggestionsReport: ...
```

`build_contracts_fix_report` always returns a `FixSuggestionsReport` — never `None`. An empty
`FixSuggestionsReport(suggestions_by_topic=[])` represents "no suggestions". The caller checks
`fix_report.has_suggestions` before rendering.

### Internal Call Chain

```
build_contracts_fix_report(report: ContractsValidationReport)
  └── for each ContractReport → _suggest_contract_fixes(contract_report) → TopicFixSuggestions | None
        └── for each PairViolations → suggest_fixes(pair) → PairFixSuggestion | None
              └── filters violations to CRITICAL only; returns None if none remain
              └── for each CRITICAL violation → _instruction_for(violation) → FixSuggestion | None
              └── builds producer_instructions via _build_block(producer_id, consumer_id, [...])
              └── builds consumer_instructions via _build_block(consumer_id, producer_id, [...])
              └── returns PairFixSuggestion(producer_id, consumer_id, producer_instructions, consumer_instructions)
        └── returns None when all pairs in the topic returned None (no failing pairs)
  └── FixSuggestionsReport(suggestions_by_topic=[...only TopicFixSuggestions that are not None...])
```

`_build_block` extracts the bare class name from `schema_id` via `rsplit("/", 1)[1]`
(e.g. `"my-service/OrderSchema"` → `"OrderSchema"`) for use in the message header.

### Block Format

```
In `OrderSchema`, make the following changes to satisfy the contract with service-b/OrderConsumer:

1. Change the type of field 'amount' from 'string' to 'integer'.
2. Add 'created_at' as a required field.
```

### Per-Rule Instruction Mapping

All data required for each instruction is already present in `violation.producer`,
`violation.consumer`, and `violation.field_path` — no additional context needed.
Variables `producer` and `consumer` refer to `violation.producer` and `violation.consumer`.

| Rule | Producer instruction | Consumer instruction |
|---|---|---|
| `TYPE_MISMATCH` | `"Change the type of field '{path}' from '{producer[type]}' to '{consumer[type]}'."` | `"Change the type of field '{path}' from '{consumer[type]}' to '{producer[type]}'."` |
| `MISSING_FIELD` | `"Add '{path}' as a required field."` | `"Add a 'load_default' to field '{path}', or mark it as not required."` |
| `REQUIREMENT_MISMATCH` | `"Mark field '{path}' as required."` | `"Add a 'load_default' to field '{path}', or mark it as not required."` |
| `NULLABILITY_MISMATCH` | `"Remove the nullable constraint from field '{path}'."` | `"Mark field '{path}' as nullable."` |
| `DIRECTION_MISMATCH` | `"Remove the load-only constraint from field '{path}' so it is included in serialised output."` | `"Mark field '{path}' as dump-only, or remove the expectation of receiving it from the producer."` |
| `STRUCTURE_MISMATCH` | `"Replace the open map for field '{path}' with a fixed-schema nested object."` | `"Replace the fixed-schema nested object for field '{path}' with an open map."` |
| `UNDECLARED_FIELD` | `"Remove field '{path}' from your schema, or rename it to match a field declared in the consumer."` | `"Declare field '{path}' in your schema, or change the unknown field policy from 'forbid' to 'ignore' or 'allow'."` |
| `METADATA_ALLOWED_VALUES_MISMATCH` | `"Restrict the allowed values for field '{path}' to {consumer[allowed_values]}."` | `"Expand the allowed values for field '{path}' to include {producer[allowed_values]}."` |
| `METADATA_RANGE_MISMATCH` | `"Tighten the range constraint on field '{path}' to match the consumer: {consumer[range]}."` | `"Widen the range constraint on field '{path}' to accept the producer's range: {producer[range]}."` |
| `METADATA_LENGTH_MISMATCH` | `"Tighten the length constraint on field '{path}' to match the consumer: {consumer[length]}."` | `"Widen the length constraint on field '{path}' to accept the producer's length: {producer[length]}."` |
| `METADATA_KEY_MISMATCH` | `"Change metadata '{key}' on field '{path}' to '{consumer[key]}'."` | `"Change metadata '{key}' on field '{path}' to '{producer[key]}'."` |

> **`METADATA_KEY_MISMATCH` note:** the `violation.producer` and `violation.consumer` dicts each
> contain a single key-value pair where the key is the metadata attribute name (e.g.
> `{"format": "iso8601"}`). Extract the key via `next(iter(violation.consumer))`.

> **`METADATA_ALLOWED_VALUES_MISMATCH` — unconstrained producer case:** when
> `violation.producer == {"allowed_values": None}` the producer instruction becomes:
> `"Add an allowed-values constraint to field '{path}' whose values are a subset of
> {consumer[allowed_values]}."` — the consumer instruction stays the same.

> **Rules not covered:** `COUNTERPART_MISMATCH` (WARNING severity, workflow issue — not a
> schema change) produces no fix suggestion. `_instruction_for` returns `None` for this rule;
> `suggest_fixes` filters it out before assembly.


---


## 2. CLI Changes — `cli/validate.py`

### New Flag (both commands)

```
--how-to-fix    Show copy-paste fix suggestions for each failing pair. [default: False]
```

### Rendering Logic

When `--how-to-fix` is passed, the CLI calls `build_contracts_fix_report(validation_report)`
once to obtain a `FixSuggestionsReport`, then passes it to `print_fix_suggestions`. No domain
calls happen inside the renderer — it purely walks the pre-built structure.

`print_report` is not modified — the two concerns are fully separate.

The output mirrors the structure of `print_report`: topic as the top-level grouping, pair header
on the next level, fix blocks indented underneath — so the developer can scan both outputs with
the same mental model.

**`validate-local-contracts --how-to-fix`**:

```
Fix Suggestions

  orders
       service-a/OrderSchema vs service-b/OrderConsumer

         Fix on your side (Producer) — copy & paste to your agent:

           In `OrderSchema`, make the following changes to satisfy the contract with service-b/OrderConsumer:

           1. Change the type of field 'amount' from 'string' to 'integer'.
           2. Add 'created_at' as a required field.

         Fix on their side (Consumer) — copy & paste to your agent:

           In `OrderConsumer`, make the following changes to satisfy the contract with service-a/OrderSchema:

           1. Change the type of field 'amount' from 'integer' to 'string'.
           2. Add a 'load_default' to field 'created_at', or mark it as not required.
```

The local side is inferred per pair: if `pair.producer_id.startswith(local_name + "/")` the
producer block is labelled **"Fix on your side (Producer)"** and the consumer block **"Fix on
their side (Consumer)"**; if `pair.consumer_id.startswith(local_name + "/")` the labels swap.
This correctly handles repositories that contain both a producer and a consumer schema (e.g. a
middleware service).

**`validate-published-contracts --how-to-fix`** — symmetrical, no local bias:

```
Fix Suggestions

  orders
       service-a/OrderSchema vs service-b/OrderConsumer

         Fix on Producer side — copy & paste to your agent:

           In `OrderSchema`, make the following changes to satisfy the contract with service-b/OrderConsumer:

           1. Change the type of field 'amount' from 'string' to 'integer'.

         Fix on Consumer side — copy & paste to your agent:

           In `OrderConsumer`, make the following changes to satisfy the contract with service-a/OrderSchema:

           1. Change the type of field 'amount' from 'integer' to 'string'.
```

### Passing `local_name` to the Renderer

`print_fix_suggestions(fix_report: FixSuggestionsReport, *, local_name: str | None)` receives a
pre-built `FixSuggestionsReport`. The renderer iterates `fix_report.suggestions_by_topic` (each a
`TopicFixSuggestions`) for the topic line, then `topic.pairs` (each a `PairFixSuggestion`)
beneath it. Because `FixSuggestionsReport` is sparse, every topic and pair present in the
structure has suggestions — no conditional skipping is needed.

When `local_name` is `None` (published mode), the renderer uses symmetrical "Producer / Consumer"
labels with no inference. `config.name` is already available from `Config()` — no extra
loading or class inspection needed.

---


## 3. Data Flow

```
[CLI] validate-local-contracts --how-to-fix
  │
  ├── service: validate_local_contracts(...)  → ContractsValidationReport
  │                                              (unchanged — no fix logic here)
  ├── [CLI] print_report(report, verbose=verbose)
  │     └── for each ContractReport → topic header
  │           └── for each PairViolations → pair header + violations (unchanged)
  │
  ├── [CLI] domain: build_contracts_fix_report(report) → FixSuggestionsReport
  │     └── 3-level transformation, CRITICAL violations only
  │           (sparse — passing pairs and empty topics omitted)
  │
  └── [CLI] print_fix_suggestions(fix_report, local_name=config.name)
        └── "Fix Suggestions" header
            └── for each TopicFixSuggestions → topic line
                  └── for each PairFixSuggestion:
                        ├── pair header  (pair.producer_id vs pair.consumer_id)
                        ├── infer local side via pair.producer_id.startswith(local_name+"/")
                        └── render pair.producer_instructions and pair.consumer_instructions
                              with context-aware labels

  └── exit 0 / 1
```

`build_contracts_fix_report` is called once before rendering, not per-pair inside the renderer.
The renderer is a pure structural walk — no domain logic inside it.

---


## 4. Test Strategy

| Layer | File | What is tested |
|---|---|---|
| Domain (instruction level) | `tests/unit/test_domain/test_fix_suggestions.py` | Per-rule: `suggest_fixes` returns a `PairFixSuggestion` whose `producer_instructions` and `consumer_instructions` match the mapping table in this doc |
| Domain (block assembly) | `tests/unit/test_domain/test_fix_suggestions.py` | Multi-violation pair produces a numbered list under the correct header in both `producer_instructions` and `consumer_instructions` |
| Domain (aggregation) | `tests/unit/test_domain/test_report.py` | `FixSuggestionsReport.has_suggestions` is `False` for empty report and `True` when at least one topic is present |
| CLI | existing CLI integration tests | `--how-to-fix` flag presence and correct label switching (local vs published) |
