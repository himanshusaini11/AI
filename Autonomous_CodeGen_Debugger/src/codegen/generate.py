import os, glob, re, torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from transformers import StoppingCriteria, StoppingCriteriaList
from src.security.guard import assert_read_allowed
from src.seeds.library import seed_prefix as lib_seed_prefix, propose_default_fn

def _resolve_model_dir(p: str) -> str:
    if os.path.isfile(os.path.join(p, "config.json")): return p
    hits = glob.glob(os.path.join(p, "**", "model*.safetensors"), recursive=True) or \
           glob.glob(os.path.join(p, "**", "pytorch_model*.bin"), recursive=True)
    if not hits: raise FileNotFoundError(f"No model weights under: {p}")
    return os.path.dirname(hits[0])

def _load(model_path: str):
    tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16 if torch.backends.mps.is_available() else torch.float32,
            device_map="auto",
            trust_remote_code=True,
        )
    except Exception as e:
        msg = str(e)
        if "SequenceSummary" in msg or "dynamic_module" in msg or "get_class_from_dynamic_module" in msg:
            raise RuntimeError(
                "This model snapshot requires an older Transformers version. "
                "Either switch to a compatible model (e.g., starcoder2-3b) or install transformers==4.36.2 in this environment for this model."
            ) from e
        raise
    if tok.pad_token_id is None: tok.pad_token_id = tok.eos_token_id
    return tok, model

_STOP_STRINGS = ["\n\ndef ", "\n\nclass ", "\nif __name__"]

class StopOnAny(StoppingCriteria):
    def __init__(self, tokenizer, stops):
        self.stop_ids = [tokenizer.encode(s, add_special_tokens=False) for s in stops]
        self.window = max(len(ids) for ids in self.stop_ids)

    def __call__(self, input_ids, scores, **kwargs):
        seq = input_ids[0].tolist()
        tail = seq[-self.window:]
        for ids in self.stop_ids:
            if len(seq) >= len(ids) and seq[-len(ids):] == ids:
                return True
        return False

def _extract_function(text: str, fn_name: str) -> str:
    pat = rf"(?s)^\s*def\s+{re.escape(fn_name)}\s*\(.*?\):\s*(?:.*?\n)*?(?=^\s*def\s+|^\s*class\s+|^\s*if __name__|^\Z)"
    m = re.search(pat, text, flags=re.M)
    return (m.group(0).rstrip() if m else text.strip())

def generate_code(task: str, model_path: str | None = None, max_new_tokens=256, fn_name: str | None = None):
    model_path = model_path or os.environ.get("CODEGEN_MODEL_PATH")
    if not model_path: raise RuntimeError("Set CODEGEN_MODEL_PATH or pass model_path.")
    model_path = _resolve_model_dir(model_path)
    assert_read_allowed(model_path)
    tok, model = _load(model_path)

    fn = fn_name or propose_default_fn(task)
    prefix = lib_seed_prefix(task, fn)

    enc = tok(prefix, return_tensors="pt", return_attention_mask=True, add_special_tokens=True)
    enc = {k: v.to(model.device) for k, v in enc.items()}

    stops = StoppingCriteriaList([StopOnAny(tok, _STOP_STRINGS)])

    with torch.no_grad():
        out = model.generate(
            **enc,
            max_new_tokens=max_new_tokens,
            do_sample=False,                    # greedy
            eos_token_id=tok.eos_token_id,
            pad_token_id=tok.pad_token_id,
            stopping_criteria=stops,
        )

    gen_ids = out[0, enc["input_ids"].shape[1]:]
    code = tok.decode(gen_ids, skip_special_tokens=True)
    final = prefix + code
    return _extract_function(final, fn)
