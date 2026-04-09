import json
import os
import re
import subprocess
from packaging import version
from typing import Any


# CONFIG: Set your paths here

MODEL_DIR = "./exported_model"

# The container in use
CONTAINER_TRANSFORMERS_VERSION = "4.36.2"
CONTAINER_TORCH_VERSION = "1.13.1"


# VALIDATION FUNCTIONS

def load_config() -> tuple[None, list[str]] | tuple[Any, list[Any]]:
    cfg_path = os.path.join(MODEL_DIR, "config.json")
    if not os.path.exists(path=cfg_path):
        return None, ["config.json missing"]
    with open(file=cfg_path, mode="r") as f:
        return json.load(fp=f), []


def check_required_files() -> list[str]:
    required = [
        "pytorch_model.bin",
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "vocab.txt",
        "special_tokens_map.json",
    ]
    missing = [f for f in required if not os.path.exists(path=os.path.join(MODEL_DIR, f))]
    return missing


def check_transformers_compat(model_cfg) -> list[Any]:
    errors = []
    model_version = model_cfg.get("transformers_version")

    if model_version is None:
        errors.append("Model config missing transformers_version (older HF versions).")
        return errors

    if version.parse(version=model_version) > version.parse(version=CONTAINER_TRANSFORMERS_VERSION):
        errors.append(
            f"Model was saved with Transformers {model_version}, "
            f"but container only supports {CONTAINER_TRANSFORMERS_VERSION}."
        )

    return errors


def check_torch_dtype(model_cfg) -> list[str] | list[Any]:
    dtype = model_cfg.get("torch_dtype")
    if dtype and "bfloat16" in dtype:
        return ["Container does not support bfloat16 weights."]
    return []


def check_tokenizer_schema() -> list[str] | list[Any]:
    tok_path = os.path.join(MODEL_DIR, "tokenizer.json")
    if not os.path.exists(path=tok_path):
        return ["tokenizer.json missing"]

    with open(file=tok_path, mode="r") as f:
        tok = json.load(f)

    if "model" not in tok:
        return ["tokenizer.json missing 'model' field — incompatible schema"]

    return []


def check_for_safetensors() -> list[str] | list[Any]:
    st_path = os.path.join(MODEL_DIR, "model.safetensors")
    if os.path.exists(st_path):
        return ["model.safetensors present — TorchServe cannot load safetensors"]
    return []


def check_for_checkpoint_artifacts()-> list[Any]:
    bad = []
    for f in ["training_args.bin", "optimizer.pt", "rng_state.pth"]:
        if os.path.exists(path=os.path.join(MODEL_DIR, f)):
            bad.append(f"{f} should NOT be included in inference tarball")
    return bad


def run_all_checks() -> list[Any]:
    errors = []

    # Required files
    missing = check_required_files()
    if missing:
        errors.append(f"Missing required files: {missing}")

    # Load config
    config, cfg_errors = load_config()
    errors.extend(cfg_errors)

    if config:
        # Transformers version compatibility
        errors.extend(check_transformers_compat(model_cfg=config))

        # Torch dtype compatibility
        errors.extend(check_torch_dtype(model_cfg=config))

    #  Tokenizer schema
    errors.extend(check_tokenizer_schema())

    # Safetensors presence
    errors.extend(check_for_safetensors())

    # Checkpoint artifacts
    errors.extend(check_for_checkpoint_artifacts())

    return errors




def valid_checks() -> None:
    errors = run_all_checks()

    if not errors:
        print("\n MODEL IS COMPATIBLE WITH THE TARGET CONTAINER\n")
    else:
        print("\n INCOMPATIBILITIES DETECTED:\n")
        for e in errors:
            print(" -", e)
