import json
import logging
from pathlib import Path
from typing import Dict

import requests
from docx import Document
from pypdf import PdfReader


SUPPORTED_SUFFIXES = {"txt", "md", "markdown", "pdf", "docx"}


logger = logging.getLogger(__name__)


class ParseError(Exception):
    pass


def parse_document(path: Path, parser_config: Dict[str, str]) -> str:
    mode = (parser_config.get("parserMode") or "local").lower()
    logger.info("开始解析文档，文件：%s，解析模式：%s", path.name, mode)
    if mode == "mineru":
        if path.suffix.lower() != ".pdf":
            logger.info("MinerU 当前按 PDF 解析器处理，非 PDF 文件转为本地解析，文件：%s", path.name)
            return parse_local(path)
        return parse_with_mineru(path, parser_config)
    return parse_local(path)


def parse_local(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    if suffix in {"txt", "md", "markdown"}:
        return read_text(path)
    if suffix == "pdf":
        return parse_pdf(path)
    if suffix == "docx":
        return parse_docx(path)
    raise ParseError("暂不支持的文件类型：{}".format(suffix))


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gb18030", errors="ignore")


def parse_pdf(path: Path) -> str:
    try:
        reader = PdfReader(str(path))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception as exc:
        raise ParseError("PDF 解析失败：{}".format(exc)) from exc


def parse_docx(path: Path) -> str:
    try:
        doc = Document(str(path))
        paragraphs = [paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception as exc:
        raise ParseError("Word 解析失败：{}".format(exc)) from exc


def parse_with_mineru(path: Path, parser_config: Dict[str, str]) -> str:
    endpoint = build_mineru_endpoint(parser_config.get("mineruBaseUrl") or "")
    if not endpoint:
        raise ParseError("MinerU 解析接口地址未配置")

    headers = {}
    api_key = parser_config.get("mineruApiKey") or ""
    if api_key:
        headers["Authorization"] = "Bearer {}".format(api_key)

    data = {
        "model": parser_config.get("mineruModel") or "mineru-vl",
        "only_md": "true" if parser_config.get("mineruOnlyMd", True) else "false",
    }

    logger.info(
        "开始调用 MinerU，文件：%s，接口：%s，model：%s，only_md：%s",
        path.name,
        endpoint,
        data["model"],
        data["only_md"],
    )
    try:
        with path.open("rb") as file:
            response = requests.post(
                endpoint,
                files={"files": (path.name, file)},
                data=data,
                headers=headers,
                timeout=180,
            )
        response.raise_for_status()
    except Exception as exc:
        logger.exception("MinerU 服务调用失败，文件：%s", path.name)
        raise ParseError("MinerU 服务调用失败：{}".format(exc)) from exc

    logger.info(
        "MinerU 响应成功，文件：%s，状态码：%s，Content-Type：%s，响应长度：%s",
        path.name,
        response.status_code,
        response.headers.get("content-type", ""),
        len(response.content or b""),
    )
    text = extract_mineru_text(response)
    if not isinstance(text, str):
        text = stringify_mineru_value(text)
    text = text.strip()
    if not text:
        logger.warning("MinerU 服务未返回可用 Markdown 文本，文件：%s", path.name)
        raise ParseError("MinerU 服务未返回可用 Markdown 文本")
    logger.info("MinerU 文本提取完成，文件：%s，文本长度：%s", path.name, len(text))
    return text


def build_mineru_endpoint(url: str) -> str:
    endpoint = (url or "").strip().rstrip("/")
    if not endpoint:
        return ""
    if endpoint.endswith("/parse") or endpoint.endswith("/mineru-parser") or "/openapi/" in endpoint:
        return endpoint
    return "{}/parse".format(endpoint)


def extract_mineru_text(response):
    content_type = (response.headers.get("content-type") or "").lower()
    if "json" in content_type:
        payload = response.json()
        logger.info("MinerU JSON 响应字段：%s", list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__)
        validate_mineru_payload(payload)
        return extract_text_from_json(payload)
    response.encoding = response.encoding or "utf-8"
    return response.text or ""


def validate_mineru_payload(payload):
    if not isinstance(payload, dict):
        return

    code = payload.get("code")
    message = payload.get("msg") or payload.get("message") or payload.get("error")
    data = payload.get("data")
    success_values = {None, 0, "0", 200, "200", "success", "ok", True}
    failed = code not in success_values
    empty_data_with_error = bool(message) and (data in ("", None) or data in ([], {}))
    if failed or empty_data_with_error:
        logger.warning("MinerU 返回业务错误，code：%s，message：%s，request_id：%s", code, message, payload.get("request_id"))
        raise ParseError("MinerU 解析失败：{}".format(message or code or "未知错误"))


def extract_text_from_json(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [extract_text_from_json(item) for item in value]
        return "\n\n".join(part for part in parts if part)
    if isinstance(value, dict):
        for key in ("markdown", "md", "text", "content", "result"):
            extracted = extract_text_from_json(value.get(key))
            if extracted:
                return extracted
        data = value.get("data")
        extracted = extract_text_from_json(data)
        if extracted:
            return extracted
        return stringify_mineru_value(value)
    return stringify_mineru_value(value)


def stringify_mineru_value(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def split_chunks(text: str, max_chars: int = 1200):
    paragraphs = [part.strip() for part in text.replace("\r\n", "\n").split("\n\n") if part.strip()]
    chunks = []
    current = ""

    for paragraph in paragraphs or [text]:
        if len(current) + len(paragraph) + 2 <= max_chars:
            current = "{}\n\n{}".format(current, paragraph).strip()
        else:
            if current:
                chunks.append(current)
            current = paragraph

        while len(current) > max_chars:
            chunks.append(current[:max_chars])
            current = current[max_chars:].strip()

    if current:
        chunks.append(current)
    return chunks
