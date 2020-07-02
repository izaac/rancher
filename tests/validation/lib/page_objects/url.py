import os
import sys


def _url(path):
    rancher_url = os.environ.get('CATTLE_TEST_URL')
    if rancher_url:
        base_url = rancher_url
        return base_url + path
    else:
        print("Missing RANCHER_URL variable")
        sys.exit(1)


