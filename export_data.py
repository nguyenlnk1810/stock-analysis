#!/usr/bin/env python3
"""
📤 EXPORT DỮ LIỆU PHÂN TÍCH -> JSON tĩnh cho GitHub Pages

Cách dùng:
  python export_data.py

Sau đó push thư mục docs/ lên GitHub Pages.
API keys SSI chỉ dùng ở local, KHÔNG bao giờ lên GitHub.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.export import DataExporter

if __name__ == "__main__":
    exporter = DataExporter()
    exporter.export_all()
