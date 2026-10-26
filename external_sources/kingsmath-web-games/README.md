# KingsMath Web Games Library (AASHA Prebuilt Harvest Resource)

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)
![Games: 190+](https://img.shields.io/badge/Games-197%20Ingested-blue.svg)

## Overview
This directory stores the official, harvested open-source source codes of **197 interactive educational web games** from [KingsMath.com](https://kingsmath.com) (Upstream repository: `https://github.com/kingsmath/web-games`).
These single-file HTML5 games form the foundation library for:
- **Foundation F23**: King's Math 10-Frame & Place Value Manipulative (`king10`, `king10blast`)
- **Foundation F24**: King's Math Dynamic Fraction & Decimal Slices (`kingpizza`, `kingfraction`)
- **Foundation F25**: King's Math Number-Line Hunter & Factor Finder (`kingline`, `kinglinedraw`)
- **Foundation F26**: King's Math Interactive Symmetry & Geometry Fold (`kingsymmetry`, `kinggeometry`)
- **Foundation F27**: King's Math Universal Gamified Assessment Engine (`kingspeedracing`, `kingfrog`, `kingtrash`, `king_science_foodweb`)

## AASHA Cleanroom Architecture
AASHA AIOS extracts and decouples the core mechanics (Lane Dodging, Lilypad Stepping, Category Sorting, Memory Matching) into the cleanroom adapter `Aasha-AI/experience_registry/adapters/aasha_gamified_assessment_adapter.js` under the `AashaExperienceContract` interface.
- **Runtime Zero CDN**: Stripped of external tracking and Google Tag Manager.
- **Procedural Web Audio**: Native oscillator synthesis (`AudioContext`).
- **Universal Decoupling**: Hardcoded arithmetic is replaced with open curriculum assessment specifications (`GamifiedAssessmentSpec`).

## License & Attribution
Licensed under **CC BY-NC 4.0** (Creative Commons Attribution-NonCommercial 4.0 International).
- **Attribution**: Powered by [KingsMath (KingsMath.com)](https://kingsmath.com).
- **Non-Commercial**: Strictly for non-commercial educational use within non-profit, classroom, and public educational environments.
