"""
Notification Service for Cross-Border Seller AI Assistant
Supports Email (SMTP) and Slack webhook notifications
"""

import smtplib
import json
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import os
import requests

class NotificationType(Enum):
    LOW_STOCK = "low_stock"
    REVIEW_ALERT = "review_alert"
    TASK_COMPLETE = "task_complete"
    DAILY_SUMMARY = "daily_summary"

class NotificationFrequency(Enum):
    IMMEDIATE = "immediate"
    HOURLY_DIGEST = "hourly_digest"
    DAILY_DIGEST = "daily_digest"

@dataclass
class NotificationPreference:
    email_enabled: bool = False
    slack_enabled: bool = False
    wechat_enabled: bool = False
    dingtalk_enabled: bool = False
    email_address: str = ""
    slack_webhook_url: str = ""
    wechat_webhook_url: str = ""
    dingtalk_webhook_url: str = ""
    notify_low_stock: bool = True
    notify_reviews: bool = True
    notify_tasks: bool = True
    frequency: str = "immediate"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    from_email: str = ""

@dataclass
class Notification:
    id: str
    type: NotificationType
    title: str
    message: str
    data: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    sent: bool = False
    sent_at: Optional[datetime] = None
    error: Optional[str] = None

class NotificationTemplates:
    """Notification template system"""

    @staticmethod
    def low_stock_alert(product: Dict[str, Any]) -> Dict[str, str]:
        """Generate low stock alert notification content"""
        product_name = product.get('product_name', 'Unknown Product')
        sku = product.get('sku', 'N/A')
        current_stock = product.get('current_stock', 0)
        threshold = product.get('threshold', 10)
        shortage = product.get('shortage', threshold - current_stock)
        severity = product.get('severity', 'warning')

        severity_emoji = "🔴" if severity == 'critical' else "🟡"

        subject_en = f"{severity_emoji} Low Stock Alert: {product_name}"
        subject_cn = f"{severity_emoji} 库存预警: {product_name}"

        body_en = f"""
{severity_emoji} LOW STOCK ALERT {severity_emoji}

Product: {product_name}
SKU: {sku}
Current Stock: {current_stock}
Threshold: {threshold}
Shortage: {shortage} units
Severity: {severity.upper()}

Please restock this item as soon as possible to avoid potential sales loss.
        """

        body_cn = f"""
{severity_emoji} 库存预警 {severity_emoji}

产品名称: {product_name}
SKU: {sku}
当前库存: {current_stock}
阈值: {threshold}
缺口: {shortage} 件
严重程度: {severity.upper()}

请尽快补货以避免潜在的销售损失。
        """

        slack_en = {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"{severity_emoji} Low Stock Alert"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Product:*\n{product_name}"},
                        {"type": "mrkdwn", "text": f"*SKU:*\n{sku}"},
                        {"type": "mrkdwn", "text": f"*Current Stock:*\n{current_stock}"},
                        {"type": "mrkdwn", "text": f"*Threshold:*\n{threshold}"},
                        {"type": "mrkdwn", "text": f"*Shortage:*\n{shortage} units"},
                        {"type": "mrkdwn", "text": f"*Severity:*\n{severity.upper()}"}
                    ]
                }
            ]
        }

        slack_cn = {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"{severity_emoji} 库存预警"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*产品:*\n{product_name}"},
                        {"type": "mrkdwn", "text": f"*SKU:*\n{sku}"},
                        {"type": "mrkdwn", "text": f"*当前库存:*\n{current_stock}"},
                        {"type": "mrkdwn", "text": f"*阈值:*\n{threshold}"},
                        {"type": "mrkdwn", "text": f"*缺口:*\n{shortage} 件"},
                        {"type": "mrkdwn", "text": f"*严重程度:*\n{severity.upper()}"}
                    ]
                }
            ]
        }

        dingtalk_en = {
            "msgtype": "markdown",
            "markdown": {
                "title": f"{severity_emoji} Low Stock Alert",
                "text": f"## {severity_emoji} Low Stock Alert\n\n**Product:** {product_name}\n**SKU:** {sku}\n**Current Stock:** {current_stock}\n**Threshold:** {threshold}\n**Shortage:** {shortage} units\n**Severity:** {severity.upper()}\n\nPlease restock this item as soon as possible."
            }
        }

        dingtalk_cn = {
            "msgtype": "markdown",
            "markdown": {
                "title": f"{severity_emoji} 库存预警",
                "text": f"## {severity_emoji} 库存预警\n\n**产品:** {product_name}\n**SKU:** {sku}\n**当前库存:** {current_stock}\n**阈值:** {threshold}\n**缺口:** {shortage} 件\n**严重程度:** {severity.upper()}\n\n请尽快补货以避免潜在的销售损失。"
            }
        }

        return {
            'subject_en': subject_en,
            'subject_cn': subject_cn,
            'body_en': body_en.strip(),
            'body_cn': body_cn.strip(),
            'slack_en': slack_en,
            'slack_cn': slack_cn,
            'wechat_en': NotificationTemplates._wechat_format_low_stock(product),
            'wechat_cn': NotificationTemplates._wechat_format_low_stock(product, lang='cn')
        }

    @staticmethod
    def review_alert(review: Dict[str, Any]) -> Dict[str, str]:
        """Generate review alert notification content"""
        product_name = review.get('product', 'Unknown Product')
        rating = review.get('rating', 0)
        reviewer = review.get('reviewer', 'Anonymous')
        review_text = review.get('review_text', review.get('review_summary', ''))
        review_date = review.get('review_date', review.get('date', 'Unknown'))
        alert_type = review.get('alert_type', review.get('issue_type', 'general'))
        priority = review.get('priority', 'medium')

        rating_stars = "⭐" * int(rating) if rating else "No rating"
        priority_emoji = "🔴" if priority == 'critical' else ("🟠" if priority == 'high' else "🟡")

        subject_en = f"{priority_emoji} Review Alert: {product_name} ({rating}/5)"
        subject_cn = f"{priority_emoji} 评论预警: {product_name} ({rating}/5)"

        body_en = f"""
{priority_emoji} REVIEW ALERT {priority_emoji}

Product: {product_name}
Rating: {rating_stars}
Reviewer: {reviewer}
Date: {review_date}
Alert Type: {alert_type}
Priority: {priority.upper()}

Review:
"{review_text}"

Action Required: Please review and respond to this feedback.
        """

        body_cn = f"""
{priority_emoji} 评论预警 {priority_emoji}

产品: {product_name}
评分: {rating_stars}
评论者: {reviewer}
日期: {review_date}
警报类型: {alert_type}
优先级: {priority.upper()}

评论内容:
"{review_text}"

需要处理: 请查看并回复此反馈。
        """

        slack_en = {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"{priority_emoji} Review Alert - {product_name}"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Rating:*\n{rating_stars}"},
                        {"type": "mrkdwn", "text": f"*Reviewer:*\n{reviewer}"},
                        {"type": "mrkdwn", "text": f"*Alert Type:*\n{alert_type}"},
                        {"type": "mrkdwn", "text": f"*Priority:*\n{priority.upper()}"}
                    ]
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Review:*\n{review_text}"}
                }
            ]
        }

        slack_cn = {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"{priority_emoji} 评论预警 - {product_name}"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*评分:*\n{rating_stars}"},
                        {"type": "mrkdwn", "text": f"*评论者:*\n{reviewer}"},
                        {"type": "mrkdwn", "text": f"*警报类型:*\n{alert_type}"},
                        {"type": "mrkdwn", "text": f"*优先级:*\n{priority.upper()}"}
                    ]
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*评论:*\n{review_text}"}
                }
            ]
        }

        dingtalk_en = {
            "msgtype": "markdown",
            "markdown": {
                "title": f"{priority_emoji} Review Alert",
                "text": f"## {priority_emoji} Review Alert - {product_name}\n\n**Rating:** {rating_stars}\n**Reviewer:** {reviewer}\n**Date:** {review_date}\n**Alert Type:** {alert_type}\n**Priority:** {priority.upper()}\n\n**Review:**\n{review_text}\n\nAction Required: Please review and respond to this feedback."
            }
        }

        dingtalk_cn = {
            "msgtype": "markdown",
            "markdown": {
                "title": f"{priority_emoji} 评论预警",
                "text": f"## {priority_emoji} 评论预警 - {product_name}\n\n**评分:** {rating_stars}\n**评论者:** {reviewer}\n**日期:** {review_date}\n**警报类型:** {alert_type}\n**优先级:** {priority.upper()}\n\n**评论:**\n{review_text}\n\n需要处理: 请查看并回复此反馈。"
            }
        }

        return {
            'subject_en': subject_en,
            'subject_cn': subject_cn,
            'body_en': body_en.strip(),
            'body_cn': body_cn.strip(),
            'slack_en': slack_en,
            'slack_cn': slack_cn,
            'dingtalk_en': dingtalk_en,
            'dingtalk_cn': dingtalk_cn,
            'wechat_en': NotificationTemplates._wechat_format_review(review),
            'wechat_cn': NotificationTemplates._wechat_format_review(review, lang='cn')
        }

    @staticmethod
    def _wechat_format_review(review: Dict[str, Any], lang: str = 'en') -> Dict[str, Any]:
        product_name = review.get('product', 'Unknown Product')
        rating = review.get('rating', 0)
        reviewer = review.get('reviewer', 'Anonymous')
        review_text = review.get('review_text', review.get('review_summary', ''))
        review_date = review.get('review_date', review.get('date', 'Unknown'))
        alert_type = review.get('alert_type', review.get('issue_type', 'general'))
        priority = review.get('priority', 'medium')

        rating_stars = "⭐" * int(rating) if rating else "No rating"
        priority_icon = "🔴" if priority == 'critical' else ("🟠" if priority == 'high' else "🟡")

        if lang == 'cn':
            return {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"### {priority_icon} 评论预警\n\n"
                               f"**产品:** {product_name}\n"
                               f"**评分:** {rating_stars}\n"
                               f"**评论者:** {reviewer}\n"
                               f"**日期:** {review_date}\n"
                               f"**警报类型:** {alert_type}\n"
                               f"**优先级:** {priority.upper()}\n\n"
                               f"**评论内容:**\n{review_text}"
                }
            }
        else:
            return {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"### {priority_icon} Review Alert\n\n"
                               f"**Product:** {product_name}\n"
                               f"**Rating:** {rating_stars}\n"
                               f"**Reviewer:** {reviewer}\n"
                               f"**Date:** {review_date}\n"
                               f"**Alert Type:** {alert_type}\n"
                               f"**Priority:** {priority.upper()}\n\n"
                               f"**Review:**\n{review_text}"
                }
        }

    @staticmethod
    def _wechat_format_low_stock(product: Dict[str, Any], lang: str = 'en') -> Dict[str, Any]:
        product_name = product.get('product_name', 'Unknown Product')
        sku = product.get('sku', 'N/A')
        current_stock = product.get('current_stock', 0)
        threshold = product.get('threshold', 10)
        shortage = product.get('shortage', threshold - current_stock)
        severity = product.get('severity', 'warning')

        severity_icon = "🔴" if severity == 'critical' else "🟡"

        if lang == 'cn':
            return {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"### {severity_icon} 库存预警\n\n"
                               f"**产品:** {product_name}\n"
                               f"**SKU:** {sku}\n"
                               f"**当前库存:** {current_stock}\n"
                               f"**阈值:** {threshold}\n"
                               f"**缺口:** {shortage} 件\n"
                               f"**严重程度:** {severity.upper()}"
                }
            }
        else:
            return {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"### {severity_icon} Low Stock Alert\n\n"
                               f"**Product:** {product_name}\n"
                               f"**SKU:** {sku}\n"
                               f"**Current Stock:** {current_stock}\n"
                               f"**Threshold:** {threshold}\n"
                               f"**Shortage:** {shortage} units\n"
                               f"**Severity:** {severity.upper()}"
                }
            }

    @staticmethod
    def _wechat_format_task(task: Dict[str, Any], lang: str = 'en') -> Dict[str, Any]:
        task_name = task.get('tool_name', 'Unknown Task')
        task_id = task.get('task_id', 'N/A')
        result_summary = task.get('result_summary', 'Task completed successfully')
        duration = task.get('duration', 'N/A')

        if lang == 'cn':
            return {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"### ✅ 任务完成\n\n"
                               f"**任务:** {task_name}\n"
                               f"**任务ID:** {task_id}\n"
                               f"**耗时:** {duration}\n\n"
                               f"**结果摘要:**\n{result_summary}"
                }
            }
        else:
            return {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"### ✅ Task Completed\n\n"
                               f"**Task:** {task_name}\n"
                               f"**Task ID:** {task_id}\n"
                               f"**Duration:** {duration}\n\n"
                               f"**Result Summary:**\n{result_summary}"
                }
            }

    @staticmethod
    def _wechat_format_test(lang: str = 'en') -> Dict[str, Any]:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if lang == 'cn':
            return {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"### ✅ 测试通知\n\n"
                               f"这是来自跨境卖家AI助手的测试消息。\n\n"
                               f"如果您收到此消息，说明您的通知设置已正确配置。\n\n"
                               f"收到时间: {timestamp}"
                }
            }
        else:
            return {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"### ✅ Test Notification\n\n"
                               f"This is a test message from Cross-Border Seller AI Assistant.\n\n"
                               f"If you received this message, your notification settings are correctly configured.\n\n"
                               f"Received at: {timestamp}"
                }
            }

    @staticmethod
    def task_complete(task: Dict[str, Any]) -> Dict[str, str]:
        """Generate task completion notification content"""
        task_name = task.get('tool_name', 'Unknown Task')
        task_id = task.get('task_id', 'N/A')
        result_summary = task.get('result_summary', 'Task completed successfully')
        duration = task.get('duration', 'N/A')

        subject_en = f"✅ Task Complete: {task_name}"
        subject_cn = f"✅ 任务完成: {task_name}"

        body_en = f"""
✅ TASK COMPLETED ✅

Task: {task_name}
Task ID: {task_id}
Duration: {duration}

Result Summary:
{result_summary}

View full results in your dashboard.
        """

        body_cn = f"""
✅ 任务完成 ✅

任务: {task_name}
任务ID: {task_id}
耗时: {duration}

结果摘要:
{result_summary}

请在仪表板中查看完整结果。
        """

        slack_en = {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "✅ Task Completed"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Task:*\n{task_name}"},
                        {"type": "mrkdwn", "text": f"*Task ID:*\n{task_id}"},
                        {"type": "mrkdwn", "text": f"*Duration:*\n{duration}"}
                    ]
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Result:*\n{result_summary}"}
                }
            ]
        }

        slack_cn = {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "✅ 任务完成"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*任务:*\n{task_name}"},
                        {"type": "mrkdwn", "text": f"*任务ID:*\n{task_id}"},
                        {"type": "mrkdwn", "text": f"*耗时:*\n{duration}"}
                    ]
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*结果:*\n{result_summary}"}
                }
            ]
        }

        dingtalk_en = {
            "msgtype": "markdown",
            "markdown": {
                "title": "✅ Task Completed",
                "text": f"## ✅ Task Completed\n\n**Task:** {task_name}\n**Task ID:** {task_id}\n**Duration:** {duration}\n\n**Result:**\n{result_summary}\n\nView full results in your dashboard."
            }
        }

        dingtalk_cn = {
            "msgtype": "markdown",
            "markdown": {
                "title": "✅ 任务完成",
                "text": f"## ✅ 任务完成\n\n**任务:** {task_name}\n**任务ID:** {task_id}\n**耗时:** {duration}\n\n**结果:**\n{result_summary}\n\n请在仪表板中查看完整结果。"
            }
        }

        return {
            'subject_en': subject_en,
            'subject_cn': subject_cn,
            'body_en': body_en.strip(),
            'body_cn': body_cn.strip(),
            'slack_en': slack_en,
            'slack_cn': slack_cn,
            'dingtalk_en': dingtalk_en,
            'dingtalk_cn': dingtalk_cn,
            'wechat_en': NotificationTemplates._wechat_format_task(task),
            'wechat_cn': NotificationTemplates._wechat_format_task(task, lang='cn')
        }

    @staticmethod
    def daily_summary(stats: Dict[str, Any]) -> Dict[str, str]:
        """Generate daily summary notification content"""
        date = stats.get('date', datetime.now().strftime('%Y-%m-%d'))
        low_stock_count = stats.get('low_stock_count', 0)
        critical_stock = stats.get('critical_stock', 0)
        pending_orders = stats.get('pending_orders', 0)
        new_reviews = stats.get('new_reviews', 0)
        critical_reviews = stats.get('critical_reviews', 0)
        total_revenue = stats.get('total_revenue', 0.0)
        completed_tasks = stats.get('completed_tasks', 0)

        alert_count = low_stock_count + critical_reviews
        alert_emoji = "🔴" if alert_count > 5 else ("🟡" if alert_count > 0 else "🟢")

        subject_en = f"{alert_emoji} Daily Summary - {date}"
        subject_cn = f"{alert_emoji} 每日摘要 - {date}"

        body_en = f"""
📊 DAILY SUMMARY - {date} 📊

📦 Inventory:
   - Low Stock Alerts: {low_stock_count}
   - Critical: {critical_stock}

📋 Orders:
   - Pending: {pending_orders}

⭐ Reviews:
   - New Reviews: {new_reviews}
   - Critical: {critical_reviews}

💰 Revenue:
   - Total: ${total_revenue:,.2f}

✅ Tasks:
   - Completed: {completed_tasks}

{alert_emoji} Action Required: {alert_count} items need attention
        """

        body_cn = f"""
📊 每日摘要 - {date} 📊

📦 库存:
   - 库存预警: {low_stock_count}
   - 紧急: {critical_stock}

📋 订单:
   - 待处理: {pending_orders}

⭐ 评论:
   - 新评论: {new_reviews}
   - 紧急: {critical_reviews}

💰 收入:
   - 总计: ${total_revenue:,.2f}

✅ 任务:
   - 已完成: {completed_tasks}

{alert_emoji} 需要处理: {alert_count} 项需要关注
        """

        slack_en = {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"📊 Daily Summary - {date}"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*📦 Low Stock:*\n{low_stock_count} (Critical: {critical_stock})"},
                        {"type": "mrkdwn", "text": f"*📋 Pending Orders:*\n{pending_orders}"},
                        {"type": "mrkdwn", "text": f"*⭐ New Reviews:*\n{new_reviews} (Critical: {critical_reviews})"},
                        {"type": "mrkdwn", "text": f"*💰 Revenue:*\n${total_revenue:,.2f}"},
                        {"type": "mrkdwn", "text": f"*✅ Tasks:*\n{completed_tasks}"},
                        {"type": "mrkdwn", "text": f"*⚠️ Action Required:*\n{alert_count} items"}
                    ]
                }
            ]
        }

        slack_cn = {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"📊 每日摘要 - {date}"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*📦 库存预警:*\n{low_stock_count} (紧急: {critical_stock})"},
                        {"type": "mrkdwn", "text": f"*📋 待处理订单:*\n{pending_orders}"},
                        {"type": "mrkdwn", "text": f"*⭐ 新评论:*\n{new_reviews} (紧急: {critical_reviews})"},
                        {"type": "mrkdwn", "text": f"*💰 收入:*\n${total_revenue:,.2f}"},
                        {"type": "mrkdwn", "text": f"*✅ 任务:*\n{completed_tasks}"},
                        {"type": "mrkdwn", "text": f"*⚠️ 需要处理:*\n{alert_count} 项"}
                    ]
                }
            ]
        }

        dingtalk_en = {
            "msgtype": "markdown",
            "markdown": {
                "title": f"📊 Daily Summary - {date}",
                "text": f"## 📊 Daily Summary - {date}\n\n**📦 Low Stock:** {low_stock_count} (Critical: {critical_stock})\n**📋 Pending Orders:** {pending_orders}\n**⭐ New Reviews:** {new_reviews} (Critical: {critical_reviews})\n**💰 Revenue:** ${total_revenue:,.2f}\n**✅ Tasks:** {completed_tasks}\n\n**⚠️ Action Required:** {alert_count} items"
            }
        }

        dingtalk_cn = {
            "msgtype": "markdown",
            "markdown": {
                "title": f"📊 每日摘要 - {date}",
                "text": f"## 📊 每日摘要 - {date}\n\n**📦 库存预警:** {low_stock_count} (紧急: {critical_stock})\n**📋 待处理订单:** {pending_orders}\n**⭐ 新评论:** {new_reviews} (紧急: {critical_reviews})\n**💰 收入:** ${total_revenue:,.2f}\n**✅ 任务:** {completed_tasks}\n\n**⚠️ 需要处理:** {alert_count} 项"
            }
        }

        return {
            'subject_en': subject_en,
            'subject_cn': subject_cn,
            'body_en': body_en.strip(),
            'body_cn': body_cn.strip(),
            'slack_en': slack_en,
            'slack_cn': slack_cn,
            'dingtalk_en': dingtalk_en,
            'dingtalk_cn': dingtalk_cn
        }

    @staticmethod
    def test_notification(lang: str = 'en') -> Dict[str, str]:
        """Generate test notification content"""
        if lang == 'cn':
            subject = "✅ 测试通知 - 跨境卖家AI助手"
            body = """
✅ 测试通知 ✅

这是来自跨境卖家AI助手的测试消息。

如果您收到此消息，说明您的通知设置已正确配置。

收到时间: {timestamp}

此致
跨境卖家AI助手
            """.strip().format(timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

            slack = {
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": "✅ 测试通知"}
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "这是来自跨境卖家AI助手的测试消息。\n\n如果您收到此消息，说明您的通知设置已正确配置。\n\n收到时间: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    }
                ]
            }
        else:
            subject = "✅ Test Notification - Cross-Border Seller AI"
            body = """
✅ TEST NOTIFICATION ✅

This is a test message from Cross-Border Seller AI Assistant.

If you received this message, your notification settings are correctly configured.

Received at: {timestamp}

Best regards,
Cross-Border Seller AI Assistant
            """.strip().format(timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

            slack = {
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": "✅ Test Notification"}
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "This is a test message from Cross-Border Seller AI Assistant.\n\nIf you received this message, your notification settings are correctly configured.\n\nReceived at: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    }
                ]
            }

        dingtalk_en = {
            "msgtype": "markdown",
            "markdown": {
                "title": "✅ Test Notification",
                "text": f"## ✅ Test Notification\n\nThis is a test message from Cross-Border Seller AI Assistant.\n\nIf you received this message, your notification settings are correctly configured.\n\nReceived at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
        }

        dingtalk_cn = {
            "msgtype": "markdown",
            "markdown": {
                "title": "✅ 测试通知",
                "text": f"## ✅ 测试通知\n\n这是来自跨境卖家AI助手的测试消息。\n\n如果您收到此消息，说明您的通知设置已正确配置。\n\n收到时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
        }

        return {
            'subject_en': subject if lang != 'cn' else "✅ Test Notification - Cross-Border Seller AI",
            'subject_cn': "✅ 测试通知 - 跨境卖家AI助手" if lang == 'cn' else subject,
            'body_en': body if lang != 'cn' else "✅ TEST NOTIFICATION ✅\n\nThis is a test message from Cross-Border Seller AI Assistant.\n\nIf you received this message, your notification settings are correctly configured.\n\nReceived at: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\n\nBest regards,\nCross-Border Seller AI Assistant",
            'body_cn': "✅ 测试通知 ✅\n\n这是来自跨境卖家AI助手的测试消息。\n\n如果您收到此消息，说明您的通知设置已正确配置。\n\n收到时间: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\n\n此致\n跨境卖家AI助手",
            'slack_en': slack if lang != 'cn' else {
                "blocks": [
                    {"type": "header", "text": {"type": "plain_text", "text": "✅ Test Notification"}},
                    {"type": "section", "text": {"type": "mrkdwn", "text": "This is a test message from Cross-Border Seller AI Assistant.\n\nIf you received this message, your notification settings are correctly configured.\n\nReceived at: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S')}}
                ]
            },
            'slack_cn': slack if lang == 'cn' else {
                "blocks": [
                    {"type": "header", "text": {"type": "plain_text", "text": "✅ 测试通知"}},
                    {"type": "section", "text": {"type": "mrkdwn", "text": "这是来自跨境卖家AI助手的测试消息。\n\n如果您收到此消息，说明您的通知设置已正确配置。\n\n收到时间: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S')}}
                ]
            },
            'dingtalk_en': dingtalk_en,
            'dingtalk_cn': dingtalk_cn,
            'wechat_en': NotificationTemplates._wechat_format_test(lang='en'),
            'wechat_cn': NotificationTemplates._wechat_format_test(lang='cn')
        }


class NotificationService:
    """Main notification service class"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._queue: List[Notification] = []
        self._history: List[Notification] = []
        self._preferences = NotificationPreference()
        self._queue_lock = threading.Lock()
        self._history_lock = threading.Lock()

        self._load_preferences()

    def _load_preferences(self):
        """Load preferences from environment variables"""
        self._preferences.email_enabled = os.getenv('NOTIFICATION_EMAIL_ENABLED', 'false').lower() == 'true'
        self._preferences.slack_enabled = os.getenv('NOTIFICATION_SLACK_ENABLED', 'false').lower() == 'true'
        self._preferences.wechat_enabled = os.getenv('NOTIFICATION_WECHAT_ENABLED', 'false').lower() == 'true'
        self._preferences.dingtalk_enabled = os.getenv('NOTIFICATION_DINGTALK_ENABLED', 'false').lower() == 'true'
        self._preferences.email_address = os.getenv('NOTIFICATION_EMAIL_TO', '')
        self._preferences.slack_webhook_url = os.getenv('NOTIFICATION_SLACK_WEBHOOK_URL', '')
        self._preferences.wechat_webhook_url = os.getenv('NOTIFICATION_WECHAT_WEBHOOK_URL', '')
        self._preferences.dingtalk_webhook_url = os.getenv('NOTIFICATION_DINGTALK_WEBHOOK_URL', '')
        self._preferences.notify_low_stock = os.getenv('NOTIFICATION_LOW_STOCK', 'true').lower() == 'true'
        self._preferences.notify_reviews = os.getenv('NOTIFICATION_REVIEWS', 'true').lower() == 'true'
        self._preferences.notify_tasks = os.getenv('NOTIFICATION_TASKS', 'true').lower() == 'true'
        self._preferences.frequency = os.getenv('NOTIFICATION_FREQUENCY', 'immediate')
        self._preferences.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self._preferences.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self._preferences.smtp_username = os.getenv('SMTP_USERNAME', '')
        self._preferences.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self._preferences.from_email = os.getenv('SMTP_FROM', os.getenv('SMTP_USERNAME', ''))

    def save_preferences_to_env(self, prefs: NotificationPreference):
        """Save preferences to environment variables (for persistence)"""
        env_file = '.env'
        env_vars = {}

        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key] = value

        env_vars['NOTIFICATION_EMAIL_ENABLED'] = 'true' if prefs.email_enabled else 'false'
        env_vars['NOTIFICATION_SLACK_ENABLED'] = 'true' if prefs.slack_enabled else 'false'
        env_vars['NOTIFICATION_WECHAT_ENABLED'] = 'true' if prefs.wechat_enabled else 'false'
        env_vars['NOTIFICATION_DINGTALK_ENABLED'] = 'true' if prefs.dingtalk_enabled else 'false'
        env_vars['NOTIFICATION_EMAIL_TO'] = prefs.email_address
        env_vars['NOTIFICATION_SLACK_WEBHOOK_URL'] = prefs.slack_webhook_url
        env_vars['NOTIFICATION_WECHAT_WEBHOOK_URL'] = prefs.wechat_webhook_url
        env_vars['NOTIFICATION_DINGTALK_WEBHOOK_URL'] = prefs.dingtalk_webhook_url
        env_vars['NOTIFICATION_LOW_STOCK'] = 'true' if prefs.notify_low_stock else 'false'
        env_vars['NOTIFICATION_REVIEWS'] = 'true' if prefs.notify_reviews else 'false'
        env_vars['NOTIFICATION_TASKS'] = 'true' if prefs.notify_tasks else 'false'
        env_vars['NOTIFICATION_FREQUENCY'] = prefs.frequency
        env_vars['SMTP_HOST'] = prefs.smtp_host
        env_vars['SMTP_PORT'] = str(prefs.smtp_port)
        env_vars['SMTP_USERNAME'] = prefs.smtp_username
        env_vars['SMTP_PASSWORD'] = prefs.smtp_password
        env_vars['SMTP_FROM'] = prefs.from_email

        with open(env_file, 'w') as f:
            for key, value in env_vars.items():
                f.write(f'{key}={value}\n')

        self._preferences = prefs

    def get_preferences(self) -> NotificationPreference:
        """Get current notification preferences"""
        return self._preferences

    def update_preferences(self, prefs: NotificationPreference):
        """Update notification preferences"""
        self._preferences = prefs
        self.save_preferences_to_env(prefs)

    def _generate_id(self) -> str:
        """Generate unique notification ID"""
        return f"notif_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self._history)}"

    def _add_to_queue(self, notification: Notification):
        """Add notification to queue"""
        with self._queue_lock:
            self._queue.append(notification)

    def _add_to_history(self, notification: Notification):
        """Add notification to history"""
        with self._history_lock:
            self._history.insert(0, notification)
            if len(self._history) > 100:
                self._history = self._history[:100]

    def get_queue(self) -> List[Dict[str, Any]]:
        """Get pending notifications from queue"""
        with self._queue_lock:
            return [
                {
                    'id': n.id,
                    'type': n.type.value,
                    'title': n.title,
                    'message': n.message,
                    'created_at': n.created_at.isoformat(),
                    'sent': n.sent,
                    'error': n.error
                }
                for n in self._queue
            ]

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get notification history"""
        with self._history_lock:
            return [
                {
                    'id': n.id,
                    'type': n.type.value,
                    'title': n.title,
                    'message': n.message,
                    'created_at': n.created_at.isoformat(),
                    'sent': n.sent,
                    'sent_at': n.sent_at.isoformat() if n.sent_at else None,
                    'error': n.error
                }
                for n in self._history[:limit]
            ]

    def clear_queue(self):
        """Clear the notification queue"""
        with self._queue_lock:
            self._queue.clear()

    def send_email(self, to: str, subject: str, body: str, is_html: bool = False) -> bool:
        """Send email via SMTP"""
        if not self._preferences.smtp_username or not self._preferences.smtp_password:
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self._preferences.from_email or self._preferences.smtp_username
            msg['To'] = to

            if is_html:
                html_part = MIMEText(body, 'html')
                msg.attach(html_part)
            else:
                text_part = MIMEText(body, 'plain')
                msg.attach(text_part)

            with smtplib.SMTP(self._preferences.smtp_host, self._preferences.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self._preferences.smtp_username, self._preferences.smtp_password)
                server.sendmail(msg['From'], [to], msg.as_string())

            return True
        except Exception as e:
            print(f"Email send error: {str(e)}")
            return False

    def send_slack(self, webhook_url: str, message: Dict[str, Any]) -> bool:
        """Send Slack notification via webhook"""
        if not webhook_url:
            webhook_url = self._preferences.slack_webhook_url

        if not webhook_url:
            return False

        try:
            response = requests.post(webhook_url, json=message, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Slack send error: {str(e)}")
            return False

    def send_wechat_notification(self, webhook_url: str, message: Dict[str, Any]) -> bool:
        """Send WeChat Work notification via webhook"""
        if not webhook_url:
            webhook_url = self._preferences.wechat_webhook_url

        if not webhook_url:
            return False

        try:
            response = requests.post(webhook_url, json=message, timeout=10)
            if response.status_code == 200:
                return True
            else:
                print(f"WeChat send error: HTTP {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"WeChat send error: {str(e)}")
            return False

    def send_dingtalk_notification(self, webhook_url: str, message: Dict[str, Any]) -> bool:
        """Send DingTalk notification via webhook"""
        if not webhook_url:
            webhook_url = self._preferences.dingtalk_webhook_url

        if not webhook_url:
            return False

        try:
            response = requests.post(webhook_url, json=message, timeout=10)
            if response.status_code == 200:
                result = response.json()
                return result.get('errcode', 0) == 0
            else:
                print(f"DingTalk send error: HTTP {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"DingTalk send error: {str(e)}")
            return False

    def notify_low_stock(self, alert: Dict[str, Any], lang: str = 'en') -> str:
        """Send low stock alert notification"""
        if not self._preferences.notify_low_stock:
            return "Low stock notifications disabled"

        notification_id = self._generate_id()
        template = NotificationTemplates.low_stock_alert(alert)

        subject = template['subject_en'] if lang != 'cn' else template['subject_cn']
        body = template['body_en'] if lang != 'cn' else template['body_cn']
        slack_content = template['slack_en'] if lang != 'cn' else template['slack_cn']
        wechat_content = template['wechat_en'] if lang != 'cn' else template['wechat_cn']

        notification = Notification(
            id=notification_id,
            type=NotificationType.LOW_STOCK,
            title=subject,
            message=body,
            data=alert
        )

        success = True

        if self._preferences.email_enabled and self._preferences.email_address:
            email_success = self.send_email(
                self._preferences.email_address,
                subject,
                body
            )
            if not email_success:
                success = False

        if self._preferences.slack_enabled and self._preferences.slack_webhook_url:
            slack_success = self.send_slack(self._preferences.slack_webhook_url, slack_content)
            if not slack_success:
                success = False

        if self._preferences.wechat_enabled and self._preferences.wechat_webhook_url:
            wechat_success = self.send_wechat_notification(self._preferences.wechat_webhook_url, wechat_content)
            if not wechat_success:
                success = False

        if self._preferences.frequency == 'immediate':
            notification.sent = success
            notification.sent_at = datetime.now() if success else None
            notification.error = None if success else "Failed to send"
            self._add_to_history(notification)
        else:
            self._add_to_queue(notification)

        return notification_id

    def notify_review_alert(self, review: Dict[str, Any], lang: str = 'en') -> str:
        """Send review alert notification"""
        if not self._preferences.notify_reviews:
            return "Review notifications disabled"

        notification_id = self._generate_id()
        template = NotificationTemplates.review_alert(review)

        subject = template['subject_en'] if lang != 'cn' else template['subject_cn']
        body = template['body_en'] if lang != 'cn' else template['body_cn']
        slack_content = template['slack_en'] if lang != 'cn' else template['slack_cn']
        wechat_content = template['wechat_en'] if lang != 'cn' else template['wechat_cn']

        notification = Notification(
            id=notification_id,
            type=NotificationType.REVIEW_ALERT,
            title=subject,
            message=body,
            data=review
        )

        success = True

        if self._preferences.email_enabled and self._preferences.email_address:
            email_success = self.send_email(
                self._preferences.email_address,
                subject,
                body
            )
            if not email_success:
                success = False

        if self._preferences.slack_enabled and self._preferences.slack_webhook_url:
            slack_success = self.send_slack(self._preferences.slack_webhook_url, slack_content)
            if not slack_success:
                success = False

        if self._preferences.wechat_enabled and self._preferences.wechat_webhook_url:
            wechat_success = self.send_wechat_notification(self._preferences.wechat_webhook_url, wechat_content)
            if not wechat_success:
                success = False

        if self._preferences.frequency == 'immediate':
            notification.sent = success
            notification.sent_at = datetime.now() if success else None
            notification.error = None if success else "Failed to send"
            self._add_to_history(notification)
        else:
            self._add_to_queue(notification)

        return notification_id

    def notify_task_complete(self, task: Dict[str, Any], lang: str = 'en') -> str:
        """Send task completion notification"""
        if not self._preferences.notify_tasks:
            return "Task notifications disabled"

        notification_id = self._generate_id()
        template = NotificationTemplates.task_complete(task)

        subject = template['subject_en'] if lang != 'cn' else template['subject_cn']
        body = template['body_en'] if lang != 'cn' else template['body_cn']
        slack_content = template['slack_en'] if lang != 'cn' else template['slack_cn']
        wechat_content = template['wechat_en'] if lang != 'cn' else template['wechat_cn']

        notification = Notification(
            id=notification_id,
            type=NotificationType.TASK_COMPLETE,
            title=subject,
            message=body,
            data=task
        )

        success = True

        if self._preferences.email_enabled and self._preferences.email_address:
            email_success = self.send_email(
                self._preferences.email_address,
                subject,
                body
            )
            if not email_success:
                success = False

        if self._preferences.slack_enabled and self._preferences.slack_webhook_url:
            slack_success = self.send_slack(self._preferences.slack_webhook_url, slack_content)
            if not slack_success:
                success = False

        if self._preferences.wechat_enabled and self._preferences.wechat_webhook_url:
            wechat_success = self.send_wechat_notification(self._preferences.wechat_webhook_url, wechat_content)
            if not wechat_success:
                success = False

        if self._preferences.frequency == 'immediate':
            notification.sent = success
            notification.sent_at = datetime.now() if success else None
            notification.error = None if success else "Failed to send"
            self._add_to_history(notification)
        else:
            self._add_to_queue(notification)

        return notification_id

    def send_daily_summary(self, stats: Dict[str, Any], lang: str = 'en') -> str:
        """Send daily summary notification"""
        notification_id = self._generate_id()
        template = NotificationTemplates.daily_summary(stats)

        subject = template['subject_en'] if lang != 'cn' else template['subject_cn']
        body = template['body_en'] if lang != 'cn' else template['body_cn']
        slack_content = template['slack_en'] if lang != 'cn' else template['slack_cn']

        notification = Notification(
            id=notification_id,
            type=NotificationType.DAILY_SUMMARY,
            title=subject,
            message=body,
            data=stats
        )

        success = True

        if self._preferences.email_enabled and self._preferences.email_address:
            email_success = self.send_email(
                self._preferences.email_address,
                subject,
                body
            )
            if not email_success:
                success = False

        if self._preferences.slack_enabled and self._preferences.slack_webhook_url:
            slack_success = self.send_slack(self._preferences.slack_webhook_url, slack_content)
            if not slack_success:
                success = False

        notification.sent = success
        notification.sent_at = datetime.now() if success else None
        notification.error = None if success else "Failed to send"
        self._add_to_history(notification)

        return notification_id

    def send_test_notification(self, lang: str = 'en') -> Dict[str, Any]:
        """Send a test notification"""
        template = NotificationTemplates.test_notification(lang)

        subject = template['subject_en'] if lang != 'cn' else template['subject_cn']
        body = template['body_en'] if lang != 'cn' else template['body_cn']
        slack_content = template['slack_en'] if lang != 'cn' else template['slack_cn']
        wechat_content = template['wechat_en'] if lang != 'cn' else template['wechat_cn']

        results = {
            'email': {'success': False, 'error': None},
            'slack': {'success': False, 'error': None},
            'wechat': {'success': False, 'error': None}
        }

        if self._preferences.email_enabled and self._preferences.email_address:
            try:
                results['email']['success'] = self.send_email(
                    self._preferences.email_address,
                    subject,
                    body
                )
            except Exception as e:
                results['email']['error'] = str(e)

        if self._preferences.slack_enabled and self._preferences.slack_webhook_url:
            try:
                results['slack']['success'] = self.send_slack(
                    self._preferences.slack_webhook_url,
                    slack_content
                )
            except Exception as e:
                results['slack']['error'] = str(e)

        if self._preferences.wechat_enabled and self._preferences.wechat_webhook_url:
            try:
                results['wechat']['success'] = self.send_wechat_notification(
                    self._preferences.wechat_webhook_url,
                    wechat_content
                )
            except Exception as e:
                results['wechat']['error'] = str(e)

        return results

    def process_queue(self) -> int:
        """Process pending notifications in queue (for digest mode)"""
        with self._queue_lock:
            queue_copy = list(self._queue)
            self._queue.clear()

        sent_count = 0

        for notification in queue_copy:
            notification.sent = True
            notification.sent_at = datetime.now()
            self._add_to_history(notification)
            sent_count += 1

        return sent_count


def get_notification_service() -> NotificationService:
    """Get the singleton notification service instance"""
    return NotificationService()
