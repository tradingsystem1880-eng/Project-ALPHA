# Atlas frontend scanning with the TypeScript compiler (ts-morph)

**Status:** Idea
**Rough size:** S

## Problem / why

Atlas extracts frontend API calls with guarded regular expressions (every path must join
openapi.json, a method-count floor, unmatched usages fail loud). A ts-morph scanner was deferred
because it adds a Node toolchain to the Python generation pipeline.

## What "done" looks like

Frontend edges come from the TypeScript compiler; the existing guards still hold; generation
stays deterministic and `generate --check` stays clean.

## Dependencies

A decision to accept a Node step in Atlas generation.

## Sources

- [Atlas design plan, alternatives and frontend scanning](../../superpowers/plans/archive/2026-08/2026-08-20-project-alpha-atlas-design.md)
