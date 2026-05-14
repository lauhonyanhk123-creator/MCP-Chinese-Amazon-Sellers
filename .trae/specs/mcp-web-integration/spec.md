# MCP Web Integration Spec

## Why
The current MCP server provides 21 powerful tools for cross-border sellers, but they're only accessible via CLI/Claude Desktop. Users need a web interface to access these tools directly without AI assistance.

## What Changes
- Integrate MCP server tools into Flask web app
- Create web UI pages for each major feature category
- Add REST API endpoints that wrap MCP tool calls
- Support authentication and session management
- Create interactive forms and dashboards

## Impact
- Affected specs: Low Stock Alerts Web UI
- Affected code: server.py, web_app.py, new templates, API routes

## ADDED Requirements

### Requirement: MCP Tool API Layer
The system SHALL provide REST API endpoints that wrap MCP tool calls.

#### Scenario: Call MCP tool via HTTP
- **WHEN** user makes POST request to `/api/tools/<tool_name>` with required parameters
- **THEN** system calls corresponding MCP tool and returns result as JSON

#### Scenario: List available tools
- **WHEN** user requests GET `/api/tools`
- **THEN** system returns list of available MCP tools with descriptions and parameters

### Requirement: Competitor Prices Web Page
The system SHALL provide a web page to analyze competitor prices on Amazon.

#### Scenario: View competitor analysis
- **WHEN** user navigates to `/competitor` page
- **THEN** system displays interface to search Amazon products and view competitor pricing data

#### Scenario: Search competitors
- **WHEN** user enters ASIN or keyword and clicks search
- **THEN** system calls `get_competitor_prices` tool and displays results

### Requirement: Review Alerts Web Page
The system SHALL provide a web page to monitor and respond to product reviews.

#### Scenario: View review alerts
- **WHEN** user navigates to `/reviews` page
- **THEN** system displays recent negative reviews and suggested responses

#### Scenario: Filter reviews
- **WHEN** user selects filter options (rating, product, date range)
- **THEN** system filters and displays matching reviews

### Requirement: Unified Dashboard
The system SHALL provide a dashboard showing key metrics from multiple MCP tools.

#### Scenario: View dashboard
- **WHEN** user navigates to `/dashboard` page
- **THEN** system displays summary cards with low stock count, recent orders, review alerts

### Requirement: Background Processing
The system SHALL support asynchronous execution of MCP tools for long-running operations.

#### Scenario: Start background task
- **WHEN** user initiates a sync operation
- **THEN** system queues task and returns task ID immediately

#### Scenario: Check task status
- **WHEN** user queries `/api/tasks/<task_id>`
- **THEN** system returns task status and results when complete

## MODIFIED Requirements

### Requirement: Low Stock Alerts Web UI
The Low Stock Alerts page SHALL now use real MCP tool data instead of mock data.

#### Scenario: Fetch real inventory data
- **WHEN** user loads `/inventory` page
- **THEN** system calls `get_low_stock_alerts` MCP tool and displays results

## REMOVED Requirements
None.

## Technical Approach

### Architecture
1. **API Layer**: Flask routes that call MCP tools synchronously
2. **Web Layer**: Jinja templates for rendering UI
3. **Data Flow**: Web UI → Flask Route → MCP Tool → JSON Response → Template

### Implementation Strategy
1. Start with REST API endpoints for all tools
2. Build web pages progressively (Competitor Prices, Review Alerts, Dashboard)
3. Replace mock data with real MCP calls
4. Add task queue for long operations
5. Add caching layer for expensive operations
