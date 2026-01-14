# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fastmcp>=2.12.5",
#   "httpx>=0.27.0,<1.0",
#   "pytz>=2024.1",
# ]
# ///

from datetime import UTC, datetime, timedelta

from fastmcp import FastMCP

# Try to import timezone libraries with fallback
try:
    import pytz

    TIMEZONE_LIB = "pytz"
except ImportError:
    try:
        from zoneinfo import ZoneInfo

        TIMEZONE_LIB = "zoneinfo"
    except ImportError:
        TIMEZONE_LIB = None

# Common timezone aliases for better compatibility
TIMEZONE_ALIASES = {
    "PT": "US/Pacific",
    "ET": "US/Eastern",
    "MT": "US/Mountain",
    "CT": "US/Central",
    "PST": "US/Pacific",
    "PDT": "US/Pacific",
    "EST": "US/Eastern",
    "EDT": "US/Eastern",
    "MST": "US/Mountain",
    "MDT": "US/Mountain",
    "CST": "US/Central",
    "CDT": "US/Central",
    "GMT": "UTC",
    "Z": "UTC",
}


def normalize_timezone(tz_name: str) -> str:
    """Normalize timezone name using aliases."""
    try:
        if not tz_name or not isinstance(tz_name, str):
            return "UTC"  # Safe fallback
        return TIMEZONE_ALIASES.get(tz_name.upper(), tz_name)
    except Exception:
        return "UTC"


def get_timezone_object(tz_name: str):
    """Get timezone object using available library."""
    try:
        if not tz_name or not isinstance(tz_name, str):
            return None

        tz_name = normalize_timezone(tz_name)

        if TIMEZONE_LIB == "pytz":
            try:
                return pytz.timezone(tz_name)
            except pytz.UnknownTimeZoneError:
                # Try common alternatives
                alternatives = {
                    "America/Los_Angeles": "US/Pacific",
                    "America/New_York": "US/Eastern",
                    "America/Chicago": "US/Central",
                    "America/Denver": "US/Mountain",
                }
                alt_name = alternatives.get(tz_name)
                if alt_name:
                    try:
                        return pytz.timezone(alt_name)
                    except pytz.UnknownTimeZoneError:
                        return None  # Return None instead of crashing
                return None  # Return None instead of raising
            except Exception:
                return None  # Handle any other pytz errors

        elif TIMEZONE_LIB == "zoneinfo":
            try:
                from zoneinfo import ZoneInfo

                return ZoneInfo(tz_name)
            except Exception:
                return None  # Handle zoneinfo errors gracefully
        else:
            return None

    except Exception:
        # Handle any unexpected errors
        return None


mcp = FastMCP(
    name="datetime_service",
    instructions="Datetime operations. Use timezone shortcuts: PT/EST/UTC. Default format: ISO.",
)


@mcp.tool()
def get_current_datetime(tz: str | None = None, format: str | None = None) -> str:
    """
    Get the current date and time.

    Args:
        tz: Target timezone (e.g., 'UTC', 'US/Pacific', 'America/Los_Angeles', 'PT', 'PST')
        format: Output format string (e.g., '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%SZ'). Defaults to ISO format.

    Returns:
        Current datetime as formatted string
    """
    try:
        # Input validation with helpful suggestions
        if tz is not None and not isinstance(tz, str):
            return """[FAILED] PARAMETER ERROR: Invalid timezone parameter

Expected: String value (e.g., 'UTC', 'US/Pacific', 'America/New_York')
Received: {type(tz).__name__}

[IDEA] CORRECT USAGE:
get_current_datetime(tz='UTC')
get_current_datetime(tz='US/Pacific')
get_current_datetime()  # Uses UTC by default"""

        if format is not None and not isinstance(format, str):
            return """[FAILED] PARAMETER ERROR: Invalid format parameter

Expected: String with datetime format codes
Received: {type(format).__name__}

[IDEA] CORRECT USAGE:
get_current_datetime(format='%Y-%m-%d %H:%M:%S')
get_current_datetime(format='%Y-%m-%dT%H:%M:%SZ')
get_current_datetime()  # Uses ISO format by default

[CLIPBOARD] COMMON FORMAT CODES:
%Y = 4-digit year (2023)
%m = Month (01-12)
%d = Day (01-31)
%H = Hour 24-hour (00-23)
%M = Minute (00-59)
%S = Second (00-59)"""

        # Get current UTC time
        now = datetime.now(UTC)

        # Convert to specified timezone if provided
        if tz:
            try:
                tz_obj = get_timezone_object(tz)
                if tz_obj:
                    if TIMEZONE_LIB == "pytz":
                        # pytz handles UTC conversion automatically
                        now = now.astimezone(tz_obj)
                    elif TIMEZONE_LIB == "zoneinfo":
                        now = now.astimezone(tz_obj)
                else:
                    # Provide helpful error but don't crash
                    normalized_tz = normalize_timezone(tz)
                    return f"""[FAILED] TIMEZONE ERROR: Unknown timezone '{tz}'

Normalized to: '{normalized_tz}'
Available library: {TIMEZONE_LIB}

[IDEA] SUPPORTED TIMEZONES:
UTC, GMT
US/Pacific, US/Eastern, US/Mountain, US/Central
America/New_York, America/Los_Angeles, America/Chicago
Europe/London, Europe/Paris, Asia/Tokyo

[IDEA] SHORTCUTS AVAILABLE:
PT/PST/PDT  US/Pacific
ET/EST/EDT  US/Eastern
MT/MST/MDT  US/Mountain
CT/CST/CDT  US/Central

[PROCESSING] RETRY WITH:
get_current_datetime(tz='UTC')
get_current_datetime(tz='US/Pacific')"""
            except Exception as tz_error:
                return f"""[FAILED] TIMEZONE PROCESSING ERROR

Timezone: '{tz}'
Error: {str(tz_error)}

[IDEA] TROUBLESHOOTING:
1. Check timezone name spelling
2. Use standard timezone identifiers
3. Try common timezones: UTC, US/Pacific, US/Eastern

[PROCESSING] RETRY WITH:
get_current_datetime(tz='UTC')
get_current_datetime()  # Uses UTC by default"""

        # Apply format if specified
        try:
            if format:
                return now.strftime(format)
            else:
                return now.isoformat()
        except Exception as fmt_error:
            return f"""[FAILED] FORMAT ERROR: Invalid datetime format

Format string: '{format}'
Error: {str(fmt_error)}

[IDEA] COMMON FORMAT EXAMPLES:
'%Y-%m-%d %H:%M:%S'  2023-12-25 14:30:45
'%Y-%m-%dT%H:%M:%SZ'  2023-12-25T14:30:45Z
'%B %d, %Y at %I:%M %p'  December 25, 2023 at 02:30 PM
'%Y/%m/%d'  2023/12/25

[PROCESSING] RETRY WITH:
get_current_datetime(format='%Y-%m-%d %H:%M:%S')
get_current_datetime()  # Uses ISO format"""

    except Exception as e:
        # Comprehensive error message with recovery suggestions
        error_details = []
        error_details.append("[FAILED] UNEXPECTED ERROR getting current datetime")
        error_details.append(f"Error: {str(e)}")

        if tz:
            try:
                normalized_tz = normalize_timezone(tz)
                error_details.append(f"Requested timezone: {tz}")
                if normalized_tz != tz:
                    error_details.append(f"Normalized timezone: {normalized_tz}")
                error_details.append(f"Available library: {TIMEZONE_LIB}")
            except Exception:
                error_details.append("Timezone processing failed")

        error_details.append("")
        error_details.append("[IDEA] RECOVERY OPTIONS:")
        error_details.append("1. Try without timezone: get_current_datetime()")
        error_details.append("2. Use UTC timezone: get_current_datetime(tz='UTC')")
        error_details.append(
            "3. Use simple format: get_current_datetime(format='%Y-%m-%d %H:%M:%S')"
        )

        return "\n".join(error_details)


