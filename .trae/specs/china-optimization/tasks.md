# China Optimization Tasks

- [x] Task 1: Add WeChat Work Notifications
  - Add WeChat Work webhook support to notification.py
  - Create send_wechat_notification() method
  - Add WeChat message formatting (markdown support)
  - Test webhook integration
  - **Depends on**: None

- [x] Task 2: Add DingTalk Notifications
  - Add DingTalk webhook support to notification.py
  - Create send_dingtalk_notification() method
  - Add DingTalk message formatting (markdown support)
  - Test webhook integration
  - **Depends on**: None

- [x] Task 3: Update Notification Preferences UI
  - Update templates/notifications.html
  - Replace Slack option with WeChat Work + DingTalk
  - Add webhook URL input fields
  - Show China-specific options prominently
  - Add test notification buttons
  - **Depends on**: Tasks 1, 2

- [x] Task 4: Replace CDN for China Accessibility
  - Update base.html to use China-accessible CDNs
  - Replace jsdelivr with bootcsscdn or local fallback
  - Replace Chart.js CDN with bootcss version
  - Add local static file fallback
  - Test page loads in China network simulation
  - **Depends on**: None

- [x] Task 5: Add China PWA Install Options
  - Update PWA install prompt in base.html
  - Add WeChat mini-program instructions
  - Add Android APK download link (optional)
  - Add QR code for mobile installation
  - **Depends on**: None

- [x] Task 6: Update Documentation
  - Add WeChat Work setup instructions
  - Add DingTalk setup instructions
  - Document China-specific configuration
  - Add troubleshooting guide
  - **Depends on**: Tasks 1, 2, 3

# Task Dependencies
- Task 3 depends on Tasks 1, 2
- Task 6 depends on Tasks 1, 2, 3, 4, 5
