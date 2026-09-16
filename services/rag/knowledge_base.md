# Interview Knowledge Base - Technical Q&A

## Machine Learning Fundamentals

**Q: What is the bias-variance tradeoff?**
A: Bias is error from erroneous assumptions in the model. Variance is error from sensitivity to small training set fluctuations. The tradeoff: increasing model complexity reduces bias but increases variance, leading to overfitting. The goal is finding the sweet spot where total error (bias + variance) is minimized. Techniques to manage this include cross-validation, regularization, and ensemble methods.

**Q: Explain the difference between L1 and L2 regularization.**
A: L1 regularization (Lasso) adds absolute value of weights to loss, driving some weights to zero, performing feature selection. L2 regularization (Ridge) adds squared weights, shrinking all weights proportionally without zeroing them. L1 is useful for sparse feature selection, L2 for generalization with many correlated features.

**Q: How does a Random Forest work?**
A: Random Forest builds multiple decision trees on bootstrapped samples of data, with each tree considering only a random subset of features at each split. The final prediction is the average (regression) or majority vote (classification) of all trees. This reduces variance compared to a single decision tree through ensemble averaging.

## Deep Learning

**Q: What is back-propagation?**
A: Back-propagation computes gradients of the loss function with respect to network weights via the chain rule, propagating errors backward through layers. These gradients are then used by optimization algorithms (SGD, Adam) to update weights and minimize loss. Requires differentiable activation functions.

**Q: Explain the role of activation functions.**
A: Activation functions introduce non-linearity into neural networks, allowing them to learn complex patterns. ReLU is computationally efficient and mitigates vanishing gradients but can cause dead neurons. Sigmoid and Tanh are smooth but suffer from vanishing gradients in deep networks. GELU and Swish offer smooth alternatives with good performance.

## Generative AI & RAG

**Q: What is RAG (Retrieval-Augmented Generation)?**
A: RAG combines a retriever (fetches relevant documents from a knowledge base) with a generator (produces answers using both retrieved context and the prompt). This grounds responses in factual data, reducing hallucinations. The retriever uses embeddings to find semantically similar documents, and the generator conditions on retrieved content.

**Q: How does a Transformer work?**
A: Transformers use self-attention mechanisms to process all tokens simultaneously rather than sequentially. Multi-head attention allows the model to focus on different representation subspaces. Positional encodings inject token order information since attention is permutation-invariant. The encoder-decoder architecture with skip connections enables parallel training and long-range dependencies.

**Q: Compare fine-tuning vs. prompt engineering.**
A: Fine-tuning updates model weights on task-specific data, requiring computational resources and time but producing higher quality results for specialized tasks. Prompt engineering crafts input instructions without changing weights, is zero-shot adaptable, but requires careful design and may not reach fine-tuned performance levels.

## System Design

**Q: What is eventual consistency and when is it used?**
A: Eventual consistency is a consistency model where updates propagate asynchronously to all nodes. Reads may return stale data temporarily, but the system converges. Used in distributed databases (DynamoDB, Cassandra) for high availability and partition tolerance (CAP theorem). Suitable for applications tolerant of temporary inconsistency like social media feeds.

**Q: Explain microservices communication patterns.**
A: Synchronous communication uses REST/gRPC APIs with direct service-to-service calls; simple but introduces coupling and latency. Asynchronous uses message queues (Kafka, RabbitMQ) or event buses for decoupled communication; scalable but adds complexity. API Gateways aggregate requests. Service meshes (Istio) manage network concerns.

## Software Engineering

**Q: What are SOLID principles?**
A: Single Responsibility (one reason to change), Open-Closed (open for extension, closed for modification), Liskov Substitution (subtypes substitutable for base), Interface Segregation (client-specific interfaces), Dependency Inversion (depend on abstractions). Improves code maintainability and testability.

**Q: Explain database indexing strategies.**
A: B-tree indexes for range queries and sorting, Hash indexes for exact match lookups, Bitmap indexes for low-cardinality columns. Composite indexes follow the leftmost-prefix rule. Covering indexes include all queried columns to avoid table lookups. Trade-off: faster reads, slower writes.
