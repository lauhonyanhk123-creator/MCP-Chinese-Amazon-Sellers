# Low Stock Alerts Web UI - Product Requirement Document

## Overview
- **Summary**: Build a web UI for the existing low stock alerts backend tool that allows cross-border sellers to view and manage inventory alerts for both 1688 and Amazon platforms.
- **Purpose**: Enable sellers to quickly identify products running low on stock to prevent overselling and ensure timely restocking.
- **Target Users**: Cross-border e-commerce sellers managing inventory across 1688 (Chinese suppliers) and Amazon.

## Goals
- Build a web UI page for viewing low stock alerts
- Support filtering by platform (1688, Amazon, both)
- Allow custom threshold configuration
- Display alerts with severity indicators (critical/warning/low)
- Bilingual support (Chinese + English)
- Consistent design with existing Profit Calculator page

## Non-Goals (Out of Scope)
- Directly updating stock levels on platforms
- Automated restocking suggestions
- Historical alert tracking
- Email/SMS notifications

## Background & Context
- Existing backend tool available: [get_low_stock_alerts](file:///workspace/server.py#L1559-L1706) in server.py
- Current web UI has homepage with "Coming Soon" placeholder for Low Stock Alerts
- Database module available for product profile persistence in [database.py](file:///workspace/database.py)
- License manager already handles feature access control in [license_manager.py](file:///workspace/license_manager.py)

## Functional Requirements
- **FR-1**: Display low stock alerts from both 1688 and Amazon platforms
- **FR-2**: Allow users to filter alerts by platform (1688 only, Amazon only, both)
- **FR-3**: Allow users to customize the low stock threshold per session
- **FR-4**: Show severity indicators (🔴 critical, 🟡 warning, 🟢 low) based on stock level
- **FR-5**: Bilingual UI support (中文/English) using existing TEXT system
- **FR-6**: Link from homepage to low stock alerts page
- **FR-7**: Link from nav bar to low stock alerts page

## Non-Functional Requirements
- **NFR-1**: Page loads in < 2 seconds (with mock data)
- **NFR-2**: Responsive design (mobile, tablet, desktop)
- **NFR-3**: Reuse existing UI components and design system
- **NFR-4**: Clean visual hierarchy with clear information architecture

## Constraints
- **Technical**: Must integrate with existing Flask app
- **Business**: Must respect license tier feature access
- **Dependencies**: Reuses existing server.py tools, database.py, license_manager.py

## Assumptions
- Backend tool already has mock data support for testing (verified in test_server.py)
- License tier already includes access to low stock alerts feature
- Bilingual TEXT system is already in place

## Acceptance Criteria

### AC-1: Low Stock Alerts Page Display
- **Given**: User navigates to /inventory page
- **When**: Page loads
- **Then**: Displays a list of low stock alerts with product name, SKU, platform, current stock, threshold, shortage, and severity
- **Verification**: `human-judgment`
- **Notes**: Verify all data points are visible and correctly formatted

### AC-2: Platform Filtering
- **Given**: User is on the low stock alerts page
- **When**: User selects a platform filter (1688 only, Amazon only, both)
- **Then**: Alerts are filtered to show only the selected platform(s)
- **Verification**: `programmatic`

### AC-3: Custom Threshold
- **Given**: User is on the low stock alerts page
- **When**: User enters a custom threshold value and applies it
- **Then**: Alerts are recalculated using the new threshold
- **Verification**: `programmatic`

### AC-4: Severity Indicators
- **Given**: User is viewing low stock alerts
- **When**: Alerts are displayed
- **Then**: Each alert shows appropriate severity icon (🔴 for <5, 🟡 for 5-10, 🟢 for >10)
- **Verification**: `human-judgment`

### AC-5: Bilingual Support
- **Given**: User switches language (中文 ↔ English)
- **When**: Page reloads
- **Then**: All UI text updates to the selected language
- **Verification**: `human-judgment`

### AC-6: Navigation Links
- **Given**: User is on homepage or any page with nav bar
- **When**: User clicks "库存管理" / "Inventory"
- **Then**: Navigates to low stock alerts page
- **Verification**: `programmatic`

### AC-7: Homepage Quick Action
- **Given**: User is on homepage
- **When**: User clicks Low Stock Alerts card
- **Then**: Navigates to low stock alerts page
- **Verification**: `programmatic`

## Open Questions
- [ ] Should alerts persist across sessions using the database? (Current decision: No, keep it stateless initially)
- [ ] Should we allow bulk actions (acknowledge, dismiss) on alerts? (Current decision: No, MVP only displays alerts)
