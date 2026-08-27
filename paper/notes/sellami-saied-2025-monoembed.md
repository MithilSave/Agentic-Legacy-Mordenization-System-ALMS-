# Sellami & Saied — "Contrastive Learning-Enhanced Large Language Models for Monolith-to-Microservice Decomposition" (MonoEmbed), arXiv:2502.04604, Feb 2025

**bib key:** `sellami2025monoembed` — also the text-only reference #3. Related work on
**LLM-based boundary selection**. Contrast: it needs model fine-tuning; ALMS does not.

---

## Problem / claim
The decomposition step (partitioning monolith components into target microservices)
is the largest roadblock in migration. Prior decomposition methods rely on static or
dynamic analysis with hand-defined features (cohesion, coupling); their simple
encodings (ST-Calls adjacency matrix, SM-BoW / TF-IDF) are "insufficient to create
domain-relevant representations". Proposal: use **language-model embeddings** of code,
improved via contrastive fine-tuning, then cluster.

## Method (MonoEmbed)
Two components: **Analysis** (LM turns each class's source into a feature vector →
N×M matrix) and **Inference** (z-score normalise → clustering → decomposition
`D = [M1..MK]`, each `Mi` a subset of classes). Class-level granularity, **source
code only**.
- **Model selection:** benchmark 18 pre-trained models + 4 static representations
  (ST-Calls, ST-Interactions, SM-BoW, SM-TFIDF) — encoder-only (CodeBERT,
  GraphCodeBERT, UniXcoder, CuBERT), encoder-decoder (CodeT5+), decoder-only
  (Llama-3 8B, CodeLlama 7B, DeepSeekCoder 6.7B), LM-embeddings (LLM2Vec 8B,
  NV-Embed 7B, SFR/E5-Mistral 7B, GritLM 7B), closed APIs (VoyageAI, OpenAI, Cohere).
- **Fine-tuning:** contrastive learning with **triplet loss** (anchor + positive from
  same microservice, hard negative from a *different* service in the *same* repo, to
  force focus on business semantics over syntactic similarity). Full-weight for small
  encoders; **LoRA** for the LLMs (to cut compute/memory). Instruction: "Given the
  source code, retrieve the bounded contexts".
- **Dataset:** self-built from GitHub — Java repos matching
  `micro(-| )?services?...(architecture|system|application)`, ≥10 stars, ≥2
  microservices; classes matched to their microservice as ground truth; triplets
  sampled.
- **Inference clustering:** compares many algorithms; **Affinity Propagation** best on
  average; K-Means / Hierarchical better *when given the target #services*.

## Evaluation setup
- **RQ1** quality of pre-trained embeddings (Embedding Quality Score = balanced BCE of
  pairwise cosine-sim vs true co-membership; lower = better). **RQ2** does fine-tuning
  help + effect of training-set size. **RQ3** which clustering algorithm. **RQ4**
  vs 6 decomposition benchmarks (Code2VecDec, CHGNN, Deeply, **Mono2Micro**,
  MSExtractor, TopicDec) on **8 monolithic Java apps** (40–531 classes), 6 quality
  metrics (CHM, CHD, BCP, ICP, NED, COV) + an aggregate SCORE.

## Headline numbers
- LLM-based embedding models (VoyageAI, NV-Embed, SFR-Mistral) produce **better
  representations for decomposition** than static analysis / Code2Vec / CodeBERT
  (top-8 ranks all LLM/CEM). Generalist Llama-3 and code-specialised DeepSeekCoder /
  CodeLlama did *poorly* — "training objectives and model architecture outweigh
  domain specialisation."
- Fine-tuning (ME-*) improves embedding quality substantially over the base models.
- **RQ4:** MonoEmbed gets the **best aggregate SCORE (6.061)** vs Mono2Micro (3.485),
  Code2VecDec (1.107), others negative. Best CHM/CHD/COV; competitive BCP; but
  **higher ICP → more inter-service coupling**. "Consistent performance across
  metrics and scales, especially for larger applications ... does not require in-depth
  analysis or additional input" (only source code).

## Stated limitations / threats
Needs a fine-tuning dataset + training (LoRA still requires GPU). Java-only,
class-level. Clustering hyper-parameters sensitive (mitigated by sweeping). Higher
inter-service coupling than coupling-optimised baselines. Ground-truth
decompositions for monoliths "rarely exist".

---

## How ALMS relates
- **Same sub-goal (boundary selection), opposite mechanism.** MonoEmbed = *learned*
  class embeddings + clustering, requires a curated microservices corpus + contrastive
  fine-tuning (LoRA/GPU). ALMS = *deterministic* AST call graph + **Louvain community
  detection**, zero training, seed-fixed, runs in milliseconds on CPU. Cite MonoEmbed
  as evidence that decomposition-by-clustering is a credible design, then position
  ALMS's version as the zero-training, zero-GPU, reproducible variant.
- **Their finding "pipeline/objective matters more than model size/specialisation"**
  parallels Mono2Sls's "pipeline design > backbone model" — together these license
  ALMS's bet that a small local model in a structured pipeline is enough.
- **Scope contrast:** MonoEmbed stops at a class→service partition; ALMS continues to
  generate deployable FastAPI code + tests + compose. Different end of the pipeline.
- **Metric borrow:** if the partner extends evaluation with a gold decomposition,
  MonoEmbed's metric set (CHM, CHD, BCP, ICP, NED, COV) and the Fβ (β=0.25) pairwise
  score are the standard to report.

## Citable sentences
- **Intro:** decomposition "identified [as] the largest and most important roadblock
  when refactoring a monolith into microservices"; static-analysis encodings alone
  are "insufficient to create domain-relevant representations".
- **Related work:** MonoEmbed shows LM-based embeddings + clustering beat classic
  static/dynamic decomposition on cohesion metrics — but at the cost of a curated
  training corpus and LoRA fine-tuning. ALMS trades some decomposition quality for
  no training and full reproducibility.
- **Discussion:** their own note that Mono2Micro (dynamic analysis) "achieved low BCP
  and ICP but sacrificed coverage and microservice balance" — useful for framing that
  every decomposition method trades off different qualities; ALMS's Louvain choice is
  one such point on that trade-off, chosen for zero-cost determinism.

## BibTeX — in paper/refs.bib.
