import argparse, sys
from .generate import generate_code

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, help="Natural-language task")
    ap.add_argument("--model", default=None, help="Path to local model dir")
    ap.add_argument("--tokens", type=int, default=256)
    ap.add_argument("--fn", default=None, help="Optional explicit function name")
    args = ap.parse_args()
    code = generate_code(args.task, model_path=args.model, max_new_tokens=args.tokens, fn_name=args.fn)
    sys.stdout.write(code)

if __name__ == "__main__":
    main()
