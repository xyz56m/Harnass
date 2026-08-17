#!/data/data/com.termux/files/usr/bin/python3
"""
Vision MCP Server — 图像识别与元信息提取

功能：
  - ocr_image: 使用 Tesseract OCR 识别图片中的文字
  - image_info: 提取图片元信息（尺寸、格式、颜色空间等）
  - list_images: 列出目录下的图片文件

实现：MCP Protocol (JSON-RPC 2.0) over stdio
"""
import json, sys, os, subprocess, base64, struct, io

# ── MCP Protocol Utilities ──────────────────────────────────────────────────

def send(msg):
    """Send a JSON-RPC message over stdout."""
    data = json.dumps(msg, ensure_ascii=False)
    sys.stdout.write("Content-Length: %d\r\n\r\n%s" % (len(data.encode()), data))
    sys.stdout.flush()

def recv():
    """Read a JSON-RPC message from stdin."""
    raw = b""
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        raw += line
        if line == b"\r\n":
            break
    header = raw.decode().strip()
    if header.startswith("Content-Length:"):
        length = int(header.split(":")[1].strip())
        body = sys.stdin.buffer.read(length)
        return json.loads(body.decode())
    return None

# ── Tool Handlers ───────────────────────────────────────────────────────────

# Images in /data/data/com.termux/files/home or /sdcard/DCIM are typical
ALLOWED_PATHS = [
    os.environ.get("HOME", "/data/data/com.termux/files/home"),
    "/sdcard",
    "/storage/emulated/0",
]

def resolve_path(path):
    """Resolve and validate a file path. Returns absolute path or None."""
    path = os.path.abspath(os.path.expanduser(path))
    # Allow any path if user explicitly passes it
    return path if os.path.exists(path) else None

