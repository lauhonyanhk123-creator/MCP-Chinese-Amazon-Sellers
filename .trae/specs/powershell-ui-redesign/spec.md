# PowerShell-Style UI Redesign Spec

## Why
Transform the Cross-Border Seller MCP web interface into a Windows PowerShell-inspired terminal aesthetic. This creates a distinctive, professional look that appeals to technical users and differentiates the product from generic web dashboards.

## What Changes
- Complete visual redesign with PowerShell terminal aesthetic
- Dark theme with classic PowerShell blue background
- Monospace typography throughout
- Terminal-style command input and output display
- ASCII art and box-drawing characters for UI elements
- Green/white/yellow text colors matching PowerShell syntax highlighting
- Scanline and CRT effects for authenticity

## Impact
- Affected specs: All web UI components
- Affected code: `templates/` directory, `static/css/`, `web_app.py` template rendering

## ADDED Requirements

### Requirement: PowerShell Visual Theme
The system SHALL provide a Windows PowerShell-inspired visual theme with:
- Dark navy blue background (#012456 - classic PowerShell blue)
- Monospace font family (Consolas, 'Courier New', monospace)
- White primary text (#FFFFFF)
- Green accent for success/commands (#00FF00)
- Yellow accent for warnings (#FFFF00)
- Red accent for errors (#FF0000)
- Cyan accent for informational text (#00FFFF)

#### Scenario: User views dashboard
- **WHEN** user navigates to any page
- **THEN** the page displays with PowerShell terminal aesthetic
- **AND** all text uses monospace typography
- **AND** background is dark navy blue

### Requirement: Terminal-Style Navigation
The system SHALL provide terminal-style navigation with:
- Command-prompt style menu items (e.g., `> Dashboard`, `> Inventory`)
- Breadcrumb displayed as directory path (e.g., `C:\Seller\Dashboard>`)
- Current location indicator with blinking cursor

#### Scenario: User navigates between pages
- **WHEN** user clicks navigation item
- **THEN** page transitions with terminal-style animation
- **AND** breadcrumb updates to show current "directory"

### Requirement: Command Input Interface
The system SHALL provide a command input area styled as PowerShell prompt:
- Prompt symbol (PS C:\Seller>)
- Blinking cursor animation
- Command history support (up/down arrows)
- Auto-complete suggestions in terminal style

#### Scenario: User enters command
- **WHEN** user types in command input
- **THEN** text appears with syntax highlighting
- **AND** suggestions appear in dropdown below prompt

### Requirement: Data Display as Terminal Output
The system SHALL display data tables and lists as terminal output:
- ASCII box-drawing characters for table borders
- Column headers in yellow
- Data rows alternating subtle background tint
- Row numbers in cyan

#### Scenario: User views inventory list
- **WHEN** user views inventory data
- **THEN** data displays in ASCII-style table
- **AND** headers are highlighted in yellow
- **AND** low stock items show in red

### Requirement: ASCII Art Elements
The system SHALL use ASCII art for:
- Logo/branding
- Section headers
- Loading indicators
- Success/error icons

#### Scenario: Application loads
- **WHEN** user opens the application
- **THEN** ASCII art logo displays
- **AND** loading animation shows terminal-style progress

## MODIFIED Requirements

### Requirement: Existing Dashboard
The dashboard SHALL be redesigned with:
- PowerShell-style command cards instead of regular cards
- Terminal window containers for each section
- Minimize/maximize/close buttons styled as terminal window controls

### Requirement: Existing Forms
All forms SHALL use terminal input styling:
- Single-line inputs with underscore placeholder
- Submit buttons styled as command execution
- Validation errors displayed as terminal error messages

## REMOVED Requirements
None - this is a visual redesign that enhances existing functionality.
