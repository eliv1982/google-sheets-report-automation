from __future__ import annotations

TITLE_CELL_FORMAT = {
    "background_color": {"red": 0.86, "green": 0.9, "blue": 0.95},
    "bold": True,
    "font_size": 16,
    "horizontal_alignment": "CENTER",
    "vertical_alignment": "MIDDLE",
    "wrap_strategy": "WRAP",
}

SECTION_TITLE_FORMAT = {
    "background_color": {"red": 0.9, "green": 0.93, "blue": 0.97},
    "bold": True,
    "font_size": 12,
    "horizontal_alignment": "CENTER",
    "vertical_alignment": "MIDDLE",
    "wrap_strategy": "WRAP",
}

TABLE_HEADER_FORMAT = {
    "background_color": {"red": 0.82, "green": 0.87, "blue": 0.92},
    "bold": True,
    "font_size": 11,
    "horizontal_alignment": "CENTER",
    "vertical_alignment": "MIDDLE",
    "wrap_strategy": "WRAP",
}

LABEL_FORMAT = {
    "background_color": {"red": 0.95, "green": 0.96, "blue": 0.98},
    "bold": True,
    "font_size": 10,
    "horizontal_alignment": "LEFT",
    "vertical_alignment": "MIDDLE",
    "wrap_strategy": "WRAP",
}

BODY_FORMAT = {
    "font_size": 10,
    "vertical_alignment": "MIDDLE",
    "wrap_strategy": "WRAP",
}

CENTERED_BODY_FORMAT = {
    "font_size": 10,
    "horizontal_alignment": "CENTER",
    "vertical_alignment": "MIDDLE",
    "wrap_strategy": "WRAP",
}

MONEY_NUMBER_FORMAT = {"type": "NUMBER", "pattern": "#,##0.00"}
PERCENT_NUMBER_FORMAT = {"type": "NUMBER", "pattern": '0.00"%"'}

COLUMN_WIDTHS = (
    170,
    130,
    185,
    160,
    170,
    150,
    160,
    110,
    120,
    120,
    130,
    110,
)

TITLE_ROW_HEIGHT = 34
SECTION_ROW_HEIGHT = 26
DETAIL_HEADER_ROW_HEIGHT = 28
DETAIL_ROW_HEIGHT = 22
FROZEN_TOP_ROWS = 6
