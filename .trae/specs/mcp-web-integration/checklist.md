# MCP Web Integration Checklist

## API Layer
- [x] /api/tools returns list of all available MCP tools
- [x] Each MCP tool has corresponding /api/tools/<tool_name> endpoint
- [x] API validates request parameters
- [x] API returns proper error messages for invalid requests
- [x] API handles async tool calls correctly

## Competitor Prices Page
- [x] /competitor page loads without errors
- [x] Search form accepts ASIN or keyword input
- [x] Search results display competitor pricing data
- [x] Page is bilingual (Chinese/English)
- [x] Homepage links to /competitor
- [x] "Coming Soon" badge removed from homepage

## Review Alerts Page
- [x] /reviews page loads without errors
- [x] Filter options work (rating, product, date)
- [x] Negative reviews display with suggested responses
- [x] Page is bilingual (Chinese/English)
- [x] Homepage links to /reviews
- [x] "Coming Soon" badge removed from homepage

## Dashboard Page
- [x] /dashboard page loads without errors
- [x] Displays low stock alerts summary
- [x] Displays recent orders summary
- [x] Displays review alerts summary
- [x] Refresh button updates all data
- [x] Page is bilingual (Chinese/English)

## Integration
- [x] /inventory page uses real MCP tool data
- [x] Loading states shown during API calls
- [x] Error handling for failed tool calls
- [x] All pages follow existing design pattern

## Background Tasks
- [x] Long operations return task ID immediately
- [x] Task status can be queried via API
- [x] UI shows task progress
- [x] Task results available when complete
