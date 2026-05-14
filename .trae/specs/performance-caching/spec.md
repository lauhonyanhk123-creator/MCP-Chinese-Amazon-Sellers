# Performance & Caching Spec

## Why
The Cross-Border Seller MCP Server handles API calls to external services (1688, Amazon) which can be slow. Adding caching and query optimization will significantly improve response times and reduce load on external APIs.

## What Changes
- Add Redis caching layer for API responses
- Add database query optimization with indexes
- Add response compression
- Add connection pooling
- Optimize slow endpoints

## Impact
- Affected code: web_app.py, database.py, new cache.py module
- External API calls reduced by 80%+ with caching
- Page load times improved by 50%+

## ADDED Requirements

### Requirement: Redis Response Caching
The system SHALL cache API responses in Redis with configurable TTL.

#### Scenario: Cache hit
- **WHEN** same API request is made within TTL window
- **THEN** return cached response without calling external API

#### Scenario: Cache miss
- **WHEN** API request has no cached response
- **THEN** call external API and cache result for future requests

### Requirement: Database Indexes
The system SHALL add database indexes for frequently queried columns.

#### Scenario: Query optimization
- **WHEN** user queries inventory or orders
- **THEN** query uses index and returns in <100ms

### Requirement: Connection Pooling
The system SHALL use connection pooling for Redis and database connections.

#### Scenario: Connection reuse
- **WHEN** multiple requests arrive
- **THEN** reuse existing connections from pool

### Requirement: Response Compression
The system SHALL compress API responses using gzip.

#### Scenario: Compressed response
- **WHEN** client accepts gzip encoding
- **THEN** return gzip-compressed response to reduce bandwidth
