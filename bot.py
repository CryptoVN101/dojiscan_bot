import os
import json
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from detector import DojiDetector
from datetime import datetime

# ========== FILE LƯU DANH SÁCH SYMBOLS ==========
SYMBOLS_FILE = "symbols.json"

# ========== CLASS QUẢN LÝ SYMBOLS ==========
class SymbolManager:
    def __init__(self, filename=SYMBOLS_FILE):
        self.filename = filename
        self.symbols = self.load_symbols()
    
    def load_symbols(self):
        """Load danh sách symbols từ file"""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                    return data.get('symbols', ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ZROUSDT", "VIRTUALUSDT", "USUALUSDT", "UNIUSDT", "REZUSDT", "LDOUSDT", "KMNOUSDT", "IOUSDT", "GMXUSDT", "ENAUSDT", "EIGENUSDT", "DYDXUSDT", "COWUSDT", "CAKEUSDT", "BERAUSDT", "BBUSDT", "ARBUSDT", "SOLUSDT", "LINKUSDT", "OPUSDT", "APTUSDT", "DOGEUSDT", "WUSDT", "LTCUSDT", "DOTUSDT", "TRXUSDT", "ETCUSDT", "XLMUSDT", "ATOMUSDT", "FILUSDT", "VETUSDT", "ICPUSDT", "THETAUSDT", "SANDUSDT", "AXSUSDT", "ALGOUSDT", "EGLDUSDT", "AAVEUSDT", "FTMUSDT", "NEARUSDT", "GRTUSDT"])
            except:
                pass
        return ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ZROUSDT", "VIRTUALUSDT", "USUALUSDT", "UNIUSDT", "REZUSDT", "LDOUSDT", "KMNOUSDT", "IOUSDT", "GMXUSDT", "ENAUSDT", "EIGENUSDT", "DYDXUSDT", "COWUSDT", "CAKEUSDT", "BERAUSDT", "BBUSDT", "ARBUSDT", "SOLUSDT", "LINKUSDT", "OPUSDT", "APTUSDT", "DOGEUSDT", "WUSDT", "LTCUSDT", "DOTUSDT", "TRXUSDT", "ETCUSDT", "XLMUSDT", "ATOMUSDT", "FILUSDT", "VETUSDT", "ICPUSDT", "THETAUSDT", "SANDUSDT", "AXSUSDT", "ALGOUSDT", "EGLDUSDT", "AAVEUSDT", "FTMUSDT", "NEARUSDT", "GRTUSDT"]  # Default symbols
    
    def save_symbols(self):
        """Lưu danh sách symbols vào file"""
        try:
            with open(self.filename, 'w') as f:
                json.dump({'symbols': self.symbols}, f, indent=2)
            return True
        except Exception as e:
            print(f"❌ Lỗi khi lưu symbols: {e}")
            return False
    
    def add_symbol(self, symbol):
        """Thêm symbol mới"""
        symbol = symbol.upper().strip()
        
        # Validate format
        if not symbol.endswith('USDT'):
            return False, "❌ Symbol phải có dạng XXXUSDT (ví dụ: BTCUSDT)"
        
        if symbol in self.symbols:
            return False, f"⚠️ {symbol} đã có trong danh sách"
        
        self.symbols.append(symbol)
        if self.save_symbols():
            return True, f"✅ Đã thêm {symbol} vào danh sách theo dõi"
        else:
            self.symbols.remove(symbol)
            return False, "❌ Lỗi khi lưu symbol"
    
    def remove_symbol(self, symbol):
        """Xóa symbol"""
        symbol = symbol.upper().strip()
        
        if symbol not in self.symbols:
            return False, f"⚠️ {symbol} không có trong danh sách"
        
        if len(self.symbols) <= 1:
            return False, "❌ Không thể xóa. Phải có ít nhất 1 symbol"
        
        self.symbols.remove(symbol)
        if self.save_symbols():
            return True, f"✅ Đã xóa {symbol} khỏi danh sách theo dõi"
        else:
            self.symbols.append(symbol)
            return False, "❌ Lỗi khi lưu thay đổi"
    
    def get_symbols(self):
        """Lấy danh sách symbols"""
        return self.symbols.copy()
    
    def get_symbols_text(self):
        """Lấy text hiển thị danh sách symbols"""
        if not self.symbols:
            return "Chưa có symbol nào"
        return "\n".join([f"  • {symbol}" for symbol in self.symbols])

# ========== COMMAND HANDLERS ==========
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho lệnh /start"""
    await update.message.reply_text(
        "🤖 <b>Bot Phát Hiện Nến Doji</b>\n\n"
        "📊 Bot tự động phát hiện nến Doji với volume thấp\n"
        "🔔 Tín hiệu sẽ được gửi tự động lên channel\n\n"
        "<b>📋 Danh sách lệnh:</b>\n\n"
        "🔍 <b>Thông tin bot:</b>\n"
        "/start - Xem hướng dẫn\n"
        "/status - Kiểm tra trạng thái bot\n"
        "/list - Xem danh sách coin đang theo dõi\n\n"
        "➕ <b>Quản lý coin:</b>\n"
        "/add BTCUSDT - Thêm coin vào danh sách\n"
        "/remove BTCUSDT - Xóa coin khỏi danh sách\n\n"
        "💡 <b>Ví dụ:</b>\n"
        "<code>/add SOLUSDT</code>\n"
        "<code>/remove BNBUSDT</code>",
        parse_mode="HTML"
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho lệnh /status"""
    symbol_manager = context.bot_data.get('symbol_manager')
    detector = context.bot_data.get('detector')
    
    symbols = symbol_manager.get_symbols()
    
    await update.message.reply_text(
        f"✅ <b>Bot đang hoạt động</b>\n\n"
        f"📊 Số coin đang theo dõi: {len(symbols)}\n"
        f"⏱️ Khung thời gian: H1, H2, H4, D1\n"
        f"🎯 Chế độ: Realtime Detection\n"
        f"📏 Ngưỡng Doji: {detector.doji_threshold}%\n"
        f"📉 Ngưỡng Volume: {detector.volume_ratio * 100}%\n"
        f"💾 Tín hiệu đã cache: {len(detector.signal_cache)}",
        parse_mode="HTML"
    )

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho lệnh /list"""
    symbol_manager = context.bot_data.get('symbol_manager')
    symbols_text = symbol_manager.get_symbols_text()
    
    await update.message.reply_text(
        f"📊 <b>Danh sách coin đang theo dõi:</b>\n\n{symbols_text}\n\n"
        f"<b>Tổng:</b> {len(symbol_manager.get_symbols())} coin",
        parse_mode="HTML"
    )

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho lệnh /add"""
    symbol_manager = context.bot_data.get('symbol_manager')
    
    # Kiểm tra tham số
    if not context.args:
        await update.message.reply_text(
            "❌ Vui lòng nhập symbol cần thêm\n\n"
            "📝 Cú pháp: <code>/add BTCUSDT</code>\n"
            "💡 Ví dụ: <code>/add SOLUSDT</code>",
            parse_mode="HTML"
        )
        return
    
    symbol = context.args[0]
    success, message = symbol_manager.add_symbol(symbol)
    
    await update.message.reply_text(message)
    
    if success:
        # Gửi danh sách mới
        symbols_text = symbol_manager.get_symbols_text()
        await update.message.reply_text(
            f"📊 <b>Danh sách mới:</b>\n\n{symbols_text}",
            parse_mode="HTML"
        )

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho lệnh /remove"""
    symbol_manager = context.bot_data.get('symbol_manager')
    
    # Kiểm tra tham số
    if not context.args:
        await update.message.reply_text(
            "❌ Vui lòng nhập symbol cần xóa\n\n"
            "📝 Cú pháp: <code>/remove BTCUSDT</code>\n"
            "💡 Ví dụ: <code>/remove BNBUSDT</code>",
            parse_mode="HTML"
        )
        return
    
    symbol = context.args[0]
    success, message = symbol_manager.remove_symbol(symbol)
    
    await update.message.reply_text(message)
    
    if success:
        # Gửi danh sách mới
        symbols_text = symbol_manager.get_symbols_text()
        await update.message.reply_text(
            f"📊 <b>Danh sách mới:</b>\n\n{symbols_text}",
            parse_mode="HTML"
        )

# ========== HÀM CHẠY SCANNER ==========
async def run_scanner(context: ContextTypes.DEFAULT_TYPE):
    """
    Chạy scanner liên tục và tự động gửi tín hiệu lên channel
    """
    bot = context.bot
    symbol_manager = context.bot_data.get('symbol_manager')
    detector = context.bot_data.get('detector')
    channel_id = context.bot_data.get('channel_id')
    
    print("🤖 Scanner đã khởi động!")
    print(f"📢 Channel: {channel_id}")
    
    while True:
        try:
            # Lấy danh sách symbols mới nhất
            symbols = symbol_manager.get_symbols()
            
            # Quét và gửi tín hiệu
            signals = await detector.scan_symbols(symbols)
            
            # Gửi tín hiệu lên channel
            for signal in signals:
                # Xác định emoji và text cho tín hiệu
                if "LONG" in signal['signal_type']:
                    signal_emoji = "🟢"
                    signal_text = "Tín hiệu đảo chiều BUY/LONG"
                else:
                    signal_emoji = "🔴"
                    signal_text = "Tín hiệu đảo chiều SELL/SHORT"
                
                message = (
                    f"👀 <b>PHÁT HIỆN NẾN DOJI</b>\n"
                    f"━━━━━━━━━━━━━━━━━\n"
                    f"🔶 <b>Token:</b> {signal['symbol']}\n"
                    f"{signal_emoji} <b>{signal_text}</b>\n"
                    f"⏰ <b>Khung thời gian:</b> {signal['timeframe']}\n"
                    f"💰 <b>Giá xác nhận:</b> ${signal['price']:.4f}"
                )
                
                try:
                    await bot.send_message(
                        chat_id=channel_id,
                        text=message,
                        parse_mode="HTML"
                    )
                    print(f"✅ Đã gửi: {signal['symbol']} - {signal['timeframe']} - {signal['close_time']}")
                except Exception as e:
                    print(f"❌ Lỗi gửi message: {e}")
            
            # Tính thời gian chờ thông minh
            wait_time = detector.calculate_wait_time()
            print(f"⏳ Đợi {wait_time}s đến lần quét tiếp theo...")
            
            await asyncio.sleep(wait_time)
            
        except Exception as e:
            print(f"❌ Lỗi scanner: {e}")
            await asyncio.sleep(10)

# ========== MAIN ==========
async def main():
    """Hàm chính"""
    # Lấy config từ environment variables
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("❌ Thiếu TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHANNEL_ID")
        print("💡 Cần setup environment variables trước khi chạy")
        return
    
    print("\n" + "="*60)
    print("🚀 ĐANG KHỞI ĐỘNG BOT DOJI DETECTOR")
    print("="*60)
    
    # Khởi tạo components
    symbol_manager = SymbolManager()
    detector = DojiDetector()
    
    print(f"\n📊 Symbols ban đầu: {', '.join(symbol_manager.get_symbols())}")
    print(f"📢 Channel ID: {TELEGRAM_CHANNEL_ID}")
    
    # Khởi tạo bot
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Lưu vào bot_data
    application.bot_data['symbol_manager'] = symbol_manager
    application.bot_data['detector'] = detector
    application.bot_data['channel_id'] = TELEGRAM_CHANNEL_ID
    
    # Thêm command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("remove", remove_command))
    
    # Khởi động bot
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    print("\n✅ Bot đã sẵn sàng!")
    print("🔄 Scanner sẽ bắt đầu quét...\n")
    
    # Chạy scanner
    await run_scanner(application)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⛔ Bot đã dừng!")