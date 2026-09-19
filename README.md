# ai-evaluation-test-harness

A deterministic regression-testing framework for language-model outputs.

`evalharness` is a test-engineering tool, not a chatbot and not a model. It takes
outputs that have already been produced, evaluates them against structured,
version-controlled test cases, and reports the result in a form CI can act on.

## The problem

You cannot regression-test a language model by re-running it and diffing the
output: the output legitimately changes between runs. So the usual approach —
snapshot the string, fail on any difference — produces a suite that is either
permanently red or quietly disabled.

This tool inverts the problem. **The model output is data; the assertions are the
deterministic part.** You capture an output once, commit it alongside the
assertions that should hold for it, and the harness re-checks those assertions.
Every evaluator is pure: same inputs, same score, every time. A red run therefore
means the recorded output changed, never that the harness drifted.

Two consequences follow, and both are deliberate:

- **It runs fully offline.** No API key, no network, no cost, no rate limit. The
  entire test suite and every bundled example run on a laptop with the network
  off, which is what makes it usable as a required CI check.
- **It separates "the output regressed" from "your suite is broken."** These exit
  with different codes, because a malformed YAML file should not look like a
  quality regression.

## Installation

```bash
git clone https://github.com/adamshahbari/ai-evaluation-test-harness
cd ai-evaluation-test-harness
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Requires Python 3.12 or newer.

## Quick start

```bash
evalharness run examples/                       # evaluate every bundled suite
evalharness run examples/json-extraction        # one suite
evalharness validate examples/                  # parse and config-check only
evalharness list examples/ --tags refund        # filter by tag
evalharness run examples/ --format json --output reports/run.json
evalharness run examples/ --fail-under 0.9      # gate the mean score
```

## Test case format

A suite is a YAML or JSON file containing a list of cases, or a mapping with a
`cases` key. Files are discovered recursively.

```yaml
cases:
  - id: refund-window-stated
    input: "How long do I have to return an item?"
    expected: "You have 30 days from delivery to request a return."
    actual: "Returns are accepted within 30 days of delivery."
    tags: [support, refund]
    threshold: 0.75
    evaluators:
      - type: contains
        weight: 2.0
        config:
          values: ["30 days"]
      - type: not_contains
        config:
          values: ["no refunds", "final sale"]
      - type: token_overlap
        weight: 1.0
        config:
          method: f1
          min_score: 0.4
