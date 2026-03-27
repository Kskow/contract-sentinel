# Design — Fix Suggestions

## Architecture Overview

```
Domain Layer:   fix_suggestions.py — pure transformation: PairViolations → PairFixSuggestion
CLI Layer:      cli/validate.py — renders PairFixSuggestion with context-aware labels;
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
class PairFixSuggestion:
    producer_fix: str   # consolidated prompt block — producer applies this to satisfy consumer
    consumer_fix: str   # consolidated prompt block — consumer applies this to satisfy producer
```

### Public Interface

```python
def suggest_fixes(pair: PairViolations) -> PairFixSuggestion | None:
    ...
```

Returns `None` when the pair has no CRITICAL violations — caller skips rendering entirely.

### Internal Call Chain

```
suggest_fixes(pair)
  └── filters violations to CRITICAL only
  └── for each violation → _instruction_for(violation) → (producer_instr: str, consumer_instr: str)
  └── _build_block(class_name, counterpart_id, producer_instrs) → producer_fix
  └── _build_block(class_name, counterpart_id, consumer_instrs) → consumer_fix
```

`_build_block` extracts the bare class name from `schema_id` (e.g. `"my-service/OrderSchema"`
→ `"OrderSchema"`) for use in the message header.

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
> the caller filters it out before assembly.


---


## 2. CLI Changes — `cli/validate.py`

### New Flag (both commands)

```
--how-to-fix    Show copy-paste fix suggestions for each failing pair. [default: False]
```

### Rendering Logic

Fix suggestions are rendered by a dedicated `print_fix_suggestions(report, *, local_name)` function,
called from the CLI command after `print_report` when `--how-to-fix` is passed. `print_report`
is not modified — the two concerns are fully separate.

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

`print_fix_suggestions(report, *, local_name: str | None)` receives the local repository name
(`config.name`). The renderer iterates `report.reports` (each a `ContractReport`) to get the
topic, then iterates `contract_report.pairs` beneath it — the same two-level loop used by
`print_report`.

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
  ├── [CLI] print_fix_suggestions(report, local_name=config.name)
  │     └── "Fix Suggestions" header
  │         └── for each ContractReport → topic line  (mirrors print_report)
  │               └── for each PairViolations:
  │                     ├── pair header  (mirrors print_report)
  │                     ├── infer local side via producer_id.startswith(local_name+"/")
  │                     └── domain: suggest_fixes(pair) → PairFixSuggestion | None
  │                           └── render two indented fix blocks with context-aware labels
  │
  └── exit 0 / 1
```

`suggest_fixes` is called at render time, not during validation. Validation and suggestion
generation are fully decoupled — running without `--how-to-fix` has zero overhead.

---


## 4. Test Strategy

| Layer | File | What is tested |
|---|---|---|
| Domain | `tests/unit/test_domain/test_fix_suggestions.py` | Per-rule: producer instruction text, consumer instruction text; `suggest_fixes` returns `None` for a passing pair; multi-violation block assembles correctly with numbered list and correct header |
| CLI | existing CLI integration tests | `--how-to-fix` flag presence and correct label switching (local vs published) |
