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
