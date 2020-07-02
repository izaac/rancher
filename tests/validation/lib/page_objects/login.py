from .url import _url


class Login(object):
    url = _url('/')
    local_username = 'input[name=username]'
    local_password = 'input[name=password]'
    local_sign_in_btn = 'button[class*=bg-primary]'
    azure_login_btn = 'i[class*=icon-azuread]'