def handle_ocr_image(args):
    """OCR: extract text from an image file using Tesseract."""
    path = args.get("path", "")
    lang = args.get("lang", "eng")
    psm = args.get("psm", 3)  # Page segmentation mode

    resolved = resolve_path(path)
    if not resolved:
        return {"content": [{"type": "text", "text": f"文件不存在: {path}"}], "isError": True}

    try:
        result = subprocess.run(
            ["tesseract", resolved, "stdout", "-l", lang, "--psm", str(psm)],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            text = result.stdout.strip()
            if not text:
                text = "[未识别出文字]"
            return {"content": [{"type": "text", "text": text}]}
        else:
            err = result.stderr.strip()[:500]
            return {"content": [{"type": "text", "text": f"OCR 失败: {err}"}], "isError": True}
    except FileNotFoundError:
        return {"content": [{"type": "text", "text": "tesseract 未安装，请执行: pkg install tesseract"}], "isError": True}
    except subprocess.TimeoutExpired:
        return {"content": [{"type": "text", "text": "OCR 超时（图片过大）"}], "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"OCR 错误: {str(e)}"}], "isError": True}

def handle_image_info(args):
    """Extract image metadata: format, dimensions, color space, file size."""
    path = args.get("path", "")
    resolved = resolve_path(path)
    if not resolved:
        return {"content": [{"type": "text", "text": f"文件不存在: {path}"}], "isError": True}

    info = []
    stat = os.stat(resolved)
    info.append(f"文件名: {os.path.basename(resolved)}")
    info.append(f"大小: {stat.st_size:,} 字节 ({stat.st_size/1024:.1f} KB)")

    # Try ImageMagick identify
    try:
        r = subprocess.run(
            ["identify", "-verbose", resolved],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0:
            # Extract key lines
            lines = r.stdout.split("\n")
            for line in lines:
                for kw in ["Geometry", "Format", "Class", "Type", "Depth", "Channel",
                           "Resolution", "Orientation", "Date", "Quality", "Compression"]:
                    if kw in line:
                        info.append(line.strip())
                        break
            if not info:
                info.append(r.stdout.strip()[:500])
        else:
            # Fallback: use python Pillow-like approach or file command
            r2 = subprocess.run(["file", resolved], capture_output=True, text=True, timeout=10)
            info.append(r2.stdout.strip())
    except FileNotFoundError:
        # No imagemagick, use file
        try:
            r2 = subprocess.run(["file", resolved], capture_output=True, text=True, timeout=10)
            info.append(r2.stdout.strip())
        except:
            info.append("(无法读取元信息)")
    except Exception as e:
        info.append(f"元信息错误: {str(e)[:100]}")

    return {"content": [{"type": "text", "text": "\n".join(info)}]}

def handle_list_images(args):
    """List image files in a directory."""
    path = args.get("path", os.environ.get("HOME", "/data/data/com.termux/files/home"))
    depth = min(args.get("depth", 1), 3)
    resolved = resolve_path(path)
    if not resolved:
        return {"content": [{"type": "text", "text": f"目录不存在: {path}"}], "isError": True}

    img_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".svg", ".ico"}
    results = []
    for root, dirs, files in os.walk(resolved):
        rel = os.path.relpath(root, resolved)
        if rel == ".":
            rel = ""
        level = rel.count(os.sep) + 1 if rel else 0
        if level > depth:
            dirs.clear()
            continue
        for f in sorted(files):
            if os.path.splitext(f)[1].lower() in img_exts:
                fp = os.path.join(root, f)
                try:
                    size = os.path.getsize(fp)
                    results.append(f"{os.path.join(rel, f)} ({size/1024:.1f} KB)" if rel else f"{f} ({size/1024:.1f} KB)")
                except:
                    pass

    if not results:
        return {"content": [{"type": "text", "text": f"在 {resolved} 中未找到图片文件"}]}

    text = f"在 {resolved} 中找到 {len(results)} 个图片文件:\n" + "\n".join(results[:200])
    if len(results) > 200:
        text += f"\n... 以及 {len(results)-200} 个更多"
    return {"content": [{"type": "text", "text": text}]}

# ── Tool Registry ───────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "ocr_image",
        "description": "使用 Tesseract OCR 识别图片中的文字。支持多种语言（默认 eng）。返回识别出的文本内容。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "图片文件路径（如 /sdcard/DCIM/photo.jpg）"},
                "lang": {"type": "string", "description": "OCR 语言（eng=英语, chi_sim=简体中文, chi_tra=繁体中文, jpn=日语, kor=韩语），默认 eng", "default": "eng"},
                "psm": {"type": "integer", "description": "页面分割模式 3=自动, 6=单文本块, 7=单行, 11=稀疏文本, 13=原始行", "default": 3}
            },
            "required": ["path"]
        }
    },
    {
        "name": "image_info",
        "description": "提取图片的元信息：尺寸、格式、色彩空间、文件大小、分辨率等。支持常见图片格式。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "图片文件路径"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "list_images",
        "description": "列出目录下的图片文件（jpg/png/gif/webp/bmp/tiff/svg/ico），支持递归。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要搜索的目录路径", "default": "$HOME"},
                "depth": {"type": "integer", "description": "递归深度（1-3）", "default": 1}
            }
        }
    }
]

HANDLERS = {
    "ocr_image": handle_ocr_image,
    "image_info": handle_image_info,
    "list_images": handle_list_images,
}

# ── Main Loop ───────────────────────────────────────────────────────────────

def main():
    # Send initialize response
    send({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "vision-mcp",
                "version": "1.0.0"
            }
        }
    })

    while True:
        msg = recv()
        if msg is None:
            break

        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        # Handle notifications (no id)
        if msg_id is None:
            if method == "notifications/initialized":
                # Send tool list
                send({
                    "jsonrpc": "2.0",
                    "method": "notifications/tools/list_changed",
                    "params": {}
                })
            continue

        # Handle requests
        if method == "tools/list":
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": TOOLS
                }
            })
        elif method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments", {})
            handler = HANDLERS.get(name)
            if handler:
                result = handler(args)
                send({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": result
                })
            else:
                send({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"未知工具: {name}"
                    }
                })
        elif method == "initialize":
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "vision-mcp", "version": "1.0.0"}
                }
            })
        else:
            # Unknown method
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {}  # Silently ignore
            })

if __name__ == "__main__":
    main()