MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_model = None


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        print("Loading embedding model...")
        _model = SentenceTransformer(MODEL_NAME)
        print("Embedding model loaded successfully.")
    return _model


def create_embedding(text: str) -> list[float]:
    model = get_model()
    embedding = model.encode(
        text,
        normalize_embeddings=True
    )

    return embedding.tolist()