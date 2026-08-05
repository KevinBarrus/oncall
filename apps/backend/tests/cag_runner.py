"""CAG (Cache-Augmented Generation) runner for oncall RAG evaluation.

Deploys Qwen2.5-1.5B-Instruct locally with 4-bit quantization (bitsandbytes NF4).
Precomputes KV Cache from all knowledge documents and reuses it for each question.

Core idea: encode all KB docs once → cache attention states → reuse for every query.
No retrieval step — the entire knowledge base is "preloaded" in the KV Cache.

Usage:
    from tests.cag_runner import ensure_model, prepare_cache, answer_question, get_knowledge_text

    ensure_model()                          # load 4-bit model (once)
    kv, kv_len, setup_ms = prepare_cache()  # precompute or load KV Cache
    contexts, answer, _, gen_ms = answer_question(kv, kv_len, "What is P0?")
"""

from __future__ import annotations

import time
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from transformers.cache_utils import DynamicCache

# Allowlist DynamicCache for safe torch.load
torch.serialization.add_safe_globals([DynamicCache, set])

# ---------------------------------------------------------------------------
# paths & constants
# ---------------------------------------------------------------------------

_TEST_DIR = Path(__file__).resolve().parent
_DATA_DIR = _TEST_DIR / "data"
_CACHE_PATH = _DATA_DIR / "cache_knowledge.pt"

MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"

_KB_FILES = [
    _DATA_DIR / "team-alert-response-spec.md",
    _DATA_DIR / "service-topology.md",
    _DATA_DIR / "incident-postmortems.md",
]

# ---------------------------------------------------------------------------
# global model state (loaded once, shared across calls)
# ---------------------------------------------------------------------------

_model: AutoModelForCausalLM | None = None
_tokenizer: AutoTokenizer | None = None


def ensure_model() -> tuple[AutoModelForCausalLM, AutoTokenizer]:
    """Load 4-bit quantized model + tokenizer. Subsequent calls return cached."""
    global _model, _tokenizer

    if _model is not None:
        return _model, _tokenizer

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    print("[cag] Loading tokenizer...")
    _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    print("[cag] Loading 4-bit model (one-time, ~6 min on CPU)...")
    t0 = time.time()
    _model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto",
    )
    mem = _model.get_memory_footprint() / 1e9
    print(f"[cag] Model ready  device={_model.device}  memory={mem:.2f}GB  "
          f"time={time.time() - t0:.0f}s")

    return _model, _tokenizer


# ---------------------------------------------------------------------------
# KV Cache core (adapted from CAG/kvcache.py)
# ---------------------------------------------------------------------------


def preprocess_knowledge(
    model: AutoModelForCausalLM,
    tokenizer: AutoTokenizer,
    prompt: str,
) -> DynamicCache:
    """One forward pass: encode `prompt` → DynamicCache of all layer K/V states."""
    embed_device = model.model.embed_tokens.weight.device
    input_ids = tokenizer.encode(prompt, return_tensors="pt").to(embed_device)
    past_key_values = DynamicCache()
    with torch.no_grad():
        outputs = model(
            input_ids=input_ids,
            past_key_values=past_key_values,
            use_cache=True,
        )
    return outputs.past_key_values


def generate(
    model: AutoModelForCausalLM,
    input_ids: torch.Tensor,
    past_key_values: DynamicCache,
    max_new_tokens: int = 300,
) -> torch.Tensor:
    """Greedy token-by-token generation from a pre-filled KV Cache.

    Args:
        model: Causal LM
        input_ids: Question tokens to append after the cached prefix
        past_key_values: Precomputed KV Cache (mutated in-place)
        max_new_tokens: Stop after this many tokens (or EOS)

    Returns:
        Generated token ids (excluding the input prefix)
    """
    embed_device = model.model.embed_tokens.weight.device
    origin_len = input_ids.shape[-1]
    input_ids = input_ids.to(embed_device)

    output_ids = input_ids.clone()
    next_token = input_ids

    with torch.no_grad():
        for _ in range(max_new_tokens):
            outputs = model(
                input_ids=next_token,
                past_key_values=past_key_values,
                use_cache=True,
            )
            next_token_logits = outputs.logits[:, -1, :]
            next_token = next_token_logits.argmax(dim=-1).unsqueeze(-1)
            next_token = next_token.to(embed_device)

            past_key_values = outputs.past_key_values
            output_ids = torch.cat([output_ids, next_token], dim=1)

            if next_token.item() == model.config.eos_token_id:
                break

    return output_ids[:, origin_len:]


