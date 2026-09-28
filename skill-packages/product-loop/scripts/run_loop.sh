#!/usr/bin/env bash
# Compatibility refusal: the former runner admitted missing bundles/budgets and used eval.
printf '%s\n' 'BLOCKED: legacy runner retired. Use the reviewed local cycle_adapter.py contract in references/runner.md.' >&2
exit 2
