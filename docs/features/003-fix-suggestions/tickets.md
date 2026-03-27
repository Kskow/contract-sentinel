# Fix Suggestions — Dev Tickets

**Feature slug:** `003-fix-suggestions`
**Spec:** `docs/features/003-fix-suggestions/product_spec.md`
**Design:** `docs/features/003-fix-suggestions/design.md`
**Created:** 2026-03-27

---

## Architecture Notes

### No New Adapters, No New Services

This feature is entirely additive and touches only two layers:

- **Domain** — one new pure module `domain/fix_suggestions.py`. Zero I/O. Consumes a
  `ContractsValidationReport` and returns a `ContractsFixReport` — a parallel 4-level hierarchy
  mirroring the validation report exactly:

  | Validation | Fix |
  |---|---|
  | `Violation` | `FixSuggestion` |
  | `PairViolations` | `PairFixSuggestion` |
  | `ContractReport` | `ContractFixReport` |
  | `ContractsValidationReport` | `ContractsFixReport` |

  No changes to existing domain files.
- **CLI** — `cli/validate.py` gains a `--how-to-fix` flag on both commands and a new standalone
  renderer `print_fix_suggestions`. `print_report` is not modified.

### Data Flow

```
[CLI] validate-local-contracts --how-to-fix
  │
  ├── service: validate_local_contracts(store, parser, loader, config)
  │     └── returns ContractsValidationReport (unchanged)
  ├── print_report(report, verbose=verbose)                              ← unchanged
  ├── domain: suggest_fixes(report) → ContractsFixReport                ← one call, not per-pair
  └── print_fix_suggestions(fix_report, local_name=config.name)
        └── walks fix_report.topics → ContractFixReport.pairs → PairFixSuggestion
              └── infer local side per pair: pair.producer_id.startswith(local_name+"/")
              └── render two indented fix blocks with context-aware labels

[CLI] validate-published-contracts --how-to-fix
  ├── domain: suggest_fixes(report) → ContractsFixReport
  └── print_fix_suggestions(fix_report, local_name=None)                ← symmetrical labels
```

### New Files

```
contract_sentinel/
└── domain/
    └── fix_suggestions.py    ← FixSuggestion, PairFixSuggestion, ContractFixReport,
                                 ContractsFixReport, suggest_fixes, _suggest_contract_fixes,
                                 _suggest_pair_fixes, _instruction_for, _build_block

tests/
└── unit/
    └── test_domain/
        └── test_fix_suggestions.py
```

### Modified Files

```
contract_sentinel/cli/validate.py   ← --how-to-fix flag (both commands), print_fix_suggestions
```

### Key Implementation Notes

- `suggest_fixes(report: ContractsValidationReport) -> ContractsFixReport` is the **public entry
  point**. Always returns a `ContractsFixReport` — never `None`. An empty
  `ContractsFixReport(topics=[])` represents "no suggestions". The CLI checks
  `fix_report.has_suggestions` before rendering.
- `_suggest_contract_fixes(contract_report: ContractReport) -> ContractFixReport | None` — returns
  `None` when all pairs in the topic pass (i.e. every `_suggest_pair_fixes` call returned `None`).
  `suggest_fixes` filters `None` values out before building `ContractsFixReport.topics`.
- `_suggest_pair_fixes(pair: PairViolations) -> PairFixSuggestion | None` — the private core.
  Filters to CRITICAL violations only; returns `None` when none remain. `COUNTERPART_MISMATCH` is
  WARNING severity and is excluded by this filter. Builds a `list[FixSuggestion]` (one per CRITICAL
  violation) and wraps it in `PairFixSuggestion`. Both `producer_id` and `consumer_id` on the
  returned object are always non-`None` (guaranteed by the CRITICAL-only filter).
- `_instruction_for(violation) -> FixSuggestion | None` — matches on `violation.rule`; returns a
  `FixSuggestion(producer_instruction, consumer_instruction)`. Returns `None` for
  `COUNTERPART_MISMATCH` (WARNING, not a schema change); the caller filters `None` out.
- `FixSuggestion` is the atomic unit — one per CRITICAL violation, mirroring `Violation`.
  `PairFixSuggestion.suggestions: list[FixSuggestion]` is the single source of truth.
- `producer_fix` and `consumer_fix` on `PairFixSuggestion` are **computed properties** that call
  `_build_block` — they are never stored redundantly as fields.
- `_build_block` extracts the bare class name from `schema_id` via `rsplit("/", 1)[1]`.
- `METADATA_KEY_MISMATCH`: extract the metadata key name via `next(iter(violation.consumer))`.
- `METADATA_ALLOWED_VALUES_MISMATCH` — unconstrained producer case: when
  `violation.producer == {"allowed_values": None}`, the producer instruction reads
  `"Add an allowed-values constraint to field '{path}' whose values are a subset of {c.allowed_values}."`
- `print_fix_suggestions` receives a pre-built `ContractsFixReport` — **no domain calls inside the
  renderer**. The renderer is a pure structural walk. Local side inference happens in the renderer,
  per pair, using `pair.producer_id.startswith(local_name + "/")`.
- `ContractsFixReport` is **sparse**: topics where all pairs pass are excluded from
  `topics`; pairs with no CRITICAL violations are excluded from `ContractFixReport.pairs`. The
  renderer iterates without any conditional checks — everything present must be printed.
- No IAM, no env vars, no LocalStack — this feature has no infrastructure requirements.

---

## Tickets

### TICKET-01 — Domain: fix suggestion hierarchy and `suggest_fixes`

**Depends on:** —
**Type:** Domain

**Goal:**
Implement the pure domain module that transforms a full `ContractsValidationReport` into a
`ContractsFixReport` — a parallel 3-level hierarchy of consolidated fix prompt blocks.

