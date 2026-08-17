#!/data/data/com.termux/files/usr/bin/python3
"""
Media MCP Server — 图片与媒体处理

功能：
  - convert_image: 图片格式转换（jpg/png/webp/gif/bmp）
  - resize_image: 调整图片尺寸
  - compress_image: 压缩图片文件
  - create_thumbnail: 生成缩略图
  - get_format_info: 获取文件格式信息（file 命令）
  - screenshot_url: 使用 wkhtmltoimage 截取网页截图（需安装 wkhtmltoimage）

实现：MCP Protocol (JSON-RPC 2.0) over stdio
"""
import json, sys, os, subprocess, shutil

# ── MCP Protocol Utilities ──────────────────────────────────────────────────

def send(msg):
    data = json.dumps(msg, ensure_ascii=False)
    sys.stdout.write("Content-Length: %d\r\n\r\n%s" % (len(data.encode()), data))
    sys.stdout.flush()

def recv():
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

def resolve_path(path):
    path = os.path.abspath(os.path.expanduser(path))
    return path if os.path.exists(path) else None

def safe_path(path):
    """Return absolute path for output (create parent dirs)."""
    path = os.path.abspath(os.path.expanduser(path))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path

# ── Tool Handlers ───────────────────────────────────────────────────────────

def handle_convert_image(args):
    src = args.get("source", "")
    dst = args.get("dest", "")
    quality = args.get("quality", 90)
    resolved = resolve_path(src)
    if not resolved:
        return {"content": [{"type": "text", "text": f"源文件不存在: {src}"}], "isError": True}
    out = safe_path(dst)
    try:
        cmd = ["convert", resolved, "-quality", str(quality), out]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            stat = os.stat(out)
            return {"content": [{"type": "text", "text": f"转换完成: {out} ({stat.st_size/1024:.1f} KB)"}]}
        else:
            return {"content": [{"type": "text", "text": f"转换失败: {r.stderr.strip()[:500]}"}], "isError": True}
    except FileNotFoundError:
        return {"content": [{"type": "text", "text": "ImageMagick 未安装，请执行: pkg install imagemagick"}], "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"错误: {str(e)}"}], "isError": True}

def handle_resize_image(args):
    src = args.get("source", "")
    dst = args.get("dest", "")
    width = args.get("width", 0)
    height = args.get("height", 0)
    percent = args.get("percent", 0)
    resolved = resolve_path(src)
    if not resolved:
        return {"content": [{"type": "text", "text": f"源文件不存在: {src}"}], "isError": True}
    out = safe_path(dst)
    try:
        if percent > 0:
            cmd = ["convert", resolved, "-resize", f"{percent}%", out]
        elif width > 0 and height > 0:
            cmd = ["convert", resolved, "-resize", f"{width}x{height}!", out]
        elif width > 0:
            cmd = ["convert", resolved, "-resize", f"{width}x", out]
        elif height > 0:
            cmd = ["convert", resolved, "-resize", f"x{height}", out]
        else:
            return {"content": [{"type": "text", "text": "请指定 width/height/percent 之一"}], "isError": True}
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            stat = os.stat(out)
            return {"content": [{"type": "text", "text": f"调整完成: {out} ({stat.st_size/1024:.1f} KB)"}]}
        else:
            return {"content": [{"type": "text", "text": f"调整失败: {r.stderr.strip()[:500]}"}], "isError": True}
    except FileNotFoundError:
        return {"content": [{"type": "text", "text": "ImageMagick 未安装"}], "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"错误: {str(e)}"}], "isError": True}

def handle_compress_image(args):
    src = args.get("source", "")
    dst = args.get("dest", "")
    quality = args.get("quality", 70)
    resolved = resolve_path(src)
    if not resolved:
        return {"content": [{"type": "text", "text": f"源文件不存在: {src}"}], "isError": True}
    out = safe_path(dst)
    try:
        src_size = os.stat(resolved).st_size
        cmd = ["convert", resolved, "-strip", "-quality", str(quality), out]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            dst_size = os.stat(out).st_size
            ratio = (1 - dst_size / src_size) * 100
            return {"content": [{"type": "text", "text": f"压缩完成: {src_size/1024:.1f} KB → {dst_size/1024:.1f} KB (减少 {ratio:.0f}%)"}], "isError": False}
        else:
            return {"content": [{"type": "text", "text": f"压缩失败: {r.stderr.strip()[:500]}"}], "isError": True}
    except FileNotFoundError:
        return {"content": [{"type": "text", "text": "ImageMagick 未安装"}], "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"错误: {str(e)}"}], "isError": True}

def handle_create_thumbnail(args):
    src = args.get("source", "")
    dst = args.get("dest", "")
    size = args.get("size", 200)
    resolved = resolve_path(src)
    if not resolved:
        return {"content": [{"type": "text", "text": f"源文件不存在: {src}"}], "isError": True}
    out = safe_path(dst)
    try:
        cmd = ["convert", resolved, "-thumbnail", f"{size}x{size}^", "-gravity", "center", "-extent", f"{size}x{size}", out]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return {"content": [{"type": "text", "text": f"缩略图已生成: {out} ({size}x{size})"}]}
        else:
            return {"content": [{"type": "text", "text": f"缩略图生成失败: {r.stderr.strip()[:500]}"}], "isError": True}
    except FileNotFoundError:
        return {"content": [{"type": "text", "text": "ImageMagick 未安装"}], "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"错误: {str(e)}"}], "isError": True}

def handle_get_format_info(args):
    path = args.get("path", "")
    resolved = resolve_path(path)
    if not resolved:
        return {"content": [{"type": "text", "text": f"文件不存在: {path}"}], "isError": True}
    try:
        r = subprocess.run(["file", resolved], capture_output=True, text=True, timeout=10)
        stat = os.stat(resolved)
        text = f"路径: {resolved}\n大小: {stat.st_size:,} 字节 ({stat.st_size/1024:.1f} KB)\n类型: {r.stdout.strip()}"
        return {"content": [{"type": "text", "text": text}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"错误: {str(e)}"}], "isError": True}

# ── Tool Registry ───────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "convert_image",
        "description": "图片格式转换。支持 jpg/png/webp/gif/bmp 等格式互转，可设置质量。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "源图片路径"},
                "dest": {"type": "string", "description": "输出路径（扩展名决定格式，如 output.png）"},
                "quality": {"type": "integer", "description": "输出质量 1-100", "default": 90}
            },
            "required": ["source", "dest"]
        }
    },
    {
        "name": "resize_image",
        "description": "调整图片尺寸。支持按像素宽高或百分比缩放。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "源图片路径"},
                "dest": {"type": "string", "description": "输出路径"},
                "width": {"type": "integer", "description": "目标宽度（像素）", "default": 0},
                "height": {"type": "integer", "description": "目标高度（像素）", "default": 0},
                "percent": {"type": "integer", "description": "缩放百分比（如 50=缩小一半）", "default": 0}
            },
            "required": ["source", "dest"]
        }
    },
    {
        "name": "compress_image",
        "description": "压缩图片文件，减小文件大小。通过降低质量来压缩。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "源图片路径"},
                "dest": {"type": "string", "description": "输出路径"},
                "quality": {"type": "integer", "description": "压缩质量 1-100（越低文件越小）", "default": 70}
            },
            "required": ["source", "dest"]
        }
    },
    {
        "name": "create_thumbnail",
        "description": "生成图片缩略图（正方形裁剪）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "源图片路径"},
                "dest": {"type": "string", "description": "输出路径"},
                "size": {"type": "integer", "description": "缩略图边长（像素）", "default": 200}
            },
            "required": ["source", "dest"]
        }
    },
    {
        "name": "get_format_info",
        "description": "使用 file 命令获取文件格式信息。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"}
            },
            "required": ["path"]
        }
    }
]

HANDLERS = {
    "convert_image": handle_convert_image,
    "resize_image": handle_resize_image,
    "compress_image": handle_compress_image,
    "create_thumbnail": handle_create_thumbnail,
    "get_format_info": handle_get_format_info,
}

# ── Main Loop ───────────────────────────────────────────────────────────────

def main():
    send({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "media-mcp", "version": "1.0.0"}
        }
    })

    initialized = False
    while True:
        msg = recv()
        if msg is None:
            break
        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if msg_id is None:
            if method == "notifications/initialized":
                initialized = True
            continue

        if method == "tools/list":
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": TOOLS}
            })
        elif method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments", {})
            handler = HANDLERS.get(name)
            if handler:
                result = handler(args)
                send({"jsonrpc": "2.0", "id": msg_id, "result": result})
            else:
                send({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"未知工具: {name}"}})
        elif method == "initialize":
            send({"jsonrpc": "2.0", "id": msg_id, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "media-mcp", "version": "1.0.0"}
            }})
        else:
            send({"jsonrpc": "2.0", "id": msg_id, "result": {}})

if __name__ == "__main__":
    main()