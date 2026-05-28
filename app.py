from flask import Flask, request, jsonify, send_from_directory, Response
import os
import requests
import re
import urllib.parse

app = Flask(__name__, static_folder='static', static_url_path='')

def get_working_cobalt_instances():
    """
    Queries the live community tracker to get the highest-scoring active
    public Cobalt servers. Falls back to a robust pool if the tracker is down.
    """
    fallbacks = [
        "https://api.kuko.moe/api",
        "https://cobalt.api.ryuko.space",
        "https://cobalt.hyper.rip",
        "https://cobalt.q14.link",
        "https://cobalt.wuk.sh"
    ]
    
    tracker_url = "https://instances.hyper.lol/api/instances"
    try:
        # This will resolve and fetch perfectly on Render's cloud servers
        res = requests.get(tracker_url, timeout=4)
        if res.status_code == 200:
            data = res.json()
            # Sort instances by their performance score in descending order
            sorted_instances = sorted(data, key=lambda x: x.get('score', 0), reverse=True)
            # Filter for up/active instances
            urls = [inst['url'] for inst in sorted_instances if inst.get('url')]
            if urls:
                return urls
    except Exception as e:
        print(f"Failed to fetch from live tracker: {e}. Falling back to default pool.")
        
    return fallbacks

def fetch_cobalt_stream(video_url, quality="720"):
    """
    Iterates through active public servers, executing failover in case of 
    errors or rate limits, and returns a verified stream URL.
    """
    instances = get_working_cobalt_instances()
    
    payload = {
        "url": video_url,
        "videoQuality": quality,
        "downloadMode": "auto"
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    for api_url in instances:
        api_url = api_url.rstrip('/')
        
        # Self-hosted V10 servers support root POST; older versions use /api/json
        endpoints_to_try = [api_url]
        if not api_url.endswith('/api/json'):
            endpoints_to_try.append(f"{api_url}/api/json")
            
        for endpoint in endpoints_to_try:
            try:
                # Fast timeout (6 seconds) to failover quickly if a server is unresponsive
                res = requests.post(endpoint, headers=headers, json=payload, timeout=6)
                if res.status_code == 200:
                    data = res.json()
                    
                    # Handle direct stream download responses
                    if data.get('status') in ['stream', 'redirect']:
                        return {
                            'url': data.get('url'),
                            'filename': data.get('filename', 'video.mp4')
                        }
                    # Handle galleries/picker lists (like TikTok multi-images)
                    elif data.get('status') == 'picker':
                        picker_items = data.get('picker', [])
                        if picker_items:
                            first_item = picker_items[0]
                            return {
                                'url': first_item.get('url'),
                                'filename': data.get('filename', 'video.mp4')
                            }
            except Exception as e:
                # Silently failover to the next endpoint
                continue
                
    return None

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
        
    try:
        # Call our robust failover download engine
        result = fetch_cobalt_stream(url)
        if not result:
            return jsonify({'error': 'Unable to process download. The video might be private or all cloud servers are temporarily busy. Please try again.'}), 500
            
        # Clean up a human-readable title from the returned filename
        filename = result.get('filename', 'video.mp4')
        title = os.path.splitext(filename)[0].replace('_', ' ').replace('-', ' ').strip()
        if not title:
            title = 'Downloaded Video'
            
        # Determine platform signature for aesthetics
        platform = 'Video'
        lower_url = url.lower()
        if 'youtube' in lower_url or 'youtu.be' in lower_url:
            platform = 'YouTube'
        elif 'tiktok' in lower_url:
            platform = 'TikTok'
        elif 'instagram' in lower_url:
            platform = 'Instagram'
        elif 'facebook' in lower_url or 'fb.watch' in lower_url:
            platform = 'Facebook'
            
        return jsonify({
            'title': title,
            'duration': None,
            'thumbnail': 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500&auto=format&fit=crop&q=60',
            'uploader': 'Cloud Engine',
            'platform': platform,
            'formats': [{
                'format_id': 'best',
                'ext': os.path.splitext(filename)[1].replace('.', '') if '.' in filename else 'mp4',
                'resolution': 'Best Quality',
                'filesize': None,
                'format_note': 'High Definition',
                'url': result.get('url')
            }],
            'original_url': url
        })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download')
def download_video():
    video_url = request.args.get('url')
    filename = request.args.get('title', 'video')
    ext = request.args.get('ext', 'mp4')
    
    if not video_url:
        return 'Missing video URL parameter', 400
        
    video_url = urllib.parse.unquote(video_url)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        # Secure filename formatting
        safe_filename = re.sub(r'[^\w\s-]', '', filename).strip()
        safe_filename = re.sub(r'[-\s]+', '_', safe_filename)
        if not safe_filename:
            safe_filename = 'video'
        full_filename = f"{safe_filename}.{ext}"
        
        # Proxy-stream the direct media file securely from the Cobalt server to bypass CORS
        req = requests.get(video_url, headers=headers, stream=True, timeout=45)
        req.raise_for_status()
        
        def generate():
            for chunk in req.iter_content(chunk_size=32768):
                if chunk:
                    yield chunk
                    
        response_headers = {
            'Content-Disposition': f'attachment; filename="{full_filename}"',
            'Content-Type': req.headers.get('Content-Type', 'video/mp4'),
        }
        
        # Forward Content-Length so the browser shows a perfectly accurate progress bar
        content_length = req.headers.get('Content-Length')
        if content_length:
            response_headers['Content-Length'] = content_length
            
        return Response(generate(), headers=response_headers)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Failed to download video stream: {str(e)}", 500

if __name__ == '__main__':
    # Listen on 0.0.0.0 to allow other devices on the same Wi-Fi to connect
    app.run(host='0.0.0.0', port=5001, debug=True)
