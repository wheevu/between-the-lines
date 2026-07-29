import sys
from contextlib import nullcontext
from types import SimpleNamespace

import numpy as np

from app.local_models import LocalModels
from app.models import Language


def test_openvino_backend_requests_model_export(monkeypatch) -> None:
    calls = []

    def sentence_transformer(*args, **kwargs):
        calls.append((args, kwargs))
        return object()

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=sentence_transformer),
    )

    models = LocalModels("openvino")
    models._ensure_embedding_model()

    assert calls == [
        (
            ("intfloat/multilingual-e5-small",),
            {
                "backend": "openvino",
                "device": "cpu",
                "model_kwargs": {"export": True},
            },
        )
    ]


def test_shadow_translation_uses_greedy_decoding(monkeypatch) -> None:
    generated_kwargs = {}

    class Encoded(dict):
        def to(self, device):
            assert device == "cpu"
            return self

    class Tokenizer:
        src_lang = None

        def convert_tokens_to_ids(self, value):
            assert value == "vie_Latn"
            return 42

        def __call__(self, values, **kwargs):
            assert values == ["A short report."]
            assert kwargs["max_length"] == 512
            return Encoded(input_ids=np.zeros((1, 20)))

        def batch_decode(self, generated, skip_special_tokens):
            assert generated == ["tokens"]
            assert skip_special_tokens
            return ["Một báo cáo ngắn."]

    class Model:
        def generate(self, **kwargs):
            generated_kwargs.update(kwargs)
            return ["tokens"]

    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(inference_mode=nullcontext),
    )
    models = LocalModels()
    models._translation_tokenizer = Tokenizer()
    models._translation_model = Model()

    translated = models._translate_loaded(
        ["A short report."],
        Language.ENGLISH,
        Language.VIETNAMESE,
    )

    assert translated == ["Một báo cáo ngắn."]
    assert generated_kwargs["num_beams"] == 1
    assert generated_kwargs["max_new_tokens"] == 64
