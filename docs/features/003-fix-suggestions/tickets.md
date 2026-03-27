# Fix Suggestions — Dev Tickets

**Feature slug:** `003-fix-suggestions`
**Spec:** `docs/features/003-fix-suggestions/product_spec.md`
**Design:** `docs/features/003-fix-suggestions/design.md`
**Created:** 2026-03-27

---

## Architecture Notes

### No New Adapters, No New Services

This feature is entirely additive and touches only two layers:

- **Domain** — `domain/report.py` gains two new data classes. A new pure module
  `domain/fix_suggestions.py` handles all transformation logic. Zero I/O.

  | Validation | Fix |
  |---|---|
  | `Violation` | `FixSuggestion` (transient, internal to `suggest_fixes`) |
  | `PairViolations` | `PairFixSuggestion` |
  | `ContractReport` | `TopicFixSuggestions` |
  | `ContractsValidationReport` | `FixSuggestionsReport` |

- **CLI** — `cli/validate.py` gains a `--how-to-fix` flag on both commands and a new standalone
  renderer `print_fix_suggestions`. `print_report` is not modified.

### Data Flow

```
[CLI] validate-local-contracts --how-to-fix
  │
  ├── service: validate_local_contracts(store, parser, loader, config)
  │     └── returns ContractsValidationReport (unchanged)
  ├── print_report(report, verbose=verbose)                                        ← unchanged
  ├── domain: build_contracts_fix_report(report) → FixSuggestionsReport           ← one call
  └── print_fix_suggestions(fix_report, local_name=config.name)
        └── walks fix_report.suggestions_by_topic → TopicFixSuggestions.pairs → PairFixSuggestion
              └── infer local side per pair: pair.producer_id.startswith(local_name+"/")
              └── render pair.producer_instructions / pair.consumer_instructions

[CLI] validate-published-contracts --how-to-fix
  ├── domain: build_contracts_fix_report(report) → FixSuggestionsReport
  └── print_fix_suggestions(fix_report, local_name=None)                          ← symmetrical labels
```

### New / Modified Files

```
contract_sentinel/
├── domain/
│   ├── report.py          ← TopicFixSuggestions, FixSuggestionsReport added
│   └── fix_suggestions.py ← new: FixSuggestion, PairFixSuggestion,
│                                  suggest_fixes, build_contracts_fix_report,
│                                  _suggest_contract_fixes, _instruction_for, _build_block

tests/
└── unit/
    └── test_domain/
        ├── test_report.py          ← FixSuggestionsReport.has_suggestions tests added
        └── test_fix_suggestions.py ← new
```

```
contract_sentinel/cli/validate.py   ← --how-to-fix flag (both commands), print_fix_suggestions
```

### Key Implementation Notes

- `suggest_fixes(pair: PairViolations) -> PairFixSuggestion | None` is the **pair-level entry
  point**. Returns `None` when the pair has no CRITICAL violations.
- `build_contracts_fix_report(report: ContractsValidationReport) -> FixSuggestionsReport` is the
  **report-level entry point** used by the CLI. Always returns a `FixSuggestionsReport` — never
  `None`. An empty `FixSuggestionsReport(suggestions_by_topic=[])` represents "no suggestions".
  The CLI checks `fix_report.has_suggestions` before rendering.
- `_suggest_contract_fixes(contract_report: ContractReport) -> TopicFixSuggestions | None` —
  returns `None` when all pairs in the topic pass. `build_contracts_fix_report` filters `None`
  values out before building `FixSuggestionsReport.suggestions_by_topic`.
- `FixSuggestion` is transient — used only inside `suggest_fixes` to pair instructions before
  passing them to `_build_block`, then discarded. It is never stored on `PairFixSuggestion`.
- `PairFixSuggestion` is a pure value object: `producer_id`, `consumer_id`,
  `producer_instructions: str`, `consumer_instructions: str`. Both instruction strings are built
  from the same `list[FixSuggestion]` in a single expression, ensuring item N on the producer
  side always corresponds to item N on the consumer side.