```

| Field | Meaning |
|---|---|
| `id` | Unique across the whole run. Duplicates are a load error. |
| `input` | The prompt. Recorded for context; evaluators do not read it. |
| `expected` | Reference output, used by comparison evaluators. |
| `actual` | The recorded output under test. |
| `tags` | Free-form labels for `--tags` filtering. |
| `threshold` | Case passes when its weighted score reaches this. Default `1.0`. |
| `evaluators` | One or more evaluator specs: `type`, optional `weight`, optional `config`. |
| `metadata` | Arbitrary mapping, carried through untouched. |

### Scoring

Each evaluator returns a score in `[0.0, 1.0]`. The case score is the
**weighted mean** of those scores, and the case passes when
`score >= threshold`. A run passes when every case passes, or — if `--fail-under`
is given — when the mean case score reaches that value.

Weight `0` keeps an evaluator visible in reports without letting it affect the
verdict, which is useful when introducing a new check before enforcing it.

## Evaluators

| Type | Purpose | Key options |
|---|---|---|
| `exact_match` | Normalised string equality | `ignore_case`, `strip`, `collapse_whitespace` |
| `contains` | Required substrings | `values`, `mode` (`all`/`any`), `ignore_case` |
| `not_contains` | Forbidden substrings | `values`, `ignore_case` |
| `regex` | Pattern match | `pattern`, `mode` (`search`/`fullmatch`), `flags`, `should_match` |
| `json_schema` | Structured output validation | `schema` (JSON Schema draft 2020-12) |
| `numeric_tolerance` | Numeric closeness | `tolerance`, `mode` (`absolute`/`relative`) |
| `required_fields` | Key presence and key/value checks | `fields`, `values` (dotted paths) |
| `token_overlap` | Lexical token overlap | `method` (`f1`/`jaccard`), `stopwords`, `min_score` |
| `composite` | Nests evaluators | `evaluators`, `mode` (`all`/`any`/`weighted`) |

Every evaluator accepts `min_score`, the score at which that individual
assertion counts as passing. It defaults to `1.0` for binary evaluators and
`0.8` for `token_overlap`.

### On `token_overlap`, and what it is not

`token_overlap` computes **token-set F1 or Jaccard overlap after
normalisation**. It is lexical. It is not semantic similarity, it is not an
embedding, and it does not use a model.

This matters because the failure mode is severe and non-obvious:

> `"the refund is approved"` vs `"the refund is not approved"`
> → F1 overlap **0.89**

The strings are near-identical and the meaning is opposite. Any tool that called
this "semantic similarity" would be lying to you at exactly the moment you most
need the truth. So it is named for the mechanism, not the aspiration.

Use it as a **weighted drift signal** with a low `min_score`, paired with a
`not_contains` or `regex` check that catches negation directly. Do not use it as
a case's only evaluator. The bundled `policy-regression` suite demonstrates this
pairing.

## Reporting

```bash
evalharness run examples/ --format text     # default; failures with reasons
evalharness run examples/ --format text --verbose   # passing assertions too
evalharness run examples/ --format json --output reports/run.json
evalharness run examples/ --format junit --output reports/junit.xml
evalharness report reports/run.json         # re-render a stored report
```

The JSON report carries a `schema_version` so downstream tooling can depend on
its shape. The JUnit XML is consumable by any CI test reporter.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Every case passed, or the `--fail-under` gate was met |
| `1` | Evaluation failed — an output regressed |
| `2` | Usage error — bad flag, unknown format, no cases matched `--tags` |
| `3` | Invalid dataset — unparseable file, unknown evaluator, duplicate id |
| `4` | Internal error |

`1` and `3` are deliberately distinct. A pipeline that treats "your YAML has a
typo" as "quality dropped" will train people to ignore the check.

Use `--no-exit-code` to always exit `0` when you want the report but not the gate.

## CI usage

```yaml
- run: evalharness validate examples/
- run: evalharness run examples/ --fail-under 0.9 --format junit --output reports/junit.xml
```

`validate` first is worth the extra second: it fails fast and unambiguously on a
broken suite, before any evaluation runs.

This repository's own workflow lints, runs the unit tests, executes the bundled
suites, and asserts that a deliberately-regressed suite exits `1` — so the gate
itself is tested, not assumed.

## Architecture

```
src/evalharness/
  domain/       TestCase, EvaluatorSpec, Dataset, Assertion, EvaluationResult, RunSummary
  evaluators/   base protocol, registry, nine implementations
  loading/      discovery, parsing, validation, error types
  engine/       runner and weighted scoring
  reporting/    console, JSON, JUnit renderers
  cli.py        Typer command surface
  exit_codes.py the process contract
```

The dependency direction is one-way: `domain` knows nothing about evaluators,
evaluators know nothing about loading, and `reporting` depends only on result
types. The runner is the only component that sees all of them.

### Design decisions

**Evaluators are constructed at load time, then again at run time.** `validate`
builds every evaluator to surface configuration errors without executing
anything, so a bad regex or malformed JSON Schema is caught before a long run
starts rather than midway through.

**A misconfigured evaluator errors the case; it does not fail it.** `ERRORED` is
a distinct status from `FAILED` and forces the run to fail regardless of
`--fail-under`, because an error means the check did not run — which is not the
same as the output being wrong, and must never be averaged away.

**Relative tolerance around zero degrades to absolute.** Dividing by an expected
value of `0` has no meaningful answer, so rather than raising or returning
infinity, the comparison falls back to an absolute one and says so in the detail
string.

**Composite nesting is capped at five levels.** Deeply nested scoring trees are
unreadable in a report, and the cap turns a config mistake into a clear error
rather than a stack overflow.

## Limitations

- It evaluates **recorded outputs**. It does not call any model. Capturing
  outputs is the caller's job, and is deliberately out of scope.
- `token_overlap` is lexical and cannot detect paraphrase or negation. See above.
- Scoring is a weighted mean. It has no opinion about whether your weights are
  sensible.
- There is no statistical significance testing, no multi-run aggregation and no
  flakiness detection.
- The bundled example suites are small, hand-written illustrations of the format.
  They are not a benchmark and no accuracy claim is made from them.

## Development

```bash
pytest                       # full suite
pytest --cov=evalharness     # with coverage
ruff check .                 # lint
ruff format --check .        # formatting
```

## Licence

MIT. See [LICENSE](LICENSE).
