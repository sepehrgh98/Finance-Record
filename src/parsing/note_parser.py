from parsing.base_parser import BaseBusinessParser
from parsing.llm_note_parser import LLMNoteContextParser
from core.config.settings import LLM_MODEL, LLM_PROVIDER, USE_LOCAL_LLM_FOR_NOTES
from core.models.business_context import BusinessContext
from core.models.document_context import DocumentContext
from core.utils.pipeline_logger import pipeline_log


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
            pipeline_log("note parser: local LLM disabled")
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
                pipeline_log("note parser: local LLM unavailable")
                return empty_context

            llm_context = LLMNoteContextParser(
                self.llm_client,
                progress_callback=context.metadata.get("progress_callback"),
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
            pipeline_log(f"note parser error: {exc}")
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
        return bool(business_context.knowledge)
