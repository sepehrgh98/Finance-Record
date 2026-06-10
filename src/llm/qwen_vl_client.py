from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from config.settings import VLM_LOCAL_FILES_ONLY
from llm.base import BaseLLMClient


class QwenVLClient(BaseLLMClient):
    """
    Shared local Qwen-VL client for text-only JSON generation and image OCR.

    The model and processor are cached at class level so notes and receipt VLM
    fallback do not load separate large model instances in the same process.
    """

    _model_cache: dict[str, Any] = {}
    _processor_cache: dict[str, Any] = {}

    def __init__(
        self,
        model: str = "Qwen/Qwen2.5-VL-3B-Instruct",
    ) -> None:
        self.model = model
        self.last_error = ""

    def is_available(self) -> bool:
        try:
            self._load_model()
            return True
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: int = 30,
    ) -> dict:
        generated_text = self.generate_text(system_prompt, user_prompt)
        parsed = self._extract_json(generated_text)

        if not isinstance(parsed, dict):
            self.last_error = "Generated JSON must be an object"
            raise ValueError(self.last_error)

        return parsed

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        max_new_tokens: int = 512,
    ) -> str:
        model, processor = self._load_model()
        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]
        text = processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = processor(
            text=[text],
            padding=True,
            return_tensors="pt",
        ).to(model.device)
        output_text = self._generate_and_decode(
            model=model,
            processor=processor,
            inputs=inputs,
            max_new_tokens=max_new_tokens,
        )
        self._debug_raw_output(output_text)
        return output_text

    def generate_image_text(
        self,
        image_path: Path,
        prompt: str,
        min_pixels: int,
        max_pixels: int,
        max_image_dimension: int,
        max_new_tokens: int = 256,
    ) -> str:
        from qwen_vl_utils import process_vision_info

        model, processor = self._load_model()

        with _PreparedImagePath(image_path, max_image_dimension) as prepared_path:
            self._debug(f"prepared image path: {prepared_path}")
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "image": str(prepared_path),
                            "min_pixels": min_pixels,
                            "max_pixels": max_pixels,
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ]
            text = processor.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
            image_inputs, video_inputs = process_vision_info(messages)
            inputs = processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            ).to(model.device)
            self._debug(
                "vision inputs prepared: "
                f"image_count={len(image_inputs or [])}, "
                f"input_tokens={len(inputs.input_ids[0])}"
            )
            output_text = self._generate_and_decode(
                model=model,
                processor=processor,
                inputs=inputs,
                max_new_tokens=max_new_tokens,
            )
            self._debug(f"raw VLM output: {output_text}")
            return output_text

    def _load_model(self):
        if (
            self.model in self._model_cache
            and self.model in self._processor_cache
        ):
            return self._model_cache[self.model], self._processor_cache[self.model]

        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

        self._debug(
            f"loading model={self.model} "
            f"local_files_only={VLM_LOCAL_FILES_ONLY}"
        )
        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            self.model,
            device_map="auto",
            torch_dtype="auto",
            local_files_only=VLM_LOCAL_FILES_ONLY,
        )
        self._debug("model loaded")
        self._debug("loading processor")
        processor = AutoProcessor.from_pretrained(
            self.model,
            local_files_only=VLM_LOCAL_FILES_ONLY,
        )
        self._debug("processor loaded")

        self._model_cache[self.model] = model
        self._processor_cache[self.model] = processor
        return model, processor

    def _generate_and_decode(
        self,
        model,
        processor,
        inputs,
        max_new_tokens: int,
    ) -> str:
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
        )
        generated_ids_trimmed = [
            output_ids[len(input_ids):]
            for input_ids, output_ids in zip(inputs.input_ids, generated_ids)
        ]
        return processor.batch_decode(
            generated_ids_trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0].strip()

    def _extract_json(self, generated_text: str) -> dict:
        try:
            return json.loads(generated_text)
        except json.JSONDecodeError:
            pass

        start = generated_text.find("{")
        end = generated_text.rfind("}")

        if start == -1 or end == -1:
            self.last_error = "Model did not return valid JSON"
            raise ValueError(self.last_error)

        try:
            return json.loads(generated_text[start:end + 1])
        except json.JSONDecodeError as exc:
            self.last_error = "Model did not return valid JSON"
            raise ValueError(self.last_error) from exc

    def _debug_raw_output(self, generated_text: str) -> None:
        if os.getenv("LLM_DEBUG") == "1" or os.getenv("OCR_DEBUG") == "1":
            print("\n" + "=" * 80)
            print("RAW MODEL OUTPUT")
            print("=" * 80)
            print(generated_text)
            print("=" * 80 + "\n")

    def _debug(self, message: str) -> None:
        if os.getenv("OCR_DEBUG") == "1" or os.getenv("LLM_DEBUG") == "1":
            print(f"[qwen-vl] {message}")


class _PreparedImagePath:
    def __init__(self, image_path: Path, max_dimension: int) -> None:
        self.image_path = image_path
        self.max_dimension = max_dimension
        self.temp_file = None

    def __enter__(self) -> Path:
        try:
            from PIL import Image, ImageOps

            with Image.open(self.image_path) as image:
                prepared = ImageOps.exif_transpose(image).convert("RGB")
                prepared.thumbnail(
                    (self.max_dimension, self.max_dimension),
                    Image.Resampling.LANCZOS,
                )

                self.temp_file = tempfile.NamedTemporaryFile(
                    suffix=".jpg",
                    delete=False,
                )
                prepared.save(self.temp_file.name, quality=92)
                self.temp_file.close()
                return Path(self.temp_file.name)
        except Exception:
            return self.image_path

    def __exit__(self, exc_type, exc, traceback) -> None:
        if not self.temp_file:
            return

        try:
            Path(self.temp_file.name).unlink(missing_ok=True)
        except Exception:
            pass
