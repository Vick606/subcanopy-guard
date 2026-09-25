# Contributing to Subcanopy Guard

Thanks for your interest. Before contributing, please read this document.

## Contributor License Agreement

All contributions require a signed [Contributor License Agreement](CLA.md). This is required to maintain the dual-licensing model that funds the project. Pull requests without a signed CLA cannot be merged.

## Development Setup

    git clone https://github.com/Vick606/subcanopy-guard
    cd subcanopy-guard
    uv sync
    uv run pytest

## Running Tests

    uv run pytest
    uv run pytest --cov=subcanopy_guard

## Linting

    uv run ruff check .
    uv run ruff format .

## Commit Convention

Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`.
