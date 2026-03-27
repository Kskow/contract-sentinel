# Design — Fix Suggestions

## Architecture Overview

```
Domain Layer:   fix_suggestions.py — pure transformation: ContractsValidationReport → ContractsFixReport
                                     3-level hierarchy mirroring the validation report:
                                     ContractsFixReport → ContractFixReport → PairFixSuggestion
CLI Layer:      cli/validate.py — renders ContractsFixReport with context-aware labels;
                                  honours --how-to-fix flag on both validate commands
```

No new adapters, no new services, no new config. This feature is entirely additive — two
existing CLI commands grow a flag, and one new domain module handles all the logic.

### File Placement

| Module | File | Change |
|---|---|---|
| Fix suggestion logic | `contract_sentinel/domain/fix_suggestions.py` | **new** |
| Validate CLI commands | `contract_sentinel/cli/validate.py` | **modified** — `--how-to-fix` flag + rendering |
| Fix suggestion unit tests | `tests/unit/test_domain/test_fix_suggestions.py` | **new** |

---

## 1. Domain Module — `fix_suggestions.py`

### Data Model

```python
@dataclasses.dataclass
class FixSuggestion:
    """Atomic fix unit — one per CRITICAL violation. Mirrors Violation."""
    producer_instruction: str   # what the producer must change
    consumer_instruction: str   # what the consumer must change

@dataclasses.dataclass
class PairFixSuggestion:
    producer_id: str
    consumer_id: str
    suggestions: list[FixSuggestion]   # mirrors PairViolations.violations

    @property
    def producer_fix(self) -> str:
        """Consolidated numbered prompt block for the producer side."""
        ...  # assembled by _build_block from [s.producer_instruction for s in suggestions]

    @property
    def consumer_fix(self) -> str:
        """Consolidated numbered prompt block for the consumer side."""
        ...  # assembled by _build_block from [s.consumer_instruction for s in suggestions]

@dataclasses.dataclass
class ContractFixReport:
    topic: str
    pairs: list[PairFixSuggestion]   # sparse — only pairs with CRITICAL violations

@dataclasses.dataclass
class ContractsFixReport:
    topics: list[ContractFixReport]  # sparse — only topics with at least one failing pair

    @property
    def has_suggestions(self) -> bool:
        return len(self.topics) > 0
```

`producer_fix` and `consumer_fix` are **computed properties** — they call `_build_block`
at access time. `suggestions` is the single source of truth; the rendered strings are derived
from it, so there is no redundant storage.

The fix report is a **sparse view** of the validation report. Topics where all pairs pass are
omitted from `ContractsFixReport.topics`. Pairs with no CRITICAL violations are omitted from
`ContractFixReport.pairs`. This means the CLI renderer can iterate the fix report without any
conditional skipping — everything present needs to be printed.

### Public Interface

```python
def suggest_fixes(report: ContractsValidationReport) -> ContractsFixReport:
    ...
```

Always returns a `ContractsFixReport` — never `None`. An empty `ContractsFixReport(topics=[])`
represents "no suggestions". The caller checks `fix_report.has_suggestions` before rendering.

### Internal Call Chain

```
suggest_fixes(report: ContractsValidationReport)
  └── for each ContractReport → _suggest_contract_fixes(contract_report) → ContractFixReport | None
        └── for each PairViolations → _suggest_pair_fixes(pair) → PairFixSuggestion | None
              └── filters violations to CRITICAL only; returns None if none remain
              └── for each CRITICAL violation → _instruction_for(violation) → FixSuggestion | None
              └── PairFixSuggestion(producer_id, consumer_id, suggestions=[...FixSuggestions...])
                    └── .producer_fix  (property) → _build_block(producer_id, consumer_id, producer_instrs)
                    └── .consumer_fix  (property) → _build_block(consumer_id, producer_id, consumer_instrs)
        └── returns None when all pairs in the topic returned None (no failing pairs)
  └── ContractsFixReport(topics=[...only ContractFixReports that are not None...])
```

`_build_block` extracts the bare class name from `schema_id` via `rsplit("/", 1)[1]`
(e.g. `"my-service/OrderSchema"` → `"OrderSchema"`) for use in the message header.

### Block Format

```
In `OrderSchema`, make the following changes to satisfy the contract with B/OrderConsumer:

1. Change the type of field 'amount' from 'string' to 'integer'.
2. Add 'created_at' as a required field.
```

### Per-Rule Instruction Mapping

All data required for each instruction is already present in `violation.producer`,
`violation.consumer`, and `violation.field_path` — no additional context needed.

