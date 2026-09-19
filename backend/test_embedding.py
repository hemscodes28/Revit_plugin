from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

print("Loading embedding model...")

model = SentenceTransformer(MODEL_NAME)

print("Model loaded successfully.")

text = "Ground floor plan"

embedding = model.encode(text)

print("Text:")
print(text)

print()
print("Embedding dimension:")
print(len(embedding))

print()
print("First 10 values:")
print(embedding[:10])