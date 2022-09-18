def tabulate(column_widths, headers_list, tabular_data):
    rows_list = []
    header = centered_header_str(headers_list, column_widths)
    rows_list.append(header)
    row_len = 0

    for width in column_widths:
        row_len += width

    rows_list.append("_" * row_len)
    for row in tabular_data:
        row_str = rows_left_justified_str(row, column_widths)
        rows_list.append(row_str)

    return "\n" + "\n".join(rows_list) + "\n"


def centered_header_str(headers, column_widths):
    titles_centered = []
    for i, value in enumerate(headers):
        column_width = column_widths[i]
        title_centered = value.center(column_width)
        titles_centered.append(title_centered)

    return "|".join(titles_centered)


def rows_left_justified_str(row_data, column_widths):
    row_data_left_justified = []
    for i, value in enumerate(row_data):
        column_width = column_widths[i]
        value_left_justified = value.ljust(column_width)
        row_data_left_justified.append(value_left_justified)
    return "|".join(row_data_left_justified)


def humanize_timedelta(td_object):

    # periods = [
    #     ('year', 60 * 60 * 24 * 365),
    #     ('month', 60 * 60 * 24 * 30),
    #     ('day', 60 * 60 * 24),
    #     ('hour', 60 * 60),
    #     ('minute', 60),
    #     ('second', 1)
    # ]
    #
    # strings = []
    # for period_name, period_seconds in periods:
    #     if seconds > period_seconds:
    #         period_value, seconds = divmod(seconds, period_seconds)
    #         has_s = 's' if period_value > 1 else ''
    #         strings.append(f'{period_value} {period_name} {has_s}')
    #
    # return ", ".join(strings)
    seconds = int(td_object)
    sec = seconds % 60
    days = int(seconds / 60 / 60 / 24)
    hours = int(seconds / 60 / 60 % 24)
    minutes = int(seconds / 60 % 60)

    return "{} days, {:02}:{:02}:{:02}".format(days, hours, minutes, sec)
