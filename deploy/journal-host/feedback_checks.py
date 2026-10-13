"""Allow nginx's asynchronous reload to settle without weakening authentication."""
import time
from urllib.error import HTTPError


def wait_for_login(check, sleep=time.sleep):
    for attempt in range(10):
        try:
            return check()
        except HTTPError as error:
            # Only the old static site's 404 is transient. A successful anonymous
            # response, wrong challenge, auth failure or other error must fail.
            if error.code != 404 or attempt == 9:
                raise
            sleep(0.5)