- `_build_block` extracts the bare class name from `schema_id` via `rsplit("/", 1)[1]`.
- `METADATA_KEY_MISMATCH`: extract the metadata key name via `next(iter(violation.consumer))`.
- `METADATA_ALLOWED_VALUES_MISMATCH` — unconstrained producer case: when
  `violation.producer == {"allowed_values": None}`, the producer instruction reads
  `"Add an allowed-values constraint to field '{path}' whose values are a subset of {consumer[allowed_values]}."`
- `print_fix_suggestions` receives a pre-built `FixSuggestionsReport` — **no domain calls inside
  the renderer**. The renderer is a pure structural walk. Local side inference happens in the
  renderer, per pair, using `pair.producer_id.startswith(local_name + "/")`.
- `FixSuggestionsReport` is **sparse**: topics where all pairs pass are excluded from
  `suggestions_by_topic`; pairs with no CRITICAL violations are excluded from
  `TopicFixSuggestions.pairs`. The renderer iterates without any conditional checks.
- No IAM, no env vars, no LocalStack — this feature has no infrastructure requirements.

---

## Tickets

### TICKET-01 — Domain: fix suggestion hierarchy and `build_contracts_fix_report` ✅

**Depends on:** —
**Type:** Domain

**Goal:**
Implement the pure domain module that transforms a full `ContractsValidationReport` into a
`FixSuggestionsReport` — a parallel 3-level hierarchy of consolidated fix prompt blocks.

**Files created / modified:**
- `contract_sentinel/domain/report.py` — `TopicFixSuggestions`, `FixSuggestionsReport` added
- `contract_sentinel/domain/fix_suggestions.py` — created
- `tests/unit/test_domain/test_report.py` — `FixSuggestionsReport.has_suggestions` tests added
- `tests/unit/test_domain/test_fix_suggestions.py` — created

**Done when:**
- [x] `FixSuggestion` dataclass exists with `producer_instruction: str` and
      `consumer_instruction: str` fields.
- [x] `PairFixSuggestion` dataclass exists with `producer_id: str`, `consumer_id: str`,
      `producer_instructions: str`, and `consumer_instructions: str` fields.
- [x] `TopicFixSuggestions` dataclass exists in `report.py` with `topic: str` and
      `pairs: list[PairFixSuggestion]` fields.
- [x] `FixSuggestionsReport` dataclass exists in `report.py` with
      `suggestions_by_topic: list[TopicFixSuggestions]` and a `has_suggestions: bool` property.
- [x] `suggest_fixes(pair: PairViolations) -> PairFixSuggestion | None` returns `None` when
      the pair has no CRITICAL violations.
- [x] `build_contracts_fix_report(report: ContractsValidationReport) -> FixSuggestionsReport`
      is the report-level public function. It never returns `None`.
- [x] `build_contracts_fix_report` returns `FixSuggestionsReport(suggestions_by_topic=[])` when
      the validation report contains no CRITICAL violations.
- [x] Topics where all pairs pass are excluded from `FixSuggestionsReport.suggestions_by_topic`.
- [x] Passing pairs within a failing topic are excluded from `TopicFixSuggestions.pairs`.
- [x] For each of the eleven rules — `TYPE_MISMATCH`, `REQUIREMENT_MISMATCH`,
      `NULLABILITY_MISMATCH`, `MISSING_FIELD`, `UNDECLARED_FIELD`, `DIRECTION_MISMATCH`,
      `STRUCTURE_MISMATCH`, `METADATA_ALLOWED_VALUES_MISMATCH`, `METADATA_RANGE_MISMATCH`,
      `METADATA_LENGTH_MISMATCH`, `METADATA_KEY_MISMATCH` — a unit test calls `suggest_fixes`
      with a single-violation pair and asserts `producer_instructions` and
      `consumer_instructions` match the mapping table in `design.md`.
