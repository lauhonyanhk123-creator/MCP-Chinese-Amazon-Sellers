# MCP Web Integration Tasks

- [x] Task 1: Create MCP Tool API Layer
  - Implement REST API endpoints wrapping MCP tools in web_app.py
  - Create /api/tools endpoint to list all available tools
  - Create /api/tools/<tool_name> endpoint for each tool
  - Add request/response validation
  - Test API endpoints with curl
  - **Depends on**: None

- [x] Task 2: Build Competitor Prices Web Page
  - Create /competitor route in web_app.py
  - Create competitor.html template
  - Add search form with ASIN/keyword input
  - Display competitor pricing results
  - Add bilingual support
  - Link from homepage to /competitor
  - **Depends on**: Task 1

- [x] Task 3: Build Review Alerts Web Page
  - Create /reviews route in web_app.py
  - Create reviews.html template
  - Add filter options (rating, product, date range)
  - Display negative reviews and suggested responses
  - Add bilingual support
  - Link from homepage to /reviews
  - **Depends on**: Task 1

- [x] Task 4: Build Dashboard Page
  - Create /dashboard route in web_app.py
  - Create dashboard.html template
  - Display summary cards: low stock count, recent orders, review alerts
  - Add refresh functionality
  - Add bilingual support
  - **Depends on**: Tasks 1, 2, 3

- [x] Task 5: Integrate MCP Tools into Existing Pages
  - Replace mock data in /inventory with real MCP tool calls
  - Add loading states and error handling
  - Test integration end-to-end
  - **Depends on**: Task 1

- [x] Task 6: Add Background Task Support
  - Implement simple task queue for long operations
  - Create /api/tasks/<task_id> endpoint
  - Add polling mechanism for task status
  - Update UI to show task progress
  - **Depends on**: Tasks 1, 4

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 1
- Task 4 depends on Tasks 1, 2, 3
- Task 5 depends on Task 1
- Task 6 depends on Tasks 1, 4
