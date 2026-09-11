"""Rate-limited, retrying wrapper around nba_api endpoint calls."""

import time

from requests.exceptions import RequestException

from . import settings


def fetch_with_retry(endpoint_cls, **kwargs):
    """Instantiate an nba_api endpoint class with retry/backoff, then sleep.

    nba_api's stats endpoints frequently time out or reset the connection
    under normal use, so failures here are expected and retried rather than
    raised on the first attempt. A fixed delay after every successful call
    keeps the pipeline under the NBA stats API's informal rate limits.
    """
    kwargs.setdefault("timeout", settings.REQUEST_TIMEOUT_SECONDS)

    last_error = None
    for attempt in range(1, settings.MAX_RETRIES + 1):
        try:
            result = endpoint_cls(**kwargs)
            time.sleep(settings.REQUEST_DELAY_SECONDS)
            return result
        except RequestException as exc:
            last_error = exc
        except Exception as exc:  # nba_api can raise bare json/value errors on bad responses
            last_error = exc

        if attempt < settings.MAX_RETRIES:
            backoff = settings.RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
            time.sleep(backoff)

    raise RuntimeError(
        f"Failed to fetch {endpoint_cls.__name__} after {settings.MAX_RETRIES} attempts "
        f"(kwargs={kwargs}): {last_error}"
    ) from last_error
