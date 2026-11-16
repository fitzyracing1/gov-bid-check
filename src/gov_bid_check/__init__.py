"""gov-bid-check: format pre-check for a draft bid or registration file."""

from gov_bid_check.check import CheckResult, check_record, check_text

__version__ = "0.1.0"
__all__ = ["CheckResult", "check_record", "check_text", "__version__"]