@mcp.tool()
def convert_timezone(
    datetime_str: str, from_tz: str, to_tz: str, format: str | None = None
) -> str:
    """
    Convert datetime from one timezone to another.

    Args:
        datetime_str: Input datetime string
        from_tz: Source timezone (e.g., 'UTC', 'US/Eastern')
        to_tz: Target timezone (e.g., 'UTC', 'US/Pacific')
        format: Output format string. If not provided, uses ISO format.

    Returns:
        Converted datetime as formatted string
    """
    try:
        # Input validation with detailed guidance
        if not datetime_str or not isinstance(datetime_str, str):
            return """[FAILED] PARAMETER ERROR: Invalid datetime_str parameter

Expected: Non-empty string with date/time
Received: {type(datetime_str).__name__} - {repr(datetime_str)}

[IDEA] CORRECT FORMATS:
• '2023-12-25 14:30:00'
• '2023-12-25T14:30:00'
• '2023-12-25T14:30:00Z'
• '12/25/2023 14:30:00'

[PROCESSING] RETRY WITH:
convert_timezone('2023-12-25 14:30:00', 'US/Eastern', 'US/Pacific')"""

        if not from_tz or not isinstance(from_tz, str):
            return """[FAILED] PARAMETER ERROR: Invalid from_tz parameter

Expected: Non-empty string with source timezone
Received: {type(from_tz).__name__} - {repr(from_tz)}

[IDEA] VALID TIMEZONES:
• 'UTC', 'GMT'
• 'US/Pacific', 'US/Eastern', 'US/Mountain', 'US/Central'
• 'America/New_York', 'America/Los_Angeles'
• Shortcuts: 'PT', 'ET', 'MT', 'CT'

[PROCESSING] RETRY WITH:
convert_timezone('{datetime_str}', 'UTC', 'US/Pacific')"""

        if not to_tz or not isinstance(to_tz, str):
            return """[FAILED] PARAMETER ERROR: Invalid to_tz parameter

Expected: Non-empty string with target timezone
Received: {type(to_tz).__name__} - {repr(to_tz)}

[IDEA] VALID TIMEZONES:
• 'UTC', 'GMT'
• 'US/Pacific', 'US/Eastern', 'US/Mountain', 'US/Central'
• 'America/New_York', 'America/Los_Angeles'
• Shortcuts: 'PT', 'ET', 'MT', 'CT'

[PROCESSING] RETRY WITH:
convert_timezone('{datetime_str}', '{from_tz}', 'US/Pacific')"""

        if format is not None and not isinstance(format, str):
            return """[FAILED] PARAMETER ERROR: Invalid format parameter

Expected: String with datetime format codes (optional)
Received: {type(format).__name__}

[IDEA] COMMON FORMATS:
• '%Y-%m-%d %H:%M:%S' → 2023-12-25 14:30:45
• '%Y-%m-%dT%H:%M:%SZ' → 2023-12-25T14:30:45Z
• '%B %d, %Y at %I:%M %p' → December 25, 2023 at 02:30 PM

[PROCESSING] RETRY WITH:
convert_timezone('{datetime_str}', '{from_tz}', '{to_tz}', '%Y-%m-%d %H:%M:%S')"""

        # Parse the datetime string (try common formats)
        dt = None
        formats_tried = []
        formats_to_try = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y",
            "%Y%m%d %H%M%S",
            "%Y%m%d",
        ]

        for fmt in formats_to_try:
            try:
                dt = datetime.strptime(datetime_str, fmt)
                break
            except ValueError:
                formats_tried.append(fmt)
                continue

        if dt is None:
            return f"""[FAILED] DATETIME PARSING ERROR: Could not parse datetime string

Input: '{datetime_str}'
Tried {len(formats_tried)} different formats

[IDEA] SUPPORTED FORMATS:
• YYYY-MM-DD HH:MM:SS (e.g., '2023-12-25 14:30:00')
• YYYY-MM-DDTHH:MM:SS (e.g., '2023-12-25T14:30:00')
• YYYY-MM-DDTHH:MM:SSZ (e.g., '2023-12-25T14:30:00Z')
• MM/DD/YYYY HH:MM:SS (e.g., '12/25/2023 14:30:00')
• YYYY-MM-DD (e.g., '2023-12-25')

[PROCESSING] RETRY WITH:
convert_timezone('2023-12-25 14:30:00', '{from_tz}', '{to_tz}')
convert_timezone('2023-12-25T14:30:00', '{from_tz}', '{to_tz}')"""

        # Convert between timezones using available library
        try:
            from_tz_norm = normalize_timezone(from_tz)
            to_tz_norm = normalize_timezone(to_tz)

            from_timezone = get_timezone_object(from_tz_norm)
            to_timezone = get_timezone_object(to_tz_norm)

            if not from_timezone:
                return f"""[FAILED] SOURCE TIMEZONE ERROR: Unknown timezone

Input timezone: '{from_tz}'
Normalized to: '{from_tz_norm}'
Available library: {TIMEZONE_LIB}

[IDEA] SUPPORTED TIMEZONES:
• UTC, GMT
• US/Pacific, US/Eastern, US/Mountain, US/Central
• America/New_York, America/Los_Angeles, America/Chicago
• Europe/London, Europe/Paris, Asia/Tokyo

[IDEA] SHORTCUTS:
• PT/PST/PDT → US/Pacific
• ET/EST/EDT → US/Eastern
• MT/MST/MDT → US/Mountain
• CT/CST/CDT → US/Central

[PROCESSING] RETRY WITH:
convert_timezone('{datetime_str}', 'UTC', '{to_tz}')
convert_timezone('{datetime_str}', 'US/Eastern', '{to_tz}')"""

            if not to_timezone:
                return f"""[FAILED] TARGET TIMEZONE ERROR: Unknown timezone

Input timezone: '{to_tz}'
Normalized to: '{to_tz_norm}'
Available library: {TIMEZONE_LIB}

[IDEA] SUPPORTED TIMEZONES:
• UTC, GMT
• US/Pacific, US/Eastern, US/Mountain, US/Central
• America/New_York, America/Los_Angeles, America/Chicago
• Europe/London, Europe/Paris, Asia/Tokyo

[IDEA] SHORTCUTS:
• PT/PST/PDT → US/Pacific
• ET/EST/EDT → US/Eastern
• MT/MST/MDT → US/Mountain
• CT/CST/CDT → US/Central

[PROCESSING] RETRY WITH:
convert_timezone('{datetime_str}', '{from_tz}', 'UTC')
convert_timezone('{datetime_str}', '{from_tz}', 'US/Pacific')"""

            if TIMEZONE_LIB == "pytz":
                # Localize to source timezone, then convert to target
                try:
                    if dt.tzinfo is None:
                        dt = from_timezone.localize(dt)
                    else:
                        dt = dt.replace(tzinfo=from_timezone)
                    converted_dt = dt.astimezone(to_timezone)
                except Exception as pytz_error:
                    return f"""[FAILED] PYTZ CONVERSION ERROR

Source timezone: {from_tz} → {from_tz_norm}
Target timezone: {to_tz} → {to_tz_norm}
Datetime: {datetime_str}
Error: {str(pytz_error)}

[IDEA] TROUBLESHOOTING:
1. Verify timezone names are correct
2. Check if datetime string includes timezone info
3. Try with UTC as intermediate step

[PROCESSING] RETRY WITH:
convert_timezone('{datetime_str}', 'UTC', '{to_tz}')"""

            elif TIMEZONE_LIB == "zoneinfo":
                try:
                    dt = dt.replace(tzinfo=from_timezone)
                    converted_dt = dt.astimezone(to_timezone)
                except Exception as zoneinfo_error:
                    return f"""[FAILED] ZONEINFO CONVERSION ERROR

Source timezone: {from_tz} → {from_tz_norm}
Target timezone: {to_tz} → {to_tz_norm}
Datetime: {datetime_str}
Error: {str(zoneinfo_error)}

[IDEA] TROUBLESHOOTING:
1. Verify timezone names are correct
2. Check if datetime string is valid
3. Try with UTC as intermediate step

[PROCESSING] RETRY WITH:
convert_timezone('{datetime_str}', 'UTC', '{to_tz}')"""
            else:
                return f"""[WARNING] TIMEZONE LIBRARY NOT AVAILABLE

Requested conversion: {from_tz} → {to_tz}
Original time: {dt.isoformat()}
Available library: {TIMEZONE_LIB or "None"}

[IDEA] TO ENABLE TIMEZONE CONVERSION:
Install a timezone library:
• pip install pytz
• Or use Python 3.9+ with zoneinfo

[PROCESSING] CURRENT RESULT:
{dt.isoformat()} (timezone conversion skipped)"""

        except Exception as tz_error:
            return f"""[FAILED] TIMEZONE CONVERSION FAILED

Source: {from_tz} → normalized: {from_tz_norm}
Target: {to_tz} → normalized: {to_tz_norm}
Library: {TIMEZONE_LIB}
Error: {str(tz_error)}

[IDEA] TROUBLESHOOTING:
1. Check timezone name spelling
2. Use standard timezone identifiers
3. Try simpler timezone names

[PROCESSING] RETRY WITH:
convert_timezone('{datetime_str}', 'UTC', 'US/Pacific')
convert_timezone('{datetime_str}', 'US/Eastern', 'UTC')"""

        # Apply format
        try:
            if format:
                return converted_dt.strftime(format)
            else:
                return converted_dt.isoformat()
        except Exception as fmt_error:
            return f"""[FAILED] FORMAT ERROR: Invalid output format

Format string: '{format}'
Converted datetime: {converted_dt}
Error: {str(fmt_error)}

[IDEA] COMMON FORMAT EXAMPLES:
• '%Y-%m-%d %H:%M:%S' → 2023-12-25 14:30:45
• '%Y-%m-%dT%H:%M:%SZ' → 2023-12-25T14:30:45Z
• '%B %d, %Y at %I:%M %p' → December 25, 2023 at 02:30 PM
• '%Y/%m/%d %H:%M' → 2023/12/25 14:30

[PROCESSING] RETRY WITH:
convert_timezone('{datetime_str}', '{from_tz}', '{to_tz}', '%Y-%m-%d %H:%M:%S')
convert_timezone('{datetime_str}', '{from_tz}', '{to_tz}')  # Uses ISO format"""

    except Exception as e:
        # Comprehensive error handling with full context
        error_report = []
        error_report.append("[FAILED] UNEXPECTED ERROR in timezone conversion")
        error_report.append(f"Error: {str(e)}")
        error_report.append("")
        error_report.append("[CLIPBOARD] PARAMETERS PROVIDED:")
        error_report.append(f"• Datetime: {repr(datetime_str)}")
        error_report.append(f"• From timezone: {repr(from_tz)}")
        error_report.append(f"• To timezone: {repr(to_tz)}")
        if format:
            error_report.append(f"• Format: {repr(format)}")
        error_report.append(f"• System library: {TIMEZONE_LIB or 'None available'}")
        error_report.append("")
        error_report.append("[IDEA] RECOVERY SUGGESTIONS:")
        error_report.append("1. Verify all parameters are valid strings")
        error_report.append("2. Use simpler datetime format: '2023-12-25 14:30:00'")
        error_report.append(
            "3. Use common timezones: 'UTC', 'US/Pacific', 'US/Eastern'"
        )
        error_report.append("4. Try without custom format first")
        error_report.append("")
        error_report.append("[PROCESSING] EXAMPLE WORKING CALLS:")
        error_report.append(
            "convert_timezone('2023-12-25 14:30:00', 'UTC', 'US/Pacific')"
        )
        error_report.append(
            "convert_timezone('2023-12-25T14:30:00', 'US/Eastern', 'US/Pacific')"
        )

        return "\n".join(error_report)
        return f"Error converting timezone: {str(e)}"


