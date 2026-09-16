"""
services/training/trainer.py - Part 1: Configuration and model loading.
"""
import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

ENABLE_FINE_TUNING = os.environ.get("ENABLE_FINE_TUNING", "false").lower() == "true"

DEFAULT_CONFIG = {
    "model_name": "microsoft/phi-2",
    "lora_r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.05,
    "target_modules": ["q_proj", "v_proj"],
    "learning_rate": 2e-4,
    "num_epochs": 3,
    "batch_size": 4,
    "gradient_accumulation_steps": 4,
    "max_length": 512,
    "warmup_ratio": 0.1,
    "weight_decay": 0.01,
    "max_grad_norm": 1.0,
    "scheduler_type": "cosine",
    "qlora": False,
    "output_dir": "./models/interview_adapter",
}


class InterviewTrainer:
    """Handles LoRA/QLoRA fine-tuning of local LLMs for interview tasks."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.model = None
        self.tokenizer = None
        self.trainer = None
        self._peft_available = None
        self._torch_available = None

    @property
    def peft_available(self) -> bool:
        if self._peft_available is None:
            try:
                import peft
                self._peft_available = True
            except ImportError:
                self._peft_available = False
        return self._peft_available

    @property
    def torch_available(self) -> bool:
        if self._torch_available is None:
            try:
                import torch
                self._torch_available = True
            except ImportError:
                self._torch_available = False
        return self._torch_available

    def load_base_model(self):
        if not self.torch_available:
            logger.error("PyTorch not installed.")
            return False
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
            import torch
            model_name = self.config["model_name"]
            logger.info("Loading base model: %s", model_name)
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            if self.config.get("qlora"):
                bnb_config = BitsAndBytesConfig(
                    load_in_4bit=True, bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True,
                )
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_name, quantization_config=bnb_config,
                    device_map="auto", trust_remote_code=True,
                )
            else:
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    device_map="auto" if torch.cuda.is_available() else None,
                    trust_remote_code=True,
                )
            logger.info("Base model loaded")
            return True
        except Exception as e:
            logger.error("Failed to load base model: %s", e)
            return False

    def setup_lora(self):
        if not self.peft_available:
            logger.error("PEFT not installed. Run: pip install peft")
            return False
        try:
            from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
            lora_config = LoraConfig(
                r=self.config["lora_r"], lora_alpha=self.config["lora_alpha"],
                lora_dropout=self.config["lora_dropout"],
                target_modules=self.config["target_modules"],
                bias="none", task_type="CAUSAL_LM",
            )
            if self.config.get("qlora"):
                self.model = prepare_model_for_kbit_training(self.model)
            self.model = get_peft_model(self.model, lora_config)
            self.model.print_trainable_parameters()
            logger.info("LoRA configured")
            return True
        except Exception as e:
            logger.error("Failed to setup LoRA: %s", e)
            return False
