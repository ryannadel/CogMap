# Changelog

All notable changes to CogMap will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses semantic versioning for public releases.

## [Unreleased]

### Added

- MIT license for public use and redistribution.
- Contribution guide with validation and skill-sync instructions.
- GitHub Actions CI that compiles Python, runs tests, and verifies the mirrored
  agent skill is synchronized.
- Regression tests for date parsing and bundled demo refresh.

### Fixed

- Preserved valid 29th, 30th, and 31st day-of-month values during date parsing
  instead of silently truncating them to the 28th.

### Changed

- Improved the public README with clearer prerequisites, demo guidance, install
  paths, and release-readiness notes.
