"""
Delivery layer.

Sends the morning briefing by email via SMTP.
If email fails, saves the report locally and logs the error.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


def send_email(subject: str, body: str, config) -> bool:
    """
    Send the briefing email.

    Args:
        subject: Email subject line
        body: Plain text email body
        config: EmailConfig object

    Returns:
        True if email was sent successfully, False otherwise
    """
    if not config.recipient_email:
        logger.error("No recipient email configured. Set RSAF_RECIPIENT_EMAIL.")
        return False

    if not config.smtp_username or not config.smtp_password:
        logger.error("SMTP credentials not configured. "
                     "Set RSAF_SMTP_USERNAME and RSAF_SMTP_PASSWORD.")
        return False

    sender = config.sender_email or config.smtp_username

    try:
        # Build the email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = config.recipient_email

        # Plain text version
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Connect and send
        logger.info(f"Connecting to SMTP server {config.smtp_host}:{config.smtp_port}")

        if config.use_tls:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port,
                                  timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port,
                                  timeout=30)

        server.login(config.smtp_username, config.smtp_password)
        server.sendmail(sender, [config.recipient_email], msg.as_string())
        server.quit()

        logger.info(f"Email sent successfully to {config.recipient_email}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        logger.error("Check your RSAF_SMTP_USERNAME and RSAF_SMTP_PASSWORD. "
                     "For Gmail, use an App Password.")
        return False

    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {e}")
        return False

    except Exception as e:
        logger.error(f"Email delivery failed: {e}", exc_info=True)
        return False
