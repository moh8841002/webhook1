"""
YouTube Shorts Downloader Webhook
این وبهوک URL یوتیوب را دریافت می‌کند و با yt-dlp فایل ویدیو و متادیتا را برمی‌گرداند
"""
from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import tempfile
import re
from datetime import datetime
import base64

app = Flask(__name__)

def sanitize_filename(filename):
    """نام فایل را برای ذخیره امن می‌کند"""
    return re.sub(r'[<>:\"/\\|?*]', '_', filename)


def prepare_cookiefile():
    """اگر متغیر محیطی YT_COOKIES وجود داشته باشد، آن را در فایل temp می‌نویسد و مسیرش را برمی‌گرداند"""
    cookies_env = os.getenv('YT_COOKIES')
    if not cookies_env:
        return None
    # محتوای کوکی‌ها را در یک فایل موقت ذخیره می‌کنیم
    temp_dir = tempfile.mkdtemp()
    cookie_path = os.path.join(temp_dir, 'cookies.txt')
    with open(cookie_path, 'w', encoding='utf-8') as f:
        f.write(cookies_env)
    return cookie_path

@app.route('/', methods=['GET'])
def home():
    """صفحه اصلی - نشان دهنده سلامت سرویس"""
    return jsonify({
        'service': 'YouTube Shorts Downloader Webhook',
        'status': 'running',
        'endpoints': {
            'POST /download': 'Download YouTube video',
            'GET /health': 'Health check',
            'GET /file/<filename>': 'Serve downloaded file'
        }
    }), 200

@app.route('/download', methods=['POST'])
def download_video():
    """
    دانلود ویدیو یوتیوب و برگرداندن URL دانلود + متادیتا
    Body: {"url": "https://youtube.com/shorts/..."}
    """
    try:
        data = request.get_json()
        video_url = data.get('url')
        
        if not video_url:
            return jsonify({'error': 'URL is required'}), 400
        
        # تنظیمات yt-dlp برای Shorts
        temp_dir = tempfile.mkdtemp()
        output_template = os.path.join(temp_dir, '%(id)s.%(ext)s')
        
        # اگر کوکی‌ها ارائه شده‌اند، به yt-dlp بدهیم (برای دور زدن 429/anti-bot)
        cookie_path = prepare_cookiefile()

        ydl_opts = {
            'format': 'best[ext=mp4]/best',  # بهترین کیفیت MP4
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            # برخی هدرها و کلاینت iOS برای کاهش احتمال بلاک
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1',
                'Accept-Language': 'en-US,en;q=0.9'
            },
            'extractor_args': {
                'youtube': {'player_client': ['ios']}
            }
        }
        if cookie_path:
            ydl_opts['cookiefile'] = cookie_path
        
        # دانلود و استخراج اطلاعات
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            
            # متادیتا
            metadata = {
                'title': info.get('title', ''),
                'description': info.get('description', ''),
                'tags': info.get('tags', []),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', ''),
                'upload_date': info.get('upload_date', ''),
                'video_id': info.get('id', ''),
                'thumbnail': info.get('thumbnail', ''),
                'view_count': info.get('view_count', 0),
            }
            
            # ساخت کپشن با هشتگ‌ها
            caption = metadata['title']
            if metadata['tags']:
                hashtags = ' '.join([f"#{tag.replace(' ', '')}" for tag in metadata['tags'][:10]])
                caption = f"{caption}\n\n{hashtags}"
            
            # مسیر فایل دانلود شده
            filename = ydl.prepare_filename(info)
            
            if not os.path.exists(filename):
                return jsonify({'error': 'Download failed - file not found'}), 500
            
            # برگرداندن اطلاعات
            response = {
                'success': True,
                'file_path': filename,
                'file_size': os.path.getsize(filename),
                'metadata': metadata,
                'caption': caption,
                'download_url': f"{request.host_url}file/{os.path.basename(filename)}",
                'temp_dir': temp_dir
            }
            
            return jsonify(response), 200
            
    except Exception as e:
        msg = str(e)
        if 'Too Many Requests' in msg or 'Sign in to confirm' in msg:
            return jsonify({'error': 'YouTube blocked the request. Provide cookies via env YT_COOKIES or try later.', 'detail': msg}), 429
        return jsonify({'error': msg}), 500

@app.route('/file/<filename>', methods=['GET'])
def serve_file(filename):
    """سرو فایل دانلود شده"""
    try:
        # جستجوی فایل در temp directories
        temp_root = tempfile.gettempdir()
        for root, dirs, files in os.walk(temp_root):
            if filename in files:
                filepath = os.path.join(root, filename)
                return send_file(filepath, as_attachment=True)
        
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """بررسی سلامت سرویس"""
    return jsonify({'status': 'healthy', 'service': 'YouTube Downloader Webhook'}), 200

if __name__ == '__main__':
    # برای تست محلی
    app.run(host='0.0.0.0', port=5000, debug=True)
