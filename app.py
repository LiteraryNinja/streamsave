from flask import Flask, request, jsonify, send_from_directory, Response
import os
import requests
import yt_dlp
import re
import urllib.parse

app = Flask(__name__, static_folder='static', static_url_path='')

# Securely extract cookies from environment variables on startup
cookies_text = os.environ.get('COOKIES_TEXT')
cookies_path = None
if cookies_text:
    temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_downloads')
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    cookies_path = os.path.join(temp_dir, 'cookies.txt')
    with open(cookies_path, 'w', encoding='utf-8') as f:
        f.write(cookies_text)

# Extract proxy configuration if available
proxy_url = os.environ.get('PROXY_URL')

def get_ydl_opts(format_id=None, temp_filepath_template=None, is_download=False):
    """
    Central helper to generate consistent yt-dlp configurations.
    Injects mobile user-agents, secure login cookies, and proxies dynamically.
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios']
            }
        }
    }
    
    if is_download:
        ydl_opts['format'] = format_id if format_id else 'best'
        ydl_opts['outtmpl'] = temp_filepath_template
    else:
        ydl_opts['skip_download'] = True
        ydl_opts['extract_flat'] = False
        
    # Inject secure cookies if available
    if cookies_path and os.path.exists(cookies_path):
        ydl_opts['cookiefile'] = cookies_path
        
    # Inject routing proxies if available
    if proxy_url:
        ydl_opts['proxy'] = proxy_url
        
    return ydl_opts

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'No URL provided'}), 400
    
    url = data['url'].strip()
    if not url:
        return jsonify({'error': 'URL is empty'}), 400
        
    # Meta Fail-Fast Check: Instagram & Facebook block datacenter IPs by default.
    # If the user tries to download Meta links and has not set up a PROXY_URL,
    # fail instantly with a beautiful, educational error message rather than hanging!
    is_meta = 'instagram.com' in url.lower() or 'facebook.com' in url.lower() or 'fb.watch' in url.lower()
    if is_meta and not proxy_url:
        return jsonify({
            'error': 'Instagram & Facebook block cloud servers by default. To unlock Instagram/Facebook downloads on your phone 24/7, you just need to add a secure PROXY_URL in your Render settings (using a cheap $1.50 residential proxy).'
        }), 400
        
    # Get centralized yt-dlp options
    ydl_opts = get_ydl_opts()
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Extract basic metadata
            title = info.get('title', 'Unknown Title')
            duration = info.get('duration') # in seconds
            thumbnail = info.get('thumbnail') or (info.get('thumbnails')[0]['url'] if info.get('thumbnails') else None)
            uploader = info.get('uploader') or info.get('channel') or 'Unknown Source'
            platform = info.get('extractor_key', 'Generic')
            
            # Extract formats that contain both video AND audio
            formats_list = []
            raw_formats = info.get('formats', [])
            
            for f in raw_formats:
                vcodec = f.get('vcodec', 'none')
                acodec = f.get('acodec', 'none')
                
                # Check for both video and audio streams
                if vcodec != 'none' and acodec != 'none':
                    height = f.get('height')
                    width = f.get('width')
                    res_label = f"{height}p" if height else (f"{width}x" if width else "Unknown")
                    
                    filesize = f.get('filesize') or f.get('filesize_approx')
                    filesize_mb = round(filesize / (1024 * 1024), 1) if filesize else None
                    
                    formats_list.append({
                        'format_id': f.get('format_id'),
                        'ext': f.get('ext', 'mp4'),
                        'resolution': res_label,
                        'filesize': filesize_mb,
                        'format_note': f.get('format_note') or f.get('resolution') or '',
                        'url': f.get('url')
                    })
            
            # If no formats with both audio & video were found (e.g. simple direct link),
            # use top-level direct URL
            if not formats_list and info.get('url'):
                formats_list.append({
                    'format_id': 'best',
                    'ext': info.get('ext', 'mp4'),
                    'resolution': 'Best Quality',
                    'filesize': None,
                    'format_note': 'Direct Stream',
                    'url': info.get('url')
                })
            
            # Sort formats by resolution height
            def get_height(fmt):
                res = fmt['resolution']
                match = re.search(r'(\d+)p', res)
                return int(match.group(1)) if match else 0
            
            formats_list = sorted(formats_list, key=get_height, reverse=True)
            
            # Deduplicate formats by resolution to keep UI neat
            seen_resolutions = set()
            deduped_formats = []
            for fmt in formats_list:
                res = fmt['resolution']
                if res not in seen_resolutions:
                    seen_resolutions.add(res)
                    deduped_formats.append(fmt)
            
            return jsonify({
                'title': title,
                'duration': duration,
                'thumbnail': thumbnail,
                'uploader': uploader,
                'platform': platform,
                'formats': deduped_formats,
                'original_url': url
            })
            
    except Exception as e:
        error_msg = str(e)
        if 'Unsupported URL' in error_msg:
            error_msg = 'Unsupported website or invalid link. Please double-check your link.'
        elif 'Sign in' in error_msg:
            error_msg = 'This video requires a sign-in or is private.'
        return jsonify({'error': error_msg}), 500

@app.route('/api/download')
def download_video():
    original_url = request.args.get('original_url')
    format_id = request.args.get('format_id')
    direct_url = request.args.get('url')
    filename = request.args.get('title', 'video')
    ext = request.args.get('ext', 'mp4')
    
    if not original_url and not direct_url:
        return 'Missing video URL parameters', 400
        
    # Set up a secure temporary downloads folder in our workspace
    temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_downloads')
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        
    import uuid
    unique_id = str(uuid.uuid4())
    temp_filepath_template = os.path.join(temp_dir, f"{unique_id}_%(id)s.%(ext)s")
    
    try:
        if original_url:
            original_url = urllib.parse.unquote(original_url)
            
            # Get centralized download options
            ydl_opts = get_ydl_opts(format_id=format_id, temp_filepath_template=temp_filepath_template, is_download=True)
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([original_url])
                
            # Find the actual downloaded file (handling arbitrary extensions)
            downloaded_file = None
            for file in os.listdir(temp_dir):
                if file.startswith(unique_id):
                    downloaded_file = os.path.join(temp_dir, file)
                    break
                    
            if not downloaded_file or not os.path.exists(downloaded_file):
                return 'Failed to process media file locally', 500
        else:
            # Fallback for direct MP4 links
            direct_url = urllib.parse.unquote(direct_url)
            downloaded_file = os.path.join(temp_dir, f"{unique_id}.{ext}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            # Inject proxies for fallback direct URL requests if proxy is active
            req_proxies = None
            if proxy_url:
                req_proxies = {
                    'http': proxy_url,
                    'https': proxy_url
                }
                
            req = requests.get(direct_url, headers=headers, proxies=req_proxies, stream=True, timeout=30)
            req.raise_for_status()
            with open(downloaded_file, 'wb') as f:
                for chunk in req.iter_content(chunk_size=32768):
                    if chunk:
                        f.write(chunk)
                        
        # Extract metadata for transfer
        content_size = os.path.getsize(downloaded_file)
        actual_ext = os.path.splitext(downloaded_file)[1].replace('.', '')
        if not actual_ext:
            actual_ext = ext
            
        safe_filename = re.sub(r'[^\w\s-]', '', filename).strip()
        safe_filename = re.sub(r'[-\s]+', '_', safe_filename)
        if not safe_filename:
            safe_filename = 'video'
        full_filename = f"{safe_filename}.{actual_ext}"
        
        # Stream chunks back to client browser
        def generate():
            try:
                with open(downloaded_file, 'rb') as f:
                    while True:
                        chunk = f.read(32768)
                        if not chunk:
                            break
                        yield chunk
            finally:
                # Guarantee temporary file is deleted immediately after transfer finishes or cancels
                if downloaded_file and os.path.exists(downloaded_file):
                    try:
                        os.remove(downloaded_file)
                    except Exception as err:
                        print(f"Error removing temp file: {err}")
                        
        response_headers = {
            'Content-Disposition': f'attachment; filename="{full_filename}"',
            'Content-Type': 'video/mp4' if actual_ext == 'mp4' else f'video/{actual_ext}',
            'Content-Length': str(content_size)
        }
        
        return Response(generate(), headers=response_headers)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        # Cleanup any partial files in case of failures before streaming starts
        for file in os.listdir(temp_dir):
            if file.startswith(unique_id):
                try:
                    os.remove(os.path.join(temp_dir, file))
                except:
                    pass
        return f"Failed to download video stream: {str(e)}", 500

if __name__ == '__main__':
    # Listen on 0.0.0.0 to allow other devices on the same Wi-Fi to connect
    app.run(host='0.0.0.0', port=5001, debug=True)