def clean_up(kv: DynamicCache, origin_len: int) -> None:
    """Truncate KV Cache back to `origin_len` to remove previous generation."""
    for i in range(len(kv.key_cache)):
        kv.key_cache[i] = kv.key_cache[i][:, :, :origin_len, :]
        kv.value_cache[i] = kv.value_cache[i][:, :, :origin_len, :]


# ---------------------------------------------------------------------------
# knowledge loading
# ---------------------------------------------------------------------------


def _load_knowledge_text() -> str:
    """Read all KB documents and concatenate into one text block."""
    parts: list[str] = []
    for path in _KB_FILES:
        if path.exists():
            text = path.read_text(encoding="utf-8")
            parts.append(f"# {path.stem}\n\n{text}")

    if not parts:
        raise FileNotFoundError(
            f"No KB documents in {_DATA_DIR}. "
            f"Expected: {[p.name for p in _KB_FILES]}"
        )

    return "\n\n---\n\n".join(parts)


def get_knowledge_text() -> str:
    """Public accessor — used as 'contexts' for RAG metric computation."""
    return _load_knowledge_text()


# ---------------------------------------------------------------------------
# prompt construction (Qwen chat template)
# ---------------------------------------------------------------------------


def _build_cache_prompt(documents_text: str) -> str:
    """Build the fixed prefix whose KV Cache will be precomputed.

    Everything up to (but not including) the specific question is cached.
    The trailing '问题：' is the insertion point for per-question text.
    """
    return (
        f"<|im_start|>system\n"
        f"你是一个运维专家助手。请严格根据提供的文档内容回答问题，给出简洁准确的答案。"
        f"如果文档中没有相关信息，请明确说「文档中未涉及」。\n"
        f"<|im_end|>\n"
        f"<|im_start|>user\n"
        f"以下是参考文档内容：\n"
        f"------------------------------------------------\n"
        f"{documents_text}\n"
        f"------------------------------------------------\n"
        f"请根据以上文档回答问题。\n"
        f"问题："
    )


def _build_question_suffix(question: str) -> str:
    """Per-question suffix appended after the cached prefix."""
    return (
        f"{question}\n"
        f"<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def prepare_cache() -> tuple[DynamicCache, int, float]:
    """Precompute KV Cache for all KB docs (or load from disk).

    Returns:
        (kv_cache, kv_len, setup_seconds)
    """
    model, tokenizer = ensure_model()

    if _CACHE_PATH.exists():
        print(f"[cag] Loading cached KV from {_CACHE_PATH.name}...")
        t0 = time.time()
        kv = torch.load(_CACHE_PATH, weights_only=True)
        kv_len = kv.key_cache[0].shape[-2]
        elapsed = time.time() - t0
        print(f"[cag] Cache loaded  kv_len={kv_len}  time={elapsed:.1f}s")
        return kv, kv_len, elapsed

    # First run — precompute and persist
    print("[cag] Precomputing KV Cache (one-time, ~30-60s on CPU)...")
    docs_text = _load_knowledge_text()
    cache_prompt = _build_cache_prompt(docs_text)

    t0 = time.time()
    kv = preprocess_knowledge(model, tokenizer, cache_prompt)
    kv_len = kv.key_cache[0].shape[-2]
    elapsed = time.time() - t0

    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.save(kv, _CACHE_PATH)

    print(f"[cag] KV Cache ready  kv_len={kv_len}  time={elapsed:.0f}s  "
          f"saved → {_CACHE_PATH.name}")

    return kv, kv_len, elapsed


def answer_question(
    kv: DynamicCache,
    kv_len: int,
    question: str,
) -> tuple[str, str, float]:
    """Answer one question using precomputed KV Cache.

    Args:
        kv: Precomputed KV Cache
        kv_len: Original cache sequence length (for clean_up)
        question: User question text

    Returns:
        (contexts_text, answer, generation_seconds)
    """
    model, tokenizer = ensure_model()

    # 1. Remove tokens from the previous question's generation
    clean_up(kv, kv_len)

    # 2. Encode this question's suffix
    question_text = _build_question_suffix(question)
    input_ids = tokenizer.encode(question_text, return_tensors="pt")

    # 3. Generate from cached state
    torch.cuda.empty_cache()  # no-op on CPU, prevents fragmentation on GPU
    t0 = time.time()
    output_ids = generate(model, input_ids, kv)
    gen_time = time.time() - t0

    # 4. Decode
    answer = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()

    return get_knowledge_text(), answer, gen_time
