import weaviate

client = weaviate.connect_to_local(port=8085, grpc_port=50052)
collection = client.collections.get("DocumentChunk") # Replace with your collection name
print(f"Total indexed objects: {len(collection)}")
client.close()