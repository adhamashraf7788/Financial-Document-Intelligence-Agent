import weaviate
client = weaviate.connect_to_local(port=8085, grpc_port=50052)
print(client.collections.list_all())
client.close()