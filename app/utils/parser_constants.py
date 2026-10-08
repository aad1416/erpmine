from typing import Final

class LlamaParseConstants:
    """Stable configuration constants for LlamaParse."""
    
    # Output Format
    RESULT_TYPE: Final[str] = "markdown"
    OUTPUT_TABLES_AS_HTML: Final[bool] = True
    COMPACT_MARKDOWN_TABLE: Final[bool] = False
    EXPAND: Final[str] = "markdown,items,text"
    
    # Page Logic
    SPLIT_BY_PAGE: Final[bool] = True
    CONTINUOUS_MODE: Final[bool] = False
    PAGE_SEPARATOR: Final[str] = "\n\n<!-- PAGE:{pageNumber} -->\n\n"
    PARSING_INSTRUCTION: Final[str] = (
        "At the beginning of content from each new page in the source document, "
        "insert a marker line: <!-- PAGE:X --> where X is the page number "
        "(starting from 1). This is critical for tracking page boundaries."
    )
    
    # Table Extraction
    AGGRESSIVE_TABLE_EXTRACTION: Final[bool] = False
    OUTLINED_TABLE_EXTRACTION: Final[bool] = True
    ADAPTIVE_LONG_TABLE: Final[bool] = True
    MERGE_TABLES_ACROSS_PAGES: Final[bool] = True
    KEEP_PAGE_SEPARATOR_WHEN_MERGING_TABLES: Final[bool] = False
    MARKDOWN_TABLE_MULTILINE_HEADER_SEPARATOR: Final[str | None] = None
    
    # Spreadsheet Logic
    SPREADSHEET_EXTRACT_SUB_TABLES: Final[bool] = True
    SPREADSHEET_FORCE_FORMULA_COMPUTATION: Final[bool] = True
    GUESS_XLSX_SHEET_NAME: Final[bool] = True
    PRESERVE_LAYOUT_ALIGNMENT_ACROSS_PAGES: Final[bool] = True
    PRESERVE_VERY_SMALL_TEXT: Final[bool] = True
    DO_NOT_UNROLL_COLUMNS: Final[bool] = True
    
    # Visuals
    HIGH_RES_OCR: Final[bool] = True
    HIDE_HEADERS: Final[bool] = True
    HIDE_FOOTERS: Final[bool] = True
    
    # Triggers
    AUTO_MODE: Final[bool] = True
    AUTO_MODE_TRIGGER_ON_TABLE_IN_PAGE: Final[bool] = True
    AUTO_MODE_TRIGGER_ON_IMAGE_IN_PAGE: Final[bool] = True
    
    @classmethod
    def get_parse_output_options(cls) -> dict:
        """Return v2 output options used by the production LlamaParse profiles."""
        return {
            "markdown": {
                "annotate_links": True,
                "inline_images": True,
                "tables": {
                    "merge_continued_tables": cls.MERGE_TABLES_ACROSS_PAGES,
                    "output_tables_as_markdown": not cls.OUTPUT_TABLES_AS_HTML,
                },
            },
            "spatial_text": {
                "preserve_layout_alignment_across_pages": (
                    cls.PRESERVE_LAYOUT_ALIGNMENT_ACROSS_PAGES
                ),
                "preserve_very_small_text": cls.PRESERVE_VERY_SMALL_TEXT,
                "do_not_unroll_columns": cls.DO_NOT_UNROLL_COLUMNS,
            },
        }

    @classmethod
    def get_parse_processing_options(cls, language: str, *, cost_optimizer: bool) -> dict:
        """Return v2 processing options for OCR and structure preservation."""
        options: dict = {
            "ocr_parameters": {"languages": [lang.strip() for lang in (language or "en").split(",") if lang.strip()]},
            "ignore": {"ignore_diagonal_text": True},
        }
        if cost_optimizer:
            options["cost_optimizer"] = {"enable": True}
        return options

class ChunkerConstants:
    """Stable configuration constants for Chunking."""
    
    # Stable heuristics (less frequently tuned)
    TABLE_MAX_TOKENS: Final[int] = 1000
    TABLE_TOKEN_OVERLAP: Final[int] = 0
