import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from backend.config.settings import settings
from backend.utils.logger import logger
from backend.utils.helpers import format_duration_readable


class EmailService:
    """Service for sending email notifications."""
    
    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.sender_email = settings.EMAIL_SENDER
        self.sender_password = settings.EMAIL_PASSWORD
        self.receiver_email = settings.EMAIL_RECEIVER
        self.sent_emails = {}
    
    def send_email(self, subject, body, html_body=None):
        """Send email with given subject and body."""
        try:
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = self.sender_email
            message['To'] = self.receiver_email
            
            if html_body:
                message.attach(MIMEText(body, 'plain'))
                message.attach(MIMEText(html_body, 'html'))
            else:
                message.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            
            logger.info(f"Email sent successfully: {subject}")
            return True
        
        except smtplib.SMTPAuthenticationError:
            logger.error("Email authentication failed: Check credentials")
            return False
        
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {str(e)}")
            return False
        
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False
    
    def send_service_down_alert(self, service_name, failure_time, issue_type):
        """Send alert email when service goes down."""
        try:
            subject = "🔴 ALERT: Your Render Service is DOWN"
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            body = f"""
Service Status Alert

Service Name: {service_name}
Status: DOWN
Time Down: {failure_time}
Issue Type: {issue_type}
Alert Sent: {timestamp}

Please check your Render dashboard for more details.

---
Render Monitor
            """.strip()
            
            html_body = f"""
            <html>
              <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
                  <h2 style="color: #d32f2f;">🔴 Service Alert</h2>
                  <p><strong>Service Name:</strong> {service_name}</p>
                  <p><strong>Status:</strong> <span style="color: #d32f2f; font-weight: bold;">DOWN</span></p>
                  <p><strong>Down Since:</strong> {failure_time}</p>
                  <p><strong>Issue Type:</strong> {issue_type}</p>
                  <p><strong>Alert Time:</strong> {timestamp}</p>
                  <p style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666;">
                    Please check your Render dashboard for more details.
                  </p>
                  <p style="font-size: 12px; color: #999;">Render Monitor</p>
                </div>
              </body>
            </html>
            """
            
            email_key = f"{service_name}_DOWN_{failure_time}"
            if email_key in self.sent_emails:
                logger.debug(f"Duplicate alert already sent for {service_name}")
                return False
            
            result = self.send_email(subject, body, html_body)
            if result:
                self.sent_emails[email_key] = datetime.now()
            return result
        
        except Exception as e:
            logger.error(f"Error sending down alert: {str(e)}")
            return False
    
    def send_service_recovered_alert(self, service_name, recovery_time, downtime_duration):
        """Send alert email when service recovers."""
        try:
            subject = "🟢 RECOVERED: Your Render Service is Back"
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            downtime_readable = format_duration_readable(downtime_duration)
            
            body = f"""
Service Recovery Alert

Service Name: {service_name}
Status: RECOVERED
Recovery Time: {recovery_time}
Total Downtime: {downtime_readable}
Alert Sent: {timestamp}

Your service is now running normally.

---
Render Monitor
            """.strip()
            
            html_body = f"""
            <html>
              <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
                  <h2 style="color: #388e3c;">🟢 Service Recovered</h2>
                  <p><strong>Service Name:</strong> {service_name}</p>
                  <p><strong>Status:</strong> <span style="color: #388e3c; font-weight: bold;">RECOVERED</span></p>
                  <p><strong>Recovery Time:</strong> {recovery_time}</p>
                  <p><strong>Total Downtime:</strong> {downtime_readable}</p>
                  <p><strong>Alert Time:</strong> {timestamp}</p>
                  <p style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd;">
                    Your service is now running normally. ✓
                  </p>
                  <p style="font-size: 12px; color: #999;">Render Monitor</p>
                </div>
              </body>
            </html>
            """
            
            email_key = f"{service_name}_RECOVERED_{recovery_time}"
            if email_key in self.sent_emails:
                logger.debug(f"Duplicate recovery email already sent for {service_name}")
                return False
            
            result = self.send_email(subject, body, html_body)
            if result:
                self.sent_emails[email_key] = datetime.now()
            return result
        
        except Exception as e:
            logger.error(f"Error sending recovery alert: {str(e)}")
            return False
    
    def send_error_spike_alert(self, error_pattern: str, count: int, sample: str) -> bool:
        """Send alert when a recurring error exceeds the spike threshold."""
        try:
            subject = f"⚠️ Recurring Error ({count}x): {error_pattern[:60]}"
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            body = f"""Recurring Error Alert

Pattern:    {error_pattern[:120]}
Count:      {count}x in recent logs
Sample:     {sample[:200]}
Alert Time: {timestamp}

This error has appeared {count} or more times recently. Please investigate.

---
Render Monitor""".strip()

            html_body = f"""
            <html>
              <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
                  <h2 style="color: #f57c00;">⚠️ Recurring Error Detected</h2>
                  <table style="width:100%;border-collapse:collapse;">
                    <tr><td style="padding:6px 0;color:#666;width:120px;">Pattern</td><td style="padding:6px 0;font-weight:600;">{error_pattern[:120]}</td></tr>
                    <tr><td style="padding:6px 0;color:#666;">Occurrences</td><td style="padding:6px 0;font-weight:600;color:#d32f2f;">{count}× in recent logs</td></tr>
                    <tr><td style="padding:6px 0;color:#666;vertical-align:top;">Sample</td><td style="padding:6px 0;"><code style="background:#f5f5f5;padding:4px 8px;border-radius:3px;font-size:12px;word-break:break-all;">{sample[:200]}</code></td></tr>
                    <tr><td style="padding:6px 0;color:#666;">Alert Time</td><td style="padding:6px 0;">{timestamp}</td></tr>
                  </table>
                  <p style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666;">
                    Check the Errors &amp; Warnings section in your dashboard for full details.
                  </p>
                  <p style="font-size: 12px; color: #999;">Render Monitor</p>
                </div>
              </body>
            </html>"""

            return self.send_email(subject, body, html_body)
        except Exception as e:
            logger.error(f"Error sending spike alert: {e}")
            return False

    def send_error_spike_recovered(self, error_pattern: str) -> bool:
        """Send notification when a previously spiking error drops below threshold."""
        try:
            subject = f"🟢 Error Resolved: {error_pattern[:70]}"
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            body = f"""Error Resolved

Pattern:     {error_pattern[:120]}
Status:      Resolved — no longer appearing frequently
Resolved At: {timestamp}

The recurring error is now below the alert threshold.

---
Render Monitor""".strip()

            html_body = f"""
            <html>
              <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
                  <h2 style="color: #388e3c;">🟢 Recurring Error Resolved</h2>
                  <p><strong>Pattern:</strong> {error_pattern[:120]}</p>
                  <p><strong>Status:</strong> <span style="color: #388e3c; font-weight: bold;">Resolved</span> — no longer appearing frequently</p>
                  <p><strong>Resolved At:</strong> {timestamp}</p>
                  <p style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd;">
                    The recurring error is now below the alert threshold. ✓
                  </p>
                  <p style="font-size: 12px; color: #999;">Render Monitor</p>
                </div>
              </body>
            </html>"""

            return self.send_email(subject, body, html_body)
        except Exception as e:
            logger.error(f"Error sending spike recovery: {e}")
            return False

    def send_ai_service_recovered(self, service_name: str) -> bool:
        """Send notification when an AI service (e.g. Gemini) comes back operational."""
        try:
            subject = f"🟢 {service_name} is Operational"
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            body = f"""Service Recovery

Service:      {service_name}
Status:       Operational
Recovered At: {timestamp}

{service_name} is back online and responding normally.

---
Render Monitor""".strip()

            html_body = f"""
            <html>
              <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
                  <h2 style="color: #388e3c;">🟢 {service_name} is Operational</h2>
                  <p><strong>Service:</strong> {service_name}</p>
                  <p><strong>Status:</strong> <span style="color: #388e3c; font-weight: bold;">Operational</span></p>
                  <p><strong>Recovered At:</strong> {timestamp}</p>
                  <p style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd;">
                    {service_name} is back online and responding normally. ✓
                  </p>
                  <p style="font-size: 12px; color: #999;">Render Monitor</p>
                </div>
              </body>
            </html>"""

            email_key = f"AI_RECOVERED_{service_name}"
            if email_key in self.sent_emails:
                if (datetime.now() - self.sent_emails[email_key]).total_seconds() < 300:
                    return False

            result = self.send_email(subject, body, html_body)
            if result:
                self.sent_emails[email_key] = datetime.now()
            return result
        except Exception as e:
            logger.error(f"Error sending AI service recovery: {e}")
            return False

    def send_crash_detected_alert(self, crash_type: str, detail: str) -> bool:
        """Send alert when a crash/OOM is detected in logs even if the service auto-recovered."""
        try:
            subject = f"🔴 Crash Detected: {crash_type}"
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            body = f"""Crash / OOM Detected

Type:       {crash_type}
Detail:     {detail[:200]}
Detected:   {timestamp}

Render restarted the service automatically, but a crash occurred.
Check memory usage and error logs for the root cause.

---
Render Monitor""".strip()

            html_body = f"""
            <html>
              <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
                  <h2 style="color: #d32f2f;">🔴 Crash / OOM Detected</h2>
                  <table style="width:100%;border-collapse:collapse;">
                    <tr><td style="padding:6px 0;color:#666;width:120px;">Type</td><td style="padding:6px 0;font-weight:600;color:#d32f2f;">{crash_type}</td></tr>
                    <tr><td style="padding:6px 0;color:#666;vertical-align:top;">Detail</td><td style="padding:6px 0;"><code style="background:#f5f5f5;padding:4px 8px;border-radius:3px;font-size:12px;word-break:break-all;">{detail[:200]}</code></td></tr>
                    <tr><td style="padding:6px 0;color:#666;">Detected At</td><td style="padding:6px 0;">{timestamp}</td></tr>
                  </table>
                  <p style="margin-top:16px;padding:12px;background:#fff3e0;border-left:4px solid #f57c00;border-radius:3px;font-size:13px;">
                    Render restarted the service automatically. Check memory usage and logs for the root cause.
                  </p>
                  <p style="font-size: 12px; color: #999;">Render Monitor</p>
                </div>
              </body>
            </html>"""

            email_key = f"CRASH_{crash_type}_{timestamp[:13]}"  # dedupe per hour per type
            if email_key in self.sent_emails:
                return False

            result = self.send_email(subject, body, html_body)
            if result:
                self.sent_emails[email_key] = datetime.now()
            return result
        except Exception as e:
            logger.error(f"Error sending crash alert: {e}")
            return False

    def test_email_connection(self):
        """Test email connection with credentials."""
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
            logger.info("Email connection test successful")
            return True
        
        except Exception as e:
            logger.error(f"Email connection test failed: {str(e)}")
            return False