**Files to create / modify:**
- `contract_sentinel/domain/fix_suggestions.py` — create
- `tests/unit/test_domain/test_fix_suggestions.py` — create

**Done when:**
- [ ] `FixSuggestion` dataclass exists with `producer_instruction: str` and
      `consumer_instruction: str` fields.
- [ ] `PairFixSuggestion` dataclass exists with `producer_id: str`, `consumer_id: str`, and
      `suggestions: list[FixSuggestion]` fields. `producer_fix` and `consumer_fix` are computed
      properties (not stored fields) that delegate to `_build_block`.
- [ ] `ContractFixReport` dataclass exists with `topic: str` and
      `pairs: list[PairFixSuggestion]` fields.
- [ ] `ContractsFixReport` dataclass exists with `topics: list[ContractFixReport]` and a
      `has_suggestions: bool` property that returns `True` when `topics` is non-empty.
- [ ] `suggest_fixes(report: ContractsValidationReport) -> ContractsFixReport` is the sole
      public function. It never returns `None`.
- [ ] `suggest_fixes` returns `ContractsFixReport(topics=[])` when the validation report
      contains no CRITICAL violations.
- [ ] `suggest_fixes` excludes topics where all pairs pass — only topics with at least one
      failing pair appear in `ContractsFixReport.topics`.
- [ ] `suggest_fixes` excludes passing pairs within a failing topic — only pairs with at least
      one CRITICAL violation appear in `ContractFixReport.pairs`.
- [ ] `_suggest_pair_fixes(pair)` (private) returns `None` when the pair contains no CRITICAL
      violations; returns a `PairFixSuggestion` with a non-empty `suggestions` list otherwise.
- [ ] For each of the eleven rules — `TYPE_MISMATCH`, `REQUIREMENT_MISMATCH`,
      `NULLABILITY_MISMATCH`, `MISSING_FIELD`, `UNDECLARED_FIELD`, `DIRECTION_MISMATCH`,
      `STRUCTURE_MISMATCH`, `METADATA_ALLOWED_VALUES_MISMATCH`, `METADATA_RANGE_MISMATCH`,
      `METADATA_LENGTH_MISMATCH`, `METADATA_KEY_MISMATCH` — a unit test calls `_suggest_pair_fixes`
      with a single-violation pair and asserts `pair.suggestions[0].producer_instruction` and
      `pair.suggestions[0].consumer_instruction` match the mapping table in `design.md`.
- [ ] A unit test with two violations in one pair asserts `len(pair.suggestions) == 2` and that
      `pair.producer_fix` (the property) assembles a numbered list (`1.`, `2.`) under the correct
      header naming both the schema class and the counterpart (e.g. `"In \`OrderSchema\`, make
      the following changes to satisfy the contract with B/OrderConsumer:"`).
- [ ] A unit test asserts `suggest_fixes` called with an all-passing `ContractsValidationReport`
      returns `ContractsFixReport(topics=[])` and `has_suggestions` is `False`.
- [ ] A unit test asserts that a topic where all pairs pass is excluded from
      `ContractsFixReport.topics` when other topics have failures.
- [ ] `domain/fix_suggestions.py` imports nothing from `cli/`, `adapters/`, or any I/O library.
- [ ] `just check` passes.

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
- [ ] `print_fix_suggestions(fix_report: ContractsFixReport, *, local_name: str | None)` is a
      standalone function, separate from `print_report`. `print_report` signature is unchanged.
- [ ] When `--how-to-fix` is passed, `suggest_fixes(validation_report)` is called once in the
      CLI command to obtain a `ContractsFixReport`, then `print_fix_suggestions(fix_report,
      local_name=config.name)` is called after `print_report`. No domain calls happen inside
      `print_fix_suggestions` — it is a pure structural walk.
- [ ] `print_fix_suggestions` is a no-op (prints nothing) when `fix_report.has_suggestions`
      is `False`.
- [ ] Output mirrors the structure of `print_report`: a `"Fix Suggestions"` top-level header,
      then topic lines, then pair headers at the same indentation as `print_report`, then fix
      blocks indented one level further underneath each pair.
- [ ] The renderer iterates `fix_report.topics` (each a `ContractFixReport`) and then
      `contract_fix_report.pairs` (each a `PairFixSuggestion`) — no conditional skipping needed
      because the domain has already filtered out passing topics and pairs.
- [ ] For each pair, the local side is inferred dynamically: if `pair.producer_id` starts with
      `local_name + "/"` the producer block is labelled `"Fix on your side (Producer) — copy &
      paste to your agent:"` and the consumer block `"Fix on their side (Consumer) — copy &
      paste to your agent:"`; if `pair.consumer_id` starts with `local_name + "/"` the labels
      swap.
- [ ] A repo containing both a producer and a consumer schema produces correct "your side"
      labels for each pair independently — not a single global role applied to all pairs.
- [ ] Running `sentinel validate-local-contracts` without `--how-to-fix` produces output
      identical to before — `suggest_fixes` and `print_fix_suggestions` are not called.
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
- [ ] When `--how-to-fix` is passed, `suggest_fixes(validation_report)` is called once to
      obtain a `ContractsFixReport`, then `print_fix_suggestions(fix_report, local_name=None)`
      is called after `print_report`.
- [ ] With `local_name=None`, blocks are labelled `"Fix on Producer side — copy & paste to
      your agent:"` and `"Fix on Consumer side — copy & paste to your agent:"` — no "your
      side" language.
- [ ] Output mirrors `print_report` structure: `"Fix Suggestions"` header, topic lines, pair
      headers, fix blocks indented underneath.
- [ ] Running `sentinel validate-published-contracts` without `--how-to-fix` produces output
      identical to before.
- [ ] `just check` passes.
