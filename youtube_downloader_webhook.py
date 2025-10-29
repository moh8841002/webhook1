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

app = Flask(__name__)

def sanitize_filename(filename):
    """نام فایل را برای ذخیره امن می‌کند"""
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

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
        
        ydl_opts = {
            'format': 'best[ext=mp4]/best',  # بهترین کیفیت MP4
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
        }
        
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
        return jsonify({'error': str(e)}), 500

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
