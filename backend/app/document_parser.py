from pathlib import Path
from typing import Dict

import requests
from docx import Document
from pypdf import PdfReader


SUPPORTED_SUFFIXES = {"txt", "md", "markdown", "pdf", "docx"}


class ParseError(Exception):
    pass


def parse_document(path: Path, parser_config: Dict[str, str]) -> str:
    mode = (parser_config.get("parserMode") or "local").lower()
    if mode == "mineru":
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
    base_url = (parser_config.get("mineruBaseUrl") or "").rstrip("/")
    if not base_url:
        raise ParseError("MinerU 服务地址未配置")

    headers = {}
    api_key = parser_config.get("mineruApiKey") or ""
    if api_key:
        headers["Authorization"] = "Bearer {}".format(api_key)

    try:
        with path.open("rb") as file:
            response = requests.post(
                "{}/parse".format(base_url),
                files={"file": (path.name, file)},
                headers=headers,
                timeout=120,
            )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise ParseError("MinerU 服务调用失败：{}".format(exc)) from exc

    text = payload.get("text") or payload.get("content") or payload.get("markdown") or ""
    if not text.strip():
        raise ParseError("MinerU 服务未返回可用文本")
    return text.strip()


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
