import sys
from pathlib import Path
from http.cookiejar import CookieJar
from typing import List, Dict

from .logger import logger

def load_browser_cookies(domain_name: str = "", verbose=True) -> List[Dict[str, dict]]:
    """
    Try to load cookies from all supported browsers and Chrome profiles.
    Returns a list of cookie sets, where each set represents cookies from a browser/profile.
    Optionally pass in a domain name to only load cookies from the specified domain.

    Parameters
    ----------
    domain_name : str, optional
        Domain name to filter cookies by, by default will load all cookies without filtering.
    verbose : bool, optional
        If `True`, will print more infomation in logs.

    Returns
    -------
    `List[Dict[str, dict]]`
        List of dictionaries, where each dict contains:
        - 'source': str - Browser/profile name (e.g., 'chrome_profile_1', 'firefox')
        - 'cookies': dict - Cookie name-value pairs for the specified domain
    """

    try:
        import browser_cookie3 as bc3
    except ImportError:
        # Fallback to try importing from local path
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "browser_cookie3",
                _LOCAL_BROWSER_COOKIE3_PATH / "__init__.py"
            )
            if spec and spec.loader:
                bc3 = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(bc3)
            else:
                if verbose:
                    logger.warning("browser-cookie3 package not found")
                return []
        except Exception as e:
            if verbose:
                logger.warning(f"Failed to load browser-cookie3: {e}")
            return []

    cookie_sets = []

    # Chrome with multi-profile support
    try:
        # Check if the local package supports get_chrome_profiles
        if hasattr(bc3, 'get_chrome_profiles'):
            try:
                profiles = bc3.get_chrome_profiles()
                if profiles:
                    for profile_name, profile_path in profiles.items():
                        try:
                            jar: CookieJar = bc3.chrome(domain_name=domain_name, profile=profile_name)
                            if jar:
                                cookie_dict = {cookie.name: cookie.value for cookie in jar}
                                if cookie_dict:  # Only add if cookies found
                                    cookie_sets.append({
                                        'source': f'chrome_{profile_name}',
                                        'cookies': cookie_dict
                                    })
                                    if verbose:
                                        logger.debug(f"Loaded cookies from Chrome profile: {profile_name}")
                        except PermissionError as e:
                            if verbose:
                                logger.warning(
                                    f"Permission denied while loading cookies from Chrome profile {profile_name}. {e}"
                                )
                            continue  # Continue to next profile
                        except bc3.BrowserCookieError:
                            if verbose:
                                logger.debug(f"No cookies found in Chrome profile {profile_name}")
                            continue  # Continue to next profile
                        except Exception as e:
                            if verbose:
                                logger.debug(f"Failed to load cookies from Chrome profile {profile_name}: {e}")
                            continue  # Continue to next profile
                else:
                    if verbose:
                        logger.debug("No Chrome profiles found")
            except Exception as e:
                if verbose:
                    logger.debug(f"Error getting Chrome profiles: {e}. Trying default Chrome...")
        
        # Fallback to default Chrome if multi-profile not supported or failed
        if not hasattr(bc3, 'get_chrome_profiles') or not cookie_sets:
            try:
                jar: CookieJar = bc3.chrome(domain_name=domain_name)
                if jar:
                    cookie_dict = {cookie.name: cookie.value for cookie in jar}
                    if cookie_dict:
                        cookie_sets.append({
                            'source': 'chrome',
                            'cookies': cookie_dict
                        })
                        if verbose:
                            logger.debug("Loaded cookies from default Chrome")
            except PermissionError as e:
                if verbose:
                    logger.warning(f"Permission denied while loading cookies from Chrome. {e}")
            except bc3.BrowserCookieError:
                if verbose:
                    logger.debug("No cookies found in default Chrome")
            except Exception as e:
                if verbose:
                    logger.debug(f"Failed to load cookies from Chrome: {e}")
    except Exception as e:
        if verbose:
            logger.debug(f"Error loading Chrome cookies: {e}")

    # Other browsers (single profile)
    for cookie_fn in [
        bc3.chromium,
        bc3.opera,
        bc3.opera_gx,
        bc3.brave,
        bc3.edge,
        bc3.vivaldi,
        bc3.firefox,
        bc3.librewolf,
        bc3.safari,
    ]:
        try:
            jar: CookieJar = cookie_fn(domain_name=domain_name)
            if jar:
                cookie_dict = {cookie.name: cookie.value for cookie in jar}
                if cookie_dict:
                    cookie_sets.append({
                        'source': cookie_fn.__name__,
                        'cookies': cookie_dict
                    })
                    if verbose:
                        logger.debug(f"Loaded cookies from {cookie_fn.__name__}")
        except bc3.BrowserCookieError:
            # No cookies found, continue to next browser
            if verbose:
                logger.debug(f"No cookies found in {cookie_fn.__name__}")
            continue
        except PermissionError as e:
            if verbose:
                logger.warning(
                    f"Permission denied while trying to load cookies from {cookie_fn.__name__}. {e}"
                )
            continue  # Continue to next browser
        except Exception as e:
            if verbose:
                logger.debug(
                    f"Error happened while trying to load cookies from {cookie_fn.__name__}. {e}"
                )
            continue  # Continue to next browser

    return cookie_sets
