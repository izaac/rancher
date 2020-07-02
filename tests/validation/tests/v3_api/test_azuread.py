from seleniumbase import BaseCase
from selenium.webdriver.remote.errorhandler import NoSuchElementException
from selenium.webdriver.common.by import By
from lib.page_objects import Login
from lib.page_objects import Main
from lib.page_objects import Auth
from lib.page_objects import MSLogin
import os
import sys
# import urllib.parse as urlparse
# from urllib.parse import parse_qs


AZURE_AD_ADMIN = os.environ.get('AZURE_AD_ADMIN')
AZURE_AD_PASSWORD = os.environ.get('AZURE_AD_PASSWORD')
AZURE_AD_TENANT_ID = os.environ.get('AZURE_AD_TENANT_ID')
AZURE_AD_APP_ID = os.environ.get('AZURE_AD_APP_ID')
AZURE_AD_APP_SECRET = os.environ.get('AZURE_AD_APP_SECRET')
RANCHER_AUTH_USERNAME = os.environ.get('RANCHER_AUTH_USERNAME', 'admin')
RANCHER_AUTH_PASSWORD = os.environ.get('RANCHER_AUTH_PASSWORD')

env_vars = {
    'AZURE_AD_ADMIN': AZURE_AD_ADMIN,
    'AZURE_AD_PASSWORD': AZURE_AD_PASSWORD,
    'AZURE_AD_TENANT_ID': AZURE_AD_TENANT_ID,
    'AZURE_AD_APP_ID': AZURE_AD_APP_ID,
    'AZURE_AD_APP_SECRET': AZURE_AD_APP_SECRET,
    'RANCHER_AUTH_PASSWORD': RANCHER_AUTH_PASSWORD
}

if None in env_vars.values():
    keys = {k for k, v in env_vars.items() if v is None}
    print("You are missing the following env vars:")
    for key in keys:
        print(key)
    sys.exit(1)


class AzureADTest(BaseCase):

    token_ad = None
    token_rancher = None

    def tearDown(self):
        super(AzureADTest, self).tearDown()

    def setUp(self):
        super(AzureADTest, self).setUp()
        if not self.check_azure_ad_is_enabled():
            print('Enabling Azure AD')
            self.enable_azuread_auth()

    def check_azure_ad_is_enabled(self):
        try:
            self.is_element_visible(Login.azure_login_btn)
        except NoSuchElementException:
            return False
        else:
            return True

    def do_ms_login(self):
        self.assert_element(MSLogin.username)
        self.type(MSLogin.username, AZURE_AD_ADMIN)
        self.click(MSLogin.next_btn)
        self.assert_element(MSLogin.password)
        self.type(MSLogin.password, AZURE_AD_PASSWORD)
        self.assert_element(MSLogin.sign_in_btn)
        self.click(MSLogin.sign_in_btn)
        self.assert_element(MSLogin.yes_btn)
        self.click(MSLogin.yes_btn)
        # url = self.get_current_url()
        # print(f'\n{url}')
        # parsed = urlparse.urlparse(url)
        # self.token_ad = parse_qs(parsed.query)['code'][0]
        # print(self.token_ad)

    def enable_azuread_auth(self):
        self.open(Login.url)
        self.type(Login.local_username, RANCHER_AUTH_USERNAME)
        self.type(Login.local_password, RANCHER_AUTH_PASSWORD)
        self.click(Login.local_sign_in_btn)
        self.assert_title(Main.title)
        self.assert_element(Main.navigation_menu)
        self.hover_and_click(Main.security_option, Main.authentication_option)
        self.assert_exact_text('Authentication', Auth.header)
        self.click(Auth.azure_ad)
        banners = self.find_visible_elements(Auth.azure_ad_banner)
        banner = banners[1] if len(banners) > 1 else banners[0]
        self.assert_equal(banner.text, 'Azure AD is not configured')
        self.assert_element(Auth.azure_ad_tennant_id)
        self.type(Auth.azure_ad_tennant_id, AZURE_AD_TENANT_ID)
        self.type(Auth.azure_ad_application_id, AZURE_AD_APP_ID)
        self.type(Auth.azure_ad_application_secret, AZURE_AD_APP_SECRET)
        self.click(Auth.enable_azure_ad)
        self.switch_to_window(1)
        self.do_ms_login()
        self.switch_to_default_window()
        self.assert_exact_text("Allow any valid Users", Auth.site_options_text)

    def test_first_login(self):
        self.open(Login.url)
        self.click(Login.azure_login_btn)
        self.do_ms_login()
        self.assert_title(Main.title)
        self.assert_element(Main.navigation_menu)
        self.hover_and_click(Main.user_menu,
                             Main.user_menu_apis_keys_option,
                             click_by=By.XPATH)
        self.click(Main.add_api_key_btn, by=By.XPATH)
        self.click(Main.api_button_create, by=By.XPATH)
        self.token_rancher = self.get_text(Main.token_code)
        print(self.token_rancher)
        self.click(Main.api_button_close)



        # import requests
        # url = "https://izaac245.qa.rancher.space/v3-public/azureADProviders/azuread?action=login"
        #
        # payload = "{\"code\":\"" + self.token_ad + "\",\"description\":\"UI Session\"" \
        #           ",\"responseType\":\"cookie\",\"ttl\":57600000}"
        # headers = {
        #     'x-api-no-challenge': 'true',
        #     'accept': 'application/json',
        #     'DNT': '1',
        #     'x-api-action-links': 'actionLinks',
        #     'x-api-csrf': '10d42745f0',
        #     # 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36',
        #     'content-type': 'application/json',
        #     'Cookie': 'CSRF=9c46ac7c68'
        # }
        #
        # response = requests.request("POST", url, headers=headers, data=payload, verify=False)
        #
        # print(response.text.encode('utf8'))