@mcp.tool()
def format_datetime(datetime_str: str, input_format: str, output_format: str) -> str:
    """
    Format datetime string from one format to another.

    Args:
        datetime_str: Input datetime string
        input_format: Input format pattern (e.g., '%Y-%m-%d %H:%M:%S')
        output_format: Output format pattern (e.g., '%B %d, %Y at %I:%M %p')

    Returns:
        Reformatted datetime string
    """
    try:
        # Input validation with helpful examples
        if not datetime_str or not isinstance(datetime_str, str):
            return """[FAILED] PARAMETER ERROR: Invalid datetime_str parameter

Expected: Non-empty string with date/time
Received: {type(datetime_str).__name__} - {repr(datetime_str)}

[IDEA] EXAMPLES:
• '2023-12-25 14:30:00'
• '12/25/2023 2:30 PM'
• '2023-12-25T14:30:00Z'

[PROCESSING] RETRY WITH:
format_datetime('2023-12-25 14:30:00', '%Y-%m-%d %H:%M:%S', '%B %d, %Y')"""

        if not input_format or not isinstance(input_format, str):
            return """[FAILED] PARAMETER ERROR: Invalid input_format parameter

Expected: Non-empty string with format codes
Received: {type(input_format).__name__} - {repr(input_format)}

[IDEA] COMMON INPUT FORMATS:
• '%Y-%m-%d %H:%M:%S' → for '2023-12-25 14:30:00'
• '%m/%d/%Y %I:%M %p' → for '12/25/2023 2:30 PM'
• '%Y-%m-%dT%H:%M:%SZ' → for '2023-12-25T14:30:00Z'
• '%Y%m%d_%H%M%S' → for '20231225_143000'

[CLIPBOARD] FORMAT CODES:
%Y=year, %m=month, %d=day, %H=hour24, %I=hour12, %M=min, %S=sec, %p=AM/PM

[PROCESSING] RETRY WITH:
format_datetime('{datetime_str}', '%Y-%m-%d %H:%M:%S', '%B %d, %Y')"""

        if not output_format or not isinstance(output_format, str):
            return """[FAILED] PARAMETER ERROR: Invalid output_format parameter

Expected: Non-empty string with format codes
Received: {type(output_format).__name__} - {repr(output_format)}

[IDEA] COMMON OUTPUT FORMATS:
• '%Y-%m-%d %H:%M:%S' → '2023-12-25 14:30:00'
• '%B %d, %Y at %I:%M %p' → 'December 25, 2023 at 02:30 PM'
• '%Y-%m-%dT%H:%M:%SZ' → '2023-12-25T14:30:00Z'
• '%A, %B %d, %Y' → 'Monday, December 25, 2023'
• '%m/%d/%Y' → '12/25/2023'

[CLIPBOARD] FORMAT CODES:
%Y=year, %m=month, %d=day, %H=hour24, %I=hour12, %M=min, %S=sec, %p=AM/PM
%A=weekday, %B=month name, %b=short month

[PROCESSING] RETRY WITH:
format_datetime('{datetime_str}', '{input_format}', '%Y-%m-%d %H:%M:%S')"""

        try:
            dt = datetime.strptime(datetime_str, input_format)
        except ValueError as ve:
            return f"""[FAILED] DATETIME PARSING ERROR: Input doesn't match format

Datetime string: '{datetime_str}'
Input format: '{input_format}'
Parse error: {str(ve)}

[IDEA] TROUBLESHOOTING:
1. Check if datetime string matches the input format exactly
2. Verify format codes are correct
3. Pay attention to separators (-, /, :, spaces)
4. Check AM/PM vs 24-hour format

[IDEA] FORMAT EXAMPLES:
• '2023-12-25 14:30:00' matches '%Y-%m-%d %H:%M:%S'
• '12/25/2023 2:30 PM' matches '%m/%d/%Y %I:%M %p'
• '2023-12-25T14:30:00Z' matches '%Y-%m-%dT%H:%M:%SZ'

[PROCESSING] RETRY WITH:
format_datetime('2023-12-25 14:30:00', '%Y-%m-%d %H:%M:%S', '{output_format}')
format_datetime('12/25/2023 2:30 PM', '%m/%d/%Y %I:%M %p', '{output_format}')"""

        try:
            return dt.strftime(output_format)
        except ValueError as fmt_error:
            return f"""[FAILED] OUTPUT FORMAT ERROR: Invalid output format

Output format: '{output_format}'
Parsed datetime: {dt}
Format error: {str(fmt_error)}

[IDEA] COMMON OUTPUT FORMATS:
• '%Y-%m-%d %H:%M:%S' → '2023-12-25 14:30:00'
• '%B %d, %Y at %I:%M %p' → 'December 25, 2023 at 02:30 PM'
• '%Y-%m-%dT%H:%M:%SZ' → '2023-12-25T14:30:00Z'
• '%A, %B %d, %Y' → 'Monday, December 25, 2023'

[PROCESSING] RETRY WITH:
format_datetime('{datetime_str}', '{input_format}', '%Y-%m-%d %H:%M:%S')"""

    except Exception as e:
        return f"""[FAILED] UNEXPECTED ERROR in datetime formatting

Error: {str(e)}

[CLIPBOARD] PROVIDED PARAMETERS:
• Datetime: {repr(datetime_str)}
• Input format: {repr(input_format)}
• Output format: {repr(output_format)}

[IDEA] RECOVERY SUGGESTIONS:
1. Verify all parameters are valid strings
2. Use simpler format codes
3. Test with known working examples first

[PROCESSING] EXAMPLE WORKING CALLS:
format_datetime('2023-12-25 14:30:00', '%Y-%m-%d %H:%M:%S', '%B %d, %Y')
format_datetime('12/25/2023', '%m/%d/%Y', '%Y-%m-%d')"""


