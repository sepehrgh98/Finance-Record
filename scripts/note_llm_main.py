from pathlib import Path

from core.models.document_context import DocumentContext
from core.models.file_info import FileInfo
from parsing.note_parser import NoteContextParser


def main():
    note_path = Path("data/shoebox/notes.txt")

    file_info = FileInfo(
        path=note_path,
        filename=note_path.name,
        extension=note_path.suffix.lower(),
        size_bytes=note_path.stat().st_size,
        sha256="",
    )
    context = DocumentContext(
        file_info=file_info,
        extracted_text=note_path.read_text(encoding="utf-8", errors="ignore"),
    )
    parser = NoteContextParser(use_local_llm=True)
    business_context = parser.parse(context)

    print("Business Context\n")
    print(f"Parser used: {context.metadata.get('note_parser', 'unknown')}\n")

    if context.metadata.get("note_parser") != "local_llm":
        error = context.metadata.get("note_llm_error")

        if error:
            print(f"LLM fallback reason: {error}\n")

    print(f"Knowledge objects found: {len(business_context.knowledge)}")
    print("Knowledge:")
    for knowledge in business_context.knowledge:
        print(f"- {knowledge}")


if __name__ == "__main__":
    main()
