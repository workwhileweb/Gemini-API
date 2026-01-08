import os
import re
import asyncio
from asyncio import Task
from pathlib import Path
from typing import List, Tuple, Union

from httpx import AsyncClient, Response

from ..constants import Endpoint, Headers
from ..exceptions import AuthError
from .load_browser_cookies import load_browser_cookies
from .logger import logger


async def send_request(
    cookies: dict, proxy: str | None = None, source: str = "unknown"
) -> tuple[Response | None, dict, str]:
    """
    Send http request with provided cookies.

    Returns
    -------
    tuple[Response | None, dict, str]
        Response, cookies, and source identifier
    """

    async with AsyncClient(
        proxy=proxy,
        headers=Headers.GEMINI.value,
        cookies=cookies,
        follow_redirects=True,
        verify=False,
    ) as client:
        response = await client.get(Endpoint.INIT.value)
        response.raise_for_status()
        return response, cookies, source


async def get_access_token(
    base_cookies: dict, proxy: str | None = None, verbose: bool = False, collect_all: bool = False
) -> Union[Tuple[str, dict], List[Tuple[str, dict, str]]]:
    """
    Send a get request to gemini.google.com for each group of available cookies and return
    the value of "SNlM0e" as access token.

    Possible cookie sources:
    - Base cookies passed to the function.
    - __Secure-1PSID from base cookies with __Secure-1PSIDTS from cache.
    - Local browser cookies (if optional dependency `browser-cookie3` is installed).

    Parameters
    ----------
    base_cookies : `dict`
        Base cookies to be used in the request.
    proxy: `str`, optional
        Proxy URL.
    verbose: `bool`, optional
        If `True`, will print more infomation in logs.
    collect_all: `bool`, optional
        If `True`, returns all valid cookie sets. If `False`, returns only the first successful one.

    Returns
    -------
    `tuple[str, dict]` or `List[tuple[str, dict, str]]`
        If collect_all=False: (access_token, cookies)
        If collect_all=True: List of (access_token, cookies, source) tuples
    """

    async with AsyncClient(proxy=proxy, follow_redirects=True, verify=False) as client:
        response = await client.get(Endpoint.GOOGLE.value)

    extra_cookies = {}
    if response.status_code == 200:
        extra_cookies = response.cookies

    tasks = []

    # Base cookies passed directly on initializing client
    if "__Secure-1PSID" in base_cookies and "__Secure-1PSIDTS" in base_cookies:
        tasks.append(Task(send_request({**extra_cookies, **base_cookies}, proxy=proxy, source="base")))
    elif verbose:
        logger.debug(
            "Skipping loading base cookies. Either __Secure-1PSID or __Secure-1PSIDTS is not provided."
        )

    # Cached cookies in local file
    cache_dir = (
        (GEMINI_COOKIE_PATH := os.getenv("GEMINI_COOKIE_PATH"))
        and Path(GEMINI_COOKIE_PATH)
        or (Path(__file__).parent / "temp")
    )
    if "__Secure-1PSID" in base_cookies:
        filename = f".cached_1psidts_{base_cookies['__Secure-1PSID']}.txt"
        cache_file = cache_dir / filename
        if cache_file.is_file():
            cached_1psidts = cache_file.read_text()
            if cached_1psidts:
                cached_cookies = {
                    **extra_cookies,
                    **base_cookies,
                    "__Secure-1PSIDTS": cached_1psidts,
                }
                tasks.append(Task(send_request(cached_cookies, proxy=proxy, source="cached")))
            elif verbose:
                logger.debug("Skipping loading cached cookies. Cache file is empty.")
        elif verbose:
            logger.debug("Skipping loading cached cookies. Cache file not found.")
    else:
        valid_caches = 0
        cache_files = cache_dir.glob(".cached_1psidts_*.txt")
        for cache_file in cache_files:
            cached_1psidts = cache_file.read_text()
            if cached_1psidts:
                cached_cookies = {
                    **extra_cookies,
                    "__Secure-1PSID": cache_file.stem[16:],
                    "__Secure-1PSIDTS": cached_1psidts,
                }
                tasks.append(Task(send_request(cached_cookies, proxy=proxy, source=f"cached_{cache_file.stem}")))
                valid_caches += 1

        if valid_caches == 0 and verbose:
            logger.debug(
                "Skipping loading cached cookies. Cookies will be cached after successful initialization."
            )

    # Browser cookies (if browser-cookie3 is installed) - now supports multi-profiles
    try:
        valid_browser_cookies = 0
        browser_cookie_sets = load_browser_cookies(
            domain_name="google.com", verbose=verbose
        )
        if browser_cookie_sets:
            for cookie_set in browser_cookie_sets:
                cookies = cookie_set.get('cookies', {})
                source = cookie_set.get('source', 'unknown')
                
                if secure_1psid := cookies.get("__Secure-1PSID"):
                    # Filter by base_cookies if provided
                    if (
                        "__Secure-1PSID" in base_cookies
                        and base_cookies["__Secure-1PSID"] != secure_1psid
                    ):
                        if verbose:
                            logger.debug(
                                f"Skipping loading local browser cookies from {source}. "
                                f"__Secure-1PSID does not match the one provided."
                            )
                        continue

                    local_cookies = {**extra_cookies, "__Secure-1PSID": secure_1psid}
                    if secure_1psidts := cookies.get("__Secure-1PSIDTS"):
                        local_cookies["__Secure-1PSIDTS"] = secure_1psidts
                    if nid := cookies.get("NID"):
                        local_cookies["NID"] = nid
                    
                    tasks.append(Task(send_request(local_cookies, proxy=proxy, source=source)))
                    valid_browser_cookies += 1
                    if verbose:
                        logger.debug(f"Loaded local browser cookies from {source}")

        if valid_browser_cookies == 0 and verbose:
            logger.debug(
                "Skipping loading local browser cookies. Login to gemini.google.com in your browser first."
            )
    except ImportError:
        if verbose:
            logger.debug(
                "Skipping loading local browser cookies. Optional dependency 'browser-cookie3' is not installed."
            )
    except Exception as e:
        if verbose:
            logger.warning(f"Skipping loading local browser cookies. {e}")

    if not tasks:
        raise AuthError(
            "No valid cookies available for initialization. Please pass __Secure-1PSID and __Secure-1PSIDTS manually."
        )

    valid_results = []
    for i, future in enumerate(asyncio.as_completed(tasks)):
        try:
            response, request_cookies, source = await future
            match = re.search(r'"SNlM0e":"(.*?)"', response.text)
            if match:
                access_token = match.group(1)
                if verbose:
                    logger.debug(
                        f"Init attempt ({i + 1}/{len(tasks)}) succeeded from {source}. Access token obtained."
                    )
                
                if collect_all:
                    valid_results.append((access_token, request_cookies, source))
                else:
                    # Return first successful result
                    return access_token, request_cookies
            elif verbose:
                logger.debug(
                    f"Init attempt ({i + 1}/{len(tasks)}) failed. Cookies invalid."
                )
        except Exception as e:
            if verbose:
                logger.debug(
                    f"Init attempt ({i + 1}/{len(tasks)}) failed with error: {e}"
                )

    if collect_all:
        if valid_results:
            return valid_results
        else:
            raise AuthError(
                "Failed to initialize client. No valid cookie sets found. "
                f"(Failed initialization attempts: {len(tasks)})"
            )
    else:
        raise AuthError(
            "Failed to initialize client. SECURE_1PSIDTS could get expired frequently, please make sure cookie values are up to date. "
            f"(Failed initialization attempts: {len(tasks)})"
        )