@mcp.tool()
def calculate_time_difference(
    start_datetime: str, end_datetime: str, unit: str | None = "seconds"
) -> str:
    """
    Calculate the difference between two datetimes.

    Args:
        start_datetime: Start datetime string
        end_datetime: End datetime string
        unit: Unit for result ('seconds', 'minutes', 'hours', 'days'). Defaults to 'seconds'.

    Returns:
        Time difference as string with specified unit
    """
    try:
        # Input validation with helpful examples
        if not start_datetime or not isinstance(start_datetime, str):
            return """[FAILED] PARAMETER ERROR: Invalid start_datetime parameter

Expected: Non-empty string with start date/time
Received: {type(start_datetime).__name__} - {repr(start_datetime)}

[IDEA] VALID FORMATS:
• '2023-12-25 10:30:00'
• '2023-12-25T10:30:00'
• '2023-12-25'

[PROCESSING] RETRY WITH:
calculate_time_difference('2023-12-25 10:00:00', '2023-12-25 15:30:00', 'hours')"""

        if not end_datetime or not isinstance(end_datetime, str):
            return """[FAILED] PARAMETER ERROR: Invalid end_datetime parameter

Expected: Non-empty string with end date/time
Received: {type(end_datetime).__name__} - {repr(end_datetime)}

[IDEA] VALID FORMATS:
• '2023-12-25 15:30:00'
• '2023-12-25T15:30:00'
• '2023-12-25'

[PROCESSING] RETRY WITH:
calculate_time_difference('{start_datetime}', '2023-12-25 15:30:00', 'hours')"""

        if unit and not isinstance(unit, str):
            return """[FAILED] PARAMETER ERROR: Invalid unit parameter

Expected: String with time unit
Received: {type(unit).__name__}

[IDEA] VALID UNITS:
• 'seconds' (default)
• 'minutes'
• 'hours'
• 'days'

[PROCESSING] RETRY WITH:
calculate_time_difference('{start_datetime}', '{end_datetime}', 'hours')"""

        # Validate unit value
        valid_units = ["seconds", "minutes", "hours", "days"]
        if unit and unit not in valid_units:
            return f"""[FAILED] INVALID UNIT: Unknown time unit

Provided unit: '{unit}'
Valid units: {", ".join(valid_units)}

[PROCESSING] RETRY WITH:
calculate_time_difference('{start_datetime}', '{end_datetime}', 'hours')
calculate_time_difference('{start_datetime}', '{end_datetime}', 'minutes')"""

        # Try to parse both datetime strings
        formats_to_try = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y",
        ]

        start_dt = None
        end_dt = None
        formats_tried = []

        # Try parsing start datetime
        for fmt in formats_to_try:
            try:
                start_dt = datetime.strptime(start_datetime, fmt)
                break
            except ValueError:
                formats_tried.append(fmt)
                continue

        if start_dt is None:
            return f"""[FAILED] START DATETIME PARSING ERROR

Could not parse: '{start_datetime}'
Tried {len(formats_tried)} different formats

[IDEA] SUPPORTED FORMATS:
• 'YYYY-MM-DD HH:MM:SS' (e.g., '2023-12-25 14:30:00')
• 'YYYY-MM-DDTHH:MM:SS' (e.g., '2023-12-25T14:30:00')
• 'YYYY-MM-DD' (e.g., '2023-12-25')
• 'MM/DD/YYYY HH:MM:SS' (e.g., '12/25/2023 14:30:00')

[PROCESSING] RETRY WITH:
calculate_time_difference('2023-12-25 10:00:00', '{end_datetime}', '{unit or "seconds"}')"""

        # Try parsing end datetime
        formats_tried = []
        for fmt in formats_to_try:
            try:
                end_dt = datetime.strptime(end_datetime, fmt)
                break
            except ValueError:
                formats_tried.append(fmt)
                continue

        if end_dt is None:
            return f"""[FAILED] END DATETIME PARSING ERROR

Could not parse: '{end_datetime}'
Tried {len(formats_tried)} different formats

[IDEA] SUPPORTED FORMATS:
• 'YYYY-MM-DD HH:MM:SS' (e.g., '2023-12-25 14:30:00')
• 'YYYY-MM-DDTHH:MM:SS' (e.g., '2023-12-25T14:30:00')
• 'YYYY-MM-DD' (e.g., '2023-12-25')
• 'MM/DD/YYYY HH:MM:SS' (e.g., '12/25/2023 14:30:00')

[PROCESSING] RETRY WITH:
calculate_time_difference('{start_datetime}', '2023-12-25 15:30:00', '{unit or "seconds"}')"""

        # Calculate difference
        diff = end_dt - start_dt
        total_seconds = diff.total_seconds()

        # Format result based on unit
        if unit == "seconds":
            result = f"{total_seconds:.2f} seconds"
        elif unit == "minutes":
            minutes = total_seconds / 60
            result = f"{minutes:.2f} minutes"
        elif unit == "hours":
            hours = total_seconds / 3600
            result = f"{hours:.2f} hours"
        elif unit == "days":
            days = total_seconds / 86400  # More precise than diff.days
            result = f"{days:.2f} days"
        else:
            # Default to comprehensive format
            result = f"Difference: {diff} ({total_seconds:.2f} seconds)"

        # Add helpful context for negative differences
        if total_seconds < 0:
            result += (
                "\n[WARNING]  Note: End time is before start time (negative difference)"
            )

        return result

    except Exception as e:
        return f"""[FAILED] UNEXPECTED ERROR calculating time difference

Error: {str(e)}

[CLIPBOARD] PROVIDED PARAMETERS:
• Start datetime: {repr(start_datetime)}
• End datetime: {repr(end_datetime)}
• Unit: {repr(unit)}

[IDEA] RECOVERY SUGGESTIONS:
1. Verify both datetimes are valid strings
2. Use simple format: 'YYYY-MM-DD HH:MM:SS'
3. Ensure end time is after start time for positive difference
4. Use valid units: seconds, minutes, hours, days

[PROCESSING] EXAMPLE WORKING CALLS:
calculate_time_difference('2023-12-25 10:00:00', '2023-12-25 15:30:00', 'hours')
calculate_time_difference('2023-12-25', '2023-12-26', 'days')"""
        return f"Error calculating time difference: {str(e)}"


