class Main(object):
    title = 'Rancher'
    navigation_menu = 'ul[class*=nav-main]'
    security_option = 'a[aria-label=Security]'
    authentication_option = 'a[href*=authentication]'
    user_menu = 'div[aria-label="User Menu: "]'
    user_menu_apis_keys_option = "//span[text()='API & Keys']"
    add_api_key_btn = "//button[text()='Add Key']"
    api_button_create = "//button[text()='Create']"
    api_button_close = "//button[text()='Close']"
    token_code = 'section > div:nth-child(7) > code'
