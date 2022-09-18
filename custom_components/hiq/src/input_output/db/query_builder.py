class QueryBuilder:
    def __init__(self, max_query_size=1000000):
        self._max_query_size = max_query_size

    def create_insert_queries(self, table, columns, rows, value_max_sizes):
        available_chars = self._max_query_size
        result = []

        query_prefix = self._create_insert_prefix(table, columns)
        available_chars = available_chars - len(query_prefix)

        # 4 - two parentheses, comma and space, 4 - two quote-marks, comma and space
        query_suffix_row_len = 4 + sum(value_max_sizes) + len(value_max_sizes) * 4

        max_rows = available_chars // query_suffix_row_len

        while len(rows) > 0:
            rows_ = rows[:max_rows]
            rows_joined = ",".join(str(row) for row in rows_)
            query = f"{query_prefix} {rows_joined}"
            result.append(query)
            rows = rows[max_rows:]
        return result

    def _create_insert_prefix(self, table, columns):
        columns_str = self._create_columns_string(columns)
        return f"INSERT INTO {table} {columns_str} VALUES "

    @classmethod
    def _create_columns_string(cls, columns):
        return "(" + ", ".join(columns) + ")"