@mcp.tool()
def add_time_to_datetime(
    datetime_str: str,
    days: int | None = 0,
    hours: int | None = 0,
    minutes: int | None = 0,
    seconds: int | None = 0,
) -> str:
    """
    Add time to a datetime.

    Args:
        datetime_str: Input datetime string
        days: Days to add
        hours: Hours to add
        minutes: Minutes to add
        seconds: Seconds to add

    Returns:
        Modified datetime as string
    """
    try:
        # Input validation
        if not datetime_str or not isinstance(datetime_str, str):
            return "Error: datetime_str must be a non-empty string"

        # Parse datetime
        formats_to_try = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]

        dt = None
        for fmt in formats_to_try:
            try:
                dt = datetime.strptime(datetime_str, fmt)
                break
            except ValueError:
                continue

        if dt is None:
            return "Error: Could not parse datetime string. Try formats like: YYYY-MM-DD HH:MM:SS"

        # Add time
        delta = timedelta(
            days=days or 0, hours=hours or 0, minutes=minutes or 0, seconds=seconds or 0
        )
        result_dt = dt + delta

        return result_dt.isoformat()

    except Exception as e:
        return f"Error adding time to datetime: {str(e)}"


@mcp.tool()
def subtract_time_from_datetime(
    datetime_str: str,
    days: int | None = 0,
    hours: int | None = 0,
    minutes: int | None = 0,
    seconds: int | None = 0,
) -> str:
    """
    Subtract time from a datetime.

    Args:
        datetime_str: Input datetime string
        days: Days to subtract
        hours: Hours to subtract
        minutes: Minutes to subtract
        seconds: Seconds to subtract

    Returns:
        Modified datetime as string
    """
    try:
        # Input validation
        if not datetime_str or not isinstance(datetime_str, str):
            return "Error: datetime_str must be a non-empty string"

        # Parse datetime
        formats_to_try = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]

        dt = None
        for fmt in formats_to_try:
            try:
                dt = datetime.strptime(datetime_str, fmt)
                break
            except ValueError:
                continue

        if dt is None:
            return "Error: Could not parse datetime string. Try formats like: YYYY-MM-DD HH:MM:SS"

        # Subtract time
        delta = timedelta(
            days=days or 0, hours=hours or 0, minutes=minutes or 0, seconds=seconds or 0
        )
        result_dt = dt - delta

        return result_dt.isoformat()

    except Exception as e:
        return f"Error subtracting time from datetime: {str(e)}"


