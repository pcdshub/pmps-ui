# List of valid rate selections from high to low in Hz
VALID_RATES = (120, 10, 1, 0)

def get_valid_rate(rate):
    """
    Return the real rate that we'll request from ACR.

    Not all rate requests are valid, there is a strict
    set that we are allowed to request. Requesting an
    inbetween value is the same as requesting the next
    lowest available value.

    Parameters
    ----------
    rate : int
        The rate in Hz that we want to request.

    Returns
    -------
    valid_rate : int
        The rate in Hz that is actually requested.
    """
    for valid_rate in VALID_RATES:
        if rate >= valid_rate:
            return valid_rate
    return 0
