from collections.abc import Sequence
from threading import Lock

from app.models import Language

NLLB_LANGUAGE_CODES = {
    Language.ENGLISH: "eng_Latn",
    Language.VIETNAMESE: "vie_Latn",
    Language.KOREAN: "kor_Hang",
}


class LocalModels:
    def __init__(self, embedding_backend: str = "torch") -> None:
        if embedding_backend not in {"torch", "openvino"}:
            raise ValueError("Embedding backend must be 'torch' or 'openvino'.")
        self.embedding_backend = embedding_backend
        self._translation_lock = Lock()
        self._embedding_lock = Lock()
        self._translation_model = None
        self._translation_tokenizer = None
        self._embedding_model = None
        self._device = "cpu"

    def translate(
        self,
        texts: Sequence[str],
        source_language: Language,
        target_language: Language,
    ) -> list[str]:
        if not texts:
            return []
        with self._translation_lock:
            self._ensure_translation_model()
            return self._translate_loaded(texts, source_language, target_language)

    def similarities(self, left: Sequence[str], right: Sequence[str]) -> list[float]:
        if len(left) != len(right):
            raise ValueError("Similarity inputs must have equal lengths.")
        if not left:
            return []
        with self._embedding_lock:
            self._ensure_embedding_model()
            source_embeddings = self._embedding_model.encode(
                [f"query: {text}" for text in left], normalize_embeddings=True
            )
            target_embeddings = self._embedding_model.encode(
                [f"passage: {text}" for text in right], normalize_embeddings=True
            )
            return [
                float(source @ target)
                for source, target in zip(source_embeddings, target_embeddings, strict=True)
            ]

    def _ensure_translation_model(self) -> None:
        if self._translation_model is not None:
            return
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        model_name = "facebook/nllb-200-distilled-600M"
        self._device = "mps" if torch.backends.mps.is_available() else "cpu"
        self._translation_tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._translation_model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        self._translation_model.to(self._device)
        self._translation_model.eval()

    def _translate_loaded(
        self,
        texts: Sequence[str],
        source_language: Language,
        target_language: Language,
    ) -> list[str]:
        import torch

        tokenizer = self._translation_tokenizer
        model = self._translation_model
        tokenizer.src_lang = NLLB_LANGUAGE_CODES[source_language]
        target_id = tokenizer.convert_tokens_to_ids(NLLB_LANGUAGE_CODES[target_language])
        results: list[str] = []
        for start in range(0, len(texts), 4):
            batch = texts[start : start + 4]
            encoded = tokenizer(
                list(batch),
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            ).to(self._device)
            with torch.inference_mode():
                input_tokens = encoded["input_ids"].shape[-1]
                max_new_tokens = min(256, max(64, input_tokens * 2 + 16))
                generated = model.generate(
                    **encoded,
                    forced_bos_token_id=target_id,
                    max_new_tokens=max_new_tokens,
                    num_beams=1,
                )
            results.extend(tokenizer.batch_decode(generated, skip_special_tokens=True))
        return results

    def _ensure_embedding_model(self) -> None:
        if self._embedding_model is not None:
            return
        from sentence_transformers import SentenceTransformer

        model_kwargs = (
            {"model_kwargs": {"export": True}} if self.embedding_backend == "openvino" else {}
        )
        self._embedding_model = SentenceTransformer(
            "intfloat/multilingual-e5-small",
            backend=self.embedding_backend,
            device="cpu" if self.embedding_backend == "openvino" else None,
            **model_kwargs,
        )
