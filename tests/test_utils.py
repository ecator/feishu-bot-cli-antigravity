from google.antigravity import types

from feishu_bot_cli_antigravity.utils import (
    create_media_from_bytes,
    format_iso_time,
    guess_mime_type,
    setup_logging,
)


def test_guess_mime_type():
    assert guess_mime_type("report.pdf") == "application/pdf"
    assert guess_mime_type("data.json") == "application/json"
    assert guess_mime_type("table.csv") == "text/csv"
    assert guess_mime_type("script.py") == "text/plain"
    assert guess_mime_type("doc.txt") == "text/plain"
    assert guess_mime_type("pic.png") == "image/png"
    assert guess_mime_type(None, "image") == "image/png"
    assert guess_mime_type(None, "audio") == "audio/mp3"
    assert guess_mime_type(None, "video") == "video/mp4"
    assert guess_mime_type("unknown.xyz", "file") == "application/octet-stream"


def test_create_media_from_bytes_image():
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    res = create_media_from_bytes(png_bytes, "test.png", "image")
    assert isinstance(res, types.Image)
    assert res.mime_type == "image/png"


def test_create_media_from_bytes_document():
    text_bytes = b"print('Hello world!')"
    res = create_media_from_bytes(text_bytes, "hello.py", "file")
    assert isinstance(res, types.Document)
    assert res.mime_type == "text/plain"

    pdf_bytes = b"%PDF-1.4 dummy pdf bytes"
    res_pdf = create_media_from_bytes(pdf_bytes, "doc.pdf", "file")
    assert isinstance(res_pdf, types.Document)
    assert res_pdf.mime_type == "application/pdf"


def test_create_media_from_bytes_utf8_fallback():
    # UTF-8 text without extension
    res = create_media_from_bytes(b"some plain text", "no_ext_file", "file")
    assert isinstance(res, types.Document)
    assert res.mime_type == "text/plain"


def test_create_media_from_bytes_unsupported_binary():
    # Unsupported binary bytes that cannot be UTF-8 decoded
    bin_bytes = b"\x00\xff\xfe\xfd\x01\x02\x03\x04"
    res = create_media_from_bytes(bin_bytes, "archive.bin", "file")
    assert isinstance(res, str)
    assert "暂不支持该格式直接解析" in res
    assert "archive.bin" in res


def test_setup_logging():
    res = setup_logging("DEBUG")
    assert res is None


def test_format_iso_time():
    # 空值/None
    assert format_iso_time(None) == ""
    assert format_iso_time("") == ""

    # 秒级时间戳 (1700000000 -> 2023-11-14T...)
    iso_sec = format_iso_time(1700000000)
    assert "2023-11-14" in iso_sec or "2023-11-15" in iso_sec
    assert "T" in iso_sec

    # 毫秒级时间戳 (1700000000000 -> 同上)
    iso_ms = format_iso_time(1700000000000)
    assert iso_ms == iso_sec

    # 字符串形式数字
    assert format_iso_time("1700000000000") == iso_sec

    # 异常输入降级返回原字符串
    assert format_iso_time("invalid_timestamp") == "invalid_timestamp"
