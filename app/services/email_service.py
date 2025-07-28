import smtplib
import logging
from email.mime.text import MIMEText
from app.core.config import settings
from typing import List

def send_welcome_email(user_email: str, user_name: str):
    """Send welcome email to new user."""
    try:
        subject = "✨ Welcome to LawVriksh - Help Us Build Something Amazing!"
        body = f"""Hello {user_name},

Thank you for joining LawVriksh! We're thrilled to have you as part of our founding member community.

Your feedback is crucial in helping us build a platform that truly serves the needs of legal professionals. Please take 5 minutes to share your insights and help shape the future of LawVriksh:

👉 Feedback Survey: https://lawvriksh.com/feedback

Start sharing and climb the leaderboard!

Best regards,
The LawVriksh Team

---
🌐 Visit us: https://www.lawvriksh.com
💬 Share feedback: https://lawvriksh.com/feedback"""

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = user_email
        
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAIL_FROM, [user_email], msg.as_string())
        
        logging.info(f"Welcome email sent successfully to {user_email}")
    except Exception as e:
        logging.error(f"Failed to send welcome email to {user_email}: {str(e)}")
        raise

def send_feedback_thank_you_email(user_email: str, user_name: str):
    """Send thank you email after feedback submission."""
    try:
        subject = "🙏 Thank You for Your Valuable Feedback!"
        body = f"""Dear {user_name},

Thank you so much for taking the time to share your valuable feedback with us!

We've successfully received your survey response, and we want you to know how much we appreciate your insights. Your feedback is incredibly important to us and will directly help shape the future of LawVriksh to better serve the legal community.

Our team will carefully review all the feedback we receive to identify key areas for improvement and new features that matter most to legal professionals like yourself.

If you have any additional thoughts or questions, please don't hesitate to reach out to us at info@lawvriksh.com.

Thank you again for being part of our founding member community and helping us build something amazing!

Best regards,
The LawVriksh Team

---
🌐 Visit us: https://www.lawvriksh.com
📧 Contact: info@lawvriksh.com"""

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = user_email

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAIL_FROM, [user_email], msg.as_string())

        logging.info(f"Feedback thank you email sent successfully to {user_email}")
        return True
    except Exception as e:
        logging.error(f"Failed to send feedback thank you email to {user_email}: {str(e)}")
        # Don't raise the exception - we don't want email failures to break feedback submission
        return False

def send_email(user_email: str, subject: str, body: str):
    """Send a generic email to a user."""
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = user_email

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAIL_FROM, [user_email], msg.as_string())

        logging.info(f"Email sent successfully to {user_email}")
        return True
    except Exception as e:
        logging.error(f"Failed to send email to {user_email}: {str(e)}")
        raise

def send_bulk_email(emails: List[str], subject: str, body: str):
    """Send an email to a list of addresses."""
    if not emails:
        logging.warning("No emails provided for bulk email")
        return
    
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = settings.EMAIL_FROM
        
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            
            for email in emails:
                try:
                    msg["To"] = email
                    server.sendmail(settings.EMAIL_FROM, [email], msg.as_string())
                    logging.info(f"Bulk email sent successfully to {email}")
                except Exception as e:
                    logging.error(f"Failed to send bulk email to {email}: {str(e)}")
                    continue
        
        logging.info(f"Bulk email process completed. Sent to {len(emails)} recipients")
    except Exception as e:
        logging.error(f"Failed to send bulk email: {str(e)}")
        raise 