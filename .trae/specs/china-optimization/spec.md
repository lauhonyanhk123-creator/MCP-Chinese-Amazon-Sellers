# China Market Optimization Spec

## Why
The current system uses Slack for notifications, but Slack is blocked in China. Chinese users need alternative notification channels that work within China's internet environment (WeChat, DingTalk, Email).

## What Changes
- Replace Slack with China-compatible alternatives
- Add WeChat Work (企业微信) webhook notifications
- Add DingTalk (钉钉) webhook notifications
- Keep email as universal fallback
- Optimize external CDN resources for China访问
- Add Chinese app store links for PWA

## Impact
- Affected specs: Notification service from world-class-enhancements
- Affected code: notification.py, templates/notifications.html, web_app.py

## ADDED Requirements

### Requirement: WeChat Work Notifications
The system SHALL support WeChat Work (企业微信) webhook notifications.

#### Scenario: Send WeChat notification
- **WHEN** user configures WeChat Work webhook URL
- **WHEN** low stock alert triggers
- **THEN** send message to WeChat Work group via webhook

### Requirement: DingTalk Notifications
The system SHALL support DingTalk (钉钉) webhook notifications.

#### Scenario: Send DingTalk notification
- **WHEN** user configures DingTalk webhook URL
- **WHEN** review alert triggers
- **THEN** send message to DingTalk group via webhook

### Requirement: China-Optimized CDN
The system SHALL use China-accessible CDN resources.

#### Scenario: Load static resources
- **WHEN** page loads in China
- **THEN** use CDN resources accessible in China (bootcss, etc.)
- **AND** fallback to local copies if CDN fails

### Requirement: China App Store Links
The system SHALL provide appropriate app store links for PWA installation.

#### Scenario: Show install prompt in China
- **WHEN** user sees PWA install prompt
- **THEN** show WeChat mini-program or Android APK download option
- **AND** provide alternative install instructions

## MODIFIED Requirements

### Requirement: Notification Service
The notification preferences UI SHALL show China-compatible options.

#### Scenario: Configure notifications
- **WHEN** user opens notification settings
- **THEN** show options: Email, WeChat Work, DingTalk
- **AND** hide Slack option or mark as "International only"

## Technical Approach

1. Add WeChat Work webhook support to notification.py
2. Add DingTalk webhook support to notification.py
3. Update notification preferences UI
4. Replace external CDN with China-friendly alternatives
5. Add local fallback for static assets
