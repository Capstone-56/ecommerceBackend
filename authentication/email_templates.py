from dataclasses import dataclass

@dataclass
class PasswordResetEmail:
    sender_email: str
    subject: str
    body_html: str

# Create an instance
password_reset_email = PasswordResetEmail(
    sender_email="BDNX@bdnx.com",
    subject="Password Reset",
    body_html="""
        <html>
        <body>
        <h2>Password Reset</h2>
        <p>Password Change Request
          We've received a password change request for your BDNX account.	
          This link will expire in 24 hours. If you did not request a password change,
          please ignore this email, no changes will be made to your account.
        </p>
        </body>
        </html>
    """
)
