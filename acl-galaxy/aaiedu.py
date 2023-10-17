"""
Backend for OpenID AAIEDU
"""

from social_core.backends.open_id_connect import OpenIdConnectAuth
from .hzsi_srce import hzsi_users
from galaxy import exceptions
import os


class AAIEDUconn(OpenIdConnectAuth):
    name = 'aaiedu'
    OIDC_ENDPOINT = 'https://login.aaiedu.hr/' #Defined in oidc_backends.xml
    EXTRA_DATA = [
        ('expires_in', 'expires_in', True),
        ('refresh_token', 'refresh_token', True),
        ('id_token', 'id_token', True),
        ('other_tokens', 'other_tokens', True)
    ]
    DEFAULT_SCOPE = ['openid', 'email', 'profile', 'offline_access', 'address', 'phone', 'hrEduPersonUniqueID']
    JWT_DECODE_OPTIONS = {'verify_at_hash': False}

    def get_user_details(self, response):
        username_key = self.setting('USERNAME_KEY', default=self.USERNAME_KEY)

        logged_username = response.get('hrEduPersonUniqueID', None)

        if logged_username:
            logged_username = logged_username[0]

        return {
            'username': logged_username,
            'fullname': response.get('name'),
            'email': response.get('email'),
            'first_name': response.get('givenName'),
            'last_name': response.get('family_name')
        }

    def auth_allowed(self, response, details):
        ret_parent = super(OpenIdConnectAuth, self).auth_allowed(response, details)
        logged_username = response.get('hrEduPersonUniqueID', None)

        if logged_username:
            logged_username = logged_username[0]

        hzsiusers = hzsi_users()
        if logged_username in hzsiusers:
            return ret_parent
        else:
            raise exceptions.AuthenticationFailed('User not registered')
