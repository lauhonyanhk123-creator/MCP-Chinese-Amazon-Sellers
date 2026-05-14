# Code Cleanup Spec

## Why
The codebase has accumulated redundant files, duplicate test structures, and untracked artifacts that should be cleaned up to maintain code quality and reduce confusion.

## What Changes

### Files to Remove
- **audit.log** - Untracked log file, should be gitignored or removed
- **test_server.py** - Duplicate test file (tests/ directory has proper test structure)
- **test_api.py** - Duplicate test file
- **test_routes.py** - Duplicate test file  
- **load_testing_docs.py** - Standalone file, functionality exists elsewhere

### Files to Consolidate
- **launcher_cn.py** - Chinese launcher, consolidate into start_prod.sh with language support

### Gitignore Updates
- Add audit.log
- Add *.log rotation patterns
- Clean up temporary files

### Code Quality
- Run ruff linter to fix import ordering and style issues
- Remove any dead code paths
- Consolidate duplicate utility functions

## Impact
- Affected code: Multiple Python files, git configuration
- Cleaner repository structure
- Faster CI/CD (fewer redundant tests)

## ADDED Requirements

### Requirement: Gitignore Configuration
The .gitignore file SHALL include all generated and log files.

#### Scenario: Git status clean
- **WHEN** user runs `git status`
- **THEN** only relevant source files are untracked (no .log, .pyc, __pycache__)

### Requirement: Consolidated Test Structure
The project SHALL have a single test directory structure under tests/.

#### Scenario: Test discovery
- **WHEN** pytest runs
- **THEN** all tests are discovered from tests/ directory only
