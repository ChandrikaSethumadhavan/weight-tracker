#!/usr/bin/env python3
"""Test script to verify email configuration"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.email_service import EmailService
from app.models import EmailSettings

# Load environment variables manually from .env file
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

load_env()

# Create email settings from environment
email_settings = EmailSettings(
    smtp_host=os.getenv("EMAIL_SMTP_HOST", ""),
    smtp_port=int(os.getenv("EMAIL_SMTP_PORT", "587")),
    username=os.getenv("EMAIL_SMTP_USERNAME", ""),
    password=os.getenv("EMAIL_SMTP_PASSWORD", ""),
    sender=os.getenv("EMAIL_SENDER", ""),
    recipient=os.getenv("EMAIL_RECIPIENT", ""),
    use_tls=True
)

# Create email service
email_service = EmailService(email_settings)

# Check if configured
if not email_service.is_configured:
    print("❌ Email service is NOT configured properly!")
    print(f"SMTP Host: {email_settings.smtp_host}")
    print(f"Username: {email_settings.username}")
    print(f"Sender: {email_settings.sender}")
    print(f"Recipient: {email_settings.recipient}")
    exit(1)

print("✅ Email service is configured!")
print(f"📧 Sender: {email_settings.sender}")
print(f"📬 Recipient: {email_settings.recipient}")
print(f"🌐 SMTP Host: {email_settings.smtp_host}:{email_settings.smtp_port}")
print("\n🚀 Sending test email...")

try:
    email_service.send_motivation(
        subject="🎉 Weight Tracker - Email Test Successful!",
        body="""Hello! 👋

This is a test email from your Weight Tracker app.

Your email configuration is working perfectly! You should now receive:
- Daily motivational messages at 08:00
- Reminders when you haven't logged your daily check-in

Keep up the great work on your health journey! 💪

---
Sent from Weight Tracker App
"""
    )
    print("✅ Test email sent successfully!")
    print(f"📬 Check your inbox at: {email_settings.recipient}")

except Exception as e:
    print(f"❌ Failed to send email: {str(e)}")
    print("\nTroubleshooting tips:")
    print("1. Make sure 2-Step Verification is enabled on your Gmail")
    print("2. Verify the App Password is correct (16 characters)")
    print("3. Check if 'Less secure app access' needs to be enabled")
    exit(1)
