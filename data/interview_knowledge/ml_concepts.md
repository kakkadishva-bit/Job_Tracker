# Machine Learning Interview Questions

## Core Concepts

### Overfitting
Overfitting occurs when a model learns the training data too well, including noise and outliers, to the point where it performs poorly on unseen data. Signs include high training accuracy but low validation accuracy.

To detect overfitting: look for a large gap between training and validation error that persists beyond a few epochs.

### Underfitting
Underfitting occurs when a model is too simple to capture the underlying patterns in the data. Both training and validation performance will be poor.

### Bias-Variance Tradeoff
Bias is error from erroneous assumptions in the learning algorithm. Variance is error from sensitivity to small fluctuations in the training set. The goal is to balance both to minimize total error.

### Regularization
Regularization techniques like L1 (Lasso) and L2 (Ridge) add penalty terms to the loss function. L1 can drive weights to zero (feature selection), while L2 spreads the penalty across all weights.

## Algorithms

### Random Forest
An ensemble of decision trees trained on random subsets of data and features. Reduces variance compared to single decision trees through bagging and feature randomness.

### Gradient Boosting
Builds trees sequentially, each correcting errors of the previous one. Uses gradient descent to minimize loss. XGBoost, LightGBM, and CatBoost are popular implementations.

### Support Vector Machines
Finds the optimal hyperplane that maximally separates classes by maximizing the margin. Uses kernel trick for non-linear separation.

### Naive Bayes
Based on Bayes theorem with independence assumption between features. Works well for text classification despite the naive assumption.

## Model Evaluation

### Cross-Validation
K-fold cross-validation splits data into k subsets, training on k-1 and validating on the remaining one, repeated k times. Provides robust performance estimates.

### Metrics
- Accuracy: correct predictions over total
- Precision: true positives over predicted positives
- Recall: true positives over actual positives
- F1: harmonic mean of precision and recall
- AUC-ROC: area under the ROC curve

### Confusion Matrix
A table showing true positives, false positives, true negatives, and false negatives. Essential for understanding model performance per class.
