# Change Log

## Unreleased

### Added

* Assertion preparation and graph projections that retain original source fields,
  record IDs, multiple relationship types, and contributing evidence.
* A data-audit command with relationship accounting, inverse-pair coverage,
  component diagnostics, artifact hashes, and source provenance.
* Explicit ancestor, descendant, root-family, and component queries, plus
  non-destructive cycle diagnostics and condensation mappings.
* Reproducible synthetic benchmarks that verify equivalent results before
  reporting query timings and process peak memory.
* An analysis command producing query comparisons, relationship-specific
  rankings, bounded source traces, figures, and a validated run manifest.
* A synthetic analysis fixture, verified notebook, temporary-kernel execution
  script, and separate notebook CI job.
* A published analysis of the pinned Etymological WordNet 2013-02-08 corpus,
  including compact artifacts and source assertion examples.
* An engineering case study and figures connecting modeling choices, analytical
  findings, performance measurements, and reproducibility instructions.

### Changed

* Default legacy subgraph selection uses shared traversals. Legacy cycle removal
  uses strongly connected components while retaining its destructive removal
  contract; existing public selection and mutation behavior remains documented.
* Documentation distinguishes historical exploration from the verified analysis
  workflow, explains graph and measurement limits, and preserves dataset
  attribution separately from the code license.

## v0.0.1 -- 2021-06-19

-----------------------

### Features

* Project initialized with cookiecutter template.

### Bug-Fixes

* No bug fixes.
