from business_parsers.base_parser import BaseBusinessParser
from business_parsers.llm_note_context_parser import LLMNoteContextParser
from config.settings import LLM_MODEL, LLM_PROVIDER, USE_LOCAL_LLM_FOR_NOTES
from models.business_context import BusinessContext
from models.document_context import DocumentContext


class NoteContextParser(BaseBusinessParser):
    """
    Extracts generic semantic facts from notes without business interpretation.
    """

    def __init__(
        self,
        use_local_llm: bool = USE_LOCAL_LLM_FOR_NOTES,
        llm_model: str = LLM_MODEL,
    ) -> None:
        self.use_local_llm = use_local_llm
        self.llm_model = llm_model
        self.llm_client = None

    def parse(self, context: DocumentContext) -> BusinessContext:
        empty_context = BusinessContext()

        if not self.use_local_llm:
            context.metadata["note_parser"] = "none"
            print("LLM parsing disabled, skipping note semantic extraction")
            return empty_context

        try:
            if self.llm_client is None:
                from llm.factory import build_llm_client

                self.llm_client = build_llm_client(
                    provider=LLM_PROVIDER,
                    model=self.llm_model,
                )

            if not self.llm_client.is_available():
                context.metadata["note_parser"] = "none"
                context.metadata["note_llm_error"] = (
                    self.llm_client.last_error or "Local LLM unavailable"
                )
                print("Local LLM unavailable, skipping note semantic extraction")
                return empty_context

            llm_context = LLMNoteContextParser(
                self.llm_client
            ).parse(context.extracted_text)

            context.metadata["note_parser"] = "local_llm"

            if not self._has_context(llm_context):
                context.metadata["note_llm_error"] = (
                    "LLM returned empty context"
                )
                return empty_context

            context.metadata["note_llm_error"] = ""
            return llm_context

        except Exception as exc:
            print(f"Error parsing note with LLM: {exc}")
            context.metadata["note_parser"] = "none"
            llm_error = (
                self.llm_client.last_error
                if self.llm_client is not None
                else ""
            )
            context.metadata["note_llm_error"] = (
                llm_error or str(exc)
            )

            return empty_context

    def _has_context(self, business_context: BusinessContext) -> bool:
        return bool(business_context.semantic_facts)
