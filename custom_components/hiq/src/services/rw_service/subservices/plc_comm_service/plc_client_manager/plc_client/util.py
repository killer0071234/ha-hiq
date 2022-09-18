from datetime import datetime


def cybro_timestamp_to_datetime(timestamp: int):
    seconds = (timestamp & 0x0000001F) * 2
    minutes = (timestamp & 0x000007E0) >> 5
    hours = (timestamp & 0x0000F800) >> 11
    days = (timestamp & 0x001F0000) >> 16
    months = (timestamp & 0x01E00000) >> 21
    years = ((timestamp & 0xFE000000) >> 25) + 1980

    try:
        return datetime(years, months, days, hours, minutes, seconds)
    except:  # noqa: E722
        return datetime(1980, 1, 1, 0, 0, 0)
