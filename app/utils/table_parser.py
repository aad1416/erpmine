import re
import uuid
from typing import List, Optional
from bs4 import BeautifulSoup, Tag


class TableParser:
    @staticmethod
    def html_to_markdown(html: str) -> Optional[str]:
        """
        Converts an HTML table to a Markdown pipe table.
        Returns None if parsing fails or no table is found.
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table")
            if not table:
                return None

            lines = []
            header_col_count = 0
            thead = table.find("thead")
            tbody = table.find("tbody") or table

            def append_body_row(cells: List[str]) -> None:
                nonlocal header_col_count, lines
                if not cells:
                    return
                # Filter out newlines in cells to preserve table structure
                clean_cells = [c.replace("\n", " ").replace("\r", "") for c in cells]
                row_line = "| " + " | ".join(clean_cells) + " |"
                
                if header_col_count == 0:
                    header_col_count = len(clean_cells)
                    lines.append(row_line)
                    lines.append(
                        "| " + " | ".join(["---"] * header_col_count) + " |"
                    )
                else:
                    lines.append(row_line)

            if thead:
                thead_rows = thead.find_all("tr")
                if thead_rows:
                    header_cells = [
                        TableParser._cell_text(td)
                        for td in thead_rows[0].find_all(["th", "td"])
                    ]
                    if header_cells:
                        # Clean newlines for header
                        header_cells = [h.replace("\n", " ").replace("\r", "") for h in header_cells]
                        header_col_count = len(header_cells)
                        lines.append("| " + " | ".join(header_cells) + " |")
                        lines.append(
                            "| " + " | ".join(["---"] * header_col_count) + " |"
                        )
                        for tr in thead_rows[1:]:
                            cells = [
                                TableParser._cell_text(td)
                                for td in tr.find_all(["th", "td"])
                            ]
                            append_body_row(cells)
                    else:
                        for tr in thead_rows:
                            cells = [
                                TableParser._cell_text(td)
                                for td in tr.find_all(["th", "td"])
                            ]
                            append_body_row(cells)

            for tr in tbody.find_all("tr"):
                if thead and tr.find_parent("thead"):
                    continue
                cells = [TableParser._cell_text(td) for td in tr.find_all(["th", "td"])]
                append_body_row(cells)

            return "\n".join(lines) if lines else None
        except Exception:
            return None

    @staticmethod
    def _cell_text(cell: Tag) -> str:
        # Get text with <br> separator, strip whitespace
        # Note: We handle newline replacement in the caller to allow for potential future options,
        # but for now we also do it here for safety on individual return values if used elsewhere.
        text = cell.get_text(separator="<br>", strip=True)
        return text.replace("|", "\\|")

    @staticmethod
    def convert_html_tables_in_text(text: str) -> str:
        """
        Scans text for HTML tables and converts them to Markdown keys, 
        then restores them as Markdown tables.
        """
        blocks: dict[str, str] = {}

        def save(match: re.Match[str]) -> str:
            key = f"__CB_{uuid.uuid4().hex}__"
            blocks[key] = match.group(0)
            return key

        text = re.sub(
            r"```.*?```|~~~.*?~~~|<pre[^>]*>.*?</pre>",
            save,
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        text = re.sub(r"(`+)([^`\n]*?)\1", save, text)
        
        def replace_table(match):
            html = match.group(0)
            markdown = TableParser.html_to_markdown(html)
            return markdown if markdown is not None else html

        text = re.sub(
            r"<table[^>]*>.*?</table>",
            replace_table,
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        
        for key, block in blocks.items():
            text = text.replace(key, block)
        return text
