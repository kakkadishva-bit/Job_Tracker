    def train(self, train_dataset, eval_dataset=None):
        """Run training."""
        if not ENABLE_FINE_TUNING:
            logger.info("Fine-tuning disabled. Set ENABLE_FINE_TUNING=true to enable.")
            return {"status": "disabled", "message": "Fine-tuning is disabled"}
        if not self.model:
            if not self.load_base_model():
                return {"status": "error", "message": "Failed to load base model"}
        if not self.setup_lora():
            return {"status": "error", "message": "Failed to setup LoRA"}
        try:
            from transformers import TrainingArguments, Trainer, DataCollatorForLanguageModeling
            training_args = TrainingArguments(
                output_dir=self.config["output_dir"],
                num_train_epochs=self.config["num_epochs"],
                per_device_train_batch_size=self.config["batch_size"],
                gradient_accumulation_steps=self.config["gradient_accumulation_steps"],
                learning_rate=self.config["learning_rate"],
                warmup_ratio=self.config["warmup_ratio"],
                weight_decay=self.config["weight_decay"],
                max_grad_norm=self.config["max_grad_norm"],
                lr_scheduler_type=self.config["scheduler_type"],
                logging_steps=10, save_steps=50,
                evaluation_strategy="steps" if eval_dataset else "no",
                eval_steps=50 if eval_dataset else None,
                save_total_limit=3,
                load_best_model_at_end=True if eval_dataset else False,
                report_to="none",
            )
            data_collator = DataCollatorForLanguageModeling(tokenizer=self.tokenizer, mlm=False)
            self.trainer = Trainer(
                model=self.model, args=training_args,
                train_dataset=train_dataset, eval_dataset=eval_dataset,
                data_collator=data_collator,
            )
            result = self.trainer.train()
            self.trainer.save_model(self.config["output_dir"])
            self.tokenizer.save_pretrained(self.config["output_dir"])
            return {"status": "success", "train_loss": result.training_loss, "steps": result.global_step}
        except Exception as e:
            logger.error("Training failed: %s", e)
            return {"status": "error", "message": str(e)}

    def generate(self, prompt: str, max_tokens: int = 256) -> str:
        if not self.model:
            return ""
        try:
            import torch
            inputs = self.tokenizer(prompt, return_tensors="pt")
            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs, max_new_tokens=max_tokens, temperature=0.7,
                    top_p=0.9, do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                )
            return self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        except Exception as e:
            logger.error("Generation failed: %s", e)
            return ""