@mcp.tool()
def get_timestamp(datetime_str: str | None = None, format: str | None = None) -> str:
    """
    Get Unix timestamp from datetime string or current time.

    Args:
        datetime_str: Input datetime string (if None, uses current time)
        format: Input format if datetime_str is provided

    Returns:
        Unix timestamp as string
    """
    try:
        if datetime_str is None:
            # Use current time
            return str(int(datetime.now(UTC).timestamp()))

        # Input validation
        if not isinstance(datetime_str, str):
            return "Error: datetime_str must be a string"

        # Parse datetime
        if format:
            try:
                dt = datetime.strptime(datetime_str, format)
            except ValueError as ve:
                return f"Error parsing datetime with format '{format}': {str(ve)}"
        else:
            formats_to_try = [
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ]

            dt = None
            for fmt in formats_to_try:
                try:
                    dt = datetime.strptime(datetime_str, fmt)
                    break
                except ValueError:
                    continue

            if dt is None:
                return "Error: Could not parse datetime string. Try formats like: YYYY-MM-DD HH:MM:SS"

        return str(int(dt.timestamp()))

    except Exception as e:
        return f"Error getting timestamp: {str(e)}"


@mcp.tool()
def from_timestamp(
    timestamp: str, tz: str | None = None, format: str | None = None
) -> str:
    """
    Convert Unix timestamp to formatted datetime.

    Args:
        timestamp: Unix timestamp as string
        tz: Target timezone (e.g., 'UTC', 'US/Pacific')
        format: Output format string

    Returns:
        Formatted datetime string
    """
    try:
        # Input validation
        if not timestamp or not isinstance(timestamp, str):
            return "Error: timestamp must be a non-empty string"

        try:
            ts = float(timestamp)
        except ValueError:
            return f"Error: Invalid timestamp '{timestamp}'. Must be a number."

        # Convert timestamp to datetime
        dt = datetime.fromtimestamp(ts, tz=UTC)

        # Apply timezone if specified
        if tz:
            try:
                tz_obj = get_timezone_object(tz)
                if tz_obj:
                    dt = dt.astimezone(tz_obj)
                else:
                    normalized_tz = normalize_timezone(tz)
                    return f"Error: Unknown timezone '{tz}' (normalized: '{normalized_tz}'). Try: UTC, US/Pacific, US/Eastern, etc."
            except Exception as tz_error:
                return f"Error processing timezone '{tz}': {str(tz_error)}"

        # Apply format if specified
        try:
            if format:
                return dt.strftime(format)
            else:
                return dt.isoformat()
        except Exception as fmt_error:
            return f"Error applying format '{format}': {str(fmt_error)}"

    except Exception as e:
        return f"Error converting timestamp: {str(e)}"


