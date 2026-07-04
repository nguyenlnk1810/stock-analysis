#!/bin/bash
set -e

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║    🤖 AI STOCK ANALYST - CÀI ĐẶT TỰ ĐỘNG       ║"
echo "║    Hệ thống phân tích chứng khoán thông minh     ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Bước 1: Kiểm tra Python
echo "📌 Bước 1/5: Kiểm tra Python..."
PYTHON_VERSION=$(python3 --version 2>&1)
echo "   ✅ $PYTHON_VERSION"

# Bước 2: Tạo môi trường ảo
echo "📌 Bước 2/5: Tạo môi trường ảo (virtual environment)..."
if [ -d "venv" ]; then
    echo "   ⚠️  Đã có venv, bỏ qua..."
else
    python3 -m venv venv
    echo "   ✅ Đã tạo venv/"
fi

source venv/bin/activate

# Bước 3: Cài thư viện
echo "📌 Bước 3/5: Cài đặt thư viện Python (có thể mất 2-3 phút)..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "   ✅ Hoàn tất cài đặt thư viện"

# Bước 4: Tạo file .env nếu chưa có
echo "📌 Bước 4/5: Cấu hình API..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "   ⚠️  ĐÃ TẠO file .env"
    echo "   ⚠️  Bạn cần điền thông tin SSI API vào file .env"
else
    echo "   ✅ File .env đã tồn tại"
fi

# Bước 5: Kiểm tra kết quả
echo "📌 Bước 5/5: Kiểm tra cài đặt..."
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from src.config import config
    from src.ssi_client import SSIClient
    from src.technical_analysis import TechnicalAnalyzer
    from src.news_fetcher import NewsFetcher
    from src.ai_agent import AIStockAgent
    print('   ✅ Tất cả modules đã import thành công!')
except Exception as e:
    print(f'   ❌ Lỗi: {e}')
    sys.exit(1)
"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║             ✅  CÀI ĐẶT HOÀN TẤT                ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "📋 Các bước tiếp theo:"
echo ""
echo "   Bước A: Mở file .env để điền API key:"
echo "      open .env"
echo ""
echo "   Bước B: (Khuyến nghị) Cài Ollama để chạy AI local miễn phí:"
echo "      /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
echo "      brew install ollama"
echo "      ollama pull llama3"
echo ""
echo "   Bước C: Chạy ứng dụng:"
echo "      source venv/bin/activate"
echo "      streamlit run run.py"
echo ""
echo "   🌐 Trình duyệt sẽ mở tại: http://localhost:8501"
echo ""