- [x] A unit test with two violations asserts both numbered items appear in the correct order
      in `producer_instructions` and `consumer_instructions`.
- [x] `domain/fix_suggestions.py` imports nothing from `cli/`, `adapters/`, or any I/O library.
- [x] `just check` passes.

---

### TICKET-02 — CLI: `print_fix_suggestions` renderer and `--how-to-fix` on `validate-local-contracts`

**Depends on:** TICKET-01
**Type:** CLI

**Goal:**
Add `--how-to-fix` to `sentinel validate-local-contracts` and implement the standalone
`print_fix_suggestions` renderer with contextual "your side / their side" labelling.

**Files to create / modify:**
- `contract_sentinel/cli/validate.py` — modify

**Done when:**
- [ ] `--how-to-fix` flag exists on `sentinel validate-local-contracts` and defaults to `False`.
- [ ] `print_fix_suggestions(fix_report: FixSuggestionsReport, *, local_name: str | None)` is a
      standalone function, separate from `print_report`. `print_report` signature is unchanged.
- [ ] When `--how-to-fix` is passed, `build_contracts_fix_report(validation_report)` is called
      once to obtain a `FixSuggestionsReport`, then `print_fix_suggestions(fix_report,
      local_name=config.name)` is called after `print_report`. No domain calls happen inside
      `print_fix_suggestions` — it is a pure structural walk.
- [ ] `print_fix_suggestions` is a no-op (prints nothing) when `fix_report.has_suggestions`
      is `False`.
- [ ] Output mirrors the structure of `print_report`: a `"Fix Suggestions"` top-level header,
      then topic lines, then pair headers at the same indentation as `print_report`, then fix
      blocks indented one level further underneath each pair.
- [ ] The renderer iterates `fix_report.suggestions_by_topic` (each a `TopicFixSuggestions`)
      and then `topic.pairs` (each a `PairFixSuggestion`) — no conditional skipping needed
      because the domain has already filtered out passing topics and pairs.
- [ ] For each pair, the local side is inferred dynamically: if `pair.producer_id` starts with
      `local_name + "/"` the producer block is labelled `"Fix on your side (Producer) — copy &
      paste to your agent:"` and the consumer block `"Fix on their side (Consumer) — copy &
      paste to your agent:"`; if `pair.consumer_id` starts with `local_name + "/"` the labels
      swap.
- [ ] A repo containing both a producer and a consumer schema produces correct "your side"
      labels for each pair independently — not a single global role applied to all pairs.
- [ ] Running `sentinel validate-local-contracts` without `--how-to-fix` produces output
      identical to before — `build_contracts_fix_report` and `print_fix_suggestions` are not called.
- [ ] `just check` passes.

---

### TICKET-03 — CLI: `--how-to-fix` on `validate-published-contracts`

**Depends on:** TICKET-02
**Type:** CLI

**Goal:**
Wire the existing `print_fix_suggestions` renderer to `sentinel validate-published-contracts`
with symmetrical "Producer / Consumer" labelling.

**Files to create / modify:**
- `contract_sentinel/cli/validate.py` — modify

**Done when:**
- [ ] `--how-to-fix` flag exists on `sentinel validate-published-contracts` and defaults to `False`.
- [ ] When `--how-to-fix` is passed, `build_contracts_fix_report(validation_report)` is called
      once to obtain a `FixSuggestionsReport`, then `print_fix_suggestions(fix_report,
      local_name=None)` is called after `print_report`.
- [ ] With `local_name=None`, blocks are labelled `"Fix on Producer side — copy & paste to
      your agent:"` and `"Fix on Consumer side — copy & paste to your agent:"` — no "your
      side" language.
- [ ] Output mirrors `print_report` structure: `"Fix Suggestions"` header, topic lines, pair
      headers, fix blocks indented underneath.
- [ ] Running `sentinel validate-published-contracts` without `--how-to-fix` produces output
      identical to before.
- [ ] `just check` passes.
