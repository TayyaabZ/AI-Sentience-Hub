# 🧠 The AI Sentience Hub
### A 3-in-1 Interactive Arcade for AI & ML Algorithms
*Built for CSC411 — Artificial Intelligence | BSIT 6B*

---

## Overview

The AI Sentience Hub is a desktop application built in Python that makes AI algorithms **visual and interactive**. Instead of watching numbers scroll past in a terminal, you can watch a Genetic Algorithm breed dungeons in real time, challenge an adversarial Minimax agent on a grid, and draw digits that three machine learning classifiers race to recognize.

It is structured as a unified graphical hub — a main menu that launches three self-contained mini-programs, each demonstrating a different AI concept from the course.

---

## Modules

### 🟢 MOD-01 · EvoMap — Evolutionary Dungeon Generator
Procedurally generates complex, playable dungeon layouts using a **Genetic Algorithm** with **BFS** fitness evaluation.

**How it works:**
- A population of 30 random dungeons is created each generation
- Each dungeon is scored by a **Fitness Function** that uses BFS to check if a path exists from Spawn → Treasure → Boss
- The fitness score rewards reachability, room count, and penalizes dead ends. A treasure detour bonus rewards placing the treasure near the natural path
- The top 50% survive (**Elitism**). Pairs breed via **Row-Splice Crossover** (a horizontal band of rows is swapped between two parents)
- Random tiles flip via **Mutation** (5% rate)
- A **Repair Pass** after every crossover/mutation ensures Spawn, Boss, and Treasure tiles always exist
- After 60 generations the fittest dungeon is displayed with an animated BFS trail

**UI Features:**
- Generation-by-generation playback with speed control (½×, 1×, 2×, ⚡)
- Arrow key scrubbing through generations
- Live stats panel: fitness score, room count, dead ends, path length, treasure detour steps
- Convergence detection

---

### 🔵 MOD-02 · Aegis Grid — A\* vs Minimax
A game of cat and mouse on a 20×20 grid. A Red agent tries to reach the goal; a Blue agent tries to block it.

**How it works:**
- **Red** uses **A\* Search** — maintains a priority queue sorted by `f(n) = g(n) + h(n)`, where `g` is the actual cost from start and `h` is a heuristic (Manhattan, Euclidean, or Chebyshev — switchable)
- **Blue** uses **Minimax with Alpha-Beta Pruning** at depth 3. It identifies candidate wall placements near Red's current path and searches the game tree to find the wall that maximally lengthens Red's route
- Alpha-Beta pruning skips branches where `α ≥ β`, cutting the search space roughly in half

**UI Features:**
- Step-by-step mode and auto-play
- A\* visualization mode showing open/closed sets frame by frame
- Switchable heuristics (Manhattan / Euclidean / Chebyshev)
- Live stats: nodes explored, branches pruned, path length, game status
- Full match log

---

### 🟣 MOD-03 · Crypto-Glyph — Handwritten Digit Recognition
Draw any digit (0–9) with your mouse. Three ML classifiers independently vote on what you drew.

**How it works:**
- Your drawing is downscaled to **28×28 pixels** (matching MNIST format), flattened to a 784-feature vector, and normalized by a pre-fitted `StandardScaler`
- Three classifiers predict the digit:
  - **Naive Bayes** — applies Bayes' theorem assuming pixel independence: `P(class|features) ∝ P(features|class) × P(class)`
  - **Decision Tree** — recursively partitions the 784-dimensional feature space by Gini impurity
  - **KNN (k=5)** — finds the 5 nearest neighbors by Euclidean distance and takes a majority vote
- If you correct a wrong prediction, the models **retrain online in a background thread**: NB gets `partial_fit()` immediately, DT batches 5 corrections, KNN appends to training data and refits

**UI Features:**
- Per-model confidence bars and probability distributions
- Confusion matrix display per classifier
- Live feedback loop with correction buttons
- Session accuracy tracking

---

## Model Accuracy (MNIST Test Set — 10,000 samples)

| Model | Accuracy | Notes |
|---|---|---|
| Naive Bayes | 52.4% | Expected — pixel independence assumption is poor for images |
| Decision Tree | 88.2% | `max_depth=20`, strong for a single tree |
| KNN (k=5) | 92.8% | Trained on 20k subset; no assumptions, high accuracy |

The contrast in accuracy is intentional — it demonstrates why algorithm choice matters.

---

## Hub Features

- Animated background with 50 floating nodes drawing proximity edges
- Animated live thumbnail previews on each card
- Clickable **ⓘ info modals** per module with algorithm explanation, key concepts, and Big-O complexity
- Live stats bar: Dungeons Evolved, Games Played, Digits Decoded — persisted to `stats.json` across sessions
- System status bar: live CPU %, RAM usage, and models loaded count
- Custom frameless window with Mac-style traffic light controls (close, minimize, fullscreen)

---

## Project Structure

```
AI-Sentience-Hub/
│
├── main.py              # Main hub menu and launcher
├── evomap.py            # Genetic Algorithm + BFS logic (backend)
├── evomap_ui.py         # EvoMap UI and playback system
├── aegis_grid.py        # A* Search + Minimax game
├── crypto_glyph.py      # Drawing canvas + ML classification UI
├── train_models.py      # Script to train and save ML models
├── theme.py             # Shared color palette, fonts, UI components
├── requirements.txt     # Python dependencies
├── stats.json           # Persistent session statistics
│
└── models/
    ├── naive_bayes.pkl      # Trained Naive Bayes model
    ├── decision_tree.pkl    # Trained Decision Tree model
    ├── knn.pkl              # Trained KNN model (k=5)
    ├── scaler.pkl           # Fitted StandardScaler
    ├── knn_train_data.pkl   # KNN training data (for online retraining)
    └── accuracy.json        # Per-model accuracy, precision, recall, confusion matrices
```

---

## Installation & Setup

### Prerequisites
- Python 3.10 or higher
- pip

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/ai-sentience-hub.git
cd ai-sentience-hub
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the hub
```bash
python main.py
```

> **Note:** The `models/` folder with pre-trained `.pkl` files is included. You do **not** need to retrain. If you want to retrain from scratch, see below.

### Optional: Retrain models
This will download the MNIST dataset (~11MB) and retrain all three classifiers. Takes about 15–20 seconds.
```bash
python train_models.py
```

---

## Dependencies

```
pygame-ce
numpy
scikit-learn
scipy
pillow
joblib
psutil
```

---

## AI Concepts Demonstrated

| Concept | Where |
|---|---|
| Genetic Algorithms | EvoMap — population, selection, crossover, mutation, repair |
| Breadth-First Search (BFS) | EvoMap — fitness evaluation and path visualization |
| A\* Search | Aegis Grid — optimal pathfinding with heuristic |
| Minimax + Alpha-Beta Pruning | Aegis Grid — adversarial wall placement |
| Naive Bayes Classification | Crypto-Glyph — probabilistic digit recognition |
| Decision Tree Classification | Crypto-Glyph — Gini-impurity feature partitioning |
| K-Nearest Neighbors | Crypto-Glyph — distance-based majority vote |
| Online Learning | Crypto-Glyph — live model retraining from user feedback |

---

## Author

| Name | Enrollment |
|---|---|
| Muhammad Tayyaab Zahoor | 01-135232-070 |

---

*CSC411 — Artificial Intelligence | Instructor: Ms. Sidra Ayesha | BSIT 6B*
