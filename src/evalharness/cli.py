from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from evalharness import __version__
from evalharness.domain.results import RunSummary
from evalharness.engine.runner import run_dataset
from evalharness.evaluators.registry import available_evaluators
from evalharness.exit_codes import ExitCode
from evalharness.loading.errors import DatasetError
from evalharness.loading.loader import load_dataset
from evalharness.reporting import console, json_report, junit

app = typer.Typer(
    name="evalharness",
    help="Deterministic regression testing for language-model outputs.",
    add_completion=False,
    no_args_is_help=True,
)

PathArg = Annotated[Path, typer.Argument(help="Test case file or directory.")]
TagsOpt = Annotated[
    str | None, typer.Option("--tags", help="Comma-separated tags; keeps cases matching any.")
]


def _fail(message: str, code: ExitCode) -> None:
    typer.secho(f"error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(int(code))


def _load(path: Path, tags: str | None):
    try:
        dataset = load_dataset(path)
    except DatasetError as exc:
        _fail(str(exc), ExitCode.INVALID_DATASET)
    selected = {tag.strip() for tag in tags.split(",") if tag.strip()} if tags else set()
    filtered = dataset.filter_by_tags(selected)
    if selected and not len(filtered):
        _fail(f"no cases match tags {sorted(selected)}", ExitCode.USAGE_ERROR)
    return filtered


def _emit(text: str, output: Path | None) -> None:
    if output is None:
        typer.echo(text)
        return
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    except OSError as exc:
        _fail(f"cannot write {output}: {exc.strerror}", ExitCode.USAGE_ERROR)
    typer.echo(f"Wrote {output}")


def _render(summary: RunSummary, fmt: str, verbose: bool) -> str:
    if fmt == "json":
        return json_report.render(summary)
    if fmt == "junit":
        return junit.render(summary)
    return console.render(summary, verbose=verbose)


@app.command()
def run(
    path: PathArg,
    fmt: Annotated[str, typer.Option("--format", help="text, json or junit.")] = "text",
    output: Annotated[Path | None, typer.Option("--output", help="Write report to a file.")] = None,
    fail_under: Annotated[
        float | None, typer.Option("--fail-under", help="Minimum acceptable mean score (0.0-1.0).")
    ] = None,
    fail_fast: Annotated[bool, typer.Option("--fail-fast", help="Stop at first failure.")] = False,
    tags: TagsOpt = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", help="Show passing assertions too.")
    ] = False,
    exit_code: Annotated[
        bool,
        typer.Option("--exit-code/--no-exit-code", help="Exit non-zero when the gate fails."),
    ] = True,
) -> None:
    """Evaluate recorded outputs against a suite of test cases."""
    if fmt not in {"text", "json", "junit"}:
        _fail(f"unknown format {fmt!r}; expected text, json or junit", ExitCode.USAGE_ERROR)
    if fail_under is not None and not 0.0 <= fail_under <= 1.0:
        _fail("--fail-under must be between 0.0 and 1.0", ExitCode.USAGE_ERROR)

    dataset = _load(path, tags)
    summary = run_dataset(dataset, fail_fast=fail_fast, fail_under=fail_under)
    _emit(_render(summary, fmt, verbose), output)

    if exit_code and not summary.meets_gate:
        raise typer.Exit(int(ExitCode.EVALUATION_FAILED))


@app.command()
def validate(path: PathArg) -> None:
    """Check that every case parses and every evaluator is configured correctly."""
    try:
        dataset = load_dataset(path)
    except DatasetError as exc:
        _fail(str(exc), ExitCode.INVALID_DATASET)
    typer.echo(f"{len(dataset)} case(s) valid across {len(dataset.sources)} file(s).")


@app.command("list")
def list_cases(path: PathArg, tags: TagsOpt = None) -> None:
    """List case ids, tags and evaluator types."""
    dataset = _load(path, tags)
    for case in dataset:
        kinds = ",".join(spec.type for spec in case.evaluators)
        label = " ".join(f"#{tag}" for tag in case.tags)
        typer.echo(f"{case.id}\t{kinds}\t{label}")


@app.command()
def inspect(
    path: PathArg,
    case_id: Annotated[str, typer.Argument(help="Case id to inspect.")],
) -> None:
    """Print a single resolved case as JSON."""
    dataset = _load(path, None)
    case = dataset.get(case_id)
    if case is None:
        _fail(f"no case with id {case_id!r}", ExitCode.USAGE_ERROR)
    typer.echo(json.dumps(case.model_dump(mode="json"), indent=2))


@app.command()
def report(
    report_file: Annotated[Path, typer.Argument(help="A JSON report written by 'run'.")],
    fmt: Annotated[str, typer.Option("--format", help="text or json.")] = "text",
) -> None:
    """Re-render a stored JSON report."""
    if fmt not in {"text", "json"}:
        _fail(f"unknown format {fmt!r}; expected text or json", ExitCode.USAGE_ERROR)
    try:
        payload = json.loads(report_file.read_text(encoding="utf-8"))
    except OSError as exc:
        _fail(f"cannot read {report_file}: {exc.strerror}", ExitCode.USAGE_ERROR)
    except json.JSONDecodeError as exc:
        _fail(f"{report_file} is not valid JSON: {exc.msg}", ExitCode.INVALID_DATASET)

    if fmt == "json":
        typer.echo(json.dumps(payload, indent=2))
        return
    try:
        stats = payload["summary"]
        typer.echo(
            f"{stats['total']} case(s): {stats['passed']} passed, "
            f"{stats['failed']} failed, {stats['errored']} errored"
        )
        typer.echo(f"Mean score: {stats['score']:.3f}")
        for case in payload["cases"]:
            typer.echo(f"{case['status'].upper():<7} {case['id']}  score={case['score']:.3f}")
    except (KeyError, TypeError) as exc:
        _fail(f"{report_file} is not an evalharness report ({exc})", ExitCode.INVALID_DATASET)


@app.command()
def evaluators() -> None:
    """List the available evaluator types."""
    for name in available_evaluators():
        typer.echo(name)


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


def main() -> None:
    try:
        app()
    except DatasetError as exc:
        _fail(str(exc), ExitCode.INVALID_DATASET)