@mcp.tool()
def get_datetime_help(topic: str | None = None) -> str:
    """
    Get comprehensive help for datetime operations and troubleshooting.

    Args:
        topic: Specific help topic ('formats', 'timezones', 'examples', 'errors')

    Returns:
        Detailed help information
    """
    if topic == "formats":
        return """[CLIPBOARD] DATETIME FORMAT CODES REFERENCE

[ABC] DATE FORMATS:
%Y = 4-digit year (2023)
%y = 2-digit year (23)
%m = Month as number (01-12)
%B = Full month name (December)
%b = Short month name (Dec)
%d = Day of month (01-31)
%A = Full weekday name (Monday)
%a = Short weekday name (Mon)
%j = Day of year (001-366)
%U = Week number (00-53, Sunday first)
%W = Week number (00-53, Monday first)

[CLOCK_ONE] TIME FORMATS:
%H = Hour 24-hour format (00-23)
%I = Hour 12-hour format (01-12)
%M = Minute (00-59)
%S = Second (00-59)
%f = Microsecond (000000-999999)
%p = AM/PM
%z = UTC offset (+HHMM or -HHMM)
%Z = Timezone name

[IDEA] COMMON COMBINATIONS:
'%Y-%m-%d %H:%M:%S' → '2023-12-25 14:30:00'
'%Y-%m-%dT%H:%M:%SZ' → '2023-12-25T14:30:00Z'
'%B %d, %Y at %I:%M %p' → 'December 25, 2023 at 02:30 PM'
'%A, %B %d, %Y' → 'Monday, December 25, 2023'
'%m/%d/%Y' → '12/25/2023'
'%d/%m/%Y' → '25/12/2023' (European format)"""

    elif topic == "timezones":
        return """[EARTH_EUROPE] TIMEZONE REFERENCE GUIDE

[SUCCESS] MAJOR TIMEZONES:
• UTC, GMT - Coordinated Universal Time
• US/Pacific - Pacific Time (US West Coast)
• US/Eastern - Eastern Time (US East Coast)
• US/Mountain - Mountain Time (US Mountain Region)
• US/Central - Central Time (US Central Region)

[EARTH_AMERICAS] AMERICAS:
• America/New_York - Eastern Time
• America/Chicago - Central Time
• America/Denver - Mountain Time
• America/Los_Angeles - Pacific Time
• America/Toronto - Eastern Time (Canada)
• America/Sao_Paulo - Brazil Time

[EARTH_EUROPE] EUROPE & AFRICA:
• Europe/London - Greenwich Mean Time
• Europe/Paris - Central European Time
• Europe/Berlin - Central European Time
• Europe/Moscow - Moscow Standard Time
• Africa/Cairo - Eastern European Time

[EARTH_ASIA] ASIA & OCEANIA:
• Asia/Tokyo - Japan Standard Time
• Asia/Shanghai - China Standard Time
• Asia/Kolkata - India Standard Time
• Asia/Dubai - Gulf Standard Time
• Australia/Sydney - Australian Eastern Time

[LIGHTNING] SHORTCUTS (automatically converted):
• PT/PST/PDT → US/Pacific
• ET/EST/EDT → US/Eastern
• MT/MST/MDT → US/Mountain
• CT/CST/CDT → US/Central
• GMT → UTC"""

    elif topic == "examples":
        return """[TOOLS] PRACTICAL EXAMPLES

[CALENDAR] GET CURRENT TIME:
get_current_datetime() → Current UTC time in ISO format
get_current_datetime(tz='US/Pacific') → Current Pacific time
get_current_datetime(format='%Y-%m-%d %H:%M:%S') → '2023-12-25 14:30:00'

[PROCESSING] CONVERT TIMEZONES:
convert_timezone('2023-12-25 14:30:00', 'UTC', 'US/Pacific')
convert_timezone('2023-12-25T14:30:00Z', 'UTC', 'US/Eastern')
convert_timezone('12/25/2023 2:30 PM', 'US/Eastern', 'UTC', '%Y-%m-%d %H:%M:%S')

[SPARKLES] FORMAT CONVERSION:
format_datetime('2023-12-25 14:30:00', '%Y-%m-%d %H:%M:%S', '%B %d, %Y')
format_datetime('12/25/2023', '%m/%d/%Y', '%Y-%m-%d')
format_datetime('2023-12-25T14:30:00Z', '%Y-%m-%dT%H:%M:%SZ', '%A, %B %d, %Y at %I:%M %p')

[TIMER] TIME CALCULATIONS:
calculate_time_difference('2023-12-25 10:00:00', '2023-12-25 15:30:00', 'hours')
add_time_to_datetime('2023-12-25 10:00:00', days=7, hours=2)
subtract_time_from_datetime('2023-12-25 10:00:00', days=1, minutes=30)

[CLOCK_ONE] TIMESTAMPS:
get_timestamp('2023-12-25 14:30:00') → Unix timestamp
from_timestamp('1703520600', 'US/Pacific') → Pacific time from timestamp"""

    elif topic == "errors":
        return """[ALERT] COMMON ERRORS & SOLUTIONS

[FAILED] TIMEZONE ERRORS:
Problem: "Unknown timezone 'EST'"
Solution: Use 'US/Eastern' or 'America/New_York' instead
Fix: convert_timezone(datetime_str, 'US/Eastern', 'US/Pacific')

[FAILED] FORMAT ERRORS:
Problem: "time data '2023-12-25' does not match format '%Y-%m-%d %H:%M:%S'"
Solution: Adjust format to match your data exactly
Fix: Use '%Y-%m-%d' for date-only strings

[FAILED] PARAMETER ERRORS:
Problem: "datetime_str must be a non-empty string"
Solution: Ensure you're passing valid string parameters
Fix: get_current_datetime(tz='UTC') not get_current_datetime(tz=None)

[FAILED] PARSING ERRORS:
Problem: Cannot parse datetime string
Solution: Check format codes match your data exactly
Common fixes:
• '2023-12-25 14:30:00' → '%Y-%m-%d %H:%M:%S'
• '12/25/2023 2:30 PM' → '%m/%d/%Y %I:%M %p'
• '2023-12-25T14:30:00Z' → '%Y-%m-%dT%H:%M:%SZ'

[IDEA] DEBUGGING TIPS:
1. Start with get_current_datetime() to test basic functionality
2. Use simple formats first, then add complexity
3. Verify timezone names with supported list
4. Check parameter types (all should be strings)
5. Use the help function: get_datetime_help('topic')"""

    else:
        return """[CLOCK_ONE] DATETIME SERVICE COMPREHENSIVE HELP

Available help topics:
• get_datetime_help('formats') - Format codes reference
• get_datetime_help('timezones') - Timezone reference
• get_datetime_help('examples') - Practical examples
• get_datetime_help('errors') - Error troubleshooting

[TOOLS] AVAILABLE FUNCTIONS:

[CALENDAR] CURRENT TIME:
• get_current_datetime(tz?, format?) → Get current date/time

[PROCESSING] TIMEZONE OPERATIONS:
• convert_timezone(datetime_str, from_tz, to_tz, format?) → Convert between timezones

[SPARKLES] FORMATTING:
• format_datetime(datetime_str, input_format, output_format) → Reformat datetime

[TIMER] TIME CALCULATIONS:
• calculate_time_difference(start, end, unit?) → Time between dates
• add_time_to_datetime(datetime_str, days?, hours?, minutes?, seconds?) → Add time
• subtract_time_from_datetime(datetime_str, days?, hours?, minutes?, seconds?) → Subtract time

[CLOCK_ONE] TIMESTAMPS:
• get_timestamp(datetime_str?, format?) → Convert to Unix timestamp
• from_timestamp(timestamp, timezone?, format?) → Convert from Unix timestamp

[SOS] ERROR HELP:
• get_datetime_help('errors') → Common problems and solutions

[IDEA] QUICK START:
1. Test basic function: get_current_datetime()
2. Try timezone conversion: convert_timezone('2023-12-25 14:30:00', 'UTC', 'US/Pacific')
3. Format conversion: format_datetime('2023-12-25', '%Y-%m-%d', '%B %d, %Y')

All functions provide detailed error messages with suggestions for fixing issues!"""


if __name__ == "__main__":
    mcp.run()
