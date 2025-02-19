import typing_extensions as typing

from bs4 import BeautifulSoup


__all__ = ["HTMLTable"]


class HTMLTable:
    """
    Helper utility to create HTML (and plain text) tables.

    !!! note "This class is iterable"
        Iterating over this class will return an iterable, where the first element is the list of headers, and then
        the rest are the individual rows.
        Changing values in this iteration will NOT update the original entries.

    Example:

    ```python
    table = HTMLTable(caption="My Table")
    table.add_columns("number", "value")
    table.add_rows("0", "hello world")
    table.add_rows("1", "foo bar")

    await bot.room_send(
        "!example:example.example",
        {
            "msgtype": "m.notice",
            "body": table.render("text"),
            "format": "org.matrix.custom.html",
            "formatted_body": table.render("html"),
        }
    )
    ```
    """

    def __init__(self, caption: str = None):
        self.caption = caption
        self.columns: typing.List[str] = []
        self.rows: typing.List[typing.List[str]] = []

    def add_column(self, column_name: str) -> typing.Self:
        """
        Add a column (header name) to the table.
        """
        self.columns.append(column_name)
        return self

    def add_columns(self, *column_names: str) -> typing.Self:
        """
        Add multiple columns (header names) to the table.
        """
        self.columns += column_names
        return self

    def add_row(self, *values: str) -> typing.Self:
        """
        Add a row to the table.

        If the number of values is not equal to the number of columns, blank values will be added to pad the row.
        """
        values = list(values)
        if len(values) < len(self.columns):
            values += [""] * (len(self.columns) - len(values))
        elif len(values) > len(self.columns):
            raise ValueError("Number of values (%d) exceeds number of columns (%d)")
        self.rows.append(values)
        return self

    def add_rows(self, *rows: typing.List[str]) -> typing.Self:
        """
        Add multiple rows to the table.
        """
        for row in rows:
            self.add_row(*row)
        return self

    def render_html(self) -> str:
        """
        Render the table as an HTML string.
        """
        soup = BeautifulSoup("<table></table>", "html.parser")
        table = soup.table

        # Create the caption
        if self.caption is not None:
            caption = soup.new_tag("caption")
            caption.string = self.caption
            table.append(caption)

        # Create the headers
        thead = soup.new_tag("thead")
        table.append(thead)
        tr = soup.new_tag("tr")
        thead.append(tr)
        for header in self.columns:
            th = soup.new_tag("th")
            th.string = header
            tr.append(th)

        # Create the rows
        tbody = soup.new_tag("tbody")
        table.append(tbody)
        for row in self.rows:
            tr = soup.new_tag("tr")
            tbody.append(tr)
            for value in row:
                td = soup.new_tag("td")
                td.string = value
                tr.append(td)

        return str(soup)  # this is "minified" HTML

    def render_text(self) -> str:
        """
        Render the table as a simple textual table

        Example:

            number | value
            -------+------
            0      | a
            1      | b
            2      | c
            3      | d
            4      | e
        """
        # Calculate the width of each column
        column_widths = [len(column) for column in self.columns]
        for row in self.rows:
            for i, value in enumerate(row):
                column_widths[i] = max(column_widths[i], len(value))

        # Create the column
        text_table = " | ".join([column.ljust(width) for column, width in zip(self.columns, column_widths)]) + "\n"

        # Create the separator
        text_table += "-+-".join(["-" * width for width in column_widths]) + "\n"

        # Create the rows
        for row in self.rows:
            text_table += (" | ".join([value.ljust(width) for value, width in zip(row, column_widths)])).strip() + "\n"
            # The strip() call removes any sort of unnecessary whitespace at the end of the line to save space.

        return text_table

    def render(self, output_format: typing.Literal["html", "text"] = "html") -> str:
        """
        Render the table in the specified format.

        :param output_format: The output format. Either "html" or "text".
        """
        if output_format == "html":
            return self.render_html()
        elif output_format == "text":
            return self.render_text()
        else:
            raise ValueError(f"Invalid output format: {output_format}")

    def remove_row(self, index: int) -> typing.Self:
        """
        Remove a row from the table.
        """
        del self.rows[index]
        return self

    def insert_row(self, index: int, *values: str) -> typing.Self:
        """
        Insert a row at a specific index.

        Note that the index will become the values. For example, inserting at index 0 will insert the row at the top,
        and inserting at index 2 will make this row 3.
        """
        values = list(values)
        if len(values) < len(self.columns):
            values += [""] * (len(self.columns) - len(values))
        elif len(values) > len(self.columns):
            raise ValueError("Number of values (%d) exceeds number of columns (%d)")
        self.rows.insert(index, values)
        return self

    def __getitem__(self, index: int) -> typing.List[str]:
        return self.rows[index]

    def __iter__(self):
        return iter([self.columns, *self.rows])