| Rule | Producer instruction | Consumer instruction |
|---|---|---|
| `TYPE_MISMATCH` | `"Change the type of field '{path}' from '{p.type}' to '{c.type}'."` | `"Change the type of field '{path}' from '{c.type}' to '{p.type}'."` |
| `MISSING_FIELD` | `"Add '{path}' as a required field."` | `"Add a 'load_default' to field '{path}', or mark it as not required."` |
| `REQUIREMENT_MISMATCH` | `"Mark field '{path}' as required."` | `"Add a 'load_default' to field '{path}', or mark it as not required."` |
| `NULLABILITY_MISMATCH` | `"Remove the nullable constraint from field '{path}'."` | `"Mark field '{path}' as nullable."` |
| `DIRECTION_MISMATCH` | `"Remove the load-only constraint from field '{path}' so it is included in serialised output."` | `"Mark field '{path}' as dump-only, or remove the expectation of receiving it from the producer."` |
| `STRUCTURE_MISMATCH` | `"Replace the open map for field '{path}' with a fixed-schema nested object."` | `"Replace the fixed-schema nested object for field '{path}' with an open map."` |
| `UNDECLARED_FIELD` | `"Remove field '{path}' from your schema, or rename it to match a field declared in the consumer."` | `"Declare field '{path}' in your schema, or change the unknown field policy from 'forbid' to 'ignore' or 'allow'."` |
| `METADATA_ALLOWED_VALUES_MISMATCH` | `"Restrict the allowed values for field '{path}' to {c.allowed_values}."` | `"Expand the allowed values for field '{path}' to include {p.allowed_values}."` |
| `METADATA_RANGE_MISMATCH` | `"Tighten the range constraint on field '{path}' to match the consumer: {c.range}."` | `"Widen the range constraint on field '{path}' to accept the producer's range: {p.range}."` |
| `METADATA_LENGTH_MISMATCH` | `"Tighten the length constraint on field '{path}' to match the consumer: {c.length}."` | `"Widen the length constraint on field '{path}' to accept the producer's length: {p.length}."` |
| `METADATA_KEY_MISMATCH` | `"Change metadata '{key}' on field '{path}' to '{c.value}'."` | `"Change metadata '{key}' on field '{path}' to '{p.value}'."` |

> **`METADATA_KEY_MISMATCH` note:** the `violation.producer` and `violation.consumer` dicts each
> contain a single key-value pair where the key is the metadata attribute name (e.g.
> `{"format": "iso8601"}`). Extract the key via `next(iter(violation.consumer))`.

> **`METADATA_ALLOWED_VALUES_MISMATCH` — unconstrained producer case:** when
> `violation.producer == {"allowed_values": None}` the producer instruction becomes:
> `"Add an allowed-values constraint to field '{path}' whose values are a subset of
> {c.allowed_values}."` — the consumer instruction stays the same.

> **Rules not covered:** `COUNTERPART_MISMATCH` (WARNING severity, workflow issue — not a
> schema change) produces no fix suggestion. `_instruction_for` returns `None` for this rule;
> `_suggest_pair_fixes` filters it out before assembly.


---


## 2. CLI Changes — `cli/validate.py`

### New Flag (both commands)

```
--how-to-fix    Show copy-paste fix suggestions for each failing pair. [default: False]
```

### Rendering Logic

When `--how-to-fix` is passed, the CLI calls `suggest_fixes(validation_report)` once to obtain
a `ContractsFixReport`, then passes it to `print_fix_suggestions`. No domain calls happen inside
the renderer — it purely walks the pre-built structure.

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

           In `OrderSchema`, make the following changes to satisfy service-b/OrderConsumer:

           1. Change the type of field 'amount' from 'string' to 'integer'.
           2. Add 'created_at' as a required field.

         Fix on their side (Consumer) — copy & paste to your agent:

           In `OrderConsumer`, make the following changes to satisfy service-a/OrderSchema:

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

           In `OrderSchema`, make the following changes to satisfy service-b/OrderConsumer:

           1. Change the type of field 'amount' from 'string' to 'integer'.

         Fix on Consumer side — copy & paste to your agent:

           In `OrderConsumer`, make the following changes to satisfy service-a/OrderSchema:

           1. Change the type of field 'amount' from 'integer' to 'string'.
```

### Passing `local_name` to the Renderer

`print_fix_suggestions(fix_report: ContractsFixReport, *, local_name: str | None)` receives a
pre-built `ContractsFixReport`. The renderer iterates `fix_report.topics` (each a
`ContractFixReport`) for the topic line, then `contract_fix_report.pairs` (each a
`PairFixSuggestion`) beneath it. Because `ContractsFixReport` is sparse, every topic and pair
present in the structure has suggestions — no conditional skipping is needed.

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
  ├── [CLI] domain: suggest_fixes(report) → ContractsFixReport
  │     └── 3-level transformation, CRITICAL violations only
  │           (sparse — passing pairs and empty topics omitted)
  │
  └── [CLI] print_fix_suggestions(fix_report, local_name=config.name)
        └── "Fix Suggestions" header
            └── for each ContractFixReport → topic line
                  └── for each PairFixSuggestion:
                        ├── pair header  (pair.producer_id vs pair.consumer_id)
                        ├── infer local side via pair.producer_id.startswith(local_name+"/")
                        └── render two indented fix blocks with context-aware labels

  └── exit 0 / 1
```

`suggest_fixes` is called once before rendering, not per-pair inside the renderer. The renderer
is a pure structural walk — no domain logic inside it.

---


## 4. Test Strategy

| Layer | File | What is tested |
|---|---|---|
| Domain (instruction level) | `tests/unit/test_domain/test_fix_suggestions.py` | Per-rule: `_suggest_pair_fixes` returns a `PairFixSuggestion` whose `suggestions[0].producer_instruction` and `suggestions[0].consumer_instruction` match the mapping table in this doc |
| Domain (block assembly) | `tests/unit/test_domain/test_fix_suggestions.py` | `pair.producer_fix` and `pair.consumer_fix` properties assemble a numbered list under the correct header for a multi-violation pair |
| Domain (aggregation) | `tests/unit/test_domain/test_fix_suggestions.py` | `suggest_fixes` returns `ContractsFixReport(topics=[])` for an all-passing report; topics where all pairs pass are excluded; passing pairs within a failing topic are excluded |
| CLI | existing CLI integration tests | `--how-to-fix` flag presence and correct label switching (local vs published) |
