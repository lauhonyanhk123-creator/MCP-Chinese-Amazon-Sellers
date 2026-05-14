# Low Stock Alerts Web UI - The Implementation Plan (Decomposed and Prioritized Task List)

## [x] Task 1: Add Bilingual TEXT entries for Inventory Alerts
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - Add Chinese and English text keys for the low stock alerts page UI elements
  - Include labels for threshold, platform filter, alert columns, etc.
- **Acceptance Criteria Addressed**: AC-5
- **Test Requirements**:
  - `programmatic` TR-1.1: All new TEXT keys exist for both languages
  - `human-judgement` TR-1.2: Text translations are accurate and natural
- **Notes**: Follow the existing TEXT structure in web_app.py

## [x] Task 2: Create inventory.html template
- **Priority**: P0
- **Depends On**: Task 1
- **Description**: 
  - Create new inventory.html template extending base.html
  - Follow the same design pattern as profit.html
  - Include platform filter dropdown
  - Include threshold input field
  - Display alerts in a responsive grid or table
  - Show severity indicators with appropriate colors/icons
- **Acceptance Criteria Addressed**: AC-1, AC-4, AC-5
- **Test Requirements**:
  - `human-judgement` TR-2.1: Page visually matches design of Profit Calculator
  - `programmatic` TR-2.2: All template placeholders are present
  - `human-judgement` TR-2.3: Severity icons are displayed correctly

## [x] Task 3: Add /inventory route to web_app.py
- **Priority**: P0
- **Depends On**: Task 2
- **Description**: 
  - Add GET route for /inventory
  - Reuse the mock data generation pattern from server.py
  - Implement platform filtering
  - Implement custom threshold support
  - Pass alerts data to template
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-3, AC-5
- **Test Requirements**:
  - `programmatic` TR-3.1: /inventory route returns 200 OK
  - `programmatic` TR-3.2: Platform filter works (1688/Amazon/both)
  - `programmatic` TR-3.3: Custom threshold updates alerts correctly

## [x] Task 4: Update navigation links
- **Priority**: P1
- **Depends On**: Task 3
- **Description**: 
  - Remove "Coming Soon" badge from homepage Low Stock Alerts card
  - Make homepage card clickable, linking to /inventory
  - Make nav bar "库存管理" / "Inventory" link active when on inventory page
- **Acceptance Criteria Addressed**: AC-6, AC-7
- **Test Requirements**:
  - `programmatic` TR-4.1: Homepage card links to /inventory
  - `programmatic` TR-4.2: Nav bar link works and shows active state

## [ ] Task 5: Add API endpoint for inventory alerts (optional enhancement)
- **Priority**: P2
- **Depends On**: Task 3
- **Description**: 
  - Add /api/inventory/alerts endpoint
  - Support platform and threshold query parameters
  - Return JSON for future AJAX use
- **Acceptance Criteria Addressed**: AC-2, AC-3
- **Test Requirements**:
  - `programmatic` TR-5.1: API endpoint returns valid JSON
  - `programmatic` TR-5.2: API supports filtering and threshold parameters

## [x] Task 6: Add visual polish and responsive testing
- **Priority**: P1
- **Depends On**: Task 4
- **Description**: 
  - Test page on various screen sizes
  - Ensure consistent spacing and alignment
  - Add subtle animations/transitions for better UX
  - Verify all links and interactive elements work
- **Acceptance Criteria Addressed**: AC-1, AC-4
- **Test Requirements**:
  - `human-judgement` TR-6.1: Page looks good on mobile (< 640px)
  - `human-judgement` TR-6.2: Page looks good on tablet (640-1024px)
  - `human-judgement` TR-6.3: Page looks good on desktop (> 1024px)
