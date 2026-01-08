# Multi-Profile Cookie Support - Implementation Summary

## Overview
This document describes the changes made to support multiple Chrome profiles and round-robin cookie rotation in the Gemini-API repository.

## Changes Made

### 1. Updated `load_browser_cookies.py`
- **Path**: `src/gemini_webapi/utils/load_browser_cookies.py`
- **Changes**:
  - Added support for local `browser_cookie3` package at `D:\github\browser_cookie3`
  - Changed return type from `dict[str, dict]` to `List[Dict[str, dict]]` to support multiple cookie sets
  - Added multi-profile support for Chrome using `get_chrome_profiles()` method (if available)
  - Each cookie set now includes a `source` identifier (e.g., `chrome_profile_1`, `chrome_profile_2`)
  - Fallback to default Chrome behavior if multi-profile support is not available

### 2. Updated `get_access_token.py`
- **Path**: `src/gemini_webapi/utils/get_access_token.py`
- **Changes**:
  - Added `collect_all` parameter to collect all valid cookie sets instead of just the first one
  - Updated `send_request()` to include `source` parameter for tracking cookie origin
  - Modified return type to support both single cookie set `(access_token, cookies)` and multiple sets `List[(access_token, cookies, source)]`
  - Updated browser cookie loading to work with the new list-based format from `load_browser_cookies()`
  - All valid cookie sets from multiple profiles are now collected and returned when `collect_all=True`

### 3. Updated `client.py`
- **Path**: `src/gemini_webapi/client.py`
- **Changes**:
  - Added new slots: `_cookie_sets` and `_cookie_index` for managing multiple cookie sets
  - Modified `__init__()` to initialize cookie rotation variables
  - Updated `init()` method to:
    - Collect all valid cookie sets from multiple profiles
    - Store them in `_cookie_sets` list
    - Initialize with the first cookie set
    - Log all found cookie sets for debugging
  - Added `_get_next_cookie_set()` method for round-robin rotation:
    - Increments `_cookie_index` in round-robin fashion
    - Updates client cookies and access token
    - Logs cookie set switching for debugging
  - Updated `generate_content()` to use `_get_next_cookie_set()` before each request
  - Updated `_batch_execute()` to use `_get_next_cookie_set()` before each batch request

### 4. Updated `requirements.txt`
- **Path**: `requirements.txt`
- **Changes**:
  - Added comment explaining that the repo uses local `browser_cookie3` package
  - Commented out `browser-cookie3` pip package (can be uncommented for fallback)

## How It Works

### Cookie Collection
1. When `GeminiClient.init()` is called, it attempts to collect all valid cookie sets
2. Cookies are collected from:
   - Base cookies (if provided)
   - Cached cookies from files
   - Browser cookies from all Chrome profiles (if local package supports it)
   - Other browsers (Firefox, Edge, etc.)

### Round-Robin Rotation
1. Each time `generate_content()` or `_batch_execute()` is called, `_get_next_cookie_set()` is invoked
2. The method:
   - Increments `_cookie_index` modulo the number of cookie sets
   - Retrieves the next cookie set from `_cookie_sets`
   - Updates the client's cookies and access token
   - Logs the switch for debugging

### Example Flow
```
Request 1 → Cookie Set 0 (chrome_profile_1)
Request 2 → Cookie Set 1 (chrome_profile_2)
Request 3 → Cookie Set 2 (firefox)
Request 4 → Cookie Set 0 (chrome_profile_1) [wraps around]
```

## Benefits

1. **Load Distribution**: Requests are distributed across multiple profiles/accounts
2. **Rate Limit Avoidance**: Reduces chance of hitting rate limits on a single account
3. **Fault Tolerance**: If one cookie set fails, others can still be used
4. **Multi-Account Support**: Easily use multiple Google accounts without manual switching

## Configuration

### Local Package Path
The local `browser_cookie3` package is expected at:
```
D:\github\browser_cookie3
```

This path is hardcoded in `load_browser_cookies.py`. To change it, modify:
```python
_LOCAL_BROWSER_COOKIE3_PATH = Path(r"D:\github\browser_cookie3")
```

### Required Local Package Features
The local `browser_cookie3` package should support:
- `get_chrome_profiles()` method that returns a dict of profile names and paths
- `chrome(domain_name=..., profile=...)` method that accepts a profile parameter

## Backward Compatibility

The implementation maintains backward compatibility:
- If only one cookie set is found, it works as before
- If `collect_all=False` is used, it returns a single cookie set
- Existing code using single cookies will continue to work

## Logging

When `verbose=True`:
- Logs the number of cookie sets found
- Lists all cookie set sources
- Logs each cookie set switch during rotation

Example log output:
```
Found 3 valid cookie set(s) from multiple profiles
  Cookie set 1: chrome_Profile 1
  Cookie set 2: chrome_Profile 2
  Cookie set 3: firefox
Switched to cookie set 2/3 from chrome_Profile 2
```

## Testing

To test the implementation:
1. Ensure you have multiple Chrome profiles with Gemini logged in
2. Initialize `GeminiClient()` without providing cookies
3. Check logs to see all cookie sets found
4. Make multiple requests and observe cookie rotation in logs

## Notes

- Cookie rotation happens automatically on each request
- Access tokens are cached per cookie set
- Auto-refresh tasks are started for all cookie sets (if enabled)
- The rotation is thread-safe within a single client instance

