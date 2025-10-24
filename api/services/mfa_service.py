import pyotp
import boto3

from django.conf import settings

from authentication.email_templates import mfa_email

from ecommerceBackend import settings

class TOTPMFAService:
    def __init__(self):
        self.ses_client = boto3.client(
            "ses",
            region_name="ap-southeast-2",
            aws_access_key_id=settings.AWS_ACCESS_KEY,
            aws_secret_access_key=settings.AWS_SECRET_KEY
        )
    

    def generate_user_secret(self, user):
        """Generate unique secret for user"""
        if not user.mfa_secret:
            user.mfa_secret = pyotp.random_base32()
            user.save()
        return user.mfa_secret
    

    def get_current_code(self, user):
        """Get current valid TOTP code for user"""
        secret = self.generate_user_secret(user)
        totp = pyotp.TOTP(secret, interval=300) # 5 minutes
        return totp.now()
    

    def verify_mfa_code(self, user, code):
        """Verify TOTP code"""
        secret = self.generate_user_secret(user)
        totp = pyotp.TOTP(secret, interval=300) # 5 minutes
        return totp.verify(code, valid_window=0)  # Only allow current window
    

    def send_mfa_code_email(self, user):
        """Send MFA code via email"""
        try:
            code = self.get_current_code(user)
            
            self.ses_client.send_email(
                Source=mfa_email.sender_email,
                Destination={"ToAddresses": [user.email]},
                Message={
                    "Subject": {"Data": mfa_email.subject, "Charset": "UTF-8"},
                    "Body": {
                        "Html": {
                            "Data": mfa_email.body_html.format(code=code), 
                            "Charset": "UTF-8"
                        },
                    }
                }
            )

            return True
        except Exception as e:
            return False
    

    def send_mfa_code_sms(self, user):
        """Send MFA code via SMS (using AWS SNS)"""
        try:
            code = self.get_current_code(user)
            
            sns_client = boto3.client(
                "sns",
                region_name="ap-southeast-2",
                aws_access_key_id=settings.AWS_ACCESS_KEY,
                aws_secret_access_key=settings.AWS_SECRET_KEY
            )
            
            sns_client.publish(
                PhoneNumber=user.phone,
                Message=f"Your BDNX security code is: {code}. This code expires in 5 minutes."
            )
            
            return True
        except Exception as e:
            return False
